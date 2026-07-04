'use client';

import { useEffect, useMemo, useState } from 'react';

type RiskFlag = { name: string; level: string; explain: string };
type CurvePoint = { trade_date?: string; nav?: number; max_drawdown?: number; daily_return?: number; turnover?: number; transaction_cost?: number };
type CapacityPoint = { participation_rate?: number; capacity?: number };
type RiskExplainer = { title: string; body: string };
type RiskTailPoint = { trade_date?: string; active_return?: number; tracking_error?: number; information_ratio?: number; beta_to_benchmark?: number; active_max_drawdown?: number; implementation_shortfall?: number };

export type BacktestPayload = {
  status?: string;
  run_id?: string;
  experiment_id?: string;
  portfolio_id?: string;
  benchmark?: string;
  metrics?: Record<string, number | string | null | undefined>;
  baseline_metrics?: Record<string, Record<string, number | string | null | undefined>>;
  risk_summary?: Record<string, number | string | RiskFlag[] | null | undefined>;
  risk_latest?: Record<string, number | string | null | undefined>;
  capacity_curve?: CapacityPoint[];
  industry_attribution?: Record<string, number>;
  style_attribution?: Record<string, number>;
  curve_tail?: CurvePoint[];
  risk_tail?: RiskTailPoint[];
  risk_explainers?: RiskExplainer[];
};

function pct(value: unknown, digits = 1) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

