import assert from 'node:assert/strict';
import { afterEach, before, test } from 'node:test';
import React from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import type { SessionInvalidationMessage } from '../src/lib/auth';

class FakeBroadcastChannel extends EventTarget {
  static instances: FakeBroadcastChannel[] = [];

  readonly posted: unknown[] = [];

  constructor(readonly name: string) {
    super();
    FakeBroadcastChannel.instances.push(this);
  }

  postMessage(message: unknown): void {
    this.posted.push(message);
  }

  close(): void {}

  receive(message: unknown): void {
    this.dispatchEvent(new MessageEvent('message', { data: message }));
  }
}

type LocationSpy = {
  search: string;
  assigned: string[];
  replaced: string[];
  assign(path: string): void;
  replace(path: string): void;
};

const browserWindow = new EventTarget() as EventTarget & {
  location: LocationSpy;
  confirm(message?: string): boolean;
};
browserWindow.location = {
  search: '',
  assigned: [],
  replaced: [],
  assign(path: string) { this.assigned.push(path); },
  replace(path: string) { this.replaced.push(path); },
};
browserWindow.confirm = () => true;

Object.assign(globalThis, {
  IS_REACT_ACT_ENVIRONMENT: true,
  window: browserWindow,
  document: { cookie: 'oa_csrf=csrf-runtime-test' },
  BroadcastChannel: FakeBroadcastChannel,
});

let auth: typeof import('../src/lib/auth');
let LoginPanel: typeof import('../src/components/LoginPanel').LoginPanel;
let AuthNav: typeof import('../src/components/AuthNav').AuthNav;
let WatchlistBoard: typeof import('../src/components/WatchlistBoard').WatchlistBoard;

before(async () => {
  auth = await import('../src/lib/auth');
  ({ LoginPanel } = await import('../src/components/LoginPanel'));
  ({ AuthNav } = await import('../src/components/AuthNav'));
  ({ WatchlistBoard } = await import('../src/components/WatchlistBoard'));
});

afterEach(() => {
  browserWindow.location.search = '';
  browserWindow.location.assigned.length = 0;
  browserWindow.location.replaced.length = 0;
});

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

async function flushAsyncWork(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await new Promise<void>((resolve) => setImmediate(resolve));
    await Promise.resolve();
  });
}

function authenticatedStatus() {
  return {
    authenticated: true,
    user: {
      id: 7,
      username: 'runtime.user',
      display_name: 'Runtime User',
      role: 'user' as const,
    },
    expires_at: '2026-07-23T00:00:00Z',
    session_generation: 'generation-runtime-test',
    setup_required: false,
    registration_open: true,
  };
}

test('one invalidation coalesces refreshes, deduplicates remote events, and reloads only after authentication changes', async () => {
  const pendingStatus = deferred<Response>();
  let statusFetches = 0;
  globalThis.fetch = (async (input: string | URL | Request) => {
    assert.equal(String(input), '/api/auth/status');
    statusFetches += 1;
    return pendingStatus.promise;
  }) as typeof fetch;

  const reloads: Promise<unknown>[] = [];
  const unsubscribers = Array.from({ length: 3 }, () => auth.subscribeSessionInvalidation((message) => {
    if (auth.shouldReloadPrivateSession(message)) {
      reloads.push(auth.getSessionStatus({ refresh: true }));
    }
  }));

  auth.invalidateSessionStatus('authentication-changed');
  assert.equal(statusFetches, 1, 'all listeners must share the first fresh status request');
  assert.equal(reloads.length, 3);
  assert.ok(reloads.every((request) => request === reloads[0]));
  pendingStatus.resolve(jsonResponse(authenticatedStatus()));
  await Promise.all(reloads);

  let remoteDeliveries = 0;
  const unsubscribeRemote = auth.subscribeSessionInvalidation((message) => {
    if (!auth.shouldReloadPrivateSession(message)) remoteDeliveries += 1;
  });
  const channel = FakeBroadcastChannel.instances.at(-1);
  assert.ok(channel);
  const duplicate: SessionInvalidationMessage = {
    type: 'stock-good:session-invalidated',
    eventId: 'remote-tab:event-1',
    sourceTabId: 'remote-tab',
    reason: 'authorization-failed',
  };
  channel.receive(duplicate);
  channel.receive(duplicate);
  assert.equal(remoteDeliveries, 1, 'the same remote eventId must be delivered once');
  assert.equal(statusFetches, 1, 'authorization failures must not schedule a private reload');
  assert.equal(auth.shouldReloadPrivateSession({ ...duplicate, reason: 'session-context-changed' }), false);

  unsubscribeRemote();
  unsubscribers.forEach((unsubscribe) => unsubscribe());
});

