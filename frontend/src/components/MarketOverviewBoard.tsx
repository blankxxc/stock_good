'use client';

import { useMemo, useState } from 'react';
import { formatAmount, formatNumber, formatPercent } from '../lib/formatters';
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


export function MarketOverviewBoard() {
  const { payload, error } = useApiPayload<MarketPayload>('/api/market');
  const [query, setQuery] = useState('');

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
    <section className="market-board artifact-backed" data-api-prefix="/api/market">
      <div className="market-board__hero">
        <div>
          <span className="badge">类似同花顺的沪深300股票全景</span>
          <h1>沪深300股票全景</h1>
          <p className="lead">首页直接展示所有股票，支持按股票代码、股票名称、行业搜索，并点击进入证券软件式个股面板。</p>
        </div>
        <div className="market-board__search">
          <label htmlFor="stock-search">搜索股票</label>
          <input id="stock-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="例如 000001、平安银行、银行" />
        </div>
      </div>
      {error ? <p className="muted">暂时无法读取 /api/market：{error}。请确认后端服务运行。</p> : null}
      <div className="market-ticker-row">
        <div><strong>{payload?.stock_count ?? (stocks.length || '—')}</strong><span>股票数量</span></div>
        <div><strong>{payload?.latest_trade_date ?? '加载中'}</strong><span>最新交易日</span></div>
        <div><strong className="positive">{breadth?.up_count ?? positiveCount}</strong><span>上涨家数</span></div>
        <div><strong className="negative">{breadth?.down_count ?? negativeCount}</strong><span>下跌家数</span></div>
        <div><strong>{breadth?.flat_count ?? flatCount}</strong><span>平盘/无变化</span></div>
        <div><strong>{breadth?.unknown_count ?? unknownCount}</strong><span>未定价/停牌</span></div>
        <div><strong>{formatAmount(totalAmount)}</strong><span>合计成交额</span></div>
      </div>
      <p className="muted daily-update-note">
        数据需要每日更新：{payload?.data_refresh_policy?.frequency ?? 'daily_after_market_close'}，建议 {payload?.data_refresh_policy?.recommended_time_cn ?? '交易日16:30后'} 执行 {payload?.data_refresh_policy?.command ?? 'scripts/update_daily_market_data.py'}。
      </p>
      <div className="stock-table-shell">
        <table className="stock-table">
          <thead>
            <tr>
              <th>股票代码</th>
              <th>股票名称</th>
              <th>最新价</th>
              <th>涨跌幅</th>
              <th>成交额</th>
              <th>换手率</th>
              <th>行业</th>
              <th>详情</th>
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
                <td><a className="button table-button" href={`/stocks/${stock.symbol}`}>查看详情</a></td>
              </tr>
            ))}
            {!filteredStocks.length ? <tr><td colSpan={8}>暂无匹配股票，等待 /api/market 返回股票列表。</td></tr> : null}
          </tbody>
        </table>
      </div>
      <p className="muted">{payload?.api_note ?? 'research_signals_only_not_investment_advice：仅研究展示，不构成交易建议。'}</p>
    </section>
  );
}
