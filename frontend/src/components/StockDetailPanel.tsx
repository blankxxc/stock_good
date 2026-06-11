'use client';

import { useMemo } from 'react';
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
  horizon: string;
  probability_up?: number;
  probability_down?: number;
  score?: number;
  rank?: number;
  confidence?: number;
};

type FactorRow = {
  factor_name?: string;
  category?: string;
  coverage?: number;
  IC_mean?: number;
  RankIC_mean?: number;
  top_bottom_spread?: number;
  cost_adjusted_spread?: number;
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
  market_notes?: MarketNote[];
};

type PriceField = 'close' | 'ma5' | 'ma20';

type ChartMetrics = {
  minPrice: number;
  maxPrice: number;
  priceTicks: number[];
  dateTicks: { index: number; label: string }[];
};

const CHART_WIDTH = 1000;
const CHART_HEIGHT = 320;
const PRICE_LEFT = 58;
const PRICE_RIGHT = 986;
const PRICE_TOP = 30;
const PRICE_BOTTOM = 262;


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

type FactorExplanation = {
  what: string;
  usage: string;
};

const FACTOR_EXPLANATIONS: Record<string, FactorExplanation> = {
  return_5d: {
    what: '过去 5 个交易日的累计收益，描述股票最近一周的短期价格表现。',
    usage: '用于判断短期强弱和趋势延续/反转背景，但需要结合成交量、行业和交易成本，不能单独当买卖信号。',
  },
  momentum_20d: {
    what: '过去约 20 个交易日的动量强度，衡量一个月维度的趋势是否持续。',
    usage: '用于横向比较同一截面里哪些股票相对更强，常和波动率、流动性一起做风险过滤。',
  },
  volatility_20d: {
    what: '过去约 20 个交易日收益波动幅度，反映价格不确定性和风险暴露。',
    usage: '用于识别高波动股票，辅助控制仓位、回撤和模型信号的稳定性。',
  },
  downside_volatility_20d: {
    what: '只关注下跌方向的 20 日波动，刻画近期下行风险。',
    usage: '用于区分“上涨中的正常波动”和“下跌风险释放”，帮助风险控制和候选股筛选。',
  },
  amihud_20d: {
    what: 'Amihud 非流动性指标，观察单位成交额对应的价格冲击程度。',
    usage: '用于评估交易拥挤和冲击成本；数值越高通常表示流动性越差，实盘更难低成本成交。',
  },
  amount_percentile_20d: {
    what: '近 20 日成交额在自身历史中的分位水平，表示交易活跃度是否放大。',
    usage: '用于确认市场关注度和资金参与度，帮助判断信号是否有足够成交承载。',
  },
  volume_shock_20d: {
    what: '近期成交量相对过去均量的异常放大/收缩，捕捉量能冲击。',
    usage: '用于识别资金异动、事件驱动或趋势确认，通常要与价格方向和公告新闻交叉验证。',
  },
  ma20_gap: {
    what: '收盘价相对 20 日均线的偏离程度，反映价格离中期成本区有多远。',
    usage: '用于观察趋势位置、超买超卖和均值回归风险，避免只看涨跌幅忽略价格所处位置。',
  },
};

const CATEGORY_EXPLANATIONS: Record<string, FactorExplanation> = {
  price_return: {
    what: '收益类因子衡量股票在某个历史窗口内的价格变化。',
    usage: '用于比较短期强弱、趋势延续或反转机会，是截面选股的基础输入之一。',
  },
  momentum: {
    what: '动量类因子衡量上涨或下跌趋势的持续性。',
    usage: '用于发现相对强势股票，但需要配合波动率和换手成本控制追高风险。',
  },
  volatility: {
    what: '波动类因子衡量收益起伏和风险暴露。',
    usage: '用于风险过滤、仓位控制和判断模型信号是否稳定。',
  },
  liquidity: {
    what: '流动性类因子衡量成交活跃度和交易冲击成本。',
    usage: '用于过滤难成交、冲击成本高或容量不足的股票。',
  },
  price_volume_structure: {
    what: '价量结构因子把价格变化和成交量变化放在一起看。',
    usage: '用于识别放量突破、缩量回落等交易软件里常见的资金行为线索。',
  },
  moving_average_gap: {
    what: '均线偏离类因子衡量当前价格相对均线成本区的位置。',
    usage: '用于辅助判断趋势、乖离、回归压力和止盈止损区间。',
  },
};

