'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
} from '../lib/auth';

import { useApiPayload } from '../lib/useApiPayload';

type MarketStock = {
  symbol: string;
  stock_name?: string;
  industry_name?: string;
  trade_date?: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  previous_close?: number;
  pct_change?: number;
  volume?: number;
  amount?: number;
  amount_billion?: number;
  turnover_rate?: number;
  tradable_flag?: boolean;
};

type MarketPayload = {
  status?: string;
  stock_count?: number;
  latest_trade_date?: string;
  breadth_summary?: {
    up_count?: number;
    down_count?: number;
    flat_count?: number;
    unknown_count?: number;
    priced_count?: number;
  };
  data_refresh_policy?: {
    frequency?: string;
    recommended_time_cn?: string;
    command?: string;
    description?: string;
  };
  stocks?: MarketStock[];
  api_note?: string;
};

type WatchlistPayload = {
  items?: Array<{ symbol: string }>;
  owner_user_id: number;
  session_generation: string;
};


export function MarketOverviewBoard() {
  const { payload, error } = useApiPayload<MarketPayload>('/api/market');
  const [query, setQuery] = useState('');
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [favorites, setFavorites] = useState<Set<string>>(new Set());
  const [favoritesLoading, setFavoritesLoading] = useState(true);
  const [pendingSymbol, setPendingSymbol] = useState('');
  const [watchlistError, setWatchlistError] = useState('');
  const favoritesRequestSequence = useRef(0);
  const favoritesOwnerId = useRef<number | null>(null);
  const favoritesSessionGeneration = useRef<string | null>(null);
  const favoritesCsrfToken = useRef<string | null>(null);

  const loadFavorites = useCallback(async (refreshSession = false) => {
    const sequence = ++favoritesRequestSequence.current;
    setAuthenticated(null);
    setFavoritesLoading(true);
    setFavorites(new Set());
    favoritesOwnerId.current = null;
    favoritesSessionGeneration.current = null;
    favoritesCsrfToken.current = null;
    setPendingSymbol('');
    setWatchlistError('');
    try {
      const session = await getSessionStatus({ refresh: refreshSession });
      if (favoritesRequestSequence.current !== sequence) return;
      if (!session.authenticated || !session.user) {
        setAuthenticated(false);
        return;
      }
      const context = sessionContext(session);
      if (!context) throw new Error('认证服务缺少会话上下文，请刷新后重试。');

      const response = await fetch('/api/watchlist', {
        cache: 'no-store',
        credentials: 'same-origin',
        headers: sessionContextHeaders(context),
      });
      if (favoritesRequestSequence.current !== sequence) return;
      if (readCsrfToken() !== context.csrfToken) {
        invalidateSessionStatus('session-context-changed');
        return;
      }
      if (response.status === 401 || response.status === 409) {
        const message = await responseError(response);
        if (favoritesRequestSequence.current !== sequence) return;
        setAuthenticated(response.status === 401 ? false : null);
        setFavorites(new Set());
        favoritesOwnerId.current = null;
        favoritesSessionGeneration.current = null;
        favoritesCsrfToken.current = null;
        setWatchlistError(message);
        invalidateSessionStatus(response.status === 401 ? 'authorization-failed' : 'session-context-changed');
        return;
      }
      if (!response.ok) {
        const message = await responseError(response);
        if (favoritesRequestSequence.current !== sequence) return;
        throw new Error(message);
      }
      const watchlist = await response.json() as WatchlistPayload;
      if (favoritesRequestSequence.current !== sequence) return;
      if (
        readCsrfToken() !== context.csrfToken
        || watchlist.owner_user_id !== context.userId
        || watchlist.session_generation !== context.sessionGeneration
      ) {
        invalidateSessionStatus('session-context-changed');
        return;
      }
      favoritesOwnerId.current = context.userId;
      favoritesSessionGeneration.current = context.sessionGeneration;
      favoritesCsrfToken.current = context.csrfToken;
      setAuthenticated(true);
      setFavorites(new Set((watchlist.items ?? []).map((item) => item.symbol)));
    } catch (exc) {
      if (favoritesRequestSequence.current === sequence) {
        setWatchlistError(exc instanceof Error ? exc.message : '读取自选状态失败。');
      }
    } finally {
      if (favoritesRequestSequence.current === sequence) setFavoritesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadFavorites();
    const unsubscribe = subscribeSessionInvalidation((message) => {
      if (shouldReloadPrivateSession(message)) {
        void loadFavorites(true);
        return;
      }
      favoritesRequestSequence.current += 1;
      favoritesOwnerId.current = null;
      favoritesSessionGeneration.current = null;
      favoritesCsrfToken.current = null;
      setFavorites(new Set());
      setPendingSymbol('');
      setAuthenticated(message.reason === 'authorization-failed' ? false : null);
      setWatchlistError(
        message.reason === 'authorization-failed'
          ? '自选访问被拒绝，请重新登录。'
          : '登录账号已变化，请重试读取当前账号的自选。',
      );
      setFavoritesLoading(false);
    });
    return () => {
      unsubscribe();
      favoritesRequestSequence.current += 1;
      favoritesOwnerId.current = null;
      favoritesSessionGeneration.current = null;
      favoritesCsrfToken.current = null;
    };
  }, [loadFavorites]);

  async function toggleFavorite(symbol: string) {
    if (authenticated === null || favoritesLoading || watchlistError) return;
    if (!authenticated) {
      window.location.assign('/login?next=/');
      return;
    }
    const ownerId = favoritesOwnerId.current;
    const sessionGeneration = favoritesSessionGeneration.current;
    const csrfToken = favoritesCsrfToken.current;
    if (pendingSymbol || ownerId === null || sessionGeneration === null || csrfToken === null) return;
    if (readCsrfToken() !== csrfToken) {
      invalidateSessionStatus('session-context-changed');
      return;
    }
    const sequence = favoritesRequestSequence.current;
    const context = { userId: ownerId, sessionGeneration, csrfToken };
    const selected = favorites.has(symbol);
    setPendingSymbol(symbol);
    setWatchlistError('');
    try {
      const response = await fetch(selected ? `/api/watchlist/${encodeURIComponent(symbol)}` : '/api/watchlist', {
        method: selected ? 'DELETE' : 'POST',
        credentials: 'same-origin',
        headers: {
          'X-CSRF-Token': csrfToken,
          ...sessionContextHeaders(context),
          ...(selected ? {} : { 'Content-Type': 'application/json' }),
        },
        ...(selected ? {} : { body: JSON.stringify({ symbol }) }),
      });
      if (readCsrfToken() !== csrfToken) {
        invalidateSessionStatus('session-context-changed');
        return;
      }
      if (
        favoritesRequestSequence.current !== sequence
        || favoritesOwnerId.current !== ownerId
        || favoritesSessionGeneration.current !== sessionGeneration
        || favoritesCsrfToken.current !== csrfToken
      ) return;
      if (!response.ok) {
        const message = await responseError(response);
        if (readCsrfToken() !== csrfToken) {
          invalidateSessionStatus('session-context-changed');
          return;
        }
        if (
          favoritesRequestSequence.current !== sequence
          || favoritesOwnerId.current !== ownerId
          || favoritesSessionGeneration.current !== sessionGeneration
          || favoritesCsrfToken.current !== csrfToken
        ) return;
        setWatchlistError(message);
        if (response.status === 401 || response.status === 409) {
          setAuthenticated(response.status === 401 ? false : null);
          setFavorites(new Set());
          favoritesOwnerId.current = null;
          favoritesSessionGeneration.current = null;
          favoritesCsrfToken.current = null;
          invalidateSessionStatus(response.status === 401 ? 'authorization-failed' : 'session-context-changed');
        }
        return;
      }
      setFavorites((current) => {
        const next = new Set(current);
        if (selected) next.delete(symbol); else next.add(symbol);
        return next;
      });
    } catch {
      if (readCsrfToken() !== csrfToken) {
        invalidateSessionStatus('session-context-changed');
      } else if (
        favoritesRequestSequence.current === sequence
        && favoritesOwnerId.current === ownerId
        && favoritesSessionGeneration.current === sessionGeneration
        && favoritesCsrfToken.current === csrfToken
      ) {
        setWatchlistError('自选操作失败，请稍后重试。');
      }
    } finally {
      if (
        favoritesRequestSequence.current === sequence
        && favoritesOwnerId.current === ownerId
        && favoritesSessionGeneration.current === sessionGeneration
        && favoritesCsrfToken.current === csrfToken
      ) {
        setPendingSymbol('');
      }
    }
  }

  const stocks = payload?.stocks ?? [];
  const filteredStocks = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return stocks;
    return stocks.filter((stock) => `${stock.symbol} ${stock.stock_name ?? ''} ${stock.industry_name ?? ''}`.toLowerCase().includes(keyword));
  }, [query, stocks]);

  const positiveCount = stocks.filter((stock) => typeof stock.pct_change === 'number' && stock.pct_change > 0).length;
  const negativeCount = stocks.filter((stock) => typeof stock.pct_change === 'number' && stock.pct_change < 0).length;
  const flatCount = stocks.filter((stock) => typeof stock.pct_change === 'number' && stock.pct_change === 0).length;
  const unknownCount = Math.max((payload?.stock_count ?? stocks.length) - positiveCount - negativeCount - flatCount, 0);
  const breadth = payload?.breadth_summary;
  const totalAmount = stocks.reduce((sum, stock) => sum + (stock.amount_billion ?? 0), 0);

  return (
    <section
      className="market-board artifact-backed"
      data-api-prefix="/api/market"
      aria-busy={favoritesLoading || Boolean(pendingSymbol)}
    >
      <div className="market-board__hero">
        <h1>沪深300股票全景</h1>
        <div className="market-board__search">
          <label htmlFor="stock-search">搜索股票</label>
          <input id="stock-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="例如 000001、平安银行、银行" />
        </div>
      </div>
      {error ? <p className="muted">暂时无法读取 /api/market：{error}。请确认后端服务运行。</p> : null}
      {watchlistError ? (
        <div className="auth-message auth-message--error auth-message--action" role="alert">
          <span>{watchlistError}</span>
          <button className="button table-button" type="button" onClick={() => void loadFavorites(true)} disabled={favoritesLoading}>重试自选状态</button>
        </div>
      ) : null}
      {favoritesLoading ? <p className="muted" role="status" aria-live="polite">正在读取当前账号的自选状态…</p> : null}
      <div className="market-ticker-row">
        <div><strong>{payload?.stock_count ?? (stocks.length || '—')}</strong><span>股票数量</span></div>
        <div><strong>{payload?.latest_trade_date ?? '加载中'}</strong><span>最新交易日</span></div>
        <div><strong className="positive">{breadth?.up_count ?? positiveCount}</strong><span>上涨家数</span></div>
        <div><strong className="negative">{breadth?.down_count ?? negativeCount}</strong><span>下跌家数</span></div>
        <div><strong>{breadth?.flat_count ?? flatCount}</strong><span>平盘/无变化</span></div>
        <div><strong>{breadth?.unknown_count ?? unknownCount}</strong><span>未定价/停牌</span></div>
        <div><strong>{formatAmount(totalAmount)}</strong><span>合计成交额</span></div>
      </div>
      <p id="market-scroll-hint" className="table-scroll-hint">表格内容较宽，可横向滚动查看全部列。</p>
      <div className="stock-table-shell" role="region" aria-label="沪深300股票行情表格，可横向滚动" aria-describedby="market-scroll-hint" tabIndex={0}>
        <table className="stock-table">
          <caption className="sr-only">沪深300股票行情及当前账号自选状态</caption>
          <thead>
            <tr>
              <th scope="col">股票代码</th>
              <th scope="col">股票名称</th>
              <th scope="col">最新价</th>
              <th scope="col">涨跌幅</th>
              <th scope="col">成交额</th>
              <th scope="col">换手率</th>
              <th scope="col">行业</th>
              <th scope="col">自选</th>
              <th scope="col">详情</th>
            </tr>
          </thead>
          <tbody>
            {filteredStocks.map((stock) => (
              <tr key={stock.symbol}>
                <td><a className="code-link" href={`/stocks/${stock.symbol}`}>{stock.symbol}</a></td>
                <td>{stock.stock_name ?? '—'}</td>
                <td>{formatNumber(stock.close)}</td>
                <td className={typeof stock.pct_change === 'number' ? (stock.pct_change >= 0 ? 'positive' : 'negative') : 'muted'}>{formatPercent(stock.pct_change)}</td>
                <td>{formatAmount(stock.amount_billion)}</td>
                <td>{formatPercent(typeof stock.turnover_rate === 'number' ? stock.turnover_rate / 100 : undefined)}</td>
                <td>{stock.industry_name ?? '—'}</td>
                <td>
                  <button
                    type="button"
                    className={`watchlist-toggle${favorites.has(stock.symbol) ? ' active' : ''}`}
                    onClick={() => toggleFavorite(stock.symbol)}
                    disabled={authenticated === null || favoritesLoading || Boolean(pendingSymbol) || Boolean(watchlistError)}
                    aria-pressed={favorites.has(stock.symbol)}
                    aria-busy={pendingSymbol === stock.symbol}
                    aria-label={favorites.has(stock.symbol) ? `从自选移除 ${stock.symbol}` : `将 ${stock.symbol} 加入自选`}
                  >
                    <span aria-hidden="true">{favorites.has(stock.symbol) ? '★' : '☆'}</span>
                    {authenticated === null || favoritesLoading ? '检查账户' : pendingSymbol === stock.symbol ? '处理中' : favorites.has(stock.symbol) ? '已自选' : '加入自选'}
                  </button>
                </td>
                <td><a className="button table-button" href={`/stocks/${stock.symbol}`}>查看详情</a></td>
              </tr>
            ))}
            {!filteredStocks.length ? <tr><td colSpan={9}>暂无匹配股票，等待 /api/market 返回股票列表。</td></tr> : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
