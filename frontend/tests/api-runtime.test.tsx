import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import React, { StrictMode } from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import { useApiPayload } from '../src/lib/useApiPayload';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
const originalFetch = globalThis.fetch;
const renderers: ReactTestRenderer[] = [];
type Payload = { value: string };
let state: ReturnType<typeof useApiPayload<Payload>>;

function Probe({ url, initial = null }: { url: string; initial?: Payload | null }) {
  state = useApiPayload(url, initial);
  return <span>{state.payload?.value}</span>;
}

async function mount(element: React.ReactElement) {
  let renderer!: ReactTestRenderer;
  await act(async () => { renderer = TestRenderer.create(element); });
  renderers.push(renderer);
  return renderer;
}

afterEach(async () => {
  for (const renderer of renderers.splice(0)) await act(async () => renderer.unmount());
  globalThis.fetch = originalFetch;
});

test('SSR snapshot avoids duplicate fetch, but explicit reload and new server data work', async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return Response.json({ value: 'refreshed' });
  };
  const initial = { value: 'server' };
  const renderer = await mount(<StrictMode><Probe url="/api/scores" initial={initial} /></StrictMode>);
  assert.equal(calls, 0);
  assert.equal(state.payload?.value, 'server');
  assert.equal(state.loading, false);
  await act(async () => state.reload());
  assert.equal(calls, 1);
  assert.equal(state.payload?.value, 'refreshed');
  await act(async () => renderer.update(<StrictMode><Probe url="/api/scores" initial={{ value: 'new server snapshot' }} /></StrictMode>));
  assert.equal(calls, 1);
  assert.equal(state.payload?.value, 'new server snapshot');
});

test('model changes fetch fresh data, including switching back; old requests cannot overwrite it', async () => {
  const requests: { url: string; signal: AbortSignal; resolve: (response: Response) => void }[] = [];
  globalThis.fetch = (url, options) => new Promise<Response>((resolve) => {
    requests.push({ url: String(url), signal: options!.signal!, resolve });
  });
  const initial = { value: 'cograsp initial' };
  const renderer = await mount(<Probe url="/api/scores?model=cograsp" initial={initial} />);
  await act(async () => renderer.update(<Probe url="/api/scores?model=sentiment_event" initial={initial} />));
  assert.equal(state.payload, null);
  assert.equal(state.loading, true);
  await act(async () => renderer.update(<Probe url="/api/scores?model=cograsp" initial={initial} />));
  assert.equal(requests.length, 2);
  assert.equal(requests[0].signal.aborted, true);
  await act(async () => requests[1].resolve(Response.json({ value: 'cograsp current' })));
  await act(async () => requests[0].resolve(Response.json({ value: 'late sentiment' })));
  assert.equal((state.payload as Payload | null)?.value, 'cograsp current');
});

test('missing SSR data is fetched and a failure can be retried', async () => {
  let calls = 0;
  globalThis.fetch = async () => ++calls === 1
    ? new Response('', { status: 503 })
    : Response.json({ value: 'recovered' });
  await mount(<Probe url="/api/market" />);
  assert.equal(state.error, 'HTTP 503');
  assert.equal(state.loading, false);
  await act(async () => state.reload());
  assert.equal(state.payload?.value, 'recovered');
  assert.equal(state.error, null);
});
