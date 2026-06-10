'use client';

import { useEffect, useState } from 'react';

type ScoreRow = {
  trade_date: string;
  symbol: string;
  industry_name?: string;
  score?: number;
  probability_up?: number;
  probability_down?: number;
  rank?: number;
  horizon?: string;
  model_version?: string;
};

type ScoresPayload = {
  status?: string;
  latest_trade_date?: string;
  latest_trade_date_by_horizon?: Record<string, string>;
  available_horizons?: string[];
  horizon_rankings?: Record<string, ScoreRow[]>;
  api_note?: string;
};

const fallbackHorizons = ['1d', '5d', '14d'];

function formatProbability(value: number | undefined) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

export function HorizonProbabilityTable() {
  const [payload, setPayload] = useState<ScoresPayload | null>(null);
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

  return (
    <div className="card artifact-backed" data-api-fields="available_horizons horizon_rankings probability_up probability_down">
      <div className="artifact-card__topline">
        <span className="badge">multi-horizon probability</span>
        <span className="status-pill">1d · 5d · 14d</span>
      </div>
      <h3>未来1d / 保留5d / 未来14d 上涨概率排序</h3>
      <p>
        这里直接读取 /api/scores 的 available_horizons 与 horizon_rankings；probability_up 是模型给出的研究概率，
        用于比较横截面排序，不构成任何交易指令。
      </p>
      {error ? <p className="muted">暂时无法读取后端 API：{error}。请确认 FastAPI 后端运行在 127.0.0.1:8000。</p> : null}
      {payload?.latest_trade_date ? <p className="muted">最新数据截面：{payload.latest_trade_date}</p> : <p className="muted">加载 /api/scores 中…</p>}
      <div className="grid">
        {horizons.map((horizon) => {
          const rows = payload?.horizon_rankings?.[horizon]?.slice(0, 8) ?? [];
          return (
            <div className="card" key={horizon}>
              <strong>{horizon === '1d' ? '未来1d' : horizon === '5d' ? '保留5d' : '未来14d'}</strong>
              <span className="muted">截面：{payload?.latest_trade_date_by_horizon?.[horizon] ?? '加载中'}</span>
              <div className="field-list">
                {rows.length ? rows.map((row) => (
                  <span key={`${horizon}-${row.trade_date}-${row.symbol}`}>
                    #{row.rank ?? '—'} {row.symbol} ↑{formatProbability(row.probability_up)} score={typeof row.score === 'number' ? row.score.toFixed(3) : '—'}
                  </span>
                )) : <span>等待后端返回 horizon_rankings[{horizon}]</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
