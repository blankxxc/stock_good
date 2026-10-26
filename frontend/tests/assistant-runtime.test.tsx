import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import React from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import AssistantPanel from '../src/components/AssistantPanel';
import { AssistantPreferencesProvider, researchReturnPath, useAssistantPreferences } from '../src/components/AssistantPreferences';
import { AssistantConnectionSettings } from '../src/components/AccountSettings';
import { invalidateSessionStatus, safeNextPath } from '../src/lib/auth';
import { chatHistory, consumeChat, safeSourceUrl, type ChatMessage } from '../src/lib/assistant';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true, self: globalThis });
const originalFetch = globalThis.fetch;
let renderer: ReactTestRenderer | null = null;
afterEach(async () => {
  if (renderer) await act(async () => renderer?.unmount());
  renderer = null; globalThis.fetch = originalFetch;
});

test('stream decoder handles split UTF-8, sources and completion', async () => {
  const bytes = new TextEncoder().encode('{"type":"delta","text":"中文"}\n{"type":"done"}\n');
  const stream = new ReadableStream({ start(controller) {
    for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
    controller.close();
  } });
  const events: string[] = [];
  await consumeChat(new Response(stream), event => events.push(event.text || event.type));
  assert.deepEqual(events, ['中文', 'done']);
});

test('stream errors and missing terminator never count as complete', async () => {
  await assert.rejects(consumeChat(new Response('{"type":"delta","text":"部分"}\n'), () => {}), /不完整/);
  await assert.rejects(consumeChat(new Response('{"type":"error","message":"额度不足"}\n'), () => {}), /额度不足/);
  await assert.rejects(consumeChat(Response.json({ detail: '参数错误' }, { status: 422 }), () => {}), /参数错误/);
});

test('history excludes failed answers and unsafe source links', () => {
  const messages: ChatMessage[] = [
    { role: 'user', content: '问题一' }, { role: 'assistant', content: '回答一', complete: true },
    { role: 'user', content: '问题二' }, { role: 'assistant', content: '部分回答', complete: false },
  ];
  assert.deepEqual(chatHistory(messages), [{ role: 'user', content: '问题一' }, { role: 'assistant', content: '回答一' }]);
  assert.equal(safeSourceUrl('/stocks/000001.SZ'), '/stocks/000001.SZ');
  for (const url of ['//evil.test', 'https://evil.test', 'javascript:alert(1)', '/admin', '/factors', '/backtests', '/models', '/backtest-risk']) assert.equal(safeSourceUrl(url), null);
});

const providers = [
  { id: 'deepseek', label: 'DeepSeek', base_url: 'https://api.deepseek.com', default_model: 'deepseek-flash' },
  { id: 'openai', label: 'OpenAI', base_url: 'https://api.openai.com/v1', default_model: 'gpt-6-sol' },
];
let preferences: ReturnType<typeof useAssistantPreferences>;
function CapturePreferences() { preferences = useAssistantPreferences(); return null; }
function Harness({ page = '/account', open = true, predictionSymbol = '' }: { page?: string; open?: boolean; predictionSymbol?: string }) {
  return <AssistantPreferencesProvider pathname={page}>
    <CapturePreferences />
    {page === '/account' ? <AssistantConnectionSettings providers={providers} /> : <AssistantPanel
      open={open} pathname={page} snapshot={{ factor_names: ['vwap_deviation'], ...(predictionSymbol ? { score_model: 'api_llm' as const, page_state: { prediction: { symbol: predictionSymbol } } } : {}) }} onClose={() => {}} />}
  </AssistantPreferencesProvider>;
}
async function applySettings() {
  await act(async () => { renderer = TestRenderer.create(<Harness />); });
  const root = renderer!.root;
  assert.equal(root.findByProps({ type: 'password' }).props.autoComplete, 'new-password');
  assert.equal(root.findByProps({ type: 'password' }).props.readOnly, true);
  await act(async () => root.findByProps({ type: 'password' }).props.onFocus());
  assert.equal(root.findByProps({ type: 'password' }).props.readOnly, false);
  await act(async () => root.findByProps({ type: 'password' }).props.onChange({ target: { value: 'test-only-key' } }));
  await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
}

