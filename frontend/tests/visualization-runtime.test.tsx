import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import React from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import { Workbench } from '../src/components/VisualizationWorkbench';
import { VisualChart } from '../src/components/VisualChart';
import { AssistantPreferencesProvider } from '../src/components/AssistantPreferences';
import { BOARD_KEY, boardRequest, dataCsv, defaultBoard, normalized, requestKey, restoreBoard, segments, validateBoard,
  type VisualData, type VisualMetadata } from '../src/lib/visualization';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true, self: globalThis });
const originalFetch = globalThis.fetch;
const storageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
let renderer: ReactTestRenderer | null = null;
afterEach(async () => {
  if (renderer) await act(async () => renderer?.unmount()); renderer = null;
  globalThis.fetch = originalFetch;
  if (storageDescriptor) Object.defineProperty(globalThis, 'localStorage', storageDescriptor);
  else Reflect.deleteProperty(globalThis, 'localStorage');
});

const meta: VisualMetadata = {
  stocks: [{ symbol: '000001.SZ', stock_name: '甲' }, { symbol: '600000.SH', stock_name: '乙' }],
  metrics: ['close', 'raw_close', 'volume', 'return_20d'].map(id => ({ id, label: id, unit: '原值', group: id === 'return_20d' ? '因子' : '行情', description: '' })),
  market_start: '2026-01-01', market_end: '2026-10-19', default_start: '2026-10-12', factor_end: '2026-10-19', price_basis: '后复权', data_version: 'test', notes: [],
};
const data: VisualData = { dates: ['2026-10-12', '2026-10-13', '2026-10-14'],
  series: [{ symbol: '000001.SZ', stock_name: '甲', metric: 'close', values: [10, null, 30], observations: 2 },
    { symbol: '000001.SZ', stock_name: '甲', metric: 'return_20d', values: [null, .2, -.1], observations: 2 }],
  metrics: meta.metrics, start_date: '2026-10-12', end_date: '2026-10-19', market_end: meta.market_end,
  factor_end: meta.factor_end, data_version: 'test', price_basis: meta.price_basis, notes: [],
};
function storage(raw?: string) {
  const values = new Map(raw ? [[BOARD_KEY, raw]] : []);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value),
  } });
  return values;
}

test('layout roundtrip retains settings and strips unrelated fields', () => {
  const board = defaultBoard(meta); board.cards[0].wide = false;
  const restored = restoreBoard(JSON.stringify({ ...board, apiKey: 'must-not-persist', cards: board.cards.map(c => ({ ...c, unknown: true })) }), meta);
  assert.deepEqual(restored, board);
  assert.equal(validateBoard(board, meta), null);
  for (const patch of [{ version: 2 }, { symbols: [] }, { symbols: ['unknown'] }, { cards: [] }, { start_date: '2026-02-30' }, { end_date: '2026-01-01' }]) {
    assert.throws(() => restoreBoard(JSON.stringify({ ...board, ...patch }), meta));
  }
});

test('layout reorder and styling do not change data query; scatter adds its X metric', () => {
  const board = defaultBoard(meta), key = requestKey(board);
  board.cards.reverse(); board.cards[0].wide = true; board.cards[0].normalize = true; board.title = '新名称';
  board.cards[0].columns = 8; board.cards[0].height = 720;
  assert.equal(requestKey(board), key);
  board.cards[0].type = 'scatter'; board.cards[0].xMetric = 'raw_close';
  assert.ok(boardRequest(board).metrics.includes('raw_close'));
});

test('resized layouts roundtrip while invalid dimensions are rejected', () => {
  const board = defaultBoard(meta);
  board.cards[0] = { ...board.cards[0], columns: 8, height: 720 };
  assert.deepEqual(restoreBoard(JSON.stringify(board), meta), board);
  for (const patch of [{ columns: 3 }, { columns: 13 }, { columns: 6.5 }, { columns: '6' }, { height: 399 }, { height: 1201 }, { height: null }]) {
    assert.throws(() => restoreBoard(JSON.stringify({ ...board, cards: [{ ...board.cards[0], ...patch }] }), meta));
  }
});

test('normalization ignores gaps and chart segments never bridge missing observations', () => {
  assert.deepEqual(normalized([1, null, 3]), [-1, null, 1]);
  assert.deepEqual(normalized([0, 0, null]), [0, 0, null]);
  assert.deepEqual(normalized([null, NaN]), [null, null]);
  assert.deepEqual(segments([1, null, 0, -2, NaN, 3]), [[{ index: 0, value: 1 }], [{ index: 2, value: 0 }, { index: 3, value: -2 }], [{ index: 5, value: 3 }]]);
});