function explainFactor(factor: FactorRow): FactorExplanation {
  const name = (factor.factor_name ?? '').toLowerCase();
  const category = (factor.category ?? '').toLowerCase();
  return FACTOR_EXPLANATIONS[name]
    ?? CATEGORY_EXPLANATIONS[category]
    ?? {
      what: '该因子是把原始行情、成交量或基本面数据加工成可比较的数值特征。',
      usage: '用于给模型提供横截面排序信息，并结合 IC、RankIC、spread 判断历史有效性。',
    };
}

export function StockDetailPanel({ symbol, initialPayload = null }: { symbol: string; initialPayload?: StockDetailPayload | null }) {
  const { payload, error } = useApiPayload<StockDetailPayload>(`/api/stocks/${encodeURIComponent(symbol)}`, initialPayload);

  const points = payload?.price_series ?? [];
  const chartPoints = points.slice(-96);
  const latest = points[points.length - 1];
  const metrics = useMemo(() => buildChartMetrics(chartPoints), [chartPoints]);
  const closeLine = useMemo(() => buildPolyline(chartPoints, 'close', metrics), [chartPoints, metrics]);
  const ma5Line = useMemo(() => buildPolyline(chartPoints, 'ma5', metrics), [chartPoints, metrics]);
  const ma20Line = useMemo(() => buildPolyline(chartPoints, 'ma20', metrics), [chartPoints, metrics]);
  const candleWidth = Math.max(3, Math.min(9, ((PRICE_RIGHT - PRICE_LEFT) / Math.max(chartPoints.length, 1)) * 0.55));
  const maxVolume = Math.max(...chartPoints.map((point) => point.volume ?? 0), 1);

  return (
    <section className="stock-detail artifact-backed" data-boundary="research_signals_only_not_investment_advice">
      <div className="stock-detail__header">
        <div>
          <span className="badge">证券软件式个股面板</span>
          <h1>{payload?.stock_name ?? symbol} <span>{payload?.symbol ?? symbol}</span></h1>
          <p className="lead">价格折线图、K线、成交量、未来 1d / 5d / 14d 模型概率、最近因子结果和市场相关资讯集中展示。</p>
        </div>
        <a className="button" href="/">返回股票全景</a>
      </div>
      {error ? <p className="muted">暂时无法读取个股 API：{error}</p> : null}
      <div className="market-ticker-row">
        <div><strong>{payload?.latest_trade_date ?? '加载中'}</strong><span>最新交易日</span></div>
        <div><strong>{formatNumber(latest?.close)}</strong><span>最新价</span></div>
        <div><strong className={(latest?.pct_change ?? 0) >= 0 ? 'positive' : 'negative'}>{formatPercent(latest?.pct_change)}</strong><span>涨跌幅</span></div>
        <div><strong>{formatNumber((latest?.amount ?? 0) / 100000000, 2)}亿</strong><span>成交额</span></div>
        <div><strong>{payload?.industry_name ?? '—'}</strong><span>行业</span></div>
      </div>

      <div className="detail-grid">
        <div className="card chart-card security-chart-card">
          <div className="artifact-card__topline">
            <strong>价格折线图 / K线</strong>
            <span className="muted">证券软件K线形态 · 时间轴 · Close / MA5 / MA20</span>
          </div>
          <div className="chart-legend securities-legend" aria-label="行情图例">
            <span className="legend-item legend-close">收盘价 {formatNumber(latest?.close)}</span>
            <span className="legend-item legend-ma5">MA5 {formatNumber(latest?.ma5)}</span>
            <span className="legend-item legend-ma20">MA20 {formatNumber(latest?.ma20)}</span>
            <span className="legend-item legend-volume-up">红柱上涨</span>
            <span className="legend-item legend-volume-down">绿柱下跌</span>
          </div>
          <svg className="price-chart securities-price-chart" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} role="img" aria-label="证券软件K线形态价格折线图">
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
                    <text className="chart-axis-label chart-axis-label--date" x={x} y="298">{tick.label}</text>
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
                  <g className={`kline-candle ${up ? 'kline-candle--up' : 'kline-candle--down'}`} key={point.trade_date}>
                    <line className="kline-wick" x1={x} x2={x} y1={highY} y2={lowY} />
                    <rect className="kline-body" x={x - candleWidth / 2} y={Math.min(openY, closeY)} width={candleWidth} height={Math.max(Math.abs(openY - closeY), 1.5)} />
                  </g>
                );
              })}
            </g>
            <polyline className="line line-close" points={closeLine} />
            <polyline className="line line-ma5" points={ma5Line} />
            <polyline className="line line-ma20" points={ma20Line} />
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
          <div className="chart-time-range muted">时间范围：{chartPoints[0]?.trade_date ?? '—'} 至 {chartPoints[chartPoints.length - 1]?.trade_date ?? '—'} · 成交量按红涨绿跌显示</div>
        </div>

        <div className="card prediction-card">
          <strong>股票预测选股概率</strong>
          {(payload?.predictions ?? []).map((row) => (
            <div className="prediction-row" key={row.horizon}>
              <span>{horizonLabel(row.horizon)}</span>
              <strong>{formatPercent(row.probability_up, 1)}</strong>
              <small>上涨概率 · 排名 #{row.rank ?? '—'} · confidence {formatPercent(row.confidence, 1)}</small>
            </div>
          ))}
          {!(payload?.predictions ?? []).length ? <p className="muted">等待 /api/stocks/{symbol} 返回 1d / 5d / 14d 预测。</p> : null}
        </div>
      </div>

      <div className="card factor-explain-card">
        <div className="artifact-card__topline">
          <strong>最近因子结果</strong>
          <span className="muted">解释因子含义、用途和历史有效性指标</span>
        </div>
        <div className="factor-help-panel">
          <div>
            <b>因子是什么</b>
            <p>因子是把行情、成交量、流动性、波动率等原始数据加工成统一口径的特征，用来描述股票在某个维度上的状态。</p>
          </div>
          <div>
            <b>干什么用</b>
            <p>因子会作为模型输入和研究诊断依据，帮助做横截面排序、风险过滤、回测归因和候选股解释；它不是单独的买卖建议。</p>
          </div>
          <div>
            <b>IC / RankIC 怎么看</b>
            <p>IC 衡量因子数值和未来收益的相关性，RankIC 衡量排序相关性，spread 表示因子高低分组的收益差。</p>
          </div>
        </div>
        <div className="factor-result-grid">
          {(payload?.recent_factors ?? []).map((factor) => {
            const explanation = explainFactor(factor);
            return (
              <div className="factor-chip" key={factor.factor_name}>
                <span>{factor.category}</span>
                <strong>{factor.factor_name}</strong>
                <p className="factor-description"><b>含义：</b>{explanation.what}</p>
                <p className="factor-usage"><b>用途：</b>{explanation.usage}</p>
                <small>IC {formatNumber(factor.IC_mean, 4)} · RankIC {formatNumber(factor.RankIC_mean, 4)} · spread {formatPercent(factor.top_bottom_spread, 2)}</small>
              </div>
            );
          })}
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
        <p className="muted">{payload?.research_boundary ?? 'research_signals_only_not_investment_advice'}</p>
      </div>
    </section>
  );
}
