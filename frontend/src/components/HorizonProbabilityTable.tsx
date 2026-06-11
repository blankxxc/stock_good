'use client';

import { useEffect, useState } from 'react';

type ScoreRow = {
  trade_date: string;
  symbol: string;
  stock_name?: string;
  industry_name?: string;
  score?: number;
  probability_up?: number;
  probability_down?: number;
  rank?: number;
  percentile?: number;
  horizon?: string;
  model_version?: string;
  candidate_reason?: string;
  review_action?: string;
};

type CandidateSummary = {
  source_horizon?: string;
  candidate_count?: number;
  pool_definition?: string;
  next_checks?: string[];
};

export type ScoresPayload = {
  status?: string;
  latest_trade_date?: string;
  latest_trade_date_by_horizon?: Record<string, string>;
  available_horizons?: string[];
  horizon_rankings?: Record<string, ScoreRow[]>;
  candidate_pool?: ScoreRow[];
  candidate_summary?: CandidateSummary;
  api_note?: string;
};

const fallbackHorizons = ['1d', '5d', '14d'];

function formatProbability(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

function formatScore(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return value.toFixed(3);
}

function horizonLabel(horizon: string) {
  if (horizon === '1d') return '未来1d';
  if (horizon === '5d') return '未来5d';
  if (horizon === '14d') return '未来14d';
  return horizon;
}

export function HorizonProbabilityTable({ initialPayload = null }: { initialPayload?: ScoresPayload | null }) {
  const [payload, setPayload] = useState<ScoresPayload | null>(initialPayload);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/scores', { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<ScoresPayload>;
      })
      .then((data) => {
        if (!cancelled) setPayload(data);
      })
      .catch((exc: Error) => {
        if (!cancelled) setError(exc.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const horizons = payload?.available_horizons?.filter((h) => fallbackHorizons.includes(h)) ?? fallbackHorizons;
  const candidatePool = payload?.candidate_pool?.slice(0, 20) ?? [];

  return (
    <div className="card artifact-backed prediction-selection" data-api-fields="available_horizons horizon_rankings probability_up probability_down candidate_pool candidate_summary">
      <div className="artifact-card__topline">
        <span className="badge">股票预测选股 · multi-horizon probability</span>
        <span className="status-pill">1d · 5d · 14d Top10 + 候选池</span>
      </div>
      <h3>未来1d / 未来5d / 未来14d 最可能上涨的10个股票</h3>
      <p>
        直接读取 /api/scores 的 available_horizons、horizon_rankings 和 candidate_pool；候选池功能已合并到本页，作为“研究候选”，不是买入名单。
      </p>
      {error ? <p className="muted">暂时无法读取后端 API：{error}。请确认 FastAPI 后端运行在 127.0.0.1:8000。</p> : null}
      {payload?.latest_trade_date ? <p className="muted">最新数据截面：{payload.latest_trade_date}</p> : <p className="muted">加载 /api/scores 中…</p>}
      <div className="prediction-horizon-grid">
        {horizons.map((horizon) => {
          const rows = payload?.horizon_rankings?.[horizon]?.slice(0, 10) ?? [];
          return (
            <div className="card horizon-card" key={horizon}>
              <div className="artifact-card__topline">
                <strong>{horizonLabel(horizon)}</strong>
                <span className="muted">截面：{payload?.latest_trade_date_by_horizon?.[horizon] ?? '加载中'}</span>
              </div>
              <table className="mini-score-table">
                <thead>
                  <tr><th>排名</th><th>股票代码</th><th>股票名称</th><th>上涨概率</th><th>下跌概率</th><th>score</th></tr>
                </thead>
                <tbody>
                  {rows.length ? rows.map((row) => (
                    <tr key={`${horizon}-${row.trade_date}-${row.symbol}`}>
                      <td>#{row.rank ?? '—'}</td>
                      <td><a className="code-link" href={`/stocks/${row.symbol}`}>{row.symbol}</a></td>
                      <td>{row.stock_name ?? '—'}</td>
                      <td className="positive">{formatProbability(row.probability_up)}</td>
                      <td>{formatProbability(row.probability_down)}</td>
                      <td>{formatScore(row.score)}</td>
                    </tr>
                  )) : <tr><td colSpan={6}>等待后端返回 horizon_rankings[{horizon}]</td></tr>}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>

      <section className="card candidate-pool-panel" id="candidate-pool">
        <div className="artifact-card__topline">
          <div>
            <span className="badge">候选池已合并到股票预测选股</span>
            <h3>研究候选池 Top20</h3>
          </div>
          <span className="status-pill">source: {payload?.candidate_summary?.source_horizon ?? '5d'}</span>
        </div>
        <p>{payload?.candidate_summary?.pool_definition ?? '默认取 5d 模型排名靠前股票，作为后续个股详情、条件测试、回测风险的研究对象。'}</p>
        <div className="candidate-workflow">
          {(payload?.candidate_summary?.next_checks ?? ['个股详情', '条件测试', '回测风险']).map((item) => <span key={item}>{item}</span>)}
        </div>
        <table className="mini-score-table">
          <thead>
            <tr><th>候选排名</th><th>股票代码</th><th>名称</th><th>行业</th><th>上涨概率</th><th>score</th><th>下一步</th></tr>
          </thead>
          <tbody>
            {candidatePool.length ? candidatePool.map((row) => (
              <tr key={`candidate-${row.trade_date}-${row.symbol}`}>
                <td>#{row.rank ?? '—'}</td>
                <td><a className="code-link" href={`/stocks/${row.symbol}`}>{row.symbol}</a></td>
                <td>{row.stock_name ?? '—'}</td>
                <td>{row.industry_name ?? '—'}</td>
                <td className="positive">{formatProbability(row.probability_up)}</td>
                <td>{formatScore(row.score)}</td>
                <td><a className="button table-button" href="/backtests">看回测风险</a></td>
              </tr>
            )) : <tr><td colSpan={7}>等待后端返回 candidate_pool</td></tr>}
          </tbody>
        </table>
        <p className="muted">候选池只是把 300 只沪深300缩小到一批研究对象；正式使用前仍需要回测风险、交易成本、行业暴露、人工复核。</p>
      </section>
    </div>
  );
}
