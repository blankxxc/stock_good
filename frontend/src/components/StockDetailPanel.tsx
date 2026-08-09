'use client';

import { useMemo, useState } from 'react';
import { compactDate, formatNumber, formatPercent } from '../lib/formatters';
import { useApiPayload } from '../lib/useApiPayload';

type PricePoint = {
  trade_date: string;
  open?: number;
  high?: number;
  low?: number;
  close?: number;
  volume?: number;
  amount?: number;
  pct_change?: number;
  ma5?: number;
  ma20?: number;
  turnover_rate?: number;
};

type PredictionRow = {
  trade_date?: string;
  prediction_target_date?: string;
  horizon: string;
  probability_up?: number;
  probability_down?: number;
  predicted_relative_change?: number;
  predicted_relative_change_pct?: number;
  score?: number;
  rank?: number;
  confidence?: number;
  model_name?: string;
  model_family?: string;
  market_regime?: string;
  sentiment_score?: number;
  sentiment_source?: string;
  sentiment_coverage?: number;
  global_probability_up?: number;
  sentiment_probability_up?: number;
  regime_adjustment?: number;
};

type FactorRow = {
  factor_name?: string;
  category?: string;
  coverage?: number;
  IC_mean?: number;
  RankIC_mean?: number;
  top_bottom_spread?: number;
  cost_adjusted_spread?: number;
  factor_value?: number;
  value_trade_date?: string;
  value_interpretation?: string;
};

type MarketNote = { title: string; body: string };

export type StockDetailPayload = {
  status?: string;
  symbol?: string;
  stock_name?: string;
  industry_name?: string;
  latest_trade_date?: string;
  research_boundary?: string;
  price_series?: PricePoint[];
  predictions?: PredictionRow[];
  recent_factors?: FactorRow[];
  factor_count?: number;
  market_notes?: MarketNote[];
};

type PriceField = 'close' | 'ma5' | 'ma20';

type ChartMetrics = {
  minPrice: number;
  maxPrice: number;
  priceTicks: number[];
  dateTicks: { index: number; label: string }[];
};

type HoveredChartPoint = {
  point: PricePoint;
  x: number;
  y: number;
};

const CHART_WIDTH = 1000;
const CHART_HEIGHT = 400;
const PRICE_LEFT = 58;
const PRICE_RIGHT = 986;
const PRICE_TOP = 34;
const PRICE_BOTTOM = 330;

function numericValues(points: PricePoint[]) {
  return points.flatMap((point) => [point.open, point.high, point.low, point.close, point.ma5, point.ma20])
    .filter((value): value is number => typeof value === 'number' && !Number.isNaN(value));
}

function buildDateTicks(points: PricePoint[]) {
  if (!points.length) return [];
  const last = points.length - 1;
  const candidates = [0, Math.floor(last * 0.25), Math.floor(last * 0.5), Math.floor(last * 0.75), last];
  return Array.from(new Set(candidates)).map((index) => ({ index, label: compactDate(points[index]?.trade_date ?? '') }));
}

function buildChartMetrics(points: PricePoint[]): ChartMetrics {
  const values = numericValues(points);
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const padding = Math.max((max - min) * 0.08, max * 0.005, 0.01);
  const minPrice = min - padding;
  const maxPrice = max + padding;
  const step = (maxPrice - minPrice) / 4;
  return {
    minPrice,
    maxPrice,
    priceTicks: [maxPrice, maxPrice - step, maxPrice - step * 2, maxPrice - step * 3, minPrice],
    dateTicks: buildDateTicks(points),
  };
}

function xForIndex(index: number, total: number) {
  if (total <= 1) return PRICE_LEFT;
  return PRICE_LEFT + (index / (total - 1)) * (PRICE_RIGHT - PRICE_LEFT);
}

function yForPrice(value: number, metrics: ChartMetrics) {
  const span = metrics.maxPrice - metrics.minPrice || 1;
  return PRICE_BOTTOM - ((value - metrics.minPrice) / span) * (PRICE_BOTTOM - PRICE_TOP);
}

