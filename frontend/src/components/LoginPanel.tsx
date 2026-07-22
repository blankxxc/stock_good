'use client';

import {
  type FormEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react';
import {
  getSessionStatus,
  invalidateSessionStatus,
  readCsrfToken,
  responseError,
  safeNextPath,
  subscribeSessionInvalidation,
  type SessionPayload,
  type SessionUser,
} from '../lib/auth';

type Mode = 'login' | 'register' | 'setup';
type StatusPayload = SessionPayload & {
  setup_required: boolean;
  registration_open: boolean;
};

type AuthResult = { user: SessionUser; expires_at: string };

const initialFields = {
  username: '',
  displayName: '',
  password: '',
  passwordConfirm: '',
  bootstrapToken: '',
};

export function LoginPanel() {
  const [mode, setMode] = useState<Mode>('login');
  const [fields, setFields] = useState(initialFields);
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const requestSequence = useRef(0);
  const actionSequence = useRef(0);
  const actionInFlight = useRef(false);
  const mounted = useRef(false);

  const loadStatus = useCallback(async (refresh = false) => {
    const sequence = ++requestSequence.current;
    setStatusLoading(true);
    setStatusError('');
    try {
      const payload = await getSessionStatus({ refresh });
      if (requestSequence.current !== sequence) return;
      setStatus({
        ...payload,
        setup_required: payload.setup_required === true,
        registration_open: payload.registration_open === true,
      });
    } catch (exc) {
      if (requestSequence.current === sequence) {
        setStatus(null);
        setStatusError(exc instanceof Error ? exc.message : '暂时无法连接认证服务。');
      }
    } finally {
      if (requestSequence.current === sequence) setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void loadStatus();
    const unsubscribe = subscribeSessionInvalidation(() => { void loadStatus(true); });
    return () => {
      mounted.current = false;
      unsubscribe();
      requestSequence.current += 1;
      actionSequence.current += 1;
    };
  }, [loadStatus]);

  function update(name: keyof typeof fields, value: string) {
    setFields((current) => ({ ...current, [name]: value }));
    if (error) setError('');
  }

  function selectMode(nextMode: Mode) {
    if (submitting || nextMode === mode) return;
    if (nextMode === 'register' && !status?.registration_open) return;
    if (nextMode === 'setup' && !status?.setup_required) return;
    setMode(nextMode);
    setError('');
    setFields((current) => ({
      ...current,
      password: '',
      passwordConfirm: '',
      bootstrapToken: '',
    }));
  }

  function handleTabKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const tablist = event.currentTarget.parentElement;
    const tabs = Array.from(tablist?.querySelectorAll<HTMLButtonElement>('[role="tab"]:not(:disabled)') ?? []);
    if (!tabs.length) return;
    const currentIndex = tabs.indexOf(event.currentTarget);
    let nextIndex = currentIndex;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = tabs.length - 1;
    if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    const nextTab = tabs[nextIndex];
    const nextMode = nextTab?.dataset.mode as Mode | undefined;
    if (!nextTab || !nextMode) return;
    event.preventDefault();
    selectMode(nextMode);
    nextTab.focus();
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || actionInFlight.current) return;
    if (mode !== 'login' && !fields.displayName.trim()) {
      setError('请输入用于页面显示的昵称。');
      return;
    }
    if (mode !== 'login' && fields.password !== fields.passwordConfirm) {
      setError('两次输入的密码不一致，请重新确认。');
      return;
    }

    const sequence = ++actionSequence.current;
    actionInFlight.current = true;
    setSubmitting(true);
    setError('');
    const endpoint = mode === 'login' ? '/api/auth/login' : mode === 'register' ? '/api/auth/register' : '/api/auth/setup-admin';
    const body = mode === 'login'
      ? { username: fields.username, password: fields.password }
      : {
          username: fields.username,
          display_name: fields.displayName.trim(),
          password: fields.password,
          password_confirm: fields.passwordConfirm,
          ...(mode === 'setup' ? { bootstrap_token: fields.bootstrapToken } : {}),
        };
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!mounted.current || actionSequence.current !== sequence) return;
      if (!response.ok) {
        const message = await responseError(response);
        if (mounted.current && actionSequence.current === sequence) setError(message);
        return;
      }
      const result = await response.json() as AuthResult;
      if (!mounted.current || actionSequence.current !== sequence) return;
      invalidateSessionStatus();
      const params = new URLSearchParams(window.location.search);
      const fallback = result.user.role === 'admin' ? '/backend-admin' : '/watchlist';
      window.location.assign(safeNextPath(params.get('next'), fallback, result.user.role === 'admin'));
    } catch {
      if (mounted.current && actionSequence.current === sequence) {
        setError('网络请求失败，请检查网络后重试。');
      }
    } finally {
      if (actionSequence.current === sequence) actionInFlight.current = false;
      if (mounted.current && actionSequence.current === sequence) setSubmitting(false);
    }
  }

  async function logout() {
    if (submitting || actionInFlight.current) return;
    const sequence = ++actionSequence.current;
    actionInFlight.current = true;
    setSubmitting(true);
    setError('');
    try {
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': readCsrfToken() },
      });
      if (!mounted.current || actionSequence.current !== sequence) return;
      if (response.ok || response.status === 401) {
        invalidateSessionStatus();
        window.location.replace('/login');
        return;
      }
      const message = await responseError(response);
      if (mounted.current && actionSequence.current === sequence) setError(message);
    } catch {
      if (mounted.current && actionSequence.current === sequence) {
        setError('退出失败，请检查网络后重试。');
      }
    } finally {
      if (actionSequence.current === sequence) actionInFlight.current = false;
      if (mounted.current && actionSequence.current === sequence) setSubmitting(false);
    }
  }

  if (statusLoading) {
    return (
      <section className="auth-card auth-status-card" aria-busy="true">
        <p className="muted" role="status" aria-live="polite">正在读取账户状态…</p>
      </section>
    );
  }

  if (!status) {
    return (
      <section className="auth-card auth-status-card">
        <h1>账户服务暂不可用</h1>
        <p className="auth-message auth-message--error" role="alert">{statusError || '暂时无法读取账户状态。'}</p>
        <button className="button" type="button" onClick={() => void loadStatus(true)}>重试连接</button>
      </section>
    );
  }

  if (status.authenticated && status.user) {
    const user = status.user;
    return (
      <section className="auth-card auth-signed-in" aria-busy={submitting}>
        <span className={`account-role account-role--${user.role}`}>{user.role === 'admin' ? '管理员' : '普通用户'}</span>
        <h1>已登录</h1>
        <p><strong>{user.display_name}</strong><span className="muted"> @{user.username}</span></p>
        <div className="auth-actions">
          <a className="button" href="/watchlist">进入我的自选</a>
          {user.role === 'admin' ? <a className="button secondary" href="/backend-admin">进入后台管理</a> : null}
          <button type="button" className="button ghost" onClick={logout} disabled={submitting} aria-busy={submitting}>
            {submitting ? '正在退出…' : '退出当前账号'}
          </button>
        </div>
        {error ? <p className="auth-message auth-message--error" role="alert">{error}</p> : null}
      </section>
    );
  }

  const confirmationError = error.startsWith('两次输入的密码不一致');

  return (
    <section className="auth-layout">
      <div className="auth-intro">
        <span className="badge">账户 · 私有自选</span>
        <h1>登录你的选股空间</h1>
        <p>每个账号拥有独立自选股票列表。行情研究页面保持公开，保存和管理自选时需要登录。</p>
        <ul className="auth-benefits">
          <li><strong>账号隔离</strong><span>自选数据只属于当前登录用户</span></li>
          <li><strong>安全会话</strong><span>密码安全哈希，会话可过期和撤销</span></li>
          <li><strong>后台分权</strong><span>普通用户无法访问管理员控制面</span></li>
        </ul>
      </div>

      <div className="auth-card">
        <div className="auth-tabs" role="tablist" aria-label="账户操作">
          <button
            id="auth-tab-login"
            data-mode="login"
            type="button"
            role="tab"
            aria-selected={mode === 'login'}
            aria-controls="auth-panel"
            tabIndex={mode === 'login' ? 0 : -1}
            className={mode === 'login' ? 'active' : ''}
            disabled={submitting}
            onClick={() => selectMode('login')}
            onKeyDown={handleTabKey}
          >登录</button>
          <button
            id="auth-tab-register"
            data-mode="register"
            type="button"
            role="tab"
            aria-selected={mode === 'register'}
            aria-controls="auth-panel"
            aria-disabled={!status.registration_open}
            tabIndex={mode === 'register' ? 0 : -1}
            className={mode === 'register' ? 'active' : ''}
            disabled={submitting || !status.registration_open}
            title={status.registration_open ? undefined : '当前暂未开放新用户注册'}
            onClick={() => selectMode('register')}
            onKeyDown={handleTabKey}
          >注册</button>
          {status.setup_required ? (
            <button
              id="auth-tab-setup"
              data-mode="setup"
              type="button"
              role="tab"
              aria-selected={mode === 'setup'}
              aria-controls="auth-panel"
              tabIndex={mode === 'setup' ? 0 : -1}
              className={mode === 'setup' ? 'active' : ''}
              disabled={submitting}
              onClick={() => selectMode('setup')}
              onKeyDown={handleTabKey}
            >管理员初始化</button>
          ) : null}
        </div>
        {!status.registration_open ? <p className="auth-registration-note">当前暂未开放新用户注册，可使用已有账号登录。</p> : null}

        <div id="auth-panel" role="tabpanel" aria-labelledby={`auth-tab-${mode}`}>
          <div className="auth-card__heading">
            <span>{mode === 'login' ? '欢迎回来' : mode === 'register' ? '创建普通用户账号' : '首次创建管理员'}</span>
            <h2>{mode === 'login' ? '账号登录' : mode === 'register' ? '注册账号' : '管理员初始化'}</h2>
            <p>{mode === 'login' ? '普通用户与管理员使用同一安全入口。' : mode === 'register' ? '公开注册只能创建普通用户，不能提升为管理员。' : '请输入部署人员提供的一次性初始化令牌；初始化完成后入口会自动关闭。'}</p>
          </div>

          <form className="auth-form" onSubmit={submit} aria-busy={submitting}>
            {mode === 'setup' ? (
              <label htmlFor="bootstrap-token">
                <span>一次性初始化令牌</span>
                <input id="bootstrap-token" name="bootstrapToken" type="password" autoComplete="off" value={fields.bootstrapToken} onChange={(event) => update('bootstrapToken', event.target.value)} required minLength={20} maxLength={256} />
              </label>
            ) : null}
            <label htmlFor="auth-username">
              <span>用户名</span>
              <input id="auth-username" name="username" type="text" autoComplete="username" autoCapitalize="none" spellCheck={false} value={fields.username} onChange={(event) => update('username', event.target.value)} required minLength={3} maxLength={32} pattern="[A-Za-z0-9._-]+" placeholder="3–32 位字母、数字或 . _ -" />
            </label>
            {mode !== 'login' ? (
              <label htmlFor="auth-display-name">
                <span>昵称</span>
                <input id="auth-display-name" name="displayName" type="text" autoComplete="name" value={fields.displayName} onChange={(event) => update('displayName', event.target.value)} required maxLength={40} placeholder="页面显示名称" />
              </label>
            ) : null}
            <label htmlFor="auth-password">
              <span>密码</span>
              <input id="auth-password" name="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} value={fields.password} onChange={(event) => update('password', event.target.value)} required minLength={mode === 'login' ? 1 : 12} maxLength={128} />
            </label>
            {mode !== 'login' ? (
              <label htmlFor="auth-password-confirm">
                <span>确认密码</span>
                <input
                  id="auth-password-confirm"
                  name="passwordConfirm"
                  type="password"
                  autoComplete="new-password"
                  value={fields.passwordConfirm}
                  onChange={(event) => update('passwordConfirm', event.target.value)}
                  required
                  minLength={12}
                  maxLength={128}
                  aria-invalid={confirmationError || undefined}
                  aria-describedby={confirmationError ? 'password-guidance auth-form-error' : 'password-guidance'}
                />
                <small id="password-guidance">至少 12 位，建议同时包含大小写字母、数字和符号。</small>
              </label>
            ) : null}
            {error ? <p id="auth-form-error" className="auth-message auth-message--error" role="alert">{error}</p> : null}
            <button className="auth-submit" type="submit" disabled={submitting} aria-busy={submitting}>
              {submitting ? '处理中…' : mode === 'login' ? '登录' : mode === 'register' ? '创建账号并登录' : '创建管理员并进入后台'}
            </button>
          </form>
        </div>
      </div>
    </section>
  );
}
