'use client';

import { useRef, type PointerEvent } from 'react';

type Gesture = { move: (dx: number, dy: number) => void; finish: (cancelled: boolean) => void };
type Props = {
  label: string; className?: string;
  onStart: () => Gesture;
  onStep: (dx: number, dy: number) => void;
  onReset: () => void;
};

/** Pointer capture keeps a resize attached to its handle, including outside the panel. */
export function ResizeHandle({ label, className = '', onStart, onStep, onReset }: Props) {
  const active = useRef<{ id: number; x: number; y: number; gesture: Gesture } | null>(null);
  function finish(event: PointerEvent<HTMLButtonElement>, cancelled: boolean) {
    const drag = active.current;
    if (!drag || drag.id !== event.pointerId) return;
    active.current = null;
    if (!cancelled) drag.gesture.move(event.clientX - drag.x, event.clientY - drag.y);
    drag.gesture.finish(cancelled);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }
  return <button type="button" className={`resize-handle ${className}`} aria-label={label}
    title={`${label}；方向键微调，双击或 Home 恢复默认大小，Esc 取消拖动`}
    onPointerDown={event => {
      if (active.current || event.button !== 0 || event.isPrimary === false) return;
      event.preventDefault(); event.stopPropagation(); event.currentTarget.focus();
      event.currentTarget.setPointerCapture(event.pointerId);
      active.current = { id: event.pointerId, x: event.clientX, y: event.clientY, gesture: onStart() };
    }}
    onPointerMove={event => {
      const drag = active.current;
      if (drag?.id === event.pointerId) { event.stopPropagation(); drag.gesture.move(event.clientX - drag.x, event.clientY - drag.y); }
    }}
    onPointerUp={event => finish(event, false)} onPointerCancel={event => finish(event, true)}
    onLostPointerCapture={event => finish(event, true)}
    onDoubleClick={onReset}
    onKeyDown={event => {
      if (event.key === 'Escape' && active.current) {
        event.preventDefault(); event.stopPropagation();
        const drag = active.current; active.current = null; drag.gesture.finish(true);
        if (event.currentTarget.hasPointerCapture(drag.id)) event.currentTarget.releasePointerCapture(drag.id);
        return;
      }
      if (active.current) return;
      const steps: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
      if (event.key === 'Home' || steps[event.key]) {
        event.preventDefault(); event.stopPropagation();
        if (event.key === 'Home') onReset();
        else { const [dx, dy] = steps[event.key]; const speed = event.shiftKey ? 2 : 1; onStep(dx * speed, dy * speed); }
      }
    }}><svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 13 13 4M8 13l5-5M12 13l1-1" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg></button>;
}
