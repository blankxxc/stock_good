import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import React from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import { useApiPayload } from '../src/lib/useApiPayload';
import { ConditionScreenTable, rowMatchesFilter, type ConditionScreenPayload } from '../src/components/ConditionScreenTable';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true, self: globalThis });
const originalFetch = globalThis.fetch;
const renderers: ReactTestRenderer[] = [];
type Payload = { selected_model: string; value: string };
let state: ReturnType<typeof useApiPayload<Payload>>;

function Probe({ url, initial, seedUrl }: { url: string; initial: Payload; seedUrl: string }) {
  state = useApiPayload(url, initial, seedUrl);
  return <span>{state.payload?.value}</span>;
}

afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => renderer.unmount());
  globalThis.fetch = originalFetch;
});

test('SSR data for another model never overwrites the selected model', async () => {
  const a = '/api/scores?model=cograsp';
  const b = '/api/scores?model=sentiment_event';
  const calls: string[] = [];
  globalThis.fetch = async (url) => {
    calls.push(String(url));
    return Response.json({ selected_model: 'sentiment_event', value: 'current sentiment' });
  };
  let renderer!: ReactTestRenderer;
  await act(async () => {
    renderer = TestRenderer.create(<Probe url={b} seedUrl={a} initial={{ selected_model: 'cograsp', value: 'old server' }} />);
  });
  renderers.push(renderer);
  assert.equal(state.payload?.value, 'current sentiment');
  await act(async () => renderer.update(<Probe url={b} seedUrl={a} initial={{ selected_model: 'cograsp', value: 'late server' }} />));
  assert.equal(state.payload?.selected_model, 'sentiment_event');
  assert.ok(calls.every(url => url === b));
  await act(async () => renderer.update(<Probe url={a} seedUrl={a} initial={{ selected_model: 'cograsp', value: 'fresh matching server' }} />));
  assert.equal(state.payload?.value, 'fresh matching server');
});

test('numeric conditions exclude missing factors instead of treating them as zero', () => {
  const schema = { type: 'number' as const };
  for (const actual of [null, undefined, '', false, Number.NaN, Infinity]) {
    for (const operator of ['eq', 'gte', 'lte', 'lt', 'between']) {
      assert.equal(rowMatchesFilter({ factor: actual }, 'factor', schema, { operator, value: '0', value2: '1' }), false);
    }
  }
  assert.equal(rowMatchesFilter({ factor: 0 }, 'factor', schema, { operator: 'eq', value: '0' }), true);
  assert.equal(rowMatchesFilter({ factor: 0.5 }, 'factor', schema, { operator: 'between', value: '0', value2: '1' }), true);
  assert.equal(rowMatchesFilter({ factor: 0.5 }, 'factor', schema, { operator: 'between', value: '1', value2: '' }), false);
  assert.equal(rowMatchesFilter({ factor: null }, 'factor', schema, {}), true);
});

test('percentage filters use the same percentage points shown in the table', () => {
  const schema = { type: 'number' as const };
  assert.equal(rowMatchesFilter({ return_10d: .15 }, 'return_10d', schema, { operator: 'gte', value: '10' }), true);
  assert.equal(rowMatchesFilter({ return_10d: .09 }, 'return_10d', schema, { operator: 'gte', value: '10' }), false);
  assert.equal(rowMatchesFilter({ pct_change: -.025 }, 'pct_change', schema, { operator: 'between', value: '-3', value2: '-2' }), true);
  assert.equal(rowMatchesFilter({ close: 12 }, 'close', schema, { operator: 'gte', value: '10' }), true);
});

const screenPayload: ConditionScreenPayload = {
  latest_trade_date: '2026-10-19', base_columns: ['symbol', 'trade_date'],
  available_factor_columns: ['return_10d'],
  column_schema: { symbol: { type: 'text' }, trade_date: { type: 'category', options: ['2026-10-19'] }, return_10d: { type: 'number' } },
  rows: Array.from({ length: 300 }, (_, i) => ({ symbol: `${String(i + 1).padStart(6, '0')}.SZ`, trade_date: '2026-10-19', return_10d: i / 1000 })),
};

async function mountScreen() {
  let renderer!: ReactTestRenderer;
  await act(async () => { renderer = TestRenderer.create(<ConditionScreenTable initialPayload={screenPayload} />); });
  renderers.push(renderer);
  return renderer;
}

test('screening pages the render work while filtering all stocks and returning to page one', async () => {
  const renderer = await mountScreen();
  const rows = () => renderer.root.findByType('tbody').findAllByType('tr');
  const next = () => renderer.root.findByProps({ 'aria-label': '下一页股票' });
  assert.equal(rows().length, 50);
  assert.ok(rows()[0].findAllByProps({ href: '/stocks/000001.SZ?from=condition-screen' }).length);
  await act(async () => next().props.onClick());
  assert.ok(rows()[0].findAllByProps({ href: '/stocks/000051.SZ?from=condition-screen' }).length);
  await act(async () => renderer.root.findByProps({ 'aria-label': '近10日涨跌幅筛选数值' }).props.onChange({ target: { value: '29' } }));
  assert.equal(rows().length, 10, 'all 300 stocks must be filtered before pagination');
  assert.ok(rows()[0].findAllByProps({ href: '/stocks/000291.SZ?from=condition-screen' }).length);
  assert.equal(next().props.disabled, true);
});

test('hiding a factor clears its condition instead of leaving an invisible stale filter', async () => {
  const renderer = await mountScreen();
  await act(async () => renderer.root.findByProps({ 'aria-label': '近10日涨跌幅筛选数值' }).props.onChange({ target: { value: '29' } }));
  const checkbox = () => renderer.root.findAllByType('input').find(node => node.props.type === 'checkbox')!;
  await act(async () => checkbox().props.onChange({ target: { checked: false } }));
  await act(async () => checkbox().props.onChange({ target: { checked: true } }));
  assert.equal(renderer.root.findByProps({ 'aria-label': '近10日涨跌幅筛选数值' }).props.value, '');
  assert.equal(renderer.root.findByType('tbody').findAllByType('tr').length, 50);
});
