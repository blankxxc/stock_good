export type SessionUser = {
  id: number;
  username: string;
  display_name: string;
  role: 'user' | 'admin';
};

export type SessionPayload = {
  authenticated: boolean;
  user?: SessionUser;
  expires_at?: string;
  session_generation?: string;
  setup_required?: boolean;
  registration_open?: boolean;
};

export type SessionContext = {
  userId: number;
  sessionGeneration: string;
  csrfToken: string;
};

export type SessionInvalidationReason =
  | 'authentication-changed'
  | 'authorization-failed'
  | 'session-context-changed';

export type SessionInvalidationMessage = {
  type: typeof SESSION_INVALIDATED_EVENT;
  eventId: string;
  sourceTabId: string;
  reason: SessionInvalidationReason;
};

let sessionStatusRequest: Promise<SessionPayload> | null = null;
const SESSION_INVALIDATED_EVENT = 'stock-good:session-invalidated';
const SESSION_BROADCAST_CHANNEL = 'stock-good:session';
const sourceTabId = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
const seenSessionEvents = new Set<string>();
let sessionEventSequence = 0;
let sessionBroadcastChannel: BroadcastChannel | null = null;

function rememberSessionEvent(eventId: string): boolean {
  if (seenSessionEvents.has(eventId)) return false;
  seenSessionEvents.add(eventId);
  if (seenSessionEvents.size > 100) {
    const oldest = seenSessionEvents.values().next().value as string | undefined;
    if (oldest) seenSessionEvents.delete(oldest);
  }
  return true;
}

function isSessionMessage(value: unknown): value is SessionInvalidationMessage {
  if (!value || typeof value !== 'object') return false;
  const message = value as Partial<SessionInvalidationMessage>;
  return message.type === SESSION_INVALIDATED_EVENT
    && typeof message.eventId === 'string'
    && typeof message.sourceTabId === 'string'
    && (
      message.reason === 'authentication-changed'
      || message.reason === 'authorization-failed'
      || message.reason === 'session-context-changed'
    );
}

function dispatchLocalSessionEvent(message: SessionInvalidationMessage): void {
  sessionStatusRequest = null;
  window.dispatchEvent(new CustomEvent<SessionInvalidationMessage>(SESSION_INVALIDATED_EVENT, {
    detail: message,
  }));
}

function getSessionBroadcastChannel(): BroadcastChannel | null {
  if (typeof window === 'undefined' || typeof BroadcastChannel === 'undefined') return null;
  try {
    if (!sessionBroadcastChannel) {
      sessionBroadcastChannel = new BroadcastChannel(SESSION_BROADCAST_CHANNEL);
      sessionBroadcastChannel.addEventListener('message', (event: MessageEvent<unknown>) => {
        if (!isSessionMessage(event.data) || event.data.sourceTabId === sourceTabId) return;
        if (!rememberSessionEvent(event.data.eventId)) return;
        dispatchLocalSessionEvent(event.data);
      });
    }
  } catch {
    sessionBroadcastChannel = null;
  }
  return sessionBroadcastChannel;
}

export function readCsrfToken(): string {
  if (typeof document === 'undefined') return '';
  const item = document.cookie
    .split(';')
    .map((value) => value.trim())
    .find((value) => value.startsWith('oa_csrf='));
  if (!item) return '';
  try {
    return decodeURIComponent(item.slice('oa_csrf='.length));
  } catch {
    return '';
  }
}

export async function responseError(response: Response): Promise<string> {
  try {
    const payload = await response.json() as { detail?: string | { message?: string }; message?: string };
    if (typeof payload.detail === 'string') return payload.detail;
    if (payload.detail && typeof payload.detail === 'object' && payload.detail.message) return payload.detail.message;
    if (payload.message) return payload.message;
  } catch {
    // Fall back to a status-based message without exposing response internals.
  }
  if (response.status === 401) return '登录状态已失效，请重新登录。';
  if (response.status === 403) return '当前账号没有执行此操作的权限。';
  if (response.status === 409) return '登录账号已变化，请刷新账户状态后重试。';
  return '请求未完成，请稍后重试。';
}

export function sessionContext(payload: SessionPayload): SessionContext | null {
  const csrfToken = readCsrfToken();
  if (
    !payload.authenticated
    || !payload.user
    || !Number.isInteger(payload.user.id)
    || payload.user.id <= 0
    || typeof payload.session_generation !== 'string'
    || !payload.session_generation
    || !csrfToken
  ) {
    return null;
  }
  return {
    userId: payload.user.id,
    sessionGeneration: payload.session_generation,
    csrfToken,
  };
}

export function sessionContextHeaders(context: SessionContext): Record<string, string> {
  return {
    'X-Expected-User-Id': String(context.userId),
    'X-Expected-Session-Generation': context.sessionGeneration,
  };
}

export function shouldReloadPrivateSession(message: SessionInvalidationMessage): boolean {
  return message.reason === 'authentication-changed';
}

export function getSessionStatus(_options: { refresh?: boolean } = {}): Promise<SessionPayload> {
  if (sessionStatusRequest) return sessionStatusRequest;

  const request = fetch('/api/auth/status', {
    cache: 'no-store',
    credentials: 'same-origin',
  }).then(async (response) => {
    if (!response.ok) throw new Error(await responseError(response));
    const payload = await response.json() as SessionPayload;
    if (typeof payload.authenticated !== 'boolean') {
      throw new Error('认证服务返回的数据格式无效。');
    }
    return payload;
  });

  sessionStatusRequest = request;
  const releaseRequest = () => {
    if (sessionStatusRequest === request) sessionStatusRequest = null;
  };
  void request.then(releaseRequest, releaseRequest);
  return request;
}

export function invalidateSessionStatus(
  reason: SessionInvalidationReason = 'authentication-changed',
): void {
  sessionStatusRequest = null;
  if (typeof window === 'undefined') return;
  const message: SessionInvalidationMessage = {
    type: SESSION_INVALIDATED_EVENT,
    eventId: `${sourceTabId}:${Date.now()}:${++sessionEventSequence}`,
    sourceTabId,
    reason,
  };
  rememberSessionEvent(message.eventId);
  dispatchLocalSessionEvent(message);
  try {
    getSessionBroadcastChannel()?.postMessage(message);
  } catch {
    sessionBroadcastChannel?.close();
    sessionBroadcastChannel = null;
  }
}

export function subscribeSessionInvalidation(
  listener: (message: SessionInvalidationMessage) => void,
): () => void {
  if (typeof window === 'undefined') return () => undefined;
  getSessionBroadcastChannel();
  const receiveLocalInvalidation = (event: Event) => {
    const message = (event as CustomEvent<SessionInvalidationMessage>).detail;
    if (isSessionMessage(message)) listener(message);
  };
  window.addEventListener(SESSION_INVALIDATED_EVENT, receiveLocalInvalidation);
  return () => window.removeEventListener(SESSION_INVALIDATED_EVENT, receiveLocalInvalidation);
}

export function safeNextPath(raw: string | null, fallback: string, allowBackendAdmin = false): string {
  if (!raw || !raw.startsWith('/') || raw.startsWith('//')) return fallback;
  const allowed = raw === '/'
    || raw === '/watchlist'
    || (allowBackendAdmin && raw === '/backend-admin')
    || /^\/stocks\/[0-9A-Za-z._-]+$/.test(raw);
  return allowed ? raw : fallback;
}
