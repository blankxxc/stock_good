'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getSessionStatus,
  invalidateSessionStatus,
  readCsrfToken,
  responseError,
  subscribeSessionInvalidation,
  type SessionUser,
} from '../lib/auth';

export function AuthNav() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusError, setStatusError] = useState('');
  const [loggingOut, setLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState('');
  const requestSequence = useRef(0);
  const actionSequence = useRef(0);
  const actionInFlight = useRef(false);
  const mounted = useRef(false);

  const loadSession = useCallback(async (refresh = false) => {
    const sequence = ++requestSequence.current;
    setLoading(true);
    setStatusError('');
    try {
      const payload = await getSessionStatus({ refresh });
      if (requestSequence.current === sequence) setUser(payload.user ?? null);
    } catch (exc) {
      if (requestSequence.current === sequence) {
        setUser(null);
        setStatusError(exc instanceof Error ? exc.message : '暂时无法读取账户状态。');
      }
    } finally {
      if (requestSequence.current === sequence) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void loadSession();
    const unsubscribe = subscribeSessionInvalidation(() => { void loadSession(true); });
    return () => {
      mounted.current = false;
      unsubscribe();
      requestSequence.current += 1;
      actionSequence.current += 1;
    };
  }, [loadSession]);

  async function logout() {
    if (loggingOut || actionInFlight.current) return;
    const sequence = ++actionSequence.current;
    actionInFlight.current = true;
    setLoggingOut(true);
    setLogoutError('');
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
      if (mounted.current && actionSequence.current === sequence) setLogoutError(message);
    } catch {
      if (mounted.current && actionSequence.current === sequence) {
        setLogoutError('退出失败，请检查网络后重试。');
      }
    } finally {
      if (actionSequence.current === sequence) actionInFlight.current = false;
      if (mounted.current && actionSequence.current === sequence) setLoggingOut(false);
    }
  }

  if (loading) {
    return <span className="auth-nav-state" role="status" aria-live="polite">正在读取账户…</span>;
  }
  if (statusError) {
    return (
      <span className="auth-nav-feedback" role="alert">
        <span>账户状态读取失败</span>
        <button type="button" onClick={() => void loadSession(true)}>重试</button>
      </span>
    );
  }
  if (!user) return <a className="auth-nav-login" href="/login">登录 / 注册</a>;

  return (
    <span className="auth-nav-session">
      {user.role === 'admin' ? <a className="auth-nav-admin" href="/backend-admin">后台管理</a> : null}
      <a className="auth-nav-user" href="/watchlist" aria-label={`打开 ${user.display_name} 的自选股票`} title={`账号：${user.username}`}>{user.display_name}</a>
      <button type="button" onClick={logout} disabled={loggingOut} aria-busy={loggingOut}>
        {loggingOut ? '正在退出…' : '退出'}
      </button>
      {logoutError ? <span className="auth-nav-error" role="alert">{logoutError}</span> : null}
    </span>
  );
}