function buildPolyline(points: PricePoint[], field: PriceField, metrics: ChartMetrics) {
  const values = points.map((point) => point[field]).filter((value): value is number => typeof value === 'number' && !Number.isNaN(value));
  if (!values.length) return '';
  return points.map((point, index) => {
    const value = point[field];
    const safeValue = typeof value === 'number' && !Number.isNaN(value) ? value : values[0];
    return `${xForIndex(index, points.length).toFixed(1)},${yForPrice(safeValue, metrics).toFixed(1)}`;
  }).join(' ');
}

function horizonLabel(horizon: string) {
  if (horizon === '1d') return '未来1d';
  if (horizon === '5d') return '未来5d';
  if (horizon === '14d') return '未来14d';
  return horizon;
}

function isUpDay(point: PricePoint) {
  const close = point.close ?? 0;
  const open = point.open ?? close;
  return close >= open;
}

function predictionTone(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'prediction-probability--flat';
  if (value > 0) return 'prediction-probability--up';
  if (value < 0) return 'prediction-probability--down';
  return 'prediction-probability--flat';
}

function relativeChangeDisplay(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${value >= 0 ? '+' : ''}${value.toFixed(3)}%`;
}

function factorValueDisplay(factor: FactorRow) {
  const name = (factor.factor_name ?? '').toLowerCase();
  if (typeof factor.factor_value !== 'number' || Number.isNaN(factor.factor_value)) return '—';
  if (['return', 'momentum', 'reversal', 'gap', 'range', 'deviation', 'volatility'].some((token) => name.includes(token))) {
    return formatPercent(factor.factor_value, 2);
  }
  return formatNumber(factor.factor_value, 4);
}

function factorMeaning(factor: FactorRow) {
  const name = (factor.factor_name ?? '').toLowerCase();
  const category = (factor.category ?? '').toLowerCase();
  if (name.includes('return')) return '收益表现：看股票近期涨跌幅。';
  if (name.includes('momentum')) return '动量：看上涨或下跌趋势是否延续。';
  if (name.includes('reversal')) return '反转：看短期涨跌后是否可能回摆。';
  if (name.includes('volatility') || name.includes('beta')) return '波动/风险：看价格波动和市场敏感度。';
  if (name.includes('liquidity') || name.includes('amount') || name.includes('volume') || name.includes('turnover')) return '流动性：看成交活跃度和资金容量。';
  if (name.includes('ma') || category.includes('moving_average')) return '均线位置：看价格相对成本区的位置。';
  if (name.includes('zscore') || name.includes('rank') || name.includes('percentile')) return '截面位置：看该股在同日股票池中的相对高低。';
  return '综合特征：补充模型对该股当前状态的判断。';
}

function valueInterpretation(factor: FactorRow) {
  return factor.value_interpretation ?? '该股暂无取值。';
}

function chartTooltipX(x: number) {
  return Math.min(Math.max(x + 14, PRICE_LEFT), PRICE_RIGHT - 220);
}

function chartTooltipY(y: number) {
  return Math.min(Math.max(y - 94, PRICE_TOP + 6), PRICE_BOTTOM - 128);
}

export function StockDetailPanel({
  symbol,
  initialPayload = null,
  returnTo = '/',
  returnLabel = '返回股票全景',
}: {
  symbol: string;
  initialPayload?: StockDetailPayload | null;
  returnTo?: string;
  returnLabel?: string;
}) {
  const { payload, error, loading, reload } = useApiPayload<StockDetailPayload>(`/api/stocks/${encodeURIComponent(symbol)}`, initialPayload);
  const [hoveredPoint, setHoveredPoint] = useState<HoveredChartPoint | null>(null);
  const [selectedFactorNames, setSelectedFactorNames] = useState<string[] | null>(null);

  const points = payload?.price_series ?? [];
  const recentFactors = payload?.recent_factors ?? [];
  const factorNames = recentFactors.map((factor) => factor.factor_name).filter((name): name is string => Boolean(name));
  const activeFactorNames = selectedFactorNames ?? factorNames;
  const visibleFactors = recentFactors.filter((factor) => activeFactorNames.includes(factor.factor_name ?? ''));
  const chartPoints = points.slice(-96);
  const latest = points[points.length - 1];
  const metrics = useMemo(() => buildChartMetrics(chartPoints), [chartPoints]);
  const closeLine = useMemo(() => buildPolyline(chartPoints, 'close', metrics), [chartPoints, metrics]);
  const ma5Line = useMemo(() => buildPolyline(chartPoints, 'ma5', metrics), [chartPoints, metrics]);
  const ma20Line = useMemo(() => buildPolyline(chartPoints, 'ma20', metrics), [chartPoints, metrics]);
  const candleWidth = Math.max(3, Math.min(9, ((PRICE_RIGHT - PRICE_LEFT) / Math.max(chartPoints.length, 1)) * 0.55));
  const maxVolume = Math.max(...chartPoints.map((point) => point.volume ?? 0), 1);

  function toggleFactor(name: string) {
    setSelectedFactorNames((current) => {
      const base = current ?? factorNames;
      return base.includes(name) ? base.filter((item) => item !== name) : [...base, name];
    });
  }

  return (
    <section className="stock-detail artifact-backed">
      <div className="stock-detail__header">
        <div>
          <h1>{payload?.stock_name ?? symbol} <span>{payload?.symbol ?? symbol}</span></h1>
        </div>
        <div className="stock-detail__actions">
          <a className="button button--secondary" href={returnTo}>{returnLabel}</a>
          <a className="button" href="/backtests">查看整体回测风险</a>
        </div>
      </div>
      {error ? (
        <div className="data-state data-state--error" role="alert">
          <span>暂时无法读取个股数据：{error}</span>
          <button className="button table-button" type="button" onClick={reload} disabled={loading}>重新加载</button>
        </div>
      ) : null}
      {loading && !payload ? <p className="data-state" role="status" aria-live="polite">正在加载个股行情与研究数据…</p> : null}
      <div className="market-ticker-row">
        <div><strong>{payload?.latest_trade_date ?? '加载中'}</strong><span>最新交易日</span></div>
        <div><strong>{formatNumber(latest?.close)}</strong><span>最新价</span></div>
        <div><strong className={(latest?.pct_change ?? 0) >= 0 ? 'positive' : 'negative'}>{formatPercent(latest?.pct_change)}</strong><span>涨跌幅</span></div>
        <div><strong>{typeof latest?.amount === 'number' ? `${formatNumber(latest.amount / 100000000, 2)}亿` : '—'}</strong><span>成交额</span></div>
        <div><strong>{payload?.industry_name ?? '—'}</strong><span>行业</span></div>
      </div>

      <div className="detail-grid">
        <div className="card chart-card security-chart-card security-chart-card--full">
          <div className="artifact-card__topline">
            <strong>价格走势 / K线</strong>
            <span className="muted">移动到蜡烛或折线点查看开高低收、均线和成交量</span>
          </div>
          <div className="chart-legend securities-legend" aria-label="行情图例">
            <span className="legend-item legend-close">收盘价 {formatNumber(latest?.close)}</span>
            <span className="legend-item legend-ma5">MA5 {formatNumber(latest?.ma5)}</span>
            <span className="legend-item legend-ma20">MA20 {formatNumber(latest?.ma20)}</span>
            <span className="legend-item legend-volume-up">红柱上涨</span>
            <span className="legend-item legend-volume-down">绿柱下跌</span>
          </div>
          <div className="moving-average-explain" aria-label="均线说明">
            <span><b>MA5 / 5日均线：</b>最近5个交易日收盘价平均值，偏短期走势，反应更快但更容易被短线波动干扰。</span>
            <span><b>MA20 / 20日均线：</b>最近20个交易日收盘价平均值，更偏中期趋势，适合观察价格是否站上阶段成本区。</span>
          </div>
          <svg className="price-chart securities-price-chart" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} role="img" aria-label="个股价格走势和K线">
            <rect x="0" y="0" width={CHART_WIDTH} height={CHART_HEIGHT} rx="18" />
            <g className="chart-grid">
              {metrics.priceTicks.map((tick) => {
                const y = yForPrice(tick, metrics);
                return (
                  <g key={tick.toFixed(4)}>
                    <line className="chart-grid-line" x1={PRICE_LEFT} x2={PRICE_RIGHT} y1={y} y2={y} />
                    <text className="chart-axis-label chart-axis-label--price" x="48" y={y + 4}>{tick.toFixed(2)}</text>
                  </g>
                );
              })}
              {metrics.dateTicks.map((tick) => {
                const x = xForIndex(tick.index, chartPoints.length);
                return (
                  <g key={`${tick.index}-${tick.label}`}>
                    <line className="chart-grid-line chart-grid-line--vertical" x1={x} x2={x} y1={PRICE_TOP} y2={PRICE_BOTTOM} />
                    <text className="chart-axis-label chart-axis-label--date" x={x} y="374">{tick.label}</text>
                  </g>
                );
              })}
            </g>
            <g className="kline-layer" aria-label="K线蜡烛图">
              {chartPoints.map((point, index) => {
                const open = point.open ?? point.close ?? 0;
                const close = point.close ?? open;
                const high = point.high ?? Math.max(open, close);
                const low = point.low ?? Math.min(open, close);
                const x = xForIndex(index, chartPoints.length);
                const openY = yForPrice(open, metrics);
                const closeY = yForPrice(close, metrics);
                const highY = yForPrice(high, metrics);
                const lowY = yForPrice(low, metrics);
                const up = isUpDay(point);
                return (
                  <g
                    className={`kline-candle ${up ? 'kline-candle--up' : 'kline-candle--down'}`}
                    key={point.trade_date}
                    tabIndex={0}
                    onFocus={() => setHoveredPoint({ point, x, y: closeY })}
                    onBlur={() => setHoveredPoint(null)}
                    onMouseEnter={() => setHoveredPoint({ point, x, y: closeY })}
                    onMouseMove={() => setHoveredPoint({ point, x, y: closeY })}
                    onMouseLeave={() => setHoveredPoint(null)}
                  >
                    <line className="kline-wick" x1={x} x2={x} y1={highY} y2={lowY} />
                    <rect className="kline-body" x={x - candleWidth / 2} y={Math.min(openY, closeY)} width={candleWidth} height={Math.max(Math.abs(openY - closeY), 1.5)} />
                  </g>
                );
              })}
            </g>
            <g className="chart-lines-layer" aria-label="常显折线">
              <polyline className="line line-close" points={closeLine} />
              <polyline className="line line-ma5" points={ma5Line} />
              <polyline className="line line-ma20" points={ma20Line} />
            </g>
            {hoveredPoint ? (
              <g className="chart-hover-tooltip" transform={`translate(${chartTooltipX(hoveredPoint.x)} ${chartTooltipY(hoveredPoint.y)})`}>
                <rect width="212" height="124" rx="12" />
                <text className="tooltip-title" x="12" y="22">{hoveredPoint.point.trade_date}</text>
                <text x="12" y="44">开盘 {formatNumber(hoveredPoint.point.open)} · 收盘 {formatNumber(hoveredPoint.point.close)}</text>
                <text x="12" y="62">最高 {formatNumber(hoveredPoint.point.high)} · 最低 {formatNumber(hoveredPoint.point.low)}</text>
                <text x="12" y="80">涨跌幅 {formatPercent(hoveredPoint.point.pct_change)}</text>
                <text x="12" y="98">MA5 {formatNumber(hoveredPoint.point.ma5)} · MA20 {formatNumber(hoveredPoint.point.ma20)}</text>
                <text x="12" y="116">成交量 {formatNumber(hoveredPoint.point.volume, 0)}</text>
              </g>
            ) : null}
          </svg>
          <div className="volume-bars securities-volume-bars" aria-label="成交量">
            {chartPoints.map((point) => {
              const up = isUpDay(point);
              return (
                <span
                  className={up ? 'volume-bar--up' : 'volume-bar--down'}
                  key={point.trade_date}
                  style={{ height: `${Math.max(((point.volume ?? 0) / maxVolume) * 100, 3)}%` }}
                  title={`${point.trade_date} 成交量 ${formatNumber(point.volume, 0)}`}
                />
              );
            })}
          </div>
          <div className="chart-time-range muted">时间范围：{chartPoints[0]?.trade_date ?? '—'} 至 {chartPoints[chartPoints.length - 1]?.trade_date ?? '—'}</div>
        </div>

        <div className="card prediction-card prediction-card--below-chart">
          <strong>COGRASP 当前沪深300重训版下一日回归输出</strong>
          <div className="prediction-list-horizontal">
            {(payload?.predictions ?? []).map((row) => (
              <div className="prediction-row" key={row.horizon}>
                <span>{horizonLabel(row.horizon)}</span>
                <strong className={predictionTone(row.predicted_relative_change_pct)}>{relativeChangeDisplay(row.predicted_relative_change_pct)}</strong>
                <small>预测相对涨跌 · 当前300只排名 #{row.rank ?? '—'} · 输入 {row.trade_date ?? '—'} · 目标 {row.prediction_target_date ?? '下一交易日'}</small>
                <small>{row.model_family ?? row.model_name ?? 'COGRASP current CSI300 retrained'}</small>
                <small>收益相关性 Top8 关系图，不含正负文本情绪</small>
              </div>
            ))}
          </div>
          {!(payload?.predictions ?? []).length ? <p className="muted">等待个股预测数据。</p> : null}
        </div>
      </div>

      <div className="card factor-explain-card">
        <div className="artifact-card__topline">
          <strong>最近因子结果</strong>
          <a className="button table-button" href="/factors">查看因子库说明</a>
        </div>
        <p className="muted factor-compact-note">
          显示当前股票的最新因子取值；IC / RankIC 仅作因子质量参考。
          <span className="factor-count-pill">共 {payload?.factor_count ?? recentFactors.length} 个因子</span>
        </p>
        <div className="factor-ic-overview" aria-label="IC和RankIC含义">
          <span><b>IC：</b>因子值与未来收益的相关性。</span>
          <span><b>RankIC：</b>因子排序与未来收益排序的相关性。</span>
        </div>
        <div className="factor-filter-panel" aria-label="因子筛选">
          <strong>因子筛选</strong>
          <div>
            {recentFactors.map((factor) => {
              const name = factor.factor_name ?? 'unknown_factor';
              return (
                <label key={name}>
                  <input checked={activeFactorNames.includes(name)} onChange={() => toggleFactor(name)} type="checkbox" />
                  <span>{name}</span>
                </label>
              );
            })}
          </div>
        </div>
        <div className="factor-result-grid compact-factor-result-grid">
          {visibleFactors.map((factor) => (
            <div className="factor-chip" key={factor.factor_name}>
              <div className="factor-quick-row">
                <span>{factor.category}</span>
                <strong>{factor.factor_name}</strong>
              </div>
              <p className="factor-meaning"><b>含义：</b>{factorMeaning(factor)}</p>
              <div className="factor-stock-value">
                <span>该股取值</span>
                <strong>{factorValueDisplay(factor)}</strong>
                <small>取值日 {factor.value_trade_date ?? '—'}</small>
              </div>
              <p className="factor-value-note">{valueInterpretation(factor)}</p>
              <small className="factor-metrics-line">参考：IC {formatNumber(factor.IC_mean, 3)} · RankIC {formatNumber(factor.RankIC_mean, 3)} · 多空 {formatPercent(factor.top_bottom_spread, 1)}</small>
            </div>
          ))}
          {!visibleFactors.length ? <p className="muted">请选择至少一个因子展示。</p> : null}
        </div>
      </div>

      <div className="card">
        <strong>市场相关资讯</strong>
        <div className="grid">
          {(payload?.market_notes ?? []).map((note) => (
            <div className="news-card" key={note.title}>
              <span className="badge">market note</span>
              <h3>{note.title}</h3>
              <p>{note.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
