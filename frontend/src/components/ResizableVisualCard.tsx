'use client';

import { useRef, useState, type CSSProperties, type HTMLAttributes, type ReactNode } from 'react';
import { ResizeHandle } from './ResizeHandle';
import { chartSize, type ChartConfig } from '../lib/visualization';

type Size = { columns: number; height: number };
type Props = Omit<HTMLAttributes<HTMLElement>, 'onResize'> & {
  card: ChartConfig; cards: ChartConfig[]; children: ReactNode; onResize: (size: Size & { wide: boolean }) => void;
};
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function ResizableVisualCard({ card, cards, children, onResize, className = '', ...attrs }: Props) {
  const element = useRef<HTMLElement>(null);
  const [preview, setPreview] = useState<Size | null>(null);
  const size = preview || chartSize(card);
  function commit(next: Size) { onResize({ ...next, wide: next.columns === 12 }); }
  return <article {...attrs} ref={element} className={`visual-card ${className}${preview ? ' visual-card--resizing' : ''}`}
    style={{ '--card-columns': size.columns, '--card-height': `${size.height}px` } as CSSProperties}>
    <div className="visual-card-content">{children}</div>
    <footer className="visual-card-size"><span>{size.columns} / 12 列 · {size.height} px{preview ? ' · 网格吸附' : ''}</span>
      <ResizeHandle label={`调整${card.title || '图表'}大小`} className="visual-resize-handle"
        onStart={() => {
          const start = chartSize(card);
          const parent = element.current?.parentElement;
          const width = parent?.getBoundingClientRect().width || 1200;
          const gap = parent ? Number.parseFloat(getComputedStyle(parent).columnGap) || 20 : 20;
          const unit = (width + gap) / 12;
          const narrow = typeof window !== 'undefined' && window.innerWidth <= 960;
          const heights = cards.filter(c => c.id !== card.id).map(c => chartSize(c).height);
          let next = start; setPreview(start);
          return { move: (dx, dy) => {
            const rawHeight = start.height + dy;
            const match = heights.reduce<number | undefined>((best, height) => Math.abs(height - rawHeight) <= 12
              && (best === undefined || Math.abs(height - rawHeight) < Math.abs(best - rawHeight)) ? height : best, undefined);
            next = { columns: narrow ? start.columns : clamp(Math.round(start.columns + dx / unit), 4, 12),
              height: clamp(match ?? Math.round(rawHeight / 20) * 20, 400, 1200) };
            setPreview(old => old?.columns === next.columns && old.height === next.height ? old : next);
          }, finish: cancelled => { setPreview(null); if (!cancelled) commit(next); } };
        }}
        onStep={(dx, dy) => commit({ columns: clamp(size.columns + dx, 4, 12), height: clamp(size.height + dy * 20, 400, 1200) })}
        onReset={() => commit({ columns: card.wide ? 12 : 6, height: 600 })} />
    </footer>
  </article>;
}
