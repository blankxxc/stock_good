'use client';

import { useEffect, useRef, useState, type CSSProperties } from 'react';

export const ASSISTANT_SIZE_KEY = 'stock-good.assistant-size.v1';
const DEFAULT = { width: 440, height: 790 };
type Size = typeof DEFAULT;

export function useAssistantSize() {
  const panel = useRef<HTMLElement>(null);
  const [size, setSize] = useState<Size>(DEFAULT);
  const [resizing, setResizing] = useState(false);
  useEffect(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(ASSISTANT_SIZE_KEY) || 'null');
      if (saved && Number.isFinite(saved.width) && Number.isFinite(saved.height)
          && saved.width >= 320 && saved.width <= 10000 && saved.height >= 200 && saved.height <= 10000) {
        setSize({ width: saved.width, height: saved.height });
      }
    } catch { /* Storage is optional; never affects the conversation. */ }
  }, []);
  function measured(): Size {
    const rect = panel.current?.getBoundingClientRect();
    return rect?.width && rect.height ? { width: rect.width, height: rect.height } : size;
  }
  function bounded(next: Size): Size {
    const mobile = window.innerWidth <= 620;
    const maxW = Math.max(1, window.innerWidth - (mobile ? 16 : 40));
    const maxH = Math.max(1, window.innerHeight - (mobile ? 100 : 112));
    return { width: Math.round(Math.min(maxW, Math.max(320, next.width))),
      height: Math.round(Math.min(maxH, Math.max(360, next.height))) };
  }
  function save(next: Size) {
    setSize(next);
    try { localStorage.setItem(ASSISTANT_SIZE_KEY, JSON.stringify(next)); } catch { /* Session sizing still works. */ }
  }
  return { panel, resizing,
    style: { '--assistant-width': `${size.width}px`, '--assistant-height': `${size.height}px` } as CSSProperties,
    onStart: () => {
      const before = size, start = measured(); let next = start;
      setResizing(true);
      return { move: (dx: number, dy: number) => { next = bounded({ width: start.width - dx, height: start.height - dy }); setSize(next); },
        finish: (cancelled: boolean) => { setResizing(false); if (cancelled) setSize(before); else save(next); } };
    },
    onStep: (dx: number, dy: number) => { const start = measured(); save(bounded({ width: start.width - dx * 20, height: start.height - dy * 20 })); },
    onReset: () => save(DEFAULT),
  };
}
