import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import React from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import APIPredictionPanel from '../src/components/APIPredictionPanel';
import { AssistantPreferencesProvider, useAssistantPreferences } from '../src/components/AssistantPreferences';
import { readPrediction, type PredictionInput } from '../src/lib/aiPrediction';
import { safeSourceUrl } from '../src/lib/assistant';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true, self: globalThis });
const originalFetch = globalThis.fetch;
let renderer: ReactTestRenderer | null = null;
let preferences: ReturnType<typeof useAssistantPreferences>;
afterEach(async () => { if (renderer) await act(async () => renderer?.unmount()); renderer = null; globalThis.fetch = originalFetch; });
function Capture() { preferences = useAssistantPreferences(); return null; }
const ids = ['return_5d', 'volatility_20d', 'volume_shock_20d'];
const query: PredictionInput = { symbol: '000001.SZ', factors: ids, horizon_days: 5, neutral_band_pct: 1 };
const meta = { stocks: [{ symbol: '000001.SZ', stock_name: '平安银行' }, { symbol: '600036.SH', stock_name: '招商银行' }],
  metrics: ids.map(id => ({ id, label: id, group: '因子', description: '测试公式', unit: '' })), market_end: '2026-10-19', price_basis: '后复权', data_version: 'test' };
function result(changes: Record<string, unknown> = {}) {
  return { status: 'estimated', probability_up: .5, probability_flat: .2, probability_down: .3, rationale: '测试因子支持但有分歧。',
    evidence: [{ factor: ids[0], impact: 'supports_up', explanation: '动量为正。' }], risks: ['未校准'], provider: 'deepseek', model: 'test-model', generated_at: '2026-10-25T00:00:00Z',
    calibration_status: 'uncalibrated', notice: '主观概率估计', input: { ...query, stock_name: '平安银行', as_of: '2026-10-19',
      price_basis: '后复权', data_version: 'test', snapshot_id: 'test-snapshot', event_definition: '未来5个交易日累计收益，震荡±1%。', prices: [{ date: '2026-10-19', close: 100, volume: 1000 }],
      factors: ids.map(id => ({ id, label: id, formula: '测试', value: .1, value_date: '2026-10-19', recent: [] })),
      history_reference: { sample_count: 50, probability_up: .4, probability_flat: .2, probability_down: .4, note: '历史重叠区间频率，不是模型准确率。' } }, ...changes };
}
function Panel() { return <AssistantPreferencesProvider pathname="/scores"><Capture /><APIPredictionPanel initialSymbol="000001.SZ" onSelectModel={() => {}} /></AssistantPreferencesProvider>; }
async function mount() { await act(async () => { renderer = TestRenderer.create(<Panel />); }); }
async function connect() { await act(async () => preferences.apply({ apiKey: 'test-only-key', model: 'test-model', provider: { id: 'deepseek', label: 'DeepSeek', base_url: 'https://api.deepseek.com', default_model: 'test-model' } })); }
const button = (text: string) => renderer!.root.findAllByType('button').find(b => b.children.join('') === text);
async function generate() { await act(async () => renderer!.root.findByType('form').props.onSubmit({ preventDefault() {} })); }
function mockPrediction(reply: () => Response | Promise<Response>) {
  globalThis.fetch = async input => input === '/api/visualization' ? Response.json(meta) : reply();
}

test('unconfigured forecast loads only metadata and links to existing settings', async () => {
  let posts = 0; mockPrediction(() => { posts++; return Response.json(result()); });
  await mount(); await generate();
  assert.equal(posts, 0); assert.equal(button('生成概率预测')!.props.disabled, true);
  assert.ok(renderer!.root.findAllByProps({ href: '/account' }).length);
  await connect(); assert.equal(posts, 0, 'setting a key must not make a paid call');
});