test('WatchlistBoard makes a bounded number of requests when the private endpoint keeps returning 401 or 409', async () => {
  for (const status of [401, 409]) {
    let statusFetches = 0;
    let watchlistFetches = 0;
    globalThis.fetch = (async (input: string | URL | Request) => {
      const url = String(input);
      if (url === '/api/auth/status') {
        statusFetches += 1;
        return jsonResponse(authenticatedStatus());
      }
      if (url === '/api/watchlist') {
        watchlistFetches += 1;
        return jsonResponse({ detail: { code: 'session_rejected', message: '请重试。' } }, status);
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as typeof fetch;

    let renderer!: ReactTestRenderer;
    await act(async () => {
      renderer = TestRenderer.create(<WatchlistBoard />);
    });
    await flushAsyncWork();
    await flushAsyncWork();
    await flushAsyncWork();

    assert.equal(statusFetches, 1);
    assert.equal(watchlistFetches, 1, `a ${status} invalidation must terminate instead of refetching watchlist`);
    assert.ok(renderer.root.findAllByProps({ role: 'alert' }).length >= 1);
    act(() => renderer.unmount());
  }
});

test('LoginPanel does not navigate when a login response completes after unmount', async () => {
  const pendingLogin = deferred<Response>();
  globalThis.fetch = (async (input: string | URL | Request) => {
    const url = String(input);
    if (url === '/api/auth/status') {
      return jsonResponse({
        authenticated: false,
        setup_required: false,
        registration_open: true,
      });
    }
    if (url === '/api/auth/login') return pendingLogin.promise;
    throw new Error(`Unexpected fetch: ${url}`);
  }) as typeof fetch;

  let renderer!: ReactTestRenderer;
  await act(async () => {
    renderer = TestRenderer.create(<LoginPanel />);
  });
  await flushAsyncWork();
  const form = renderer.root.findByType('form');
  act(() => { void form.props.onSubmit({ preventDefault() {} }); });
  act(() => renderer.unmount());

  pendingLogin.resolve(jsonResponse({
    user: authenticatedStatus().user,
    expires_at: authenticatedStatus().expires_at,
    session_generation: authenticatedStatus().session_generation,
  }));
  await flushAsyncWork();
  assert.deepEqual(browserWindow.location.assigned, []);
  assert.deepEqual(browserWindow.location.replaced, []);
});

test('AuthNav does not navigate when a logout response completes after unmount', async () => {
  const pendingLogout = deferred<Response>();
  globalThis.fetch = (async (input: string | URL | Request) => {
    const url = String(input);
    if (url === '/api/auth/status') return jsonResponse(authenticatedStatus());
    if (url === '/api/auth/logout') return pendingLogout.promise;
    throw new Error(`Unexpected fetch: ${url}`);
  }) as typeof fetch;

  let renderer!: ReactTestRenderer;
  await act(async () => {
    renderer = TestRenderer.create(<AuthNav />);
  });
  await flushAsyncWork();
  const logout = renderer.root.findAllByType('button').find((button) => button.props.children === '退出');
  assert.ok(logout);
  act(() => { void logout.props.onClick(); });
  act(() => renderer.unmount());

  pendingLogout.resolve(new Response(null, { status: 204 }));
  await flushAsyncWork();
  assert.deepEqual(browserWindow.location.assigned, []);
  assert.deepEqual(browserWindow.location.replaced, []);
});