test('personal settings are shared across routes and panel sends key only in header', async () => {
  const calls: { url: string; init?: RequestInit }[] = [];
  globalThis.fetch = async (url, init) => {
    calls.push({ url: String(url), init });
    return new Response('{"type":"context","sources":[],"notes":[]}\n{"type":"delta","text":"依据行情的分析"}\n{"type":"done"}\n');
  };
  await applySettings();
  assert.equal(calls.length, 0, 'applying settings never calls a model');
  await act(async () => renderer!.update(<Harness page="/stocks/000001.SZ" />));
  const root = renderer!.root;
  assert.equal(root.findAllByProps({ type: 'password' }).length, 0);
  assert.equal(root.findAllByType('select').length, 0);
  assert.equal(root.findAllByType('input').length, 0, 'chat panel should not contain a separate stock or settings form');
  assert.ok(root.findByProps({ 'aria-label': '新建对话' }));
  await act(async () => root.findByType('textarea').props.onChange({ target: { value: '分析这只股票' } }));
  await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  const call = calls.find(item => item.url.endsWith('/chat'))!;
  const payload = JSON.parse(String(call.init?.body));
  assert.equal(payload.symbol, '000001.SZ');
  assert.deepEqual(payload.factor_names, ['vwap_deviation']);
  assert.equal((call.init?.headers as Record<string, string>)['X-AI-API-Key'], 'test-only-key');
  assert.equal(call.init?.credentials, 'omit');
  assert.ok(!String(call.init?.body).includes('test-only-key'));
  await act(async () => renderer!.update(<Harness page="/stocks/000001.SZ" open={false} />));
  await act(async () => renderer!.update(<Harness page="/visualization" />));
  assert.equal(root.findByType('textarea').props.value, '');
  assert.equal(preferences.connection?.apiKey, 'test-only-key');
  await act(async () => renderer!.update(<Harness />));
  assert.equal(root.findByProps({ type: 'password' }).props.value, 'test-only-key');
  assert.equal(preferences.returnPath, '/visualization');
  assert.equal(calls.length, 1);
});

test('changing service clears the draft key and only applies a validated connection', async () => {
  await applySettings();
  const root = renderer!.root;
  await act(async () => root.findByType('select').props.onChange({ target: { value: 'openai' } }));
  assert.equal(root.findByProps({ type: 'password' }).props.value, '');
  assert.equal(root.findByProps({ type: 'password' }).props.readOnly, true);
  assert.equal(root.findByProps({ id: 'account-ai-model' }).props.value, 'gpt-6-sol');
  await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  assert.equal(preferences.connection?.provider.id, 'deepseek', 'invalid draft must not overwrite applied configuration');
  assert.ok(root.findByProps({ role: 'alert' }));
  await act(async () => root.findByProps({ type: 'password' }).props.onChange({ target: { value: 'new-test-only-key' } }));
  await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  assert.equal(preferences.connection?.provider.id, 'openai');
  assert.equal(preferences.connection?.apiKey, 'new-test-only-key');
  await act(async () => root.findAllByType('button').find(item => item.props.children === '清除配置')!.props.onClick());
  assert.equal(preferences.connection, null);
  assert.equal(root.findByProps({ type: 'password' }).props.value, '');
});

test('unconfigured chat links to personal settings and performs no network request', async () => {
  let requests = 0;
  globalThis.fetch = async () => { requests++; throw new Error('Unexpected request'); };
  await act(async () => { renderer = TestRenderer.create(<Harness page="/" />); });
  assert.equal(renderer!.root.findByType('textarea').props.disabled, true);
  assert.ok(renderer!.root.findAllByType('a').some(item => item.props.href === '/account'));
  assert.equal(renderer!.root.findAllByProps({ type: 'password' }).length, 0);
  assert.equal(requests, 0);
  assert.equal(safeNextPath('/account', '/'), '/account');
  assert.equal(safeNextPath('//evil.test/account', '/'), '/');
});

test('navigation aborts in-flight request and ignores late responses', async () => {
  let aborted = false;
  globalThis.fetch = async (url, init) => {
    init?.signal?.addEventListener('abort', () => { aborted = true; });
    return new Promise<Response>(() => {});
  };
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/" />));
  await act(async () => renderer!.root.findByType('textarea').props.onChange({ target: { value: '分析趋势' } }));
  await act(async () => renderer!.root.findByType('form').props.onSubmit({ preventDefault() {} }));
  await act(async () => renderer!.update(<Harness page="/visualization" />));
  assert.equal(aborted, true);
  assert.equal(renderer!.root.findByType('textarea').props.disabled, false);
});

