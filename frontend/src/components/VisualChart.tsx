'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { displayValue, downloadFile, normalized, segments, type ChartConfig, type VisualData } from '../lib/visualization';

const COLORS = ['#38bdf8', '#f5c84c', '#c4a2ff', '#69dcb1'];
const L = 76, T = 24;
function bounds(values: number[], zero: boolean): [number, number] {
  let lo = values.length ? Math.min(...values) : 0, hi = values.length ? Math.max(...values) : 1;
  if (zero) { lo = Math.min(0, lo); hi = Math.max(0, hi); }
  const pad = hi === lo ? Math.max(Math.abs(lo) * .05, .001) : (hi - lo) * .08;
  return [lo - pad, hi + pad];
}

export function VisualChart({ card, data }: { card: ChartConfig; data: VisualData }) {
  const svg = useRef<SVGSVGElement>(null);
  const plot = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState({ width: 840, height: 310 });
  const W = viewport.width, H = viewport.height, R = W - 24, B = H - 52;
  const [cursor, setCursor] = useState<number | null>(null);
  const [showTable, setShowTable] = useState(false);
  const series = useMemo(() => data.series.filter(s => s.metric === card.metric).map(s => ({ ...s,
    values: card.normalize ? normalized(s.values) : s.values,
    x: (() => { const v = data.series.find(t => t.symbol === s.symbol && t.metric === card.xMetric)?.values || []; return card.normalize ? normalized(v) : v; })(),
  })), [data, card.metric, card.xMetric, card.normalize]);
  const metric = data.metrics.find(m => m.id === card.metric);
  const xMetric = data.metrics.find(m => m.id === card.xMetric);
  const scatter = card.type === 'scatter';
  const valid = series.flatMap(s => s.values.flatMap((y, i) => y !== null && (!scatter || s.x[i] != null) ? [y] : []));
  const [ylo, yhi] = bounds(valid, card.type === 'bar' || card.type === 'area');
  const [xlo, xhi] = bounds(series.flatMap(s => s.x.filter((x, i): x is number => x !== null && s.values[i] != null)), false);
  const y = (v: number) => B - (v - ylo) / (yhi - ylo) * (B - T);
  const x = (i: number) => L + (i + .5) / Math.max(data.dates.length, 1) * (R - L);
  const sx = (v: number) => L + (v - xlo) / (xhi - xlo) * (R - L);
  const active = Math.min(cursor ?? data.dates.length - 1, data.dates.length - 1);
  const unit = card.normalize ? 'Z-score（各序列独立标准化）' : metric?.unit;
  useEffect(() => {
    const node = plot.current;
    if (!node || typeof ResizeObserver === 'undefined') return;
    const observer = new ResizeObserver(entries => {
      const rect = entries[0]?.contentRect;
      if (!rect?.width || !rect.height) return;
      const next = { width: Math.round(rect.width), height: Math.round(rect.height) };
      setViewport(old => old.width === next.width && old.height === next.height ? old : next);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [data, card.metric, card.xMetric, card.type]);
  if (!data.dates.length || !valid.length) return <div className="visual-empty">此区间没有可绘制的数据。请调整日期或指标，缺失值不会按 0 绘制。</div>;
  function exportSvg() {
    if (!svg.current) return;
    const clone = svg.current.cloneNode(true) as SVGSVGElement;
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    clone.removeAttribute('class');
    clone.setAttribute('width', String(W));
    clone.setAttribute('style', 'background:#0c1725;color:#aabbd0;font-family:Arial,sans-serif');
    const desc = document.createElementNS('http://www.w3.org/2000/svg', 'desc');
    desc.textContent = `${card.title}; ${data.start_date} 至 ${data.end_date}; ${metric?.label}; ${unit}; ${data.price_basis}; 数据版本 ${data.data_version}. ${series.map(s => s.stock_name + ' ' + s.symbol).join(', ')}`;
    clone.prepend(desc);
    let top = H + 20;
    const textLine = (text: string, color = '#b7cad8') => {
      const chars = Array.from(text), length = Math.max(12, Math.floor((W - 60) / 12));
      for (let offset = 0; offset < chars.length; offset += length) {
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        line.setAttribute('x', '30'); line.setAttribute('y', String(top)); line.setAttribute('fill', color); line.setAttribute('font-size', '12');
        line.textContent = chars.slice(offset, offset + length).join(''); clone.append(line); top += 18;
      }
    };
    textLine(`${card.title} · ${metric?.label} · ${unit}`);
    textLine(`${data.start_date} — ${data.end_date} · 数据版本 ${data.data_version}`);
    series.forEach((s, i) => textLine(`${s.stock_name} ${s.symbol}`, COLORS[i]));
    clone.setAttribute('height', String(top));
    clone.setAttribute('viewBox', `0 0 ${W} ${top}`);
    downloadFile(new XMLSerializer().serializeToString(clone), `chart-${card.id}.svg`, 'image/svg+xml');
  }
  return <>
    <div className="visual-chart-meta"><span>{metric?.label} · {unit}</span><button type="button" onClick={exportSvg}>导出 SVG</button></div>
    <div ref={plot} className="visual-plot"><svg ref={svg} className="visual-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${card.title}，${metric?.label}，${data.start_date} 至 ${data.end_date}`}
      onPointerMove={event => { if (!scatter) { const box = event.currentTarget.getBoundingClientRect(); setCursor(Math.max(0, Math.min(data.dates.length - 1, Math.floor(((event.clientX - box.left) / box.width * W - L) / (R - L) * data.dates.length)))); } }}>
      <title>{card.title} · {metric?.label}</title>
      {[0, 1, 2, 3, 4].map(i => { const value = ylo + (yhi - ylo) * i / 4; return <g key={i}>
        <line x1={L} x2={R} y1={y(value)} y2={y(value)} stroke="#29394d" strokeDasharray="3 5" />
        <text x={L - 9} y={y(value) + 4} textAnchor="end" fill="#9eafc4" fontSize="11">{displayValue(value)}</text>
      </g>; })}
      {ylo < 0 && yhi > 0 && <line x1={L} x2={R} y1={y(0)} y2={y(0)} stroke="#5c7189" />}
      {series.map((s, si) => <g key={s.symbol} fill={COLORS[si]} stroke={COLORS[si]}>
        {scatter ? s.values.map((v, i) => v !== null && s.x[i] != null ? <circle key={i} cx={sx(s.x[i]!)} cy={y(v)} r="3" opacity=".65"><title>{s.stock_name} · {data.dates[i]} · X {displayValue(s.x[i])} / Y {displayValue(v)}</title></circle> : null)
          : card.type === 'bar' ? s.values.map((v, i) => v === null ? null : <rect key={i} x={x(i) - (R - L) / data.dates.length * .4 + si * (R - L) / data.dates.length * .8 / series.length}
            y={Math.min(y(v), y(0))} width={Math.max(.2, (R - L) / data.dates.length * .8 / series.length)} height={Math.max(v === 0 ? 0 : .6, Math.abs(y(v) - y(0)))} stroke="none" opacity=".8" />)
          : segments(s.values).map((segment, i) => <g key={i}>
            {card.type === 'area' && <path d={`M${x(segment[0].index)},${y(0)} ${segment.map(p => `L${x(p.index)},${y(p.value)}`).join(' ')} L${x(segment.at(-1)!.index)},${y(0)} Z`} opacity=".12" stroke="none" />}
            <polyline points={segment.map(p => `${x(p.index)},${y(p.value)}`).join(' ')} fill="none" strokeWidth="1.8" />
            {segment.length === 1 && <circle cx={x(segment[0].index)} cy={y(segment[0].value)} r="2.5" />}
          </g>)}
      </g>)}
      {!scatter && <line x1={x(active)} x2={x(active)} y1={T} y2={B} stroke="#a2b7ca" strokeDasharray="4 4" opacity=".6" />}
      {(W < 400 ? [0, 1] : [0, .5, 1]).map(f => <text key={f} x={L + (R - L) * f} y={B + 23} textAnchor={f === 0 ? 'start' : f === 1 ? 'end' : 'middle'} fill="#9eafc4" fontSize="11">
        {scatter ? displayValue(xlo + (xhi - xlo) * f) : data.dates[Math.round((data.dates.length - 1) * f)]}
      </text>)}
      {scatter && <text x={(L + R) / 2} y={H - 3} textAnchor="middle" fill="#9eafc4" fontSize="11">X：{xMetric?.label} · {card.normalize ? 'Z-score' : xMetric?.unit}</text>}
    </svg></div>
    <div className="visual-legend">{series.map((s, i) => <span key={s.symbol}><i style={{ background: COLORS[i] }} />{s.stock_name} <small>{s.symbol}</small></span>)}</div>
    {!scatter && <div className="visual-cursor"><label>查看日期 <input aria-label={`${card.title}查看日期`} type="range" min="0" max={data.dates.length - 1} value={active} onChange={e => setCursor(Number(e.target.value))} /></label>
      <div><strong>{data.dates[active]}</strong>{series.map(s => <span key={s.symbol}>{s.stock_name} {displayValue(s.values[active])}</span>)}</div></div>}
    <p className="visual-chart-footnote">{scatter ? '仅绘制同一股票、同一交易日同时有 X / Y 数值的点；悬停查看详情。相关关系不等于因果关系。' : '横轴按交易日排列；空缺处断开。滑动日期条可查看具体数值。'}{card.normalize && ' 标准化使用整个所选区间，只用于图形比较；常数序列显示为 0。'}</p>
    <details className="visual-table" onToggle={e => setShowTable(e.currentTarget.open)}><summary>查看图表数值与缺失情况</summary>{showTable && <div><table><thead><tr><th>日期</th>{series.map(s => <th key={s.symbol}>{s.stock_name}{scatter ? ' · X / Y' : ''}</th>)}</tr></thead><tbody>
      {data.dates.map((day, i) => <tr key={day}><th>{day}</th>{series.map(s => <td key={s.symbol}>{scatter ? `${displayValue(s.x[i])} / ` : ''}{displayValue(s.values[i])}</td>)}</tr>)}
    </tbody></table></div>}</details>
  </>;
}
