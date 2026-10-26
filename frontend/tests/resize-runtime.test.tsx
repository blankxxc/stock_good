import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import React from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import { ResizeHandle } from '../src/components/ResizeHandle';
import { ResizableVisualCard } from '../src/components/ResizableVisualCard';
import { ASSISTANT_SIZE_KEY, useAssistantSize } from '../src/components/useAssistantSize';
import { VisualChart } from '../src/components/VisualChart';
import type { ChartConfig, VisualData } from '../src/lib/visualization';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const globals = ['window', 'localStorage', 'getComputedStyle', 'ResizeObserver'] as const;
const originals = new Map(globals.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
let renderer: ReactTestRenderer | null = null;
function stub(key: string, value: unknown) { Object.defineProperty(globalThis, key, { configurable: true, value }); }
afterEach(async () => {
  if (renderer) await act(async () => renderer?.unmount()); renderer = null;
  for (const key of globals) { const value = originals.get(key); if (value) Object.defineProperty(globalThis, key, value); else Reflect.deleteProperty(globalThis, key); }
});
function pointer() {
  let captured: number | null = null;
  const target = { focus() {}, setPointerCapture(id: number) { captured = id; }, hasPointerCapture(id: number) { return captured === id; }, releasePointerCapture() { captured = null; } };
  return (x: number, y: number, id = 1) => ({ clientX: x, clientY: y, pointerId: id, button: 0, isPrimary: true, currentTarget: target, preventDefault() {}, stopPropagation() {} });
}
const key = (value: string) => ({ key: value, shiftKey: false, preventDefault() {}, stopPropagation() {} });
const card: ChartConfig = { id: 'one', title: '价格', type: 'line', metric: 'close', xMetric: 'close', wide: false, normalize: false };

test('card resize snaps live, commits only on release, and cancellation leaves saved layout untouched', async () => {
  stub('window', { innerWidth: 1600, innerHeight: 1000 });
  stub('getComputedStyle', () => ({ columnGap: '20px' }));
  const changes: unknown[] = [];
  await act(async () => { renderer = TestRenderer.create(<ResizableVisualCard card={card} cards={[card, { ...card, id: 'peer', height: 613 }]}
    onResize={size => changes.push(size)}><h3>价格</h3></ResizableVisualCard>, { createNodeMock: element => element.type === 'article'
      ? { parentElement: { getBoundingClientRect: () => ({ width: 1180 }) } } : null }); });
  const handle = () => renderer!.root.findByType('button');
  const style = () => renderer!.root.findByType('article').props.style;
  const event = pointer();
  await act(async () => handle().props.onPointerDown(event(100, 100)));
  await act(async () => handle().props.onPointerMove(event(302, 107)));
  assert.equal(style()['--card-columns'], 8);
  assert.equal(style()['--card-height'], '613px', 'nearby peer height wins over regular 20px grid');
  assert.equal(changes.length, 0);
  await act(async () => handle().props.onPointerMove(event(900, 700, 2)));
  assert.equal(style()['--card-columns'], 8, 'another pointer must not take over');
  await act(async () => handle().props.onPointerUp(event(302, 107)));
  assert.deepEqual(changes, [{ columns: 8, height: 613, wide: false }]);
  await act(async () => handle().props.onLostPointerCapture(event(302, 107)));
  assert.equal(changes.length, 1, 'release does not commit twice');
  await act(async () => handle().props.onPointerDown(event(100, 100)));
  await act(async () => handle().props.onPointerMove(event(-900, 3000)));
  assert.equal(style()['--card-columns'], 4);
  assert.equal(style()['--card-height'], '1200px');
  await act(async () => handle().props.onPointerCancel(event(-900, 3000)));
  assert.equal(style()['--card-columns'], 6);
  assert.equal(style()['--card-height'], '600px');
  assert.equal(changes.length, 1);
  await act(async () => handle().props.onKeyDown(key('ArrowRight')));
  assert.deepEqual(changes.at(-1), { columns: 7, height: 600, wide: false });
});

test('narrow screens resize height without overwriting desktop column preference', async () => {
  stub('window', { innerWidth: 390, innerHeight: 844 });
  let result: unknown;
  await act(async () => { renderer = TestRenderer.create(<ResizableVisualCard card={{ ...card, columns: 8 }} cards={[card]} onResize={size => { result = size; }}>图表</ResizableVisualCard>); });
  const button = renderer!.root.findByType('button'), event = pointer();
  await act(async () => button.props.onPointerDown(event(300, 500)));
  await act(async () => button.props.onPointerUp(event(100, 621)));
  assert.deepEqual(result, { columns: 8, height: 720, wide: false });
});

function AssistantFrame() {
  const size = useAssistantSize();
  return <aside ref={size.panel} style={size.style}><ResizeHandle label="resize" onStart={size.onStart} onStep={size.onStep} onReset={size.onReset} /></aside>;
}
test('assistant resize is viewport bounded, persists dimensions only, restores and cancels safely', async () => {
  stub('window', { innerWidth: 1600, innerHeight: 1000 });
  const saved = new Map<string, string>();
  stub('localStorage', { getItem: (key: string) => saved.get(key) ?? null, setItem: (key: string, value: string) => saved.set(key, value) });
  const mount = async () => act(async () => { renderer = TestRenderer.create(<AssistantFrame />, {
    createNodeMock: element => element.type === 'aside' ? { getBoundingClientRect: () => {
      const style = renderer!.root.findByType('aside').props.style;
      return { width: Math.min(1560, parseFloat(style['--assistant-width'])), height: Math.min(888, parseFloat(style['--assistant-height'])) };
    } } : null,
  }); });
  await mount();
  const handle = () => renderer!.root.findByType('button');
  const style = () => renderer!.root.findByType('aside').props.style;
  const event = pointer();
  await act(async () => handle().props.onPointerDown(event(500, 300)));
  await act(async () => handle().props.onPointerMove(event(300, 250)));
  assert.equal(style()['--assistant-width'], '640px');
  assert.equal(style()['--assistant-height'], '840px');
  assert.equal(saved.size, 0);
  await act(async () => handle().props.onPointerUp(event(300, 250)));
  assert.deepEqual(JSON.parse(saved.get(ASSISTANT_SIZE_KEY)!), { width: 640, height: 840 });
  await act(async () => renderer!.unmount()); renderer = null;
  await mount();
  assert.equal(style()['--assistant-width'], '640px');
  await act(async () => handle().props.onPointerDown(event(500, 300)));
  await act(async () => handle().props.onPointerMove(event(-10000, -10000)));
  assert.equal(style()['--assistant-width'], '1560px');
  assert.equal(style()['--assistant-height'], '888px');
  await act(async () => handle().props.onKeyDown({ ...key('Escape'), currentTarget: event(0, 0).currentTarget }));
  assert.equal(style()['--assistant-width'], '640px');
  assert.deepEqual(JSON.parse(saved.get(ASSISTANT_SIZE_KEY)!), { width: 640, height: 840 });
  await act(async () => handle().props.onKeyDown(key('ArrowRight')));
  assert.equal(style()['--assistant-width'], '620px');
  await act(async () => handle().props.onDoubleClick());
  assert.deepEqual(JSON.parse(saved.get(ASSISTANT_SIZE_KEY)!), { width: 440, height: 790 });
  assert.deepEqual([...saved.keys()], [ASSISTANT_SIZE_KEY]);
});

test('pointer capture loss cancels and secondary presses cannot begin a resize', async () => {
  const finished: boolean[] = []; let started = 0;
  await act(async () => { renderer = TestRenderer.create(<ResizeHandle label="resize" onReset={() => {}} onStep={() => {}}
    onStart={() => { started++; return { move() {}, finish: cancelled => finished.push(cancelled) }; }} />); });
  const button = renderer!.root.findByType('button'), event = pointer();
  await act(async () => button.props.onPointerDown({ ...event(0, 0), button: 2 }));
  assert.equal(started, 0);
  await act(async () => button.props.onPointerDown(event(0, 0)));
  await act(async () => button.props.onLostPointerCapture(event(40, 40)));
  await act(async () => button.props.onPointerUp(event(40, 40)));
  assert.deepEqual(finished, [true]);
});

test('chart uses actual resized plot dimensions and releases its observer', async () => {
  let notify: (entries: unknown[]) => void = () => {}; let disconnected = 0;
  stub('ResizeObserver', class { constructor(callback: typeof notify) { notify = callback; } observe() {} disconnect() { disconnected++; } });
  const data: VisualData = { dates: ['2026-10-19'], series: [{ symbol: '000001.SZ', stock_name: '甲', metric: 'close', values: [10], observations: 1 }],
    metrics: [{ id: 'close', label: '价格', unit: '元', group: '行情', description: '' }], start_date: '2026-10-19', end_date: '2026-10-19',
    market_end: '2026-10-19', factor_end: null, data_version: 'test', price_basis: '后复权', notes: [] };
  await act(async () => { renderer = TestRenderer.create(<VisualChart card={card} data={data} />, { createNodeMock: () => ({}) }); });
  await act(async () => notify([{ contentRect: { width: 380, height: 240 } }]));
  assert.equal(renderer!.root.findByType('svg').props.viewBox, '0 0 380 240');
  assert.ok(renderer!.root.findAllByType('line').every(line => line.props.x2 <= 380));
  await act(async () => renderer!.unmount()); renderer = null;
  assert.equal(disconnected, 1);
});
