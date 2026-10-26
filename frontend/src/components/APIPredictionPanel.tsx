'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { useAssistantPreferences } from './AssistantPreferences';
import { useAssistantContext } from './AssistantRoot';
import { useApiPayload } from '../lib/useApiPayload';
import { displayValue, downloadFile, type VisualMetadata } from '../lib/visualization';
import { DEFAULT_PREDICTION_FACTORS, probabilityText, readPrediction, type AIPrediction, type PredictionInput } from '../lib/aiPrediction';

export default function APIPredictionPanel({ initialSymbol = '', onSelectModel }: { initialSymbol?: string; onSelectModel: (id: string) => void }) {
  const { connection, revision, rememberPage } = useAssistantPreferences();
  const { payload: meta, error: metaError, loading, reload } = useApiPayload<VisualMetadata>('/api/visualization');
  const [symbol, setSymbol] = useState(initialSymbol);
  useEffect(() => {
    if (/^\d{6}\.(SH|SZ|BJ)$/.test(symbol)) rememberPage('/scores', new URLSearchParams({ model: 'api_llm', symbol }).toString());
  }, [symbol, rememberPage]);
  const [horizon, setHorizon] = useState(5);
  const [band, setBand] = useState(1);
  const [factors, setFactors] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ key: string; data: AIPrediction } | null>(null);
  const active = useRef<AbortController | null>(null);
  const initialized = useRef(false);
  const catalog = meta?.metrics.filter(m => m.group === '因子') ?? [];
  useEffect(() => {
    if (!meta || initialized.current) return;
    initialized.current = true;
    if (!initialSymbol) setSymbol(meta.stocks[0]?.symbol ?? '');
    const available = meta.metrics.filter(m => m.group === '因子').map(m => m.id);
    const preferred = DEFAULT_PREDICTION_FACTORS.filter(id => available.includes(id));
    setFactors([...new Set([...preferred, ...available])].slice(0, Math.max(3, preferred.length)));
  }, [meta, initialSymbol]);
  const query: PredictionInput = { symbol, horizon_days: horizon, neutral_band_pct: band, factors };
  const key = JSON.stringify([query, revision, meta?.data_version]);
  const visible = result?.key === key ? result.data : null;
  const valid = !!meta?.stocks.some(s => s.symbol === symbol) && factors.length >= 3 && factors.length <= 10 &&
    factors.every(f => catalog.some(m => m.id === f)) && Number.isFinite(band) && band >= .1 && band <= 5;
  useEffect(() => {
    active.current?.abort(); active.current = null;
    setBusy(false); setResult(null); setError('');
    return () => { active.current?.abort(); active.current = null; };
  }, [key]);
  useAssistantContext({ score_model: 'api_llm', factor_names: factors, page_state: { prediction: {
    symbol, horizon_days: horizon, neutral_band_pct: Number.isFinite(band) ? band : null,
    status: visible?.status ?? 'not_generated', as_of: visible?.input.as_of ?? meta?.market_end,
    probabilities: visible ? { up: visible.probability_up, flat: visible.probability_flat, down: visible.probability_down } : null,
    calibration_status: 'uncalibrated', rationale: visible?.rationale,
  } } });
  function cancel() { active.current?.abort(); active.current = null; setBusy(false); }
  async function generate() {
    if (!connection || !valid || active.current) return;
    const controller = new AbortController(); active.current = controller;
    setBusy(true); setError(''); setResult(null);
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 85000);
    try {
      const response = await fetch('/api/assistant/predict', {
        method: 'POST', credentials: 'omit', cache: 'no-store', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-AI-API-Key': connection.apiKey },
        body: JSON.stringify({ ...query, provider: connection.provider.id, model: connection.model }),
      });
      const data = await response.json();
      if (active.current !== controller || controller.signal.aborted) return;
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '预测失败，请检查参数或稍后重试。');
      const prediction = readPrediction(data, query);
      if (prediction.provider !== connection.provider.id || prediction.model !== connection.model) throw new Error('预测模型与当前设置不符，请重试。');
      setResult({ key, data: prediction });
    } catch (failure) {
      if (active.current === controller) setError(timedOut ? '预测超时，请重试或更换模型。' : failure instanceof Error ? failure.message : '预测失败，请重试。');
    } finally {
      clearTimeout(timer);
      if (active.current === controller) { active.current = null; setBusy(false); }
    }
  }
  const impact = { supports_up: '支持上涨', supports_down: '支持下跌', mixed: '信号分歧' };
  return <section className="card ai-plan api-prediction" aria-label="API 大模型概率预测">
    <header><div><span className="ai-plan-eyebrow">✦ FACTOR FORECAST</span><h1>用因子，研究未来的可能性</h1></div><Link prefetch={false} href="/account">{connection ? 'AI 设置' : '配置 API Key'}</Link></header>
    <p className="ai-plan-description">结合本地日线与所选因子，由你的 API 模型估计上涨、震荡、下跌概率。概率为模型主观估计，尚未经过历史校准。</p>
    <div className="model-selector-panel"><label><span>预测模型</span><select aria-label="预测模型" value="api_llm" onChange={e => onSelectModel(e.target.value)}>
      <option value="cograsp">COGRASP 当前沪深300重训</option><option value="sentiment_event">情绪/事件融合 LightGBM</option><option value="api_llm">API 大模型 · 因子概率估计</option>
    </select></label><span>{connection ? `${connection.provider.label} · ${connection.model}` : '使用个人设置中的模型和 API Key'}</span></div>
    {!connection && <p className="ai-plan-setup">请到<Link prefetch={false} href="/account">个人设置</Link>填写 API Key 和模型名称，再返回生成预测。</p>}
    {loading && !meta && <p role="status">正在读取股票和因子目录…</p>}
    {metaError && <p role="alert">数据目录加载失败。<button type="button" onClick={reload}>重新加载</button></p>}
    {meta && <form onSubmit={e => { e.preventDefault(); void generate(); }}>
      <div className="api-prediction-controls">
        <label>预测股票<input aria-label="预测股票" list="ai-prediction-stocks" value={symbol} onChange={e => setSymbol(e.target.value.trim().toUpperCase())} placeholder="例如 000001.SZ" />
          <datalist id="ai-prediction-stocks">{meta.stocks.map(s => <option key={s.symbol} value={s.symbol}>{s.stock_name}</option>)}</datalist>
          <small>{meta.stocks.find(s => s.symbol === symbol)?.stock_name ?? '请选择本地股票池中的完整代码'}</small></label>
        <label>预测周期<select aria-label="预测周期" value={horizon} onChange={e => setHorizon(Number(e.target.value))}>{[1, 5, 10, 20].map(n => <option key={n} value={n}>未来 {n} 个交易日</option>)}</select></label>
        <label>震荡范围（±%）<input aria-label="震荡范围" type="number" min="0.1" max="5" step="0.1" value={Number.isFinite(band) ? band : ''} onChange={e => setBand(e.target.value === '' ? NaN : Number(e.target.value))} /></label>
      </div>
      <details className="api-prediction-factors" open><summary>参与分析的因子 · 已选 {factors.length} / 10（至少 3 个）</summary>
        <input aria-label="搜索预测因子" value={search} onChange={e => setSearch(e.target.value)} placeholder="搜索因子名称或代码" />
        <div>{catalog.filter(m => `${m.label} ${m.id}`.toLowerCase().includes(search.toLowerCase())).map(m => <label key={m.id} title={m.description}>
          <input type="checkbox" checked={factors.includes(m.id)} disabled={!factors.includes(m.id) && factors.length >= 10} onChange={e => setFactors(current => e.target.checked ? [...current, m.id] : current.filter(id => id !== m.id))} />
          <span>{m.label}<small>{m.id}</small></span></label>)}</div>
      </details>
      <div className="ai-plan-actions"><span>行情截至 {meta.market_end} · {meta.price_basis} · 每次分析 1 只股票</span>
        {busy ? <button type="button" onClick={cancel}>停止预测</button> : <button type="submit" disabled={!connection || !valid}>生成概率预测</button>}</div>
      <p className="api-prediction-note" role="status">{busy ? '模型正在分析价格与因子，请稍候…' : `点击生成后，将所选股票的日线与因子发送到${connection?.provider.label ?? '所选模型服务'}，可能产生 API 费用。`}</p>
    </form>}
    {error && <p className="ai-plan-error" role="alert">{error}</p>}
    {visible && <div className="api-prediction-result" aria-label="AI 概率预测结果">
      <header><div><h2>{visible.input.stock_name} · {visible.input.symbol}</h2><p className="api-prediction-note">截至 {visible.input.as_of} · 未来 {visible.input.horizon_days} 个交易日 · {visible.model} · 未校准</p></div>
        <button type="button" onClick={() => downloadFile(JSON.stringify(visible, null, 2), `AI预测_${symbol}_${visible.input.as_of}.json`, 'application/json')}>导出预测快照</button></header>
      {visible.status === 'estimated' ? <div className="api-probabilities">{([
        ['上涨', visible.probability_up, 'up'], ['震荡', visible.probability_flat, 'flat'], ['下跌', visible.probability_down, 'down'],
      ] as const).map(([label, probability, direction]) => <div key={direction} className={`api-probability api-probability--${direction}`}>
        <span>{label}概率</span><strong>{probabilityText(probability)}</strong><div className="api-probability-track"><i style={{ width: `${(probability ?? 0) * 100}%` }} /></div>
      </div>)}</div> : <p className="ai-plan-setup">模型认为依据不足，本次未给出概率。</p>}
      <p className="api-prediction-note">{visible.input.event_definition}</p><p>{visible.rationale}</p>
      {!!visible.evidence.length && <div className="api-prediction-evidence">{visible.evidence.map(e => {
        const factor = visible.input.factors.find(f => f.id === e.factor)!;
        return <article key={e.factor}><span>{impact[e.impact]}</span><h3>{factor.label}</h3><small>实际值 {displayValue(factor.value)} · {factor.value_date ?? '缺失'}</small><p>{e.explanation}</p></article>;
      })}</div>}
      <h3>局限与反证</h3><ul>{visible.risks.map((risk, i) => <li key={i}>{risk}</li>)}</ul>
      <details className="api-prediction-audit"><summary>查看输入因子与历史参考</summary>
        <div className="api-prediction-table"><table><thead><tr><th>因子</th><th>实际值</th><th>观测日期</th></tr></thead><tbody>{visible.input.factors.map(f => <tr key={f.id}><td title={f.formula}>{f.label}</td><td>{f.value === null ? '缺失' : displayValue(f.value)}</td><td>{f.value_date ?? '—'}</td></tr>)}</tbody></table></div>
        <p>历史参考：{visible.input.history_reference.sample_count} 个区间；上涨 {probabilityText(visible.input.history_reference.probability_up)}、震荡 {probabilityText(visible.input.history_reference.probability_flat)}、下跌 {probabilityText(visible.input.history_reference.probability_down)}。</p>
        <p>{visible.input.history_reference.note}</p><p>数据版本 {visible.input.data_version} · 快照 {visible.input.snapshot_id}</p>
      </details><p className="api-prediction-note">{visible.notice}</p>
    </div>}
  </section>;
}
