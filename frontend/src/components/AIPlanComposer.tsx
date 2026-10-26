'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useAssistantPreferences } from './AssistantPreferences';

type Plan<T> = { task: string; status: 'ready' | 'needs_changes'; summary: string; notes: string[]; unsupported: string[]; config: T | null; key: string };
type Props<T> = {
  task: 'visualization' | 'strategy'; current: T; contextKey: string; disabled?: boolean;
  parseConfig: (value: unknown) => T;
  preview: (config: T) => ReactNode;
  onApply: (config: T, run: boolean) => void | Promise<void>;
};

/** Shared BYOK form. Generated configurations stay drafts until explicitly applied. */
export function AIPlanComposer<T>({ task, current, contextKey, disabled = false, parseConfig, preview, onApply }: Props<T>) {
  const { connection, revision } = useAssistantPreferences();
  const [prompt, setPrompt] = useState('');
  const [plan, setPlan] = useState<Plan<T> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const active = useRef<AbortController | null>(null);
  const key = JSON.stringify([task, revision, contextKey, current]);
  const visible = plan?.key === key ? plan : null;
  const visual = task === 'visualization';
  const examples = visual
    ? ['对比平安银行和招商银行近三个月的价格与成交量，分别用折线图和柱状图', '保留当前股票和时间，用散点图看 20 日收益率与 20 日波动率的关系']
    : ['比较近半年的动量和低波动策略，观察 20 日，每 5 个交易日调仓，持仓 10 只', '比较反转和均线趋势，观察 10 日，持仓 5 只，手续费 3 基点，滑点 5 基点'];

  useEffect(() => {
    active.current?.abort(); active.current = null;
    setBusy(false); setPlan(null); setError('');
    return () => { active.current?.abort(); active.current = null; };
  }, [key]);

  function cancel() { active.current?.abort(); active.current = null; setBusy(false); }
  function edit(value: string) { cancel(); setPrompt(value); setPlan(null); setError(''); }
  async function generate() {
    if (!connection || !prompt.trim() || disabled || active.current) return;
    const controller = new AbortController(); active.current = controller;
    setBusy(true); setError(''); setPlan(null);
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; controller.abort(); }, 85000);
    try {
      const response = await fetch('/api/assistant/plan', {
        method: 'POST', credentials: 'omit', cache: 'no-store', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-AI-API-Key': connection.apiKey },
        body: JSON.stringify({ provider: connection.provider.id, model: connection.model, task, prompt: prompt.trim(), current }),
      });
      const payload = await response.json();
      if (active.current !== controller || controller.signal.aborted) return;
      if (!response.ok) throw new Error(typeof payload.detail === 'string' ? payload.detail : '配置生成失败，请检查需求或稍后重试。');
      if (payload.task !== task || !['ready', 'needs_changes'].includes(payload.status) || typeof payload.summary !== 'string' ||
          !Array.isArray(payload.notes) || !Array.isArray(payload.unsupported) ||
          [...payload.notes, ...payload.unsupported].some(v => typeof v !== 'string')) throw new Error('模型方案格式无效，请重新生成。');
      if (payload.status === 'ready' && (payload.unsupported.length || !payload.config)) throw new Error('方案包含未支持的要求，无法应用。');
      setPlan({ ...payload, config: payload.status === 'ready' ? parseConfig(payload.config) : null, key });
    } catch (failure) {
      if (active.current === controller) setError(timedOut ? '生成超时，请重试或更换模型。' : failure instanceof Error ? failure.message : '生成失败，请重试。');
    } finally {
      clearTimeout(timer);
      if (active.current === controller) { active.current = null; setBusy(false); }
    }
  }
  async function apply(run: boolean) {
    if (!visible?.config || disabled) return;
    try { await onApply(visible.config, run); setPlan(null); }
    catch (failure) { setError(failure instanceof Error ? failure.message : '无法应用方案，请检查配置。'); }
  }

  return <section className="ai-plan" aria-label={visual ? 'AI 生成看板' : 'AI 策略实验员'}>
    <header><div><span className="ai-plan-eyebrow">✦ AI RESEARCH</span><h2>{visual ? '一句话，生成研究看板' : '把策略想法变成一次实验'}</h2></div>
      <Link prefetch={false} href="/account">{connection ? 'AI 设置' : '配置 API Key'}</Link></header>
    <p className="ai-plan-description">{visual ? '描述股票、区间和想看的指标，生成后可继续编辑图表。' : '支持动量、反转、低波动和均线趋势的独立比较；可设置观察期、调仓、成本和排除条件。'} 相对日期以本地最新行情为截止。</p>
    {!connection && <p className="ai-plan-setup">请先到<Link prefetch={false} href="/account">个人设置</Link>填写模型与 API Key。已有看板和手动实验仍可使用。</p>}
    <form onSubmit={e => { e.preventDefault(); void generate(); }}>
      <label className="sr-only" htmlFor={`ai-plan-${task}`}>{visual ? '描述看板需求' : '描述策略需求'}</label>
      <textarea id={`ai-plan-${task}`} value={prompt} onChange={e => edit(e.target.value)} maxLength={3000} rows={3} placeholder={examples[0]} disabled={disabled} />
      <div className="ai-plan-actions"><span>{busy ? '正在理解需求并校验配置…' : '生成配置草案，应用后可继续调整。'}</span>
        {busy ? <button type="button" onClick={cancel}>停止生成</button> : <button type="submit" disabled={!connection || !prompt.trim() || disabled}>{visual ? '生成看板方案' : '生成策略方案'}</button>}</div>
    </form>
    <div className="ai-plan-examples">{examples.map(example => <button type="button" key={example} disabled={disabled} onClick={() => edit(example)}>{example}</button>)}</div>
    {error && <p role="alert" className="ai-plan-error">{error}</p>}
    {visible && <div className="ai-plan-preview" aria-label="AI 配置草案">
      <strong>{visible.status === 'ready' ? '配置草案 · 尚未应用' : '这些要求需要调整'}</strong><p>{visible.summary}</p>
      {visible.config && preview(visible.config)}
      {!!visible.notes.length && <ul>{visible.notes.map((note, i) => <li key={i}>{note}</li>)}</ul>}
      {!!visible.unsupported.length && <ul className="ai-plan-error">{visible.unsupported.map((note, i) => <li key={i}>{note}</li>)}</ul>}
      {visible.config && <div className="ai-plan-actions"><button type="button" disabled={disabled} onClick={() => void apply(false)}>{visual ? '应用到看板' : '填入参数，继续编辑'}</button>
        {!visual && <button type="button" disabled={disabled} onClick={() => void apply(true)}>应用并运行比较</button>}</div>}
    </div>}
  </section>;
}
