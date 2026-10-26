'use client';

import { useEffect, useRef } from 'react';
import type { AssistantChat } from './useAssistantChats';

export function AssistantChatTabs({ chats, selected, onSelect, onClose }: {
  chats: AssistantChat[]; selected: string; onSelect: (id: string) => void; onClose: (id: string) => void;
}) {
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const focusAfterClose = useRef(false);
  useEffect(() => {
    const button = buttons.current.get(selected);
    button?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    if (focusAfterClose.current) { button?.focus(); focusAfterClose.current = false; }
  }, [selected, chats.length]);
  function close(id: string) { focusAfterClose.current = true; onClose(id); }
  return <div className="assistant-tabs" role="tablist" aria-label="对话标签">
    {chats.map((chat, index) => <div key={chat.id} className={`assistant-tab${chat.id === selected ? ' is-selected' : ''}`} role="presentation">
      <button ref={node => { if (node) buttons.current.set(chat.id, node); else buttons.current.delete(chat.id); }}
        id={`assistant-tab-${chat.id}`} type="button" role="tab" aria-selected={chat.id === selected}
        aria-controls={`assistant-conversation-${chat.id}`} tabIndex={chat.id === selected ? 0 : -1}
        title={chat.title} onClick={() => onSelect(chat.id)}
        onKeyDown={event => {
          let next: number | undefined;
          if (event.key === 'ArrowRight') next = (index + 1) % chats.length;
          if (event.key === 'ArrowLeft') next = (index - 1 + chats.length) % chats.length;
          if (event.key === 'Home') next = 0;
          if (event.key === 'End') next = chats.length - 1;
          if (next !== undefined) { event.preventDefault(); onSelect(chats[next].id); buttons.current.get(chats[next].id)?.focus(); }
          if (event.key === 'Delete') {
            event.preventDefault(); close(chat.id);
          }
        }}><span>{chat.title}</span>{chat.busy && <i className="assistant-tab-busy" aria-label="正在回复" />}</button>
      <button className="assistant-tab-close" type="button" aria-label={`关闭对话：${chat.title}`} title="关闭并移除此对话"
        onClick={() => close(chat.id)}>×</button>
    </div>)}
  </div>;
}
