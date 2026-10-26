'use client';

import { useEffect, useRef, useState } from 'react';
import { useApiPayload } from '../lib/useApiPayload';
import { useAssistantContext } from './AssistantRoot';
import { VisualChart } from './VisualChart';
import { ResizableVisualCard } from './ResizableVisualCard';
import { AIPlanComposer } from './AIPlanComposer';
import { BOARD_KEY, CHART_TYPES, boardRequest, chartSize, dataCsv, defaultBoard, downloadFile, requestKey, restoreBoard, validateBoard,
  type Board, type ChartConfig, type ChartKind, type VisualData, type VisualMetadata } from '../lib/visualization';

export function VisualizationWorkbench() {
  const { payload, error, reload } = useApiPayload<VisualMetadata>('/api/visualization');
  return <section className="visual-workbench">
    <header className="visual-heading"><div><span className="visual-eyebrow">VISUAL RESEARCH / 日频研究</span><h1>数据可视化</h1><p>把价格与因子放在同一张看板，让研究过程看得见。</p></div><span className="visual-heading-badge">自由组合 · 历史对比</span></header>
    {error ? <div role="alert" className="visual-notice">无法读取可视化数据目录。<button type="button" onClick={reload}>重试</button></div> : payload ? <Workbench meta={payload} /> : <div role="status" className="visual-empty">正在读取股票与因子目录…</div>}
  </section>;
}

