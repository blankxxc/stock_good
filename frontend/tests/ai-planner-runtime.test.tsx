import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import React from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import { AIPlanComposer } from '../src/components/AIPlanComposer';
import { AssistantPreferencesProvider, useAssistantPreferences } from '../src/components/AssistantPreferences';
import { Workbench } from '../src/components/VisualizationWorkbench';
import { StrategyLab } from '../src/components/StrategyLab';
import { BOARD_KEY, defaultBoard, restoreBoard, type Board, type VisualMetadata } from '../src/lib/visualization';
import { readStrategyConfig } from '../src/lib/strategyLab';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true, self: globalThis });
const originalFetch = globalThis.fetch;
const storageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
let renderer: ReactTestRenderer | null = null;
let preferences: ReturnType<typeof useAssistantPreferences>;
afterEach(async () => {
  if (renderer) await act(async () => renderer?.unmount()); renderer = null;
  globalThis.fetch = originalFetch;
  if (storageDescriptor) Object.defineProperty(globalThis, 'localStorage', storageDescriptor);
  else Reflect.deleteProperty(globalThis, 'localStorage');
});
function Capture() { preferences = useAssistantPreferences(); return null; }
function Settings({ children }: { children: React.ReactNode }) {
  return <AssistantPreferencesProvider pathname="/visualization"><Capture />{children}</AssistantPreferencesProvider>;
}
async function connect() {
  await act(async () => preferences.apply({ apiKey: 'test-only-key', model: 'test-model',
    provider: { id: 'deepseek', label: 'DeepSeek', base_url: 'https://api.deepseek.com', default_model: 'test-model' } }));
}
const meta: VisualMetadata = {
  stocks: [{ symbol: '000001.SZ', stock_name: '平安银行' }, { symbol: '600036.SH', stock_name: '招商银行' }],
  metrics: ['close', 'volume'].map(id => ({ id, label: id, unit: '原值', group: '行情', description: '' })),
  market_start: '2026-01-01', market_end: '2026-10-19', default_start: '2026-07-01', factor_end: '2026-10-19',
  price_basis: '后复权', data_version: 'test', notes: [],
};
const board = defaultBoard(meta);
const generated: Board = { ...board, title: 'AI 银行对比', symbols: meta.stocks.map(s => s.symbol), cards: board.cards.slice(0, 2) };
const response = (config: unknown = generated, task = 'visualization') => ({ task, status: 'ready', summary: '生成比较方案', notes: ['本地日频行情'], unsupported: [], config });
const button = (text: string) => renderer!.root.findAllByType('button').find(b => b.children.join('') === text)!;
async function generate() {
  await act(async () => renderer!.root.findByType('textarea').props.onChange({ target: { value: '比较银行' } }));
  await act(async () => renderer!.root.findByType(AIPlanComposer).findByType('form').props.onSubmit({ preventDefault() {} }));
}
function Panel({ current = board, apply = () => {} }: { current?: Board; apply?: (c: Board) => void }) {
  return <Settings><AIPlanComposer task="visualization" current={current} contextKey="test"
    parseConfig={v => restoreBoard(JSON.stringify(v), meta)} preview={c => <p>{c.title}</p>} onApply={apply} /></Settings>;
}
function storage() {
  const values = new Map<string, string>();
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => values.set(k, v),
  } });
  return values;
}

test('unconfigured planning stays local and points to existing account settings', async () => {
  let requests = 0; globalThis.fetch = async () => { requests++; return Response.json({}); };
  await act(async () => { renderer = TestRenderer.create(<Panel />); });
  await generate();
  assert.equal(requests, 0);
  assert.equal(button('生成看板方案').props.disabled, true);
  assert.ok(renderer!.root.findAllByProps({ href: '/account' }).length);
});

test('plan is previewed first; credentials stay in header and only explicit apply changes configuration', async () => {
  let applied: Board | null = null;
  globalThis.fetch = async (_input, init) => {
    assert.equal(new Headers(init?.headers).get('X-AI-API-Key'), 'test-only-key');
    assert.equal(init?.credentials, 'omit');
    assert.ok(!String(init?.body).includes('test-only-key'));
    assert.equal(JSON.parse(String(init?.body)).current.title, board.title);
    return Response.json(response());
  };
  await act(async () => { renderer = TestRenderer.create(<Panel apply={c => { applied = c; }} />); });
  await connect(); await generate();
  assert.equal(applied, null);
  assert.ok(renderer!.root.findByProps({ 'aria-label': 'AI 配置草案' }));
  await act(async () => button('应用到看板').props.onClick());
  assert.deepEqual(applied, generated);
});