test('chat composer accepts the next draft while replying, and stop and new chat remain available', async () => {
  let signal: AbortSignal | null = null;
  globalThis.fetch = async (_url, init) => { signal = init!.signal!; return new Promise<Response>(() => {}); };
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/visualization" />));
  const root = renderer!.root;
  const input = () => root.findByType('textarea');
  await act(async () => input().props.onChange({ target: { value: '解释当前因子' } }));
  await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  assert.equal(input().props.disabled, false);
  await act(async () => input().props.onChange({ target: { value: '接下来看看风险' } }));
  await act(async () => root.findByProps({ 'aria-label': '停止生成' }).props.onClick());
  assert.equal((signal as unknown as AbortSignal).aborted, true);
  assert.equal(input().props.value, '接下来看看风险');
  assert.equal(root.findByProps({ 'aria-label': '发送消息' }).props.disabled, false);
  await act(async () => root.findByProps({ 'aria-label': '新建对话' }).props.onClick());
  assert.equal(input().props.value, '');
  assert.equal(root.findAllByType('article').length, 0);
});

test('failed replies do not overwrite a newly typed draft', async () => {
  let finish!: (response: Response) => void;
  globalThis.fetch = async () => new Promise<Response>(resolve => { finish = resolve; });
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/" />));
  const root = renderer!.root;
  await act(async () => root.findByType('textarea').props.onChange({ target: { value: '上一条消息' } }));
  await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  await act(async () => root.findByType('textarea').props.onChange({ target: { value: '新的草稿' } }));
  await act(async () => finish(Response.json({ detail: '模型暂时不可用' }, { status: 503 })));
  assert.equal(root.findByType('textarea').props.value, '新的草稿');
  assert.ok(root.findByProps({ role: 'alert' }));
});

test('conversation tabs preserve drafts and messages and send only their own history', async () => {
  const payloads: any[] = [];
  globalThis.fetch = async (_url, init) => {
    const body = JSON.parse(String(init?.body)); payloads.push(body);
    return new Response(JSON.stringify({ type: 'delta', text: `回复：${body.messages.at(-1).content}` }) + '\n{"type":"done"}\n');
  };
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/visualization" />));
  const root = renderer!.root;
  const tabs = () => root.findAllByProps({ role: 'tab' });
  const type = async (value: string) => act(async () => root.findByType('textarea').props.onChange({ target: { value } }));
  const send = async () => act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  await type('对话甲'); await send(); await type('甲的后续草稿');
  await act(async () => root.findByProps({ 'aria-label': '新建对话' }).props.onClick());
  assert.equal(tabs().length, 2);
  assert.equal(root.findByType('textarea').props.value, '');
  await type('对话乙'); await send(); await type('乙的后续草稿');
  assert.deepEqual(payloads[1].messages, [{ role: 'user', content: '对话乙' }]);
  await act(async () => tabs()[1].props.onKeyDown({ key: 'ArrowLeft', preventDefault() {} }));
  assert.equal(tabs()[0].props['aria-selected'], true);
  assert.equal(root.findByType('textarea').props.value, '甲的后续草稿');
  assert.ok(JSON.stringify(renderer!.toJSON()).includes('回复：对话甲'));
  await send();
  assert.deepEqual(payloads[2].messages, [
    { role: 'user', content: '对话甲' }, { role: 'assistant', content: '回复：对话甲' }, { role: 'user', content: '甲的后续草稿' },
  ]);
  await act(async () => tabs()[0].props.onKeyDown({ key: 'End', preventDefault() {} }));
  assert.equal(root.findByType('textarea').props.value, '乙的后续草稿');
  assert.equal(root.findByProps({ role: 'tabpanel' }).props['aria-labelledby'], tabs()[1].props.id);
});

test('simultaneous replies remain in their original tab even when completed out of order', async () => {
  const pending: { signal: AbortSignal; resolve: (value: Response) => void }[] = [];
  globalThis.fetch = async (_url, init) => new Promise(resolve => pending.push({ signal: init!.signal!, resolve }));
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/" />));
  const root = renderer!.root;
  const ask = async (question: string) => {
    await act(async () => root.findByType('textarea').props.onChange({ target: { value: question } }));
    await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  };
  await ask('第一个问题');
  await act(async () => root.findByProps({ 'aria-label': '新建对话' }).props.onClick());
  await ask('第二个问题');
  assert.equal(pending.length, 2);
  assert.ok(pending.every(request => !request.signal.aborted));
  await act(async () => pending[1].resolve(new Response('{"type":"delta","text":"第二个回答"}\n{"type":"done"}\n')));
  await act(async () => pending[0].resolve(new Response('{"type":"delta","text":"第一个回答"}\n{"type":"done"}\n')));
  assert.ok(JSON.stringify(renderer!.toJSON()).includes('第二个回答'));
  assert.ok(!JSON.stringify(renderer!.toJSON()).includes('第一个回答'));
  await act(async () => root.findAllByProps({ role: 'tab' })[0].props.onClick());
  assert.ok(JSON.stringify(renderer!.toJSON()).includes('第一个回答'));
  assert.ok(!JSON.stringify(renderer!.toJSON()).includes('第二个回答'));
  assert.equal(root.findAllByProps({ 'aria-label': '停止生成' }).length, 0);
});