test('manual forecast sends key only in header and renders three probabilities with real evidence', async () => {
  let posts = 0;
  globalThis.fetch = async (input, init) => {
    if (input === '/api/visualization') return Response.json(meta);
    assert.equal(input, '/api/assistant/predict'); posts++;
    assert.equal(new Headers(init?.headers).get('X-AI-API-Key'), 'test-only-key');
    assert.equal(init?.credentials, 'omit'); assert.ok(!String(init?.body).includes('test-only-key'));
    assert.deepEqual(JSON.parse(String(init?.body)), { ...query, provider: 'deepseek', model: 'test-model' });
    return Response.json(result());
  };
  await mount(); await connect(); await generate();
  assert.equal(posts, 1);
  const text = JSON.stringify(renderer!.toJSON());
  assert.ok(text.includes('50.0%') && text.includes('20.0%') && text.includes('30.0%'));
  assert.ok(text.includes('2026-10-19') && text.includes('未校准') && text.includes('动量为正'));
  assert.ok(!text.includes('test-only-key'));
});

test('parameter edits, key changes and stopping abort requests and ignore late results', async () => {
  const pending: { signal: AbortSignal; resolve: (r: Response) => void }[] = [];
  globalThis.fetch = async (input, init) => input === '/api/visualization' ? Response.json(meta) : new Promise(resolve => pending.push({ signal: init!.signal!, resolve }));
  await mount(); await connect(); await generate();
  await act(async () => renderer!.root.findByProps({ 'aria-label': '预测周期' }).props.onChange({ target: { value: '10' } }));
  assert.equal(pending[0].signal.aborted, true);
  await act(async () => pending[0].resolve(Response.json(result())));
  assert.equal(button('导出预测快照'), undefined);
  await generate(); await act(async () => preferences.clear());
  assert.equal(pending[1].signal.aborted, true);
  await act(async () => pending[1].resolve(Response.json(result())));
  assert.equal(button('导出预测快照'), undefined);
  await connect(); await generate(); await act(async () => button('停止预测')!.props.onClick());
  assert.equal(pending[2].signal.aborted, true);
  await act(async () => pending[2].resolve(Response.json(result())));
  assert.equal(button('导出预测快照'), undefined);
});

test('malformed probability and mismatched stock never render an estimate', async () => {
  for (const bad of [result({ probability_up: .9 }), result({ input: { ...result().input, symbol: '600036.SH' } })]) {
    mockPrediction(() => Response.json(bad));
    if (!renderer) { await mount(); await connect(); }
    await generate();
    assert.ok(renderer!.root.findByProps({ role: 'alert' })); assert.equal(button('导出预测快照'), undefined);
  }
});

test('abstention keeps null probabilities and missing factors visibly missing', async () => {
  const base = result();
  mockPrediction(() => Response.json(result({ status: 'insufficient_data', probability_up: null, probability_flat: null, probability_down: null, evidence: [],
    input: { ...base.input, factors: base.input.factors.map(f => ({ ...f, value: null, value_date: null })) } })));
  await mount(); await connect(); await generate();
  const text = JSON.stringify(renderer!.toJSON());
  assert.ok(text.includes('本次未给出概率') && text.includes('缺失'));
  assert.ok(!text.includes('50.0%'));
  assert.ok(button('导出预测快照'));
});

test('export snapshot contains inputs and result without credentials', async () => {
  mockPrediction(() => Response.json(result())); await mount(); await connect(); await generate();
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, 'document');
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
  let blob: Blob | null = null; let clicked = false;
  URL.createObjectURL = value => { blob = value as Blob; return 'blob:test'; }; URL.revokeObjectURL = () => {};
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { createElement: () => ({ click: () => { clicked = true; } }) } });
  try {
    await act(async () => button('导出预测快照')!.props.onClick());
    const text = await (blob as unknown as Blob).text();
    assert.ok(clicked && text.includes('test-snapshot') && text.includes('0.5') && !text.includes('test-only-key'));
  } finally {
    URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke;
    if (descriptor) Object.defineProperty(globalThis, 'document', descriptor); else Reflect.deleteProperty(globalThis, 'document');
  }
});

test('strict reader rejects invented evidence, NaN, wrong totals and missing response structures', () => {
  for (const changes of [{ probability_up: NaN }, { probability_up: '0.5' }, { probability_up: true }, { probability_down: .4 },
    { input: {} }, { risks: null }, { evidence: [{ factor: 'invented', impact: 'supports_up', explanation: 'test' }] }]) {
    assert.throws(() => readPrediction(result(changes), query));
  }
  assert.equal(safeSourceUrl('/scores?model=api_llm'), '/scores?model=api_llm');
});
