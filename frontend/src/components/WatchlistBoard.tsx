'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { formatAmount, formatNumber, formatPercent } from '../lib/formatters';
import {
  getSessionStatus,
  invalidateSessionStatus,
  readCsrfToken,
  responseError,
  sessionContext,
  sessionContextHeaders,
  shouldReloadPrivateSession,
  subscribeSessionInvalidation,
  type SessionContext,
  type SessionUser,
} from '../lib/auth';

type WatchlistStock = {
  symbol: string;
  stock_name?: string;
  industry_name?: string;
  close?: number;
  pct_change?: number;
  amount_billion?: number;
  turnover_rate?: number;
  trade_date?: string;
};

type WatchlistItem = {
  symbol: string;
  created_at: string;
  stock?: WatchlistStock | null;
};

type WatchlistPayload = {
  items: WatchlistItem[];
  count: number;
  owner_user_id: number;
  session_generation: string;
};

function formatSavedDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString('zh-CN');
}

export function WatchlistBoard() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [needsLogin, setNeedsLogin] = useState(false);
  const [pendingSymbol, setPendingSymbol] = useState('');
  const requestSequence = useRef(0);
  const activeSessionContext = useRef<SessionContext | null>(null);

  const loadWatchlist = useCallback(async (refreshSession = false) => {
    const sequence = ++requestSequence.current;
    let redirecting = false;
    setLoading(true);
    setError('');
    setNeedsLogin(false);
    setUser(null);
    setItems([]);
    activeSessionContext.current = null;
    setPendingSymbol('');
    try {
      const session = await getSessionStatus({ refresh: refreshSession });
      if (requestSequence.current !== sequence) return;
      if (!session.authenticated || !session.user) {
        redirecting = true;
        window.location.replace('/login?next=/watchlist');
        return;
      }
      const context = sessionContext(session);
      if (!context) throw new Error('认证服务缺少会话上下文，请刷新后重试。');

      const response = await fetch('/api/watchlist', {
        cache: 'no-store',
        credentials: 'same-origin',
        headers: sessionContextHeaders(context),
      });
      if (requestSequence.current !== sequence) return;
      if (response.status === 401 || response.status === 409) {
        const message = await responseError(response);
        if (requestSequence.current !== sequence) return;
        setUser(null);
        setItems([]);
        activeSessionContext.current = null;
        setNeedsLogin(response.status === 401);
        setError(message);
        invalidateSessionStatus(response.status === 401 ? 'authorization-failed' : 'session-context-changed');
        return;
      }
      if (!response.ok) {
        const message = await responseError(response);
        if (requestSequence.current !== sequence) return;
        throw new Error(message);
      }
      const watchlist = await response.json() as WatchlistPayload;
      if (requestSequence.current !== sequence) return;
      if (
        readCsrfToken() !== context.csrfToken
        || watchlist.owner_user_id !== context.userId
        || watchlist.session_generation !== context.sessionGeneration
      ) {
        invalidateSessionStatus('session-context-changed');
        return;
      }
      activeSessionContext.current = context;
      setUser(session.user);
      setItems(Array.isArray(watchlist.items) ? watchlist.items : []);
    } catch (exc) {
      if (requestSequence.current === sequence) {
        setError(exc instanceof Error ? exc.message : '读取自选列表失败。');
      }
    } finally {
      if (requestSequence.current === sequence && !redirecting) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWatchlist();
    const unsubscribe = subscribeSessionInvalidation((message) => {
      if (shouldReloadPrivateSession(message)) {
        void loadWatchlist(true);
        return;
      }
      requestSequence.current += 1;
      activeSessionContext.current = null;
      setUser(null);
      setItems([]);
      setPendingSymbol('');
      setNeedsLogin(message.reason === 'authorization-failed');
      setError(
        message.reason === 'authorization-failed'
          ? '自选访问被拒绝，请重新登录。'
          : '登录账号已变化，请重试读取当前账号的自选。',
      );
      setLoading(false);
    });
    return () => {
      unsubscribe();
      requestSequence.current += 1;
      activeSessionContext.current = null;
    };
  }, [loadWatchlist]);

  async function remove(symbol: string) {
    const context = activeSessionContext.current;
    if (pendingSymbol || needsLogin || !context) return;
    if (readCsrfToken() !== context.csrfToken) {
      invalidateSessionStatus('session-context-changed');
      return;
    }
    const sequence = requestSequence.current;
    const item = items.find((candidate) => candidate.symbol === symbol);
    const stockLabel = item?.stock?.stock_name ? `${item.stock.stock_name}（${symbol}）` : symbol;
    if (!window.confirm(`确定将 ${stockLabel} 移出当前账号的自选列表吗？`)) return;

    setPendingSymbol(symbol);
    setError('');
    try {
      const response = await fetch(`/api/watchlist/${encodeURIComponent(symbol)}`, {
        method: 'DELETE',
        credentials: 'same-origin',
        headers: {
          'X-CSRF-Token': context.csrfToken,
          ...sessionContextHeaders(context),
        },
      });
      if (readCsrfToken() !== context.csrfToken) {
        invalidateSessionStatus('session-context-changed');
        return;
      }
      if (requestSequence.current !== sequence || activeSessionContext.current !== context) return;
      if (response.status === 401 || response.status === 409) {
        const message = await responseError(response);
        if (requestSequence.current !== sequence || activeSessionContext.current !== context) return;
        setUser(null);
        setItems([]);
        activeSessionContext.current = null;
        setNeedsLogin(response.status === 401);
        setError(message);
        invalidateSessionStatus(response.status === 401 ? 'authorization-failed' : 'session-context-changed');
        return;
      }
      if (response.status === 404) {
        setItems((current) => current.filter((candidate) => candidate.symbol !== symbol));
        return;
      }
      if (!response.ok) {
        const message = await responseError(response);
        if (requestSequence.current !== sequence || activeSessionContext.current !== context) return;
        setError(message);
        return;
      }
      setItems((current) => current.filter((candidate) => candidate.symbol !== symbol));
    } catch {
      if (readCsrfToken() !== context.csrfToken) {
        invalidateSessionStatus('session-context-changed');
      } else if (requestSequence.current === sequence && activeSessionContext.current === context) {
        setError('移出自选失败，请检查网络后重试。');
      }
    } finally {
      if (requestSequence.current === sequence && activeSessionContext.current === context) {
        setPendingSymbol('');
      }
    }
  }

  const countUnavailable = loading || (Boolean(error) && items.length === 0);

  return (
    <section className="watchlist-board artifact-backed" aria-busy={loading || Boolean(pendingSymbol)}>
      <div className="watchlist-hero">
        <div>
          <span className="badge">私有自选</span>
          <h1>我的自选股票</h1>
          <p>{user ? `${user.display_name} 的独立选股列表` : '正在验证账号…'}，其他用户无法读取或修改。</p>
        </div>
        <div className="watchlist-summary">
          <strong aria-label={countUnavailable ? '自选数量暂不可用' : `已关注 ${items.length} 只股票`}>{countUnavailable ? '—' : items.length}</strong>
          <span>已关注股票</span>
          <a className="button" href="/">去股票全景添加</a>
        </div>
      </div>

      {error ? (
        <div className="auth-message auth-message--error auth-message--action" role="alert">
          <span>{error}</span>
          {needsLogin
            ? <a className="button table-button" href="/login?next=/watchlist">重新登录</a>
            : <button className="button table-button" type="button" onClick={() => void loadWatchlist(true)} disabled={loading}>重试读取</button>}
        </div>
      ) : null}
      {loading ? <p className="muted" role="status" aria-live="polite">正在读取当前账号的自选股票…</p> : null}
      {!loading && !error && !items.length ? (
        <div className="watchlist-empty">
          <span aria-hidden="true">☆</span>
          <h2>还没有自选股票</h2>
          <p>可以从市场全景直接收藏，也可以先查看模型候选或使用条件筛选缩小范围。</p>
          <div className="watchlist-empty__actions">
            <a className="button primary" href="/scores">查看预测候选</a>
            <a className="button" href="/condition-screen">使用条件选股</a>
            <a className="button button--secondary" href="/">浏览股票全景</a>
          </div>
        </div>
      ) : null}
      {!loading && user && items.length ? (
        <>
          <p id="watchlist-scroll-hint" className="table-scroll-hint">表格内容较宽，可横向滚动查看全部列。</p>
          <div
            className="stock-table-shell"
            role="region"
            aria-label="自选股票表格，可横向滚动"
            aria-describedby="watchlist-scroll-hint"
            aria-busy={Boolean(pendingSymbol)}
            tabIndex={0}
          >
            <table className="stock-table watchlist-table">
              <caption className="sr-only">当前账号的自选股票及行情</caption>
              <thead>
                <tr>
                  <th scope="col">股票代码</th>
                  <th scope="col">股票名称</th>
                  <th scope="col">最新价</th>
                  <th scope="col">涨跌幅</th>
                  <th scope="col">成交额</th>
                  <th scope="col">行业</th>
                  <th scope="col">加入时间</th>
                  <th scope="col">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const stock = item.stock;
                  const busy = pendingSymbol === item.symbol;
                  return (
                    <tr key={item.symbol}>
                      <td><a className="code-link" href={`/stocks/${item.symbol}?from=watchlist`}>{item.symbol}</a></td>
                      <td>{stock?.stock_name ?? '—'}</td>
                      <td>{formatNumber(stock?.close)}</td>
                      <td className={typeof stock?.pct_change === 'number' ? (stock.pct_change >= 0 ? 'positive' : 'negative') : 'muted'}>{formatPercent(stock?.pct_change)}</td>
                      <td>{formatAmount(stock?.amount_billion)}</td>
                      <td>{stock?.industry_name ?? '—'}</td>
                      <td>{formatSavedDate(item.created_at)}</td>
                      <td>
                        <div className="watchlist-actions">
                          <a className="button table-button" href={`/stocks/${item.symbol}?from=watchlist`}>详情</a>
                          <button
                            type="button"
                            className="button table-button danger"
                            onClick={() => void remove(item.symbol)}
                            disabled={Boolean(pendingSymbol) || needsLogin}
                            aria-busy={busy}
                            aria-label={`将 ${stock?.stock_name ?? item.symbol} 移出自选`}
                          >
                            {busy ? '正在移出…' : '移出自选'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
}