test('closing a tab aborts only its request, ignores late output, and closing the last tab leaves an empty chat', async () => {
  const pending: { signal: AbortSignal; resolve: (value: Response) => void }[] = [];
  globalThis.fetch = async (_url, init) => new Promise(resolve => pending.push({ signal: init!.signal!, resolve }));
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/" />));
  const root = renderer!.root;
  const ask = async (question: string) => {
    await act(async () => root.findByType('textarea').props.onChange({ target: { value: question } }));
    await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  };
  await ask('需要关闭');
  await act(async () => root.findByProps({ 'aria-label': '新建对话' }).props.onClick());
  await ask('继续生成');
  await act(async () => root.findByProps({ 'aria-label': '关闭对话：需要关闭' }).props.onClick());
  assert.equal(pending[0].signal.aborted, true);
  assert.equal(pending[1].signal.aborted, false);
  await act(async () => pending[0].resolve(new Response('{"type":"delta","text":"关闭后的迟到消息"}\n{"type":"done"}\n')));
  assert.ok(!JSON.stringify(renderer!.toJSON()).includes('关闭后的迟到消息'));
  await act(async () => root.findAllByProps({ role: 'tab' })[0].props.onKeyDown({ key: 'Delete', preventDefault() {} }));
  assert.equal(pending[1].signal.aborted, true);
  assert.equal(root.findAllByProps({ role: 'tab' }).length, 1);
  assert.equal(root.findAllByType('article').length, 0);
  assert.equal(root.findByType('textarea').props.value, '');
});

test('research scopes restore their own conversations on return and credential changes clear every scope', async () => {
  globalThis.fetch = async () => new Response('{"type":"delta","text":"已完成"}\n{"type":"done"}\n');
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/stocks/000001.SZ" />));
  const root = renderer!.root;
  await act(async () => root.findByType('textarea').props.onChange({ target: { value: '平安银行草稿' } }));
  await act(async () => root.findByProps({ 'aria-label': '新建对话' }).props.onClick());
  await act(async () => root.findByType('textarea').props.onChange({ target: { value: '平安银行问题' } }));
  await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  await act(async () => renderer!.update(<Harness page="/stocks/600036.SH" />));
  assert.equal(root.findAllByProps({ role: 'tab' }).length, 1);
  assert.equal(root.findAllByType('article').length, 0);
  await act(async () => root.findByType('textarea').props.onChange({ target: { value: '招商银行草稿' } }));
  await act(async () => renderer!.update(<Harness page="/stocks/000001.SZ" />));
  assert.equal(root.findAllByProps({ role: 'tab' }).length, 2);
  assert.equal(root.findAllByType('article').length, 2);
  await act(async () => root.findAllByProps({ role: 'tab' })[0].props.onClick());
  assert.equal(root.findByType('textarea').props.value, '平安银行草稿');
  await act(async () => preferences.clear());
  assert.equal(root.findAllByProps({ role: 'tab' }).length, 1);
  assert.equal(root.findByType('textarea').props.value, '');
  await act(async () => renderer!.update(<Harness page="/stocks/600036.SH" />));
  assert.equal(root.findByType('textarea').props.value, '');
  assert.equal(root.findByType('textarea').props.disabled, true);
});

test('clearing credentials aborts replies in all tabs and late results never restore cleared conversations', async () => {
  const pending: { signal: AbortSignal; resolve: (value: Response) => void }[] = [];
  globalThis.fetch = async (_url, init) => new Promise(resolve => pending.push({ signal: init!.signal!, resolve }));
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/" />));
  const root = renderer!.root;
  for (const question of ['甲', '乙']) {
    if (question === '乙') await act(async () => root.findByProps({ 'aria-label': '新建对话' }).props.onClick());
    await act(async () => root.findByType('textarea').props.onChange({ target: { value: question } }));
    await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  }
  await act(async () => preferences.clear());
  assert.ok(pending.every(request => request.signal.aborted));
  for (const request of pending) await act(async () => request.resolve(new Response('{"type":"delta","text":"过期的回复"}\n{"type":"done"}\n')));
  assert.equal(root.findAllByProps({ role: 'tab' }).length, 1);
  assert.equal(root.findAllByType('article').length, 0);
  assert.ok(!JSON.stringify(renderer!.toJSON()).includes('过期的回复'));
});

