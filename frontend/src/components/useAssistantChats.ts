'use client';

import { useEffect, useRef, useState } from 'react';
import type { ChatMessage } from '../lib/assistant';

export type AssistantChat = {
  id: string; title: string; draft: string; messages: ChatMessage[];
  busy: boolean; error: string; notice: string;
  selectedSkillIds: string[];
};
type Group = { chats: AssistantChat[]; selected: string };
type State = { revision: number; groups: Record<string, Group> };
type Request = { scope: string; controller: AbortController };
const emptyChat = (number: number): AssistantChat => ({ id: `chat-${number}`, title: `新对话 ${number}`,
  draft: '', messages: [], busy: false, error: '', notice: '', selectedSkillIds: [] });
const groupFor = (chat: AssistantChat): Group => ({ chats: [chat], selected: chat.id });

/** Conversations live only in memory, partitioned by the page's research context. */
export function useAssistantChats(scope: string, revision: number) {
  const sequence = useRef(1);
  const requests = useRef(new Map<string, Request>());
  const [state, setState] = useState<State>(() => ({ revision, groups: { [scope]: groupFor(emptyChat(1)) } }));
  const group = state.revision === revision ? state.groups[scope] : undefined;
  const current = group?.chats.find(chat => chat.id === group.selected) || null;
  function fresh() { return emptyChat(++sequence.current); }
  function update(id: string, patch: (chat: AssistantChat) => AssistantChat, targetScope = scope) {
    setState(previous => {
      const target = previous.groups[targetScope];
      if (previous.revision !== revision || !target?.chats.some(chat => chat.id === id)) return previous;
      return { ...previous, groups: { ...previous.groups, [targetScope]: { ...target,
        chats: target.chats.map(chat => chat.id === id ? patch(chat) : chat) } } };
    });
  }
  useEffect(() => {
    for (const [id, request] of requests.current) {
      if (request.scope !== scope || state.revision !== revision) {
        requests.current.delete(id); request.controller.abort();
        if (state.revision === revision) update(id, chat => ({ ...chat, busy: false, notice: '切换研究页面，已停止生成。' }), request.scope);
      }
    }
    if (state.revision !== revision || !state.groups[scope]) {
      const next = groupFor(fresh());
      setState(previous => previous.revision !== revision ? { revision, groups: { [scope]: next } }
        : previous.groups[scope] ? previous : { ...previous, groups: { ...previous.groups, [scope]: next } });
    }
    // Scope and credentials delimit conversations; message updates must not restart them.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, revision]);
  useEffect(() => {
    const pending = requests.current;
    return () => { for (const request of pending.values()) request.controller.abort(); pending.clear(); };
  }, []);

  function select(id: string) {
    setState(previous => {
      const target = previous.groups[scope];
      if (!target?.chats.some(chat => chat.id === id)) return previous;
      return { ...previous, groups: { ...previous.groups, [scope]: { ...target, selected: id } } };
    });
  }
  function create() {
    const next = fresh();
    setState(previous => ({ ...previous, groups: { ...previous.groups, [scope]: {
      chats: [...(previous.groups[scope]?.chats || []), next], selected: next.id,
    } } }));
  }
  function stop(id: string) {
    const request = requests.current.get(id);
    requests.current.delete(id); request?.controller.abort();
    update(id, chat => ({ ...chat, busy: false, notice: '已停止生成。' }));
  }
  function close(id: string) {
    const request = requests.current.get(id);
    requests.current.delete(id); request?.controller.abort();
    const replacement = fresh();
    setState(previous => {
      const target = previous.groups[scope];
      if (!target) return previous;
      const index = target.chats.findIndex(chat => chat.id === id);
      if (index < 0) return previous;
      const remaining = target.chats.filter(chat => chat.id !== id);
      if (!remaining.length) remaining.push(replacement);
      const selected = target.selected === id ? remaining[Math.min(index, remaining.length - 1)]?.id : target.selected;
      return { ...previous, groups: { ...previous.groups, [scope]: { chats: remaining, selected: selected || '' } } };
    });
  }
  function begin(id: string) {
    if (requests.current.has(id)) return null;
    const controller = new AbortController(); requests.current.set(id, { scope, controller }); return controller;
  }
  function isActive(id: string, controller: AbortController) { return requests.current.get(id)?.controller === controller && !controller.signal.aborted; }
  function finish(id: string, controller: AbortController) {
    if (isActive(id, controller)) { requests.current.delete(id); update(id, chat => ({ ...chat, busy: false })); }
  }
  return { chats: group?.chats || [], current, select, create, close, stop, update, begin, isActive, finish };
}
