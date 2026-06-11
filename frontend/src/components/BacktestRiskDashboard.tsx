'use client';

import { useEffect, useState } from 'react';

type RiskFlag = { name: string; level: string; explain: string };
type CurvePoint = { trade_date?: string; nav?: number; max_drawdown?: number; daily_return?: number; turnover?: number; transaction_cost?: number };
type CapacityPoint = { participation_rate?: number; capacity?: number };
type RiskExplainer = { title: string; body: string };

export type BacktestPayload = {
  status?: string;
  run_id?: string;
  portfolio_id?: string;
  benchmark?: string;
  equity_curve_rows?: number;
  risk_report_rows?: number;
  risk_summary?: Record<string, number | string | RiskFlag[] | null | undefined>;
  risk_latest?: Record<string, number | string | null | undefined>;
  capacity_curve?: CapacityPoint[];
  industry_attribution?: Record<string, number>;
  style_attribution?: Record<string, number>;
  curve_tail?: CurvePoint[];
  risk_explainers?: RiskExplainer[];
};

function pct(value: unknown, digits = 1) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

function num(value: unknown, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return value.toFixed(digits);
}

function money(value: unknown) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  if (Math.abs(value) >= 100_000_000) return `${(value / 100_000_000).toFixed(2)} 亿`;
  if (Math.abs(value) >= 10_000) return `${(value / 10_000).toFixed(2)} 万`;
  return value.toFixed(0);
}

function levelLabel(level: string) {
  if (level === 'danger') return '高风险';
  if (level === 'warning') return '需关注';
  if (level === 'ok') return '正常';
  return '未知';
}

function sortedEntries(payload?: Record<string, number>) {
  return Object.entries(payload ?? {}).sort((a, b) => Math.abs(b[1] ?? 0) - Math.abs(a[1] ?? 0)).slice(0, 8);
}

export function BacktestRiskDashboard({ initialPayload = null }: { initialPayload?: BacktestPayload | null }) {
  const [payload, setPayload] = useState<BacktestPayload | null>(initialPayload);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/backtests', { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<BacktestPayload>;
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

  const summary = payload?.risk_summary ?? {};
  const flags = (summary.risk_flags as RiskFlag[] | undefined) ?? [];
  const curve = payload?.curve_tail ?? [];
  const latestCurve = curve[curve.length - 1];

  return (
    <div className="card backtest-risk-dashboard" data-api-fields="risk_summary risk_flags capacity_curve risk_attribution curve_tail">
      <div className="artifact-card__topline">
        <span className="badge">回测风险 · risk dashboard</span>
        <span className="status-pill">{payload?.status ?? 'loading'}</span>
      </div>
      <h3>策略回测与风险评估</h3>
      <p>把“这个选股方法历史上怎么亏、亏多深、换手多高、容量够不够、风险来自哪里”集中展示。它不是收益承诺，也不是交易指令。</p>
      {error ? <p className="muted">暂时无法读取后端 API：{error}。请确认 FastAPI 后端运行在 127.0.0.1:8000。</p> : null}

      <div className="risk-kpi-grid">
        <div><span>最新净值</span><strong>{num(summary.nav_latest, 3)}</strong><small>累计收益 {pct(summary.cumulative_return)}</small></div>
        <div><span>最大回撤</span><strong className="negative">{pct(summary.max_drawdown)}</strong><small>越深越危险</small></div>
        <div><span>夏普比率</span><strong>{num(summary.sharpe, 2)}</strong><small>收益 / 波动</small></div>
        <div><span>换手率</span><strong>{pct(summary.turnover)}</strong><small>成本敏感度</small></div>
        <div><span>成本后收益</span><strong className={typeof summary.cost_adjusted_return === 'number' && summary.cost_adjusted_return >= 0 ? 'positive' : 'negative'}>{pct(summary.cost_adjusted_return)}</strong><small>扣除交易成本</small></div>
        <div><span>策略容量</span><strong>{money(summary.capacity)}</strong><small>估算承载资金</small></div>
      </div>

      <div className="risk-flag-grid">
        {flags.map((flag) => (
          <div className={`risk-flag risk-flag--${flag.level}`} key={flag.name}>
            <strong>{flag.name}：{levelLabel(flag.level)}</strong>
            <p>{flag.explain}</p>
          </div>
        ))}
      </div>

      <div className="grid">
        <div className="card">
          <strong>最近回测状态</strong>
          <dl className="meta-grid">
            <div><dt>run_id</dt><dd>{payload?.run_id ?? '—'}</dd></div>
            <div><dt>portfolio</dt><dd>{payload?.portfolio_id ?? '—'}</dd></div>
            <div><dt>benchmark</dt><dd>{payload?.benchmark ?? '—'}</dd></div>
            <div><dt>latest_date</dt><dd>{summary.latest_trade_date?.toString() ?? latestCurve?.trade_date ?? '—'}</dd></div>
          </dl>
        </div>
        <div className="card">
          <strong>主动风险</strong>
          <dl className="meta-grid">
            <div><dt>active_return</dt><dd>{pct(payload?.risk_latest?.active_return)}</dd></div>
            <div><dt>tracking_error</dt><dd>{pct(payload?.risk_latest?.tracking_error)}</dd></div>
            <div><dt>information_ratio</dt><dd>{num(payload?.risk_latest?.information_ratio, 2)}</dd></div>
            <div><dt>beta_to_benchmark</dt><dd>{num(payload?.risk_latest?.beta_to_benchmark, 2)}</dd></div>
          </dl>
        </div>
      </div>

      <div className="grid">
        <div className="card">
          <strong>容量曲线 capacity_curve</strong>
          <table className="mini-score-table">
            <thead><tr><th>参与率</th><th>估算容量</th></tr></thead>
            <tbody>
              {(payload?.capacity_curve ?? []).map((row) => <tr key={row.participation_rate}><td>{pct(row.participation_rate)}</td><td>{money(row.capacity)}</td></tr>)}
            </tbody>
          </table>
        </div>
        <div className="card">
          <strong>风格暴露 Top8</strong>
          <table className="mini-score-table">
            <thead><tr><th>风格因子</th><th>暴露值</th></tr></thead>
            <tbody>
              {sortedEntries(payload?.style_attribution).map(([key, value]) => <tr key={key}><td>{key}</td><td>{num(value, 3)}</td></tr>)}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <strong>最近30个回测点</strong>
        <table className="mini-score-table">
          <thead><tr><th>日期</th><th>净值</th><th>日收益</th><th>最大回撤</th><th>换手</th><th>交易成本</th></tr></thead>
          <tbody>
            {curve.map((row) => (
              <tr key={row.trade_date}>
                <td>{row.trade_date ?? '—'}</td>
                <td>{num(row.nav, 3)}</td>
                <td className={typeof row.daily_return === 'number' && row.daily_return >= 0 ? 'positive' : 'negative'}>{pct(row.daily_return)}</td>
                <td className="negative">{pct(row.max_drawdown)}</td>
                <td>{pct(row.turnover)}</td>
                <td>{pct(row.transaction_cost, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="factor-help-panel">
        {(payload?.risk_explainers ?? []).map((item) => <div key={item.title}><b>{item.title}</b><p>{item.body}</p></div>)}
      </div>
    </div>
  );
}