test('account invalidation clears the shared key and aborts active analysis', async () => {
  const priorWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const priorChannel = globalThis.BroadcastChannel;
  Object.defineProperty(globalThis, 'window', { configurable: true, value: new EventTarget() });
  Object.defineProperty(globalThis, 'BroadcastChannel', { configurable: true, writable: true, value: undefined });
  try {
    let aborted = false;
    globalThis.fetch = async (_url, init) => {
      init?.signal?.addEventListener('abort', () => { aborted = true; });
      return new Promise<Response>(() => {});
    };
    await applySettings();
    await act(async () => renderer!.update(<Harness page="/" />));
    await act(async () => renderer!.root.findByType('textarea').props.onChange({ target: { value: '分析趋势' } }));
    await act(async () => renderer!.root.findByType('form').props.onSubmit({ preventDefault() {} }));
    await act(async () => invalidateSessionStatus());
    assert.equal(preferences.connection, null);
    assert.equal(aborted, true);
    assert.equal(renderer!.root.findByType('textarea').props.disabled, true);
    assert.equal(renderer!.root.findAllByType('article').length, 0);
    await act(async () => renderer?.unmount()); renderer = null;
  } finally {
    if (priorWindow) Object.defineProperty(globalThis, 'window', priorWindow);
    else Reflect.deleteProperty(globalThis, 'window');
    globalThis.BroadcastChannel = priorChannel;
  }
});

test('a fresh app tree starts without the previous key', async () => {
  await applySettings();
  await act(async () => renderer?.unmount());
  await act(async () => { renderer = TestRenderer.create(<Harness />); });
  assert.equal(preferences.connection, null);
  assert.equal(renderer!.root.findByProps({ type: 'password' }).props.value, '');
});

test('changing the API prediction stock aborts the previous assistant analysis', async () => {
  let signal: AbortSignal | null = null;
  let finish!: (response: Response) => void;
  globalThis.fetch = async (_url, init) => {
    signal = init!.signal!;
    assert.equal(JSON.parse(String(init?.body)).symbol, '000001.SZ');
    return new Promise(resolve => { finish = resolve; });
  };
  await applySettings();
  await act(async () => renderer!.update(<Harness page="/scores" predictionSymbol="000001.SZ" />));
  await act(async () => renderer!.root.findByType('textarea').props.onChange({ target: { value: '分析当前股票' } }));
  await act(async () => renderer!.root.findByType('form').props.onSubmit({ preventDefault() {} }));
  await act(async () => renderer!.update(<Harness page="/scores" predictionSymbol="600036.SH" />));
  assert.equal((signal as unknown as AbortSignal).aborted, true);
  await act(async () => finish(new Response('{"type":"delta","text":"旧股票回答"}\n{"type":"done"}\n')));
  assert.equal(renderer!.root.findAllByType('article').length, 0);
  assert.ok(!JSON.stringify(renderer!.toJSON()).includes('旧股票回答'));
});

test('account return retains the chosen prediction model and stock without copying unrelated query data', async () => {
  const priorWindow = Object.getOwnPropertyDescriptor(globalThis, 'window');
  const priorChannel = globalThis.BroadcastChannel;
  Object.defineProperty(globalThis, 'BroadcastChannel', { configurable: true, writable: true, value: undefined });
  const fakeWindow = Object.assign(new EventTarget(), { location: { pathname: '/scores', search: '?model=api_llm&symbol=000001.SZ&api_key=discard-this' } });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: fakeWindow });
  try {
    await act(async () => { renderer = TestRenderer.create(<Harness page="/scores" />); });
    assert.equal(preferences.returnPath, '/scores?model=api_llm&symbol=000001.SZ');
    await act(async () => preferences.rememberPage('/scores', 'model=api_llm&symbol=600036.SH'));
    fakeWindow.location.pathname = '/account'; fakeWindow.location.search = '';
    await act(async () => renderer!.update(<Harness />));
    assert.equal(preferences.returnPath, '/scores?model=api_llm&symbol=600036.SH');
    assert.ok(renderer!.root.findAllByProps({ href: preferences.returnPath }).length);
    assert.equal(researchReturnPath('/admin-console', 'model=api_llm'), null);
    assert.equal(researchReturnPath('//evil.test'), null);
    assert.equal(researchReturnPath('/scores', 'model=unknown&symbol=../secret&key=discard'), '/scores');
  } finally {
    await act(async () => renderer?.unmount()); renderer = null;
    if (priorWindow) Object.defineProperty(globalThis, 'window', priorWindow); else Reflect.deleteProperty(globalThis, 'window');
    globalThis.BroadcastChannel = priorChannel;
  }
});
