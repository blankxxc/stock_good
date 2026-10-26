'use client';

import dynamic from 'next/dynamic';
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';

export type AssistantSnapshot = {
  score_model?: 'cograsp' | 'sentiment_event' | 'api_llm';
  factor_names?: string[];
  page_state?: Record<string, unknown>;
};
type Register = (snapshot: AssistantSnapshot | null, owner: object) => void;
const PageContext = createContext<Register>(() => {});
const ChatPanel = dynamic(() => import('./AssistantPanel'), {
  ssr: false,
  loading: () => <div className="assistant-loading" role="status">正在打开研究助手…</div>,
});

/** Publish a small, explicit public-data summary, never page HTML or account data. */
export function useAssistantContext(snapshot: AssistantSnapshot) {
  const register = useContext(PageContext);
  const owner = useRef({});
  const serialized = JSON.stringify(snapshot);
  useEffect(() => {
    const token = owner.current;
    register(JSON.parse(serialized), token);
    return () => register(null, token);
  }, [register, serialized]);
}

export function AssistantRoot({ pathname, children }: { pathname: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [entry, setEntry] = useState<{ path: string; snapshot: AssistantSnapshot; owner: object } | null>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const register = useCallback<Register>((snapshot, owner) => {
    setEntry(current => snapshot ? { path: pathname, snapshot, owner } : current?.owner === owner ? null : current);
  }, [pathname]);
  const available = pathname !== '/account' && !pathname.startsWith('/admin') && !pathname.startsWith('/login') && !pathname.startsWith('/settings');
  return <PageContext.Provider value={register}>
    {children}
    {available && <button ref={launcher} className="assistant-launcher" type="button"
      aria-label={open ? '收起 AI 研究助手' : '打开 AI 研究助手'} aria-expanded={open} aria-controls="research-assistant"
      onClick={() => { setLoaded(true); setOpen(current => !current); }}>
      <span className="assistant-launcher__icon" aria-hidden="true">✦</span><span>AI 助手</span>
    </button>}
    {loaded && <ChatPanel open={open && available} pathname={pathname}
      snapshot={entry?.path === pathname ? entry.snapshot : null}
      onClose={() => { setOpen(false); launcher.current?.focus(); }} />}
  </PageContext.Provider>;
}