export function Workbench({ meta }: { meta: VisualMetadata }) {
  const [board, setBoard] = useState<Board>(() => defaultBoard(meta));
  const [data, setData] = useState<VisualData | null>(null);
  const [dataKey, setDataKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [dragged, setDragged] = useState<string | null>(null);
  const pending = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const importInput = useRef<HTMLInputElement>(null);
  const key = requestKey(board);
  const current = dataKey === key ? data : null;
  const validation = validateBoard(board, meta);
  const selectedFactors = boardRequest(board).metrics.filter(m => meta.metrics.some(item => item.id === m && item.group === '因子'));
  useAssistantContext({ factor_names: selectedFactors, page_state: { visualization: {
    ...(current ? boardRequest(board) : {}), loaded: Boolean(current),
    charts: board.cards.map(c => ({ title: c.title, type: c.type, metric: c.metric, xMetric: c.type === 'scatter' ? c.xMetric : undefined, normalize: c.normalize })),
  } } });

  async function load(next: Board) {
    const failure = validateBoard(next, meta);
    if (failure) { setError(failure); return; }
    pending.current?.abort();
    const controller = new AbortController(); pending.current = controller;
    const id = ++generation.current;
    setLoading(true); setError(''); setData(null); setDataKey('');
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const response = await fetch('/api/visualization/series', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(boardRequest(next)), signal: controller.signal, cache: 'no-store' });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '图表参数或数据不可用，请检查后重试。');
      if (generation.current === id) { setData(result); setDataKey(requestKey(next)); }
    } catch (reason) {
      if (generation.current === id) setError(reason instanceof Error && reason.name !== 'AbortError' ? reason.message : '加载超时或已取消，请重试。');
    } finally { clearTimeout(timeout); if (generation.current === id) setLoading(false); }
  }

  useEffect(() => {
    let initial = defaultBoard(meta);
    try { const saved = localStorage.getItem(BOARD_KEY); if (saved) { initial = restoreBoard(saved, meta); setNotice('已恢复本机保存的看板。'); } }
    catch { setNotice('保存的看板无法恢复，已使用默认布局。'); }
    setBoard(initial); void load(initial);
    return () => { generation.current++; pending.current?.abort(); };
    // Metadata identifies the available universe; user edits do not trigger queries.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta]);

  function updateCard(id: string, patch: Partial<ChartConfig>) {
    setBoard(b => ({ ...b, cards: b.cards.map(c => c.id === id ? { ...c, ...patch } : c) }));
  }
  function move(id: string, target: string) {
    setBoard(b => { const cards = [...b.cards]; const from = cards.findIndex(c => c.id === id), to = cards.findIndex(c => c.id === target);
      if (from < 0 || to < 0) return b; const [item] = cards.splice(from, 1); cards.splice(to, 0, item); return { ...b, cards }; });
  }
  function save() {
    if (validation) { setError(validation); return; }
    try { localStorage.setItem(BOARD_KEY, JSON.stringify(board)); setNotice('看板已保存到当前浏览器，下次打开自动恢复。'); }
    catch { setError('浏览器无法保存，请使用“导出布局”备份。'); }
  }
  async function importBoard(file: File | undefined) {
    if (!file) return;
    try {
      if (file.size > 16000) throw new Error('布局文件过大。');
      const next = restoreBoard(await file.text(), meta); setBoard(next); setNotice('布局已导入，点击保存可保留在本机。'); void load(next);
    } catch (reason) { setError(reason instanceof Error ? reason.message : '无法读取布局文件。'); }
    if (importInput.current) importInput.current.value = '';
  }
  function metricOptions() {
    return ['行情', '因子'].map(group => <optgroup key={group} label={group}>{meta.metrics.filter(m => m.group === group).map(m => <option key={m.id} value={m.id}>{m.label === m.id ? m.id : `${m.label} · ${m.id}`}</option>)}</optgroup>);
  }
  const visibleStocks = meta.stocks.filter(s => `${s.symbol} ${s.stock_name}`.toLowerCase().includes(search.toLowerCase()));
  return <>
    <div className="visual-summary"><span><i />本地日频</span><span>行情截至 <strong>{meta.market_end}</strong></span><span>因子截至 <strong>{meta.factor_end || '暂无'}</strong></span><span>{meta.stocks.length} 只股票 · {meta.metrics.filter(m => m.group === '因子').length} 个因子</span></div>
    <AIPlanComposer task="visualization" current={board} contextKey={meta.data_version}
      parseConfig={value => restoreBoard(JSON.stringify(value), meta)}
      onApply={next => { const failure = validateBoard(next, meta); if (failure) throw new Error(failure);
        setBoard(next); setNotice('AI 看板已应用，可继续编辑；点击“保存看板”保留在本机。'); void load(next); }}
      preview={next => <><dl className="ai-plan-facts"><div><dt>看板</dt><dd>{next.title}</dd></div>
        <div><dt>股票</dt><dd>{next.symbols.map(symbol => `${meta.stocks.find(s => s.symbol === symbol)?.stock_name || symbol} (${symbol})`).join('、')}</dd></div>
        <div><dt>历史区间</dt><dd>{next.start_date} — {next.end_date}</dd></div></dl>
        <ol>{next.cards.map(card => <li key={card.id}>{card.title} · {CHART_TYPES[card.type]} · {meta.metrics.find(m => m.id === card.metric)?.label}
          {card.type === 'scatter' ? ` / X：${meta.metrics.find(m => m.id === card.xMetric)?.label}` : ''} · {card.normalize ? '标准化' : '原始值'}</li>)}</ol></>} />
    <section className="visual-controls" aria-label="看板设置">
      <div className="visual-toolbar"><label className="visual-title-field">看板名称<input aria-label="看板名称" maxLength={60} value={board.title} onChange={e => setBoard(b => ({ ...b, title: e.target.value }))} /></label>
        <div className="visual-actions"><button type="button" onClick={save}>保存看板</button><button type="button" onClick={() => downloadFile(JSON.stringify(board, null, 2), 'research-board.json', 'application/json')}>导出布局</button>
          <button type="button" onClick={() => importInput.current?.click()}>导入布局</button><input ref={importInput} type="file" accept=".json,application/json" hidden aria-label="导入看板文件" onChange={e => void importBoard(e.target.files?.[0])} />
          <button type="button" onClick={() => { const next = defaultBoard(meta); setBoard(next); setNotice('已恢复默认布局，尚未覆盖保存的看板。'); void load(next); }}>默认布局</button></div>
      </div>
      <div className="visual-config-grid"><fieldset className="visual-stock-picker"><legend>选择对比股票 <span>{board.symbols.length} / 4</span></legend>
        <input type="search" aria-label="搜索股票" placeholder="搜索代码或名称" value={search} onChange={e => setSearch(e.target.value)} />
        <div className="visual-selected">{board.symbols.map(symbol => <button key={symbol} type="button" aria-label={`移除 ${symbol}`} onClick={() => setBoard(b => ({ ...b, symbols: b.symbols.filter(s => s !== symbol) }))}>{meta.stocks.find(s => s.symbol === symbol)?.stock_name || symbol}<span>×</span></button>)}</div>
        <div className="visual-stock-list">{visibleStocks.map(s => <label key={s.symbol}><input type="checkbox" checked={board.symbols.includes(s.symbol)} disabled={board.symbols.length >= 4 && !board.symbols.includes(s.symbol)}
          onChange={e => { const checked = e.target.checked; setBoard(b => ({ ...b, symbols: checked ? [...b.symbols, s.symbol] : b.symbols.filter(v => v !== s.symbol) })); }} /><span>{s.stock_name}<small>{s.symbol}</small></span></label>)}{!visibleStocks.length && <p>未找到匹配的股票。</p>}</div>
      </fieldset><div className="visual-date-settings"><div className="visual-date-pair"><label>开始日期<input type="date" min={meta.market_start} max={board.end_date} value={board.start_date} onChange={e => setBoard(b => ({ ...b, start_date: e.target.value }))} /></label>
        <label>结束日期<input type="date" min={board.start_date || meta.market_start} max={meta.market_end} value={board.end_date} onChange={e => setBoard(b => ({ ...b, end_date: e.target.value }))} /></label></div>
        <p>可用历史：{meta.market_start} — {meta.market_end}。选择的股票和日期应用到整个看板；每张图可单独选择因子与展示方式。</p>
        <div className="visual-actions"><button className="visual-primary" type="button" disabled={Boolean(validation)} onClick={() => void load(board)}>{loading ? '重新加载图表' : '更新图表'}</button>
          <button type="button" disabled={!current || loading} onClick={() => current && downloadFile(dataCsv(current), `research-data-${current.end_date}.csv`, 'text/csv;charset=utf-8')}>导出原始数据 CSV</button></div>
        <span className="visual-load-status" role="status">{loading ? '正在按需读取历史数据…' : validation || (!current ? '选择已改变，点击“更新图表”应用。' : `已加载 ${current.dates.length} 个交易日 · ${current.series.length} 条序列`)}</span>
      </div></div>
    </section>
    {error && <p className="visual-error" role="alert">{error}</p>}{notice && <p className="visual-notice" role="status">{notice}</p>}
    <div className="visual-board-heading"><div><h2>{board.title || '研究看板'}</h2><p>左上把手调整顺序，右下角拖动缩放；宽度吸附网格，高度自动对齐。调整后点击“保存看板”。最多 8 张图表。</p></div><button type="button" className="visual-primary" disabled={board.cards.length >= 8} onClick={() => setBoard(b => ({ ...b, cards: [...b.cards,
      { id: crypto.randomUUID(), title: '新的观察图', type: 'line', metric: b.cards[0]?.metric || meta.metrics[0].id, xMetric: 'close', wide: false, normalize: false }] }))}>＋ 添加图表</button></div>
    <div className="visual-board">{board.cards.map((card, index) => <ResizableVisualCard key={card.id} card={card} cards={board.cards}
      onResize={size => updateCard(card.id, size)} className={dragged === card.id ? 'visual-card--dragging' : ''}
      onDragOver={event => { if (dragged) event.preventDefault(); }} onDrop={event => { event.preventDefault(); if (dragged) move(dragged, card.id); setDragged(null); }}>
      <header className="visual-card-header"><span className="visual-drag-handle" draggable onDragStart={e => { setDragged(card.id); e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', card.id); }} onDragEnd={() => setDragged(null)} title="拖动调整顺序" aria-hidden="true">⠿</span>
        <h3>{card.title || '未命名图表'}</h3><span>{CHART_TYPES[card.type]}</span><div className="visual-card-actions">
          <button type="button" aria-label={`${card.title}前移`} disabled={index === 0} onClick={() => move(card.id, board.cards[index - 1].id)}>↑</button>
          <button type="button" aria-label={`${card.title}后移`} disabled={index === board.cards.length - 1} onClick={() => move(card.id, board.cards[index + 1].id)}>↓</button>
          <button type="button" aria-label={`删除${card.title}`} disabled={board.cards.length === 1} onClick={() => setBoard(b => ({ ...b, cards: b.cards.filter(c => c.id !== card.id) }))}>×</button></div>
      </header>
      <details className="visual-card-config"><summary>编辑图表 · {meta.metrics.find(m => m.id === card.metric)?.label}</summary><div>
        <label>图表标题<input maxLength={60} value={card.title} onChange={e => updateCard(card.id, { title: e.target.value })} /></label>
        <label>图表类型<select value={card.type} onChange={e => updateCard(card.id, { type: e.target.value as ChartKind })}>{Object.entries(CHART_TYPES).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
        <label>{card.type === 'scatter' ? 'Y 轴指标' : '股票行情 / 因子'}<select value={card.metric} onChange={e => updateCard(card.id, { metric: e.target.value })}>{metricOptions()}</select></label>
        {card.type === 'scatter' && <label>X 轴指标<select value={card.xMetric} onChange={e => updateCard(card.id, { xMetric: e.target.value })}>{metricOptions()}</select></label>}
        <label>显示宽度<select value={chartSize(card).columns} onChange={e => updateCard(card.id, { columns: Number(e.target.value), wide: Number(e.target.value) === 12 })}>
          {Array.from({ length: 9 }, (_, i) => i + 4).map(n => <option key={n} value={n}>{({ 4: '三分之一', 6: '半宽', 8: '三分之二', 12: '整行' } as Record<number, string>)[n] || `${n} / 12 列`}</option>)}
        </select></label>
        <label>图表高度<select value={chartSize(card).height} onChange={e => updateCard(card.id, { height: Number(e.target.value) })}>
          {[...new Set([400, 480, 600, 720, 840, 960, 1200, chartSize(card).height])].sort((a, b) => a - b).map(height => <option key={height} value={height}>{height} px</option>)}
        </select></label>
        <label>数值处理<select value={card.normalize ? 'zscore' : 'raw'} onChange={e => updateCard(card.id, { normalize: e.target.value === 'zscore' })}><option value="raw">原始数值</option><option value="zscore">标准化 Z-score</option></select></label>
      </div><p>{meta.metrics.find(m => m.id === card.metric)?.description || '使用对应交易日的原始观测值。'}</p></details>
      {current ? <VisualChart card={card} data={current} /> : <div className="visual-empty">{loading ? '正在加载历史数据…' : '点击“更新图表”显示当前选择。'}</div>}
    </ResizableVisualCard>)}</div>
    <aside className="visual-methodology"><strong>数据口径</strong><p>{meta.notes.join(' ')} 当前研究价口径：{current?.price_basis || meta.price_basis}。CSV 始终导出原始值，布局保存到当前浏览器；导出布局文件可在其他设备恢复。</p></aside>
  </>;
}