function signedPct(value: unknown, digits = 1) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(digits)}%`;
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

function levelTone(level: string) {
  if (level === 'danger') return 'risk-tone--danger';
  if (level === 'warning') return 'risk-tone--warning';
  if (level === 'ok') return 'risk-tone--ok';
  return 'risk-tone--unknown';
}

function valueClass(value: unknown) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '';
  return value >= 0 ? 'positive' : 'negative';
}

function sortedNumericEntries(payload?: Record<string, number>) {
  return Object.entries(payload ?? {})
    .filter((entry): entry is [string, number] => typeof entry[1] === 'number' && Number.isFinite(entry[1]))
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 8);
}

function EmptyState({ label }: { label: string }) {
  return <div className="risk-empty-state">暂无 {label} 数据，请先运行每日更新/研究回测流水线。</div>;
}

function AttributionBars({ title, data, accent }: { title: string; data?: Record<string, number>; accent: 'cyan' | 'purple' }) {
  const entries = sortedNumericEntries(data);
  const maxAbs = Math.max(...entries.map(([, value]) => Math.abs(value)), 0.000001);
  return (
    <div className="card attribution-card">
      <div className="panel-title-row"><strong>{title}</strong><span>{entries.length ? `${entries.length} 项` : '暂无数据'}</span></div>
      {entries.length ? (
        <div className="attribution-bars">
          {entries.map(([key, value]) => (
            <div className="attribution-row" key={key}>
              <span>{key}</span>
              <div className="attribution-track"><i className={`attribution-fill attribution-fill--${accent}`} style={{ width: `${Math.max(5, Math.abs(value) / maxAbs * 100)}%` }} /></div>
              <b className={valueClass(value)}>{num(value, 3)}</b>
            </div>
          ))}
        </div>
      ) : <EmptyState label={title} />}
    </div>
  );
}

function EquityMiniChart({ curve }: { curve: CurvePoint[] }) {
  const points = curve.filter((row) => typeof row.nav === 'number' && Number.isFinite(row.nav));
  if (points.length < 2) return <EmptyState label="净值曲线" />;

  const width = 820;
  const height = 250;
  const pad = 28;
  const values = points.map((row) => row.nav as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, 0.0001);
  const x = (index: number) => pad + (index / Math.max(points.length - 1, 1)) * (width - pad * 2);
  const y = (value: number) => pad + ((max - value) / spread) * (height - pad * 2);
  const navPath = points.map((row, index) => `${index === 0 ? 'M' : 'L'} ${x(index).toFixed(2)} ${y(row.nav as number).toFixed(2)}`).join(' ');
  const areaPath = `${navPath} L ${x(points.length - 1).toFixed(2)} ${height - pad} L ${pad} ${height - pad} Z`;
  const last = points[points.length - 1];

  return (
    <div className="equity-chart-shell">
      <svg className="equity-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="最近回测净值曲线">
        <defs>
          <linearGradient id="equityGlow" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((line) => <line className="chart-grid-line" key={line} x1={pad} x2={width - pad} y1={pad + line * ((height - pad * 2) / 3)} y2={pad + line * ((height - pad * 2) / 3)} />)}
        <path d={areaPath} fill="url(#equityGlow)" />
        <path className="equity-chart-line" d={navPath} />
        <circle cx={x(points.length - 1)} cy={y(last.nav as number)} r="4.5" className="equity-chart-dot" />
        <text x={pad} y={height - 8} className="chart-axis-label">{points[0].trade_date}</text>
        <text x={width - pad} y={height - 8} className="chart-axis-label chart-axis-label--price">{last.trade_date}</text>
        <text x={width - pad} y={pad + 12} className="chart-axis-label chart-axis-label--price">NAV {num(last.nav, 3)}</text>
      </svg>
    </div>
  );
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
        if (!cancelled) {
          setPayload(data);
          setError(null);
        }
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
  const riskTail = payload?.risk_tail ?? [];
  const latestDate = String(summary.latest_trade_date ?? latestCurve?.trade_date ?? '—');
  const capacity = payload?.capacity_curve ?? [];
  const baselineRows = useMemo(() => Object.entries(payload?.baseline_metrics ?? {}).slice(0, 5), [payload?.baseline_metrics]);

  return (
    <div className="backtest-risk-dashboard">
      <section className="card risk-command-center">
        <div className="artifact-card__topline">
          <span className="badge">风险看板</span>
        </div>
        <div className="risk-hero-grid">
          <div className="risk-hero-copy">
            <h2>回测风险</h2>
            <p>历史表现、回撤压力和当前风控状态</p>
            <div className="risk-context-strip">
              <span>组合 <b>{payload?.portfolio_id ?? '—'}</b></span>
              <span>基准 <b>{payload?.benchmark ?? '—'}</b></span>
              <span>日期 <b>{latestDate}</b></span>
            </div>
          </div>
          <div className="risk-verdict-card">
            <span>总体风控结论</span>
            <strong>{flags.some((flag) => flag.level === 'danger') ? '高风险复核' : flags.some((flag) => flag.level === 'warning') ? '需要关注' : '状态正常'}</strong>
            <p>最大回撤 {pct(summary.max_drawdown)} · 换手 {pct(summary.turnover)} · Sharpe {num(summary.sharpe, 2)}</p>
          </div>
        </div>
        {error ? <p className="muted">暂时无法读取回测数据：{error}</p> : null}
      </section>

      <section className="risk-kpi-grid risk-kpi-grid--premium">
        <div><span>最新净值</span><strong>{num(summary.nav_latest, 3)}</strong><small>累计收益 {signedPct(summary.cumulative_return)}</small></div>
        <div className="risk-kpi-danger"><span>最大回撤</span><strong className="negative">{pct(summary.max_drawdown)}</strong><small>越深越危险</small></div>
        <div><span>夏普比率</span><strong>{num(summary.sharpe, 2)}</strong><small>收益 / 波动</small></div>
        <div><span>Calmar</span><strong>{num(summary.calmar, 2)}</strong><small>年化收益 / 回撤</small></div>
        <div><span>胜率</span><strong>{pct(summary.hit_rate)}</strong><small>正收益样本占比</small></div>
        <div><span>策略容量</span><strong>{money(summary.capacity)}</strong><small>估算承载资金</small></div>
        <div><span>换手率</span><strong>{pct(summary.turnover)}</strong><small>成本敏感度</small></div>
        <div><span>成本后收益</span><strong className={valueClass(summary.cost_adjusted_return)}>{signedPct(summary.cost_adjusted_return)}</strong><small>扣除交易成本</small></div>
      </section>

      <section className="risk-two-column">
        <div className="card chart-card risk-chart-card">
          <div className="panel-title-row"><strong>最近30个回测点 · NAV / Drawdown</strong><span>{curve.length}个点</span></div>
          <p className="muted section-one-liner">净值看收益路径，回撤看历史最大亏损压力。</p>
          <EquityMiniChart curve={curve} />
        </div>
        <div className="risk-flag-grid risk-flag-grid--stacked">
          {flags.length ? flags.map((flag) => (
            <div className={`risk-flag risk-flag--${flag.level}`} key={flag.name}>
              <div className="risk-flag-head"><strong>{flag.name}</strong><span className={levelTone(flag.level)}>{levelLabel(flag.level)}</span></div>
              <p>{flag.explain}</p>
            </div>
          )) : <EmptyState label="风险旗标" />}
        </div>
      </section>

      <section className="grid risk-detail-grid">
        <div className="card">
          <div className="panel-title-row"><strong>主动风险</strong><span>{payload?.risk_latest?.risk_model_version?.toString() ?? 'risk_model'}</span></div>
          <p className="muted section-one-liner">主动风险衡量策略相对基准多赚/少赚，以及偏离基准的波动。</p>
          <dl className="meta-grid compact-meta-grid risk-metric-grid">
            <div>
              <dt>相对收益</dt>
              <dd className={valueClass(payload?.risk_latest?.active_return)}>{signedPct(payload?.risk_latest?.active_return)}</dd>
              <small>策略比基准多赚或少赚了多少。</small>
            </div>
            <div>
              <dt>跟踪误差</dt>
              <dd>{pct(payload?.risk_latest?.tracking_error)}</dd>
              <small>策略相对基准偏离得有多剧烈。</small>
            </div>
            <div>
              <dt>信息比率</dt>
              <dd>{num(payload?.risk_latest?.information_ratio, 2)}</dd>
              <small>每承担一份主动风险换来多少超额收益。</small>
            </div>
            <div>
              <dt>对基准 Beta</dt>
              <dd>{num(payload?.risk_latest?.beta_to_benchmark, 2)}</dd>
              <small>策略跟随基准涨跌的敏感程度。</small>
            </div>
            <div>
              <dt>主动最大回撤</dt>
              <dd className="negative">{pct(payload?.risk_latest?.active_max_drawdown)}</dd>
              <small>相对基准时，历史最深亏损压力。</small>
            </div>
            <div>
              <dt>执行损耗</dt>
              <dd className={valueClass(payload?.risk_latest?.implementation_shortfall)}>{signedPct(payload?.risk_latest?.implementation_shortfall, 2)}</dd>
              <small>交易执行和成本拖累了多少收益。</small>
            </div>
          </dl>
        </div>
      </section>

      <section className="grid risk-detail-grid">
        <div className="card capacity-panel">
          <div className="panel-title-row"><strong>容量曲线</strong><span>{capacity.length ? '资金承载估算' : '暂无数据'}</span></div>
          <p className="muted section-one-liner">容量曲线估算不同参与率下，策略大概能承载多少资金。</p>
          {capacity.length ? (
            <div className="capacity-ladder">
              {capacity.map((row) => (
                <div key={row.participation_rate}>
                  <span>参与率 {pct(row.participation_rate)}</span>
                  <strong>{money(row.capacity)}</strong>
                </div>
              ))}
            </div>
          ) : <EmptyState label="容量曲线" />}
        </div>
        <div className="card">
          <div className="panel-title-row"><strong>Baseline 对比</strong><span>{baselineRows.length ? `${baselineRows.length}个基准` : '暂无数据'}</span></div>
          <p className="muted section-one-liner">Baseline 是用简单基准策略对照当前策略，避免只看单一结果。</p>
          {baselineRows.length ? (
            <div className="backtest-table-shell">
              <table className="mini-score-table">
                <thead><tr><th>基准</th><th>TopK</th><th>Sharpe</th><th>MaxDD</th></tr></thead>
                <tbody>
                  {baselineRows.map(([name, row]) => <tr key={name}><td>{name}</td><td>{signedPct(row.TopK_return)}</td><td>{num(row.Sharpe, 2)}</td><td className="negative">{pct(row.MaxDrawdown)}</td></tr>)}
                </tbody>
              </table>
            </div>
          ) : <EmptyState label="baseline 对比" />}
        </div>
      </section>

      <section className="risk-attribution-section">
        <p className="muted section-one-liner risk-grid-note">风格暴露看收益更像哪类因子，行业归因看收益主要来自哪些行业。</p>
        <AttributionBars title="风格暴露 Top8" data={payload?.style_attribution} accent="purple" />
        <AttributionBars title="行业归因 Top8" data={payload?.industry_attribution} accent="cyan" />
      </section>

      <section className="card">
        <div className="panel-title-row"><strong>最近30个回测点</strong><span>净值 / 收益 / 回撤 / 成本</span></div>
        <div className="backtest-table-shell">
          <table className="mini-score-table">
            <thead><tr><th>日期</th><th>净值</th><th>日收益</th><th>最大回撤</th><th>换手</th><th>交易成本</th></tr></thead>
            <tbody>
              {curve.map((row) => (
                <tr key={row.trade_date}>
                  <td>{row.trade_date ?? '—'}</td>
                  <td>{num(row.nav, 3)}</td>
                  <td className={valueClass(row.daily_return)}>{signedPct(row.daily_return)}</td>
                  <td className="negative">{pct(row.max_drawdown)}</td>
                  <td>{pct(row.turnover)}</td>
                  <td>{pct(row.transaction_cost, 2)}</td>
                </tr>
              ))}
              {!curve.length ? <tr><td colSpan={6}><EmptyState label="最近回测点" /></td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <div className="panel-title-row"><strong>最近风险归因流水</strong><span>{riskTail.length ? `${riskTail.length}条` : '暂无数据'}</span></div>
        <div className="backtest-table-shell">
          <table className="mini-score-table">
            <thead><tr><th>日期</th><th>主动收益</th><th>跟踪误差</th><th>IR</th><th>Beta</th><th>主动回撤</th><th>执行损耗</th></tr></thead>
            <tbody>
              {riskTail.map((row) => (
                <tr key={row.trade_date}>
                  <td>{row.trade_date ?? '—'}</td>
                  <td className={valueClass(row.active_return)}>{signedPct(row.active_return)}</td>
                  <td>{pct(row.tracking_error)}</td>
                  <td>{num(row.information_ratio, 2)}</td>
                  <td>{num(row.beta_to_benchmark, 2)}</td>
                  <td className="negative">{pct(row.active_max_drawdown)}</td>
                  <td className={valueClass(row.implementation_shortfall)}>{signedPct(row.implementation_shortfall, 2)}</td>
                </tr>
              ))}
              {!riskTail.length ? <tr><td colSpan={7}><EmptyState label="风险归因流水" /></td></tr> : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
