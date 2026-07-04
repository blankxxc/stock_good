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
  const [selectedCandidateHorizon, setSelectedCandidateHorizon] = useState('5d');
  const [selectedCandidateLimit, setSelectedCandidateLimit] = useState(20);

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
  const candidateSourceHorizon = horizons.includes(selectedCandidateHorizon) ? selectedCandidateHorizon : (horizons[0] ?? '5d');
  const candidateSourceRows = payload?.horizon_rankings?.[candidateSourceHorizon] ?? payload?.candidate_pool ?? [];
  const normalizedCandidateLimit = Math.min(Math.max(1, selectedCandidateLimit || 1), Math.max(candidateSourceRows.length, 1));
  const candidatePool = candidateSourceRows.slice(0, normalizedCandidateLimit);

  return (
    <div className="card artifact-backed prediction-selection">
      <div className="artifact-card__topline">
        <span className="badge">股票预测选股</span>
        <span className="status-pill">1d · 5d · 14d Top10</span>
      </div>
      <h3>未来1d / 未来5d / 未来14d 上涨概率排行</h3>
      <p>按上涨概率展示三个周期的 Top10，点击股票代码查看个股详情。</p>
      {error ? <p className="muted">暂时无法读取评分数据：{error}</p> : null}
      {payload?.latest_trade_date ? <p className="muted">最新数据截面：{payload.latest_trade_date}</p> : <p className="muted">加载评分数据中…</p>}
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
                  <tr><th>排名</th><th>股票代码</th><th>股票名称</th><th>上涨概率</th></tr>
                </thead>
                <tbody>
                  {rows.length ? rows.map((row) => (
                    <tr key={`${horizon}-${row.trade_date}-${row.symbol}`}>
                      <td>#{row.rank ?? '—'}</td>
                      <td><a className="code-link" href={`/stocks/${row.symbol}`}>{row.symbol}</a></td>
                      <td>{row.stock_name ?? '—'}</td>
                      <td className="positive">{formatProbability(row.probability_up)}</td>
                    </tr>
                  )) : <tr><td colSpan={4}>等待评分数据</td></tr>}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>

      <section className="card candidate-pool-panel" id="candidate-pool">
        <div className="artifact-card__topline">
          <div>
            <span className="badge">研究候选</span>
            <h3>研究候选池 Top{normalizedCandidateLimit}</h3>
          </div>
          <span className="status-pill">基于{horizonLabel(candidateSourceHorizon)}</span>
        </div>
        <div className="candidate-controls" aria-label="候选池筛选">
          <label>
            <span>选择周期</span>
            <select className="candidate-horizon-select" value={candidateSourceHorizon} onChange={(event) => setSelectedCandidateHorizon(event.target.value)}>
              {horizons.map((horizon) => <option key={horizon} value={horizon}>{horizonLabel(horizon)}</option>)}
            </select>
          </label>
          <label>
            <span>Top数量</span>
            <input
              className="candidate-limit-input"
              type="number"
              min={1}
              max={Math.max(candidateSourceRows.length, 1)}
              step={1}
              value={selectedCandidateLimit}
              onChange={(event) => setSelectedCandidateLimit(Math.max(1, Math.floor(Number(event.target.value) || 1)))}
            />
          </label>
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
            )) : <tr><td colSpan={7}>等待候选池数据</td></tr>}
          </tbody>
        </table>
        <p className="muted">候选池只是把 300 只沪深300缩小到一批研究对象；正式使用前仍需要回测风险、交易成本、行业暴露、人工复核。</p>
      </section>
    </div>
  );
}
