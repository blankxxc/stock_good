'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { subscribeSessionInvalidation } from '../lib/auth';
import { PAGE_NAMES } from '../lib/assistant';
import { defaultInstructions, INSTRUCTIONS_KEY, parseInstructions, restoreInstructions, type AssistantInstructions } from '../lib/assistantInstructions';

export type AssistantProvider = { id: string; label: string; base_url: string; default_model: string };
export type AssistantConnection = { provider: AssistantProvider; model: string; apiKey: string };
type Preferences = {
  connection: AssistantConnection | null;
  revision: number;
  returnPath: string;
  rememberPage: (pathname: string, search?: string) => void;
  apply: (connection: AssistantConnection) => void;
  clear: () => void;
  instructions: AssistantInstructions;
  instructionStorageError: string;
  saveInstructions: (next: AssistantInstructions) => boolean;
};
const PreferencesContext = createContext<Preferences | null>(null);

/** Keep only public navigation fields; never remember arbitrary URL parameters. */
export function researchReturnPath(pathname: string, search = ''): string | null {
  const stockPage = /^\/stocks\/\d{6}\.(SH|SZ|BJ)$/.test(pathname);
  if (!Object.hasOwn(PAGE_NAMES, pathname) && !stockPage) return null;
  const source = new URLSearchParams(search), target = new URLSearchParams();
  if (pathname === '/scores') {
    const model = source.get('model'), symbol = source.get('symbol');
    if (model && ['cograsp', 'sentiment_event', 'api_llm'].includes(model)) target.set('model', model);
    if (symbol && /^\d{6}\.(SH|SZ|BJ)$/.test(symbol)) target.set('symbol', symbol);
  } else if (stockPage) {
    const from = source.get('from');
    if (from && ['condition-screen', 'scores', 'watchlist', 'graph'].includes(from)) target.set('from', from);
  }
  return pathname + (target.size ? `?${target}` : '');
}

/** One in-memory connection for the current tab; never serialize credentials. */
export function AssistantPreferencesProvider({ pathname, children }: { pathname: string; children: ReactNode }) {
  const [connection, setConnection] = useState<AssistantConnection | null>(null);
  const [revision, setRevision] = useState(0);
  const [returnPath, setReturnPath] = useState('/');
  const [instructions, setInstructions] = useState<AssistantInstructions>(defaultInstructions);
  const [instructionStorageError, setInstructionStorageError] = useState('');
  useEffect(() => {
    try { const saved = localStorage.getItem(INSTRUCTIONS_KEY); if (saved) setInstructions(restoreInstructions(saved)); }
    catch { setInstructionStorageError('无法读取本机的提示词与技能，当前使用默认配置。'); }
  }, []);
  const saveInstructions = useCallback((next: AssistantInstructions) => {
    const clean = parseInstructions(next);
    setInstructions(clean);
    try { localStorage.setItem(INSTRUCTIONS_KEY, JSON.stringify(clean)); setInstructionStorageError(''); return true; }
    catch { setInstructionStorageError('已在本次浏览中应用，但浏览器未能保存；刷新后需要重新设置。'); return false; }
  }, []);
  const rememberPage = useCallback((path: string, search = '') => {
    const next = researchReturnPath(path, search);
    if (next) setReturnPath(next);
  }, []);
  const apply = useCallback((next: AssistantConnection) => {
    setConnection({ ...next, provider: { ...next.provider }, model: next.model.trim(), apiKey: next.apiKey.trim() });
    setRevision(value => value + 1);
  }, []);
  const clear = useCallback(() => {
    setConnection(null);
    setRevision(value => value + 1);
  }, []);
  useEffect(() => subscribeSessionInvalidation(clear), [clear]);
  useEffect(() => {
    const search = typeof window !== 'undefined' && window.location?.pathname === pathname ? window.location.search : '';
    rememberPage(pathname, search);
  }, [pathname, rememberPage]);
  const value = useMemo(() => ({ connection, revision, returnPath, rememberPage, apply, clear, instructions, instructionStorageError, saveInstructions }),
    [connection, revision, returnPath, rememberPage, apply, clear, instructions, instructionStorageError, saveInstructions]);
  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function useAssistantPreferences() {
  const context = useContext(PreferencesContext);
  if (!context) throw new Error('Assistant preferences provider is missing');
  return context;
}