test('CSV retains negative numbers and nulls while escaping text cells', () => {
  const csv = dataCsv({ ...data, series: [{ ...data.series[1], stock_name: '=malicious,"text"' }] });
  assert.ok(csv.startsWith('\uFEFF'));
  assert.ok(csv.includes('"\'=malicious,""text"""'));
  assert.ok(csv.includes(',"原值",-0.1,"test"'));
  assert.ok(csv.includes(',"原值","","test"'));
});

test('line gaps, negative bars, and scatter paired dates render correctly', async () => {
  const card = defaultBoard(meta).cards[0];
  await act(async () => { renderer = TestRenderer.create(<VisualChart card={card} data={data} />); });
  assert.equal(renderer!.root.findAllByType('polyline').length, 2);
  assert.equal(renderer!.root.findAllByType('table').length, 0, 'hidden data tables must not render thousands of rows');
  await act(async () => renderer!.update(<VisualChart card={{ ...card, type: 'bar', metric: 'return_20d' }} data={data} />));
  const bars = renderer!.root.findAllByType('rect');
  assert.equal(bars.length, 2);
  assert.ok(bars.every(bar => bar.props.height > 0));
  await act(async () => renderer!.update(<VisualChart card={{ ...card, type: 'scatter', metric: 'return_20d', xMetric: 'close' }} data={data} />));
  assert.equal(renderer!.root.findAllByType('circle').length, 1, 'only one day has both X and Y');
});

test('saved layout restores, reorders, saves, and does not refetch for chart styling', async () => {
  const board = defaultBoard(meta); board.title = '已保存的研究';
  const values = storage(JSON.stringify(board));
  let count = 0;
  globalThis.fetch = async () => { count++; return Response.json(data); };
  await act(async () => { renderer = TestRenderer.create(<AssistantPreferencesProvider pathname="/visualization"><Workbench meta={meta} /></AssistantPreferencesProvider>); });
  assert.equal(renderer!.root.findByProps({ 'aria-label': '看板名称' }).props.value, board.title);
  assert.equal(count, 1);
  const resize = renderer!.root.findByProps({ 'aria-label': '调整价格趋势大小' });
  await act(async () => resize.props.onKeyDown({ key: 'ArrowDown', preventDefault() {}, stopPropagation() {} }));
  await act(async () => renderer!.root.findByProps({ 'aria-label': '价格趋势后移' }).props.onClick());
  assert.equal(renderer!.root.findAllByType('h3')[0].children.join(''), '成交量观察');
  const save = renderer!.root.findAllByType('button').find(b => b.children.join('') === '保存看板')!;
  await act(async () => save.props.onClick());
  assert.equal(JSON.parse(values.get(BOARD_KEY)!).cards[0].id, 'volume');
  assert.equal(JSON.parse(values.get(BOARD_KEY)!).cards.find((c: any) => c.id === 'price').height, 620);
  assert.equal(count, 1);
});

test('old responses cannot overwrite new selections and edits hide outdated charts', async () => {
  storage();
  const requests: { body: any; resolve: (response: Response) => void }[] = [];
  globalThis.fetch = async (_input, init) => new Promise<Response>(resolve => requests.push({ body: JSON.parse(String(init?.body)), resolve }));
  await act(async () => { renderer = TestRenderer.create(<AssistantPreferencesProvider pathname="/visualization"><Workbench meta={meta} /></AssistantPreferencesProvider>); });
  await act(async () => renderer!.root.findAllByProps({ type: 'date' })[0].props.onChange({ target: { value: '2026-10-13' } }));
  assert.equal(requests.length, 1, 'draft edits do not trigger requests');
  const update = renderer!.root.findAllByType('button').find(b => /更新图表|重新加载图表/.test(b.children.join('')))!;
  await act(async () => update.props.onClick());
  assert.equal(requests.length, 2);
  await act(async () => requests[1].resolve(Response.json({ ...data, start_date: '2026-10-13' })));
  assert.equal(renderer!.root.findAllByType(VisualChart)[0].props.data.start_date, '2026-10-13');
  await act(async () => requests[0].resolve(Response.json(data)));
  assert.equal(renderer!.root.findAllByType(VisualChart)[0].props.data.start_date, '2026-10-13');
  await act(async () => renderer!.root.findAllByProps({ type: 'date' })[0].props.onChange({ target: { value: '2026-10-14' } }));
  assert.equal(renderer!.root.findAllByType(VisualChart).length, 0);
});
