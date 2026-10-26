'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useApiPayload } from '../lib/useApiPayload';
import { useAssistantContext } from './AssistantRoot';
import { AIPlanComposer } from './AIPlanComposer';
import { readStrategyConfig, strategyPreview, type Strategy, type StrategyConfig as Config } from '../lib/strategyLab';

type StCoverage = { known_fraction: number | null; unknown_count: number; observation_count: number; exclude_unknown?: boolean };
type Metadata = {
  st_coverage?: StCoverage;
  strategies: { id: Strategy; label: string; description: string }[]; assumptions: string[];
  market_start: string; market_end: string; default_start: string; default_end: string; stock_count: number;
};
type Holding = { symbol: string; stock_name: string; weight: number; market_value: number };
type Order = { symbol: string; stock_name: string; side: string; notional: number; cost: number; status: string };
type Point = {
  trade_date: string; signal_date: string | null; nav: number; equity: number; daily_return: number;
  drawdown: number; cash: number; cost: number; turnover: number; rebalance: boolean;
  holding_count: number; holdings?: Holding[]; orders?: Order[];
};
type Metrics = {
  total_return: number; annualized_return: number | null; max_drawdown: number; sharpe: number | null;
  win_rate: number; average_turnover: number; total_cost: number; final_equity: number;
  trade_count: number; blocked_orders: number; excess_return?: number;
};
type Result = { id: string; label: string; metrics: Metrics; curve: Point[] };
type Experiment = {
  st_coverage?: StCoverage;
  experiment_id: string; created_at: string; engine_version: string; config: Config;
  data_fingerprint: string; actual_start: string; actual_end: string; trading_days: number;
  results: Result[]; baseline: Result; assumptions: string[];
};
type HistoryItem = { experiment_id: string; created_at: string; config: Config; summary: string };
const HISTORY_KEY = 'stock-good-strategy-lab-v1';
const COLORS = ['#38bdf8', '#fb923c', '#c4b5fd', '#2dd4bf', '#94a3b8'];
const INITIAL: Config = {
  start_date: '', end_date: '', strategies: ['momentum', 'reversal', 'low_volatility', 'trend'],
  lookback: 20, top_k: 10, rebalance_days: 5, initial_capital: 100000, fee_bps: 3, slippage_bps: 5,
  exclude_st: true, exclude_extreme: false, exclude_abnormal: false,
};
const pct = (n: number | null | undefined) => typeof n === 'number' && Number.isFinite(n) ? `${(n * 100).toFixed(2)}%` : '—';
const money = (n: number) => n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function download(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function ComparisonChart({ series, cursor, onCursor, mode }: {
  series: Result[]; cursor: number; onCursor: (index: number) => void; mode: 'nav' | 'drawdown';
}) {
  const width = 1000, height = 300, left = 65, right = 22, top = 20, bottom = 34;
  const values = series.flatMap((result) => result.curve.map((p) => p[mode]));
  const min = Math.min(mode === 'nav' ? 1 : 0, ...values), max = Math.max(mode === 'nav' ? 1 : 0, ...values);
  const span = Math.max(max - min, 0.01);
  const count = series[0].curve.length;
  const x = (i: number) => left + i / Math.max(count - 1, 1) * (width - left - right);
  const y = (value: number) => top + (max - value) / span * (height - top - bottom);
  return <svg className="lab-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={mode === 'nav' ? '策略净值对比，点击曲线区域定位回放日期' : '策略回撤对比，点击定位回放日期'} onClick={(event) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    const position = ((event.clientX - bounds.left) / bounds.width * width - left) / (width - left - right);
    onCursor(Math.max(0, Math.min(count - 1, Math.round(position * (count - 1)))));
  }}>
    {[0, 1, 2, 3, 4].map((tick) => {
      const value = max - tick / 4 * span;
      return <g key={tick}><line x1={left} x2={width - right} y1={y(value)} y2={y(value)} stroke="currentColor" opacity=".12" /><text x={left - 10} y={y(value) + 4} textAnchor="end">{mode === 'nav' ? value.toFixed(2) : pct(value)}</text></g>;
    })}
    {series.map((result, index) => <path key={result.id} d={result.curve.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[mode]).toFixed(1)}`).join(' ')} fill="none" stroke={COLORS[index]} strokeWidth="2.3" strokeDasharray={result.id === 'equal_weight' ? '6 4' : undefined} />)}
    <line x1={x(cursor)} x2={x(cursor)} y1={top} y2={height - bottom} stroke="currentColor" opacity=".5" strokeDasharray="3 4" />
    {series.map((result, index) => <circle key={result.id} cx={x(cursor)} cy={y(result.curve[cursor][mode])} r="4" fill={COLORS[index]} />)}
    <text x={left} y={height - 8}>{series[0].curve[0].trade_date}</text>
    <text x={width - right} y={height - 8} textAnchor="end">{series[0].curve[count - 1].trade_date}</text>
  </svg>;
}

export function StrategyLab() {
  const { payload: metadata, error: metaError, loading: metaLoading, reload } = useApiPayload<Metadata>('/api/strategy-lab');
  const [config, setConfig] = useState<Config>(INITIAL);
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [storageNote, setStorageNote] = useState('');
  const [selected, setSelected] = useState('momentum');
  const [cursor, setCursor] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [mode, setMode] = useState<'nav' | 'drawdown'>('nav');
  const controller = useRef<AbortController | null>(null);
  const result = experiment?.results.find((item) => item.id === selected) ?? experiment?.results[0];
  const point = result?.curve[cursor];
  const series = useMemo(() => experiment ? [...experiment.results, experiment.baseline] : [], [experiment]);
  const changed = experiment !== null && JSON.stringify(config) !== JSON.stringify(experiment.config);
  useAssistantContext({ page_state: { experiment: {
    draft_config: config, config_changed_since_run: changed,
    ...(experiment ? {
      experiment_id: experiment.experiment_id, config: experiment.config,
      actual_start: experiment.actual_start, actual_end: experiment.actual_end,
      data_fingerprint: experiment.data_fingerprint, engine_version: experiment.engine_version,
      results: series.map(item => ({ label: item.label, metrics: item.metrics })),
      assumptions: experiment.assumptions, st_coverage: experiment.st_coverage,
      replay: point ? { strategy: result?.label, trade_date: point.trade_date,
        nav: point.nav, drawdown: point.drawdown, holding_count: point.holding_count,
        holdings_sample: point.holdings?.slice(0, 8) } : null,
    } : { results: [] }),
  } } });

  useEffect(() => {
    if (metadata) setConfig((current) => ({ ...current, start_date: current.start_date || metadata.default_start, end_date: current.end_date || metadata.default_end }));
  }, [metadata]);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
      if (Array.isArray(saved)) setHistory(saved.filter((entry) => entry && typeof entry.experiment_id === 'string' && entry.config && Array.isArray(entry.config.strategies)).slice(0, 8));
    } catch { setStorageNote('本地记录暂不可用，仍可运行并导出实验。'); }
    return () => controller.current?.abort();
  }, []);
  useEffect(() => {
    if (!playing || !result) return;
    if (cursor >= result.curve.length - 1) { setPlaying(false); return; }
    const timer = setTimeout(() => setCursor((current) => current + 1), 650);
    return () => clearTimeout(timer);
  }, [playing, cursor, result]);

  function update<K extends keyof Config>(key: K, value: Config[K]) { setConfig((current) => ({ ...current, [key]: value })); }
  function seek(index: number) { setPlaying(false); setCursor(index); }
  async function run(nextConfig = config) {
    if (busy || controller.current) return;
    setBusy(true); setError(''); setPlaying(false);
    const active = new AbortController();
    controller.current = active;
    try {
      const response = await fetch('/api/strategy-lab/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(nextConfig), signal: active.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '参数无效或服务暂不可用，请检查日期和数值范围。');
      if (active.signal.aborted) return;
      const next = data as Experiment;
      setExperiment(next); setSelected(next.results[0].id); setCursor(0);
      const saved = [{ experiment_id: next.experiment_id, created_at: next.created_at, config: next.config,
        summary: next.results.map((item) => `${item.label} ${pct(item.metrics.total_return)}`).join(' · ') }, ...history.filter((item) => item.experiment_id !== next.experiment_id)].slice(0, 8);
      setHistory(saved);
      try { localStorage.setItem(HISTORY_KEY, JSON.stringify(saved)); } catch { setStorageNote('本地记录保存失败，请导出实验结果。'); }
    } catch (failure) {
      if (!active.signal.aborted) setError(failure instanceof Error ? failure.message : '实验失败，请重试。');
    } finally { if (controller.current === active) { controller.current = null; if (!active.signal.aborted) setBusy(false); } }
  }
  function exportMetrics() {
    if (!experiment) return;
    const rows = [['策略', '累计收益', '年化收益', '最大回撤', '夏普', '正收益日占比', '累计成本', '最终资产'], ...series.map((item) => [item.label, item.metrics.total_return, item.metrics.annualized_return, item.metrics.max_drawdown, item.metrics.sharpe, item.metrics.win_rate, item.metrics.total_cost, item.metrics.final_equity])];
    download(`strategy-${experiment.experiment_id}.csv`, '\uFEFF' + rows.map((row) => row.map((value) => `"${String(value ?? '').replaceAll('"', '""')}"`).join(',')).join('\r\n'), 'text/csv;charset=utf-8');
  }

  return <div className="strategy-lab">
    <header className="card lab-header"><div><span className="badge">历史回溯 · 策略实验</span><h1>让策略回到历史中</h1><p>设定同一段历史，比较不同选股规则，再逐日查看组合如何变化。</p></div><a className="button" href="/visualization">打开数据可视化</a></header>
    {metaError ? <div className="card" role="alert">无法读取行情范围：{metaError} <button type="button" className="button" onClick={reload}>重试</button></div> : null}
    {metaLoading && !metadata ? <p role="status">正在读取可回溯的行情范围…</p> : null}
    {metadata && config.start_date && <AIPlanComposer task="strategy" current={config} contextKey={`${metadata.market_start}|${metadata.market_end}`} disabled={busy}
      parseConfig={readStrategyConfig}
      onApply={async (next, execute) => { setConfig(next); if (execute) await run(next); }}
      preview={next => <dl className="ai-plan-facts">{strategyPreview(next).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>} />}
    <form className="card lab-form" onSubmit={(event) => { event.preventDefault(); void run(); }}>
      <div className="lab-section-title"><h2>设置实验</h2><span>{metadata ? `${metadata.stock_count} 只股票 · ${metadata.market_start} 至 ${metadata.market_end}` : '等待行情数据'}</span></div>
      <fieldset disabled={busy || !metadata}>
        <legend>选择要比较的策略</legend>
        <div className="lab-strategies">{metadata?.strategies.map((strategy) => <label key={strategy.id} className={config.strategies.includes(strategy.id) ? 'is-selected' : ''}>
          <input type="checkbox" checked={config.strategies.includes(strategy.id)} onChange={(event) => update('strategies', event.target.checked ? [...config.strategies, strategy.id] : config.strategies.filter((id) => id !== strategy.id))} />
          <strong>{strategy.label}</strong><small>{strategy.description}</small>
        </label>)}</div>
        <div className="lab-fields">
          <label>开始日期<input type="date" required min={metadata?.market_start} max={config.end_date || metadata?.market_end} value={config.start_date} onChange={(e) => update('start_date', e.target.value)} /></label>
          <label>结束日期<input type="date" required min={config.start_date || metadata?.market_start} max={metadata?.market_end} value={config.end_date} onChange={(e) => update('end_date', e.target.value)} /></label>
          <label>观察期（交易日）<input type="number" required min="2" max="120" value={config.lookback} onChange={(e) => update('lookback', Number(e.target.value))} /></label>
          <label>目标持仓数量<input type="number" required min="1" max="50" value={config.top_k} onChange={(e) => update('top_k', Number(e.target.value))} /></label>
          <label>调仓间隔（交易日）<input type="number" required min="1" max="60" value={config.rebalance_days} onChange={(e) => update('rebalance_days', Number(e.target.value))} /></label>
          <label>初始资金（元）<input type="number" required min="1000" max="100000000" step="1000" value={config.initial_capital} onChange={(e) => update('initial_capital', Number(e.target.value))} /></label>
          <label>单边手续费（基点）<input type="number" required min="0" max="100" step="0.1" value={config.fee_bps} onChange={(e) => update('fee_bps', Number(e.target.value))} /></label>
          <label>单边滑点（基点）<input type="number" required min="0" max="100" step="0.1" value={config.slippage_bps} onChange={(e) => update('slippage_bps', Number(e.target.value))} /></label>
        </div>
        <div className="lab-filters">
          <label><input type="checkbox" checked={config.exclude_st} onChange={(e) => update('exclude_st', e.target.checked)} />剔除 ST</label>
          <label><input type="checkbox" checked={config.exclude_extreme} onChange={(e) => update('exclude_extreme', e.target.checked)} />剔除十日涨幅大于 100%</label>
          <label><input type="checkbox" checked={config.exclude_abnormal} onChange={(e) => update('exclude_abnormal', e.target.checked)} />剔除十日内至少四次异动</label>
        </div>
        <p className="lab-hint">1 基点 = 0.01%。过滤条件使用选股日数据；必要因子缺失时也会排除该股。勾选剔除 ST 时，历史 ST 状态未知的股票也会排除。观察期须有足够的区间前历史行情。</p>
        {metadata?.st_coverage ? <p className="lab-hint">历史 ST 状态覆盖：{pct(metadata.st_coverage.known_fraction)}；未知 {metadata.st_coverage.unknown_count.toLocaleString()} 条 / 共 {metadata.st_coverage.observation_count.toLocaleString()} 条日线。</p> : null}
      </fieldset>
      <div className="lab-actions"><button className="button primary" type="submit" disabled={busy || !metadata || config.strategies.length === 0}>{busy ? '正在计算实验…' : '运行并比较'}</button><span role="status">{busy ? '按交易日计算净值、持仓与成交记录。' : changed ? '参数已修改；下方仍是上次实验结果。' : '同一参数与数据版本可重复验证。'}</span></div>
      {error ? <p className="lab-error" role="alert">{error}</p> : null}
    </form>

    {experiment && result && point ? <>
      <section className="card lab-results">
        <div className="lab-section-title"><div><h2>策略效果对比</h2><p>{experiment.actual_start} — {experiment.actual_end} · {experiment.trading_days} 个交易日 · 初始 {money(experiment.config.initial_capital)} 元</p></div>
          <div className="lab-actions"><button type="button" className="button" onClick={exportMetrics}>导出指标 CSV</button><button type="button" className="button" onClick={() => download(`strategy-${experiment.experiment_id}.json`, JSON.stringify(experiment, null, 2), 'application/json')}>导出完整实验</button></div>
        </div>
        {experiment.st_coverage ? <p className="lab-hint">调仓信号日 ST 状态覆盖：{pct(experiment.st_coverage.known_fraction)}；未知 {experiment.st_coverage.unknown_count.toLocaleString()} 条股票日记录，{experiment.st_coverage.exclude_unknown ? '已按过滤规则排除' : '本次未启用 ST 过滤'}。</p> : null}
        <div className="lab-table-scroll"><table className="lab-table"><caption>整个实验区间的成本后表现；点击策略名称切换回放。</caption><thead><tr><th>策略</th><th>累计收益</th><th>年化收益</th><th>最大回撤</th><th>夏普</th><th>超额收益</th><th>正收益日</th><th>日均双边换手</th><th>累计成本</th></tr></thead>
          <tbody>{series.map((item, i) => <tr key={item.id} className={item.id === result.id ? 'is-selected' : ''}><th><i className="lab-color" style={{ background: COLORS[i] }} />{item.id === 'equal_weight' ? item.label : <button type="button" onClick={() => setSelected(item.id)}>{item.label}</button>}</th><td>{pct(item.metrics.total_return)}</td><td>{pct(item.metrics.annualized_return)}</td><td>{pct(item.metrics.max_drawdown)}</td><td>{item.metrics.sharpe?.toFixed(2) ?? '—'}</td><td>{pct(item.metrics.excess_return)}</td><td>{pct(item.metrics.win_rate)}</td><td>{pct(item.metrics.average_turnover)}</td><td>{money(item.metrics.total_cost)} 元</td></tr>)}</tbody>
        </table></div>
        <div className="lab-section-title lab-chart-controls"><div className="lab-actions"><button type="button" className="button" aria-pressed={mode === 'nav'} onClick={() => setMode('nav')}>净值曲线</button><button type="button" className="button" aria-pressed={mode === 'drawdown'} onClick={() => setMode('drawdown')}>回撤曲线</button></div><span>点击图表定位日期，或使用下方回放滑块</span></div>
        <ComparisonChart series={series} cursor={cursor} onCursor={seek} mode={mode} />
        <div className="lab-legend">{series.map((item, i) => <span key={item.id}><i className="lab-color" style={{ background: COLORS[i] }} />{item.label} {mode === 'nav' ? item.curve[cursor].nav.toFixed(4) : pct(item.curve[cursor].drawdown)}</span>)}</div>
      </section>

      <section className="card lab-replay">
        <div className="lab-section-title"><div><h2>逐日回放</h2><p>{result.label} · {point.trade_date} · {point.rebalance ? `调仓日，使用 ${point.signal_date} 收盘信号` : '持有日'}</p></div><label>回放策略<select value={result.id} onChange={(e) => setSelected(e.target.value)}>{experiment.results.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label></div>
        <div className="lab-playback">
          <button type="button" className="button" disabled={cursor === 0} onClick={() => seek(cursor - 1)}>上一日</button>
          <button type="button" className="button primary" onClick={() => { if (cursor === result.curve.length - 1) setCursor(0); setPlaying(!playing); }}>{playing ? '暂停' : '播放'}</button>
          <button type="button" className="button" disabled={cursor === result.curve.length - 1} onClick={() => seek(cursor + 1)}>下一日</button>
          <input aria-label="回放交易日" type="range" min="0" max={result.curve.length - 1} value={cursor} onChange={(e) => seek(Number(e.target.value))} />
          <select aria-label="跳转到交易日" value={cursor} onChange={(e) => seek(Number(e.target.value))}>{result.curve.map((p, i) => <option key={p.trade_date} value={i}>{p.trade_date}</option>)}</select>
        </div>
        <div className="lab-kpis"><div><span>当日资产</span><strong>{money(point.equity)}</strong><small>净值 {point.nav.toFixed(4)}</small></div><div><span>当日收益</span><strong>{pct(point.daily_return)}</strong><small>区间累计 {pct(point.nav - 1)}</small></div><div><span>当前回撤</span><strong>{pct(point.drawdown)}</strong><small>相对区间历史最高资产</small></div><div><span>可用现金</span><strong>{money(point.cash)}</strong><small>持有 {point.holding_count} 只股票</small></div></div>
        <div className="lab-replay-tables">
          <div><h3>收盘持仓</h3><div className="lab-table-scroll lab-scroll-limit"><table className="lab-table"><thead><tr><th>股票</th><th>权重</th><th>市值（元）</th></tr></thead><tbody>{point.holdings?.length ? point.holdings.map((holding) => <tr key={holding.symbol}><th>{holding.stock_name}<small>{holding.symbol}</small></th><td>{pct(holding.weight)}</td><td>{money(holding.market_value)}</td></tr>) : <tr><td colSpan={3}>当前空仓，资金保留为现金。</td></tr>}</tbody></table></div></div>
          <div><h3>当日成交与未成交记录</h3><div className="lab-table-scroll lab-scroll-limit"><table className="lab-table"><thead><tr><th>股票 / 方向</th><th>金额（元）</th><th>成本（元）</th><th>状态</th></tr></thead><tbody>{point.orders?.length ? point.orders.map((order, i) => <tr key={`${order.symbol}-${i}`}><th>{order.stock_name}<small>{order.symbol} · {order.side === 'buy' ? '买入' : '卖出'}</small></th><td>{money(order.notional)}</td><td>{money(order.cost)}</td><td>{order.status}</td></tr>) : <tr><td colSpan={4}>当日没有订单。</td></tr>}</tbody></table></div></div>
        </div>
        <p className="lab-hint">本次实验共 {result.metrics.trade_count} 笔成交，{result.metrics.blocked_orders} 笔因行情不可交易而未成交；未成交订单不会自动递延。</p>
      </section>
    </> : <section className="card lab-empty"><h2>从一组参数开始</h2><p>运行后将在这里展示多策略净值与回撤曲线。拖动日期滑块，可检查每一步选股、调仓和成本。</p></section>}

    <section className="card"><div className="lab-section-title"><h2>最近实验参数</h2>{history.length ? <button type="button" className="button" disabled={busy} onClick={() => { setHistory([]); try { localStorage.removeItem(HISTORY_KEY); } catch { setStorageNote('本地记录清理失败。'); } }}>清空记录</button> : null}</div><p className="lab-hint">此浏览器保留最近 8 组参数与结果摘要；恢复后重新运行会使用当前本地数据。完整结果可用上方按钮导出保存。</p>
      {storageNote ? <p role="status">{storageNote}</p> : null}
      <div className="lab-history">{history.length ? history.map((item) => <div key={item.experiment_id}><div><strong>{item.config.start_date} — {item.config.end_date}</strong><p>{item.summary}</p><small>观察 {item.config.lookback} 日 · 持仓 {item.config.top_k} · 每 {item.config.rebalance_days} 日调仓</small></div><button type="button" className="button" disabled={busy} onClick={() => { setConfig(item.config); setPlaying(false); setError(''); }}>恢复参数</button></div>) : <p>还没有运行过实验。</p>}</div>
    </section>
    <details className="card lab-methodology"><summary>计算口径与数据版本</summary><ul>{(experiment?.assumptions ?? metadata?.assumptions ?? []).map((text) => <li key={text}>{text}</li>)}</ul>{experiment ? <p>实验 {experiment.experiment_id} · 引擎 {experiment.engine_version}<br />行情指纹 {experiment.data_fingerprint}<br />生成时间 {new Date(experiment.created_at).toLocaleString('zh-CN')}</p> : null}</details>
  </div>;
}