test('editing current configuration or clearing credentials aborts and ignores late plans', async () => {
  const pending: { signal: AbortSignal; resolve: (response: Response) => void }[] = [];
  globalThis.fetch = async (_input, init) => new Promise(resolve => pending.push({ signal: init!.signal!, resolve }));
  await act(async () => { renderer = TestRenderer.create(<Panel />); });
  await connect(); await generate();
  await act(async () => renderer!.update(<Panel current={{ ...board, title: '手动修改' }} />));
  assert.equal(pending[0].signal.aborted, true);
  await act(async () => pending[0].resolve(Response.json(response())));
  assert.equal(button('应用到看板'), undefined);
  await generate();
  await act(async () => preferences.clear());
  assert.equal(pending[1].signal.aborted, true);
  await act(async () => pending[1].resolve(Response.json(response())));
  assert.equal(button('应用到看板'), undefined);
});

test('unsupported requirements and unknown metrics cannot be applied', async () => {
  globalThis.fetch = async () => Response.json({ ...response(), status: 'needs_changes', config: null, unsupported: ['不支持分钟数据'] });
  await act(async () => { renderer = TestRenderer.create(<Panel />); });
  await connect(); await generate();
  assert.equal(button('应用到看板'), undefined);
  globalThis.fetch = async () => Response.json(response({ ...generated, cards: [{ ...generated.cards[0], metric: 'unknown' }] }));
  await generate();
  assert.ok(renderer!.root.findByProps({ role: 'alert' }));
  assert.equal(button('应用到看板'), undefined);
});

test('generated board applies to real workbench, fetches selected series and saves an editable key-free layout', async () => {
  const values = storage(); const series: any[] = [];
  globalThis.fetch = async (input, init) => {
    if (input === '/api/assistant/plan') return Response.json(response());
    const query = JSON.parse(String(init?.body)); series.push(query);
    return Response.json({ ...query, dates: [], series: [], metrics: meta.metrics, notes: [], price_basis: '后复权' });
  };
  await act(async () => { renderer = TestRenderer.create(<Settings><Workbench meta={meta} /></Settings>); });
  await connect(); await generate();
  assert.equal(series.length, 1, 'preview does not load or overwrite board');
  await act(async () => button('应用到看板').props.onClick());
  assert.equal(renderer!.root.findByProps({ 'aria-label': '看板名称' }).props.value, generated.title);
  assert.deepEqual(series[1].symbols, generated.symbols);
  await act(async () => button('保存看板').props.onClick());
  assert.equal(JSON.parse(values.get(BOARD_KEY)!).title, generated.title);
  assert.ok(!values.get(BOARD_KEY)!.includes('test-only-key'));
});

test('AI strategy executes the generated parameters, not the previous form values', async () => {
  storage(); let executed: unknown = null;
  const config = { start_date: '2026-07-01', end_date: '2026-10-19', strategies: ['low_volatility'], lookback: 10,
    top_k: 5, rebalance_days: 20, initial_capital: 200000, fee_bps: 4, slippage_bps: 6,
    exclude_st: true, exclude_extreme: true, exclude_abnormal: false };
  globalThis.fetch = async (input, init) => {
    if (input === '/api/strategy-lab') return Response.json({ ...meta, default_end: meta.market_end,
      stock_count: 2, assumptions: [], strategies: [{ id: 'low_volatility', label: '低波动', description: '低波动优先' }] });
    if (input === '/api/assistant/plan') return Response.json(response(config, 'strategy'));
    assert.equal(input, '/api/strategy-lab/run'); executed = JSON.parse(String(init?.body));
    return Response.json({ detail: '测试回测错误应正常显示' }, { status: 422 });
  };
  await act(async () => { renderer = TestRenderer.create(<Settings><StrategyLab /></Settings>); });
  await connect(); await generate();
  assert.equal(executed, null);
  await act(async () => button('应用并运行比较').props.onClick());
  assert.deepEqual(executed, config);
  assert.ok(renderer!.root.findAllByProps({ role: 'alert' }).some(n => n.children.join('').includes('测试回测错误')));
  assert.deepEqual(readStrategyConfig(config), config);
  assert.throws(() => readStrategyConfig({ ...config, fee_bps: -1 }));
});
