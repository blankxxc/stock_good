'use client';

import { useEffect, useRef } from 'react';
import Link from 'next/link';
import type { AssistantSnapshot } from './AssistantRoot';
import { useAssistantPreferences } from './AssistantPreferences';
import { chatHistory, consumeChat, safeSourceUrl, type ChatMessage } from '../lib/assistant';
import { ResizeHandle } from './ResizeHandle';
import { useAssistantSize } from './useAssistantSize';
import { useAssistantChats } from './useAssistantChats';
import { AssistantChatTabs } from './AssistantChatTabs';
import { AssistantSkillPicker } from './AssistantSkillPicker';
import { instructionPayload } from '../lib/assistantInstructions';

type Props = { open: boolean; pathname: string; snapshot: AssistantSnapshot | null; onClose: () => void };

export default function AssistantPanel({ open, pathname, snapshot, onClose }: Props) {
  const sizing = useAssistantSize();
  const { connection, revision, instructions } = useAssistantPreferences();
  const transcript = useRef<HTMLDivElement>(null);
  const followOutput = useRef(true);
  const closeButton = useRef<HTMLButtonElement>(null);
  const questionInput = useRef<HTMLTextAreaElement>(null);
  const focusNewChat = useRef(false);
  const prediction = snapshot?.page_state?.prediction;
  const predictionSymbol = prediction && typeof prediction === 'object' && 'symbol' in prediction
    && typeof prediction.symbol === 'string' && /^\d{6}\.(SH|SZ|BJ)$/.test(prediction.symbol) ? prediction.symbol : '';
  const pageSymbol = pathname.startsWith('/stocks/') ? decodeURIComponent(pathname.split('/').pop() || '')
    : pathname === '/scores' && snapshot?.score_model === 'api_llm' ? predictionSymbol : '';
  const scoreModel = snapshot?.score_model || 'cograsp';
  const chats = useAssistantChats(JSON.stringify([pathname, pageSymbol, scoreModel]), revision);
  const current = chats.current;
  const activeId = current?.id || '';
  const { draft = '', messages = [], busy = false, error = '', notice = '' } = current || {};

  useEffect(() => { followOutput.current = true; }, [activeId]);
  useEffect(() => {
    if (open) (connection ? questionInput.current : closeButton.current)?.focus();
  }, [open, connection]);
  useEffect(() => {
    if (focusNewChat.current && current) { questionInput.current?.focus(); focusNewChat.current = false; }
  }, [activeId, current]);
  useEffect(() => {
    const input = questionInput.current;
    if (!open || !input) return;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;
  }, [open, draft, activeId]);
  useEffect(() => {
    if (open && transcript.current && followOutput.current) transcript.current.scrollTop = messages.length || error ? transcript.current.scrollHeight : 0;
  }, [open, messages, busy, error, activeId]);

  function setDraft(value: string) {
    if (current) chats.update(current.id, chat => ({ ...chat, draft: value }));
  }
  async function send(text = draft) {
    const question = text.trim();
    if (!current || !question || busy) return;
    const id = current.id;
    if (!connection) { chats.update(id, chat => ({ ...chat, error: '请先在个人设置中配置 AI 助手。' })); return; }
    let customization: ReturnType<typeof instructionPayload>;
    try { customization = instructionPayload(instructions, current.selectedSkillIds); }
    catch (reason) { chats.update(id, chat => ({ ...chat, error: reason instanceof Error ? reason.message : '技能配置不可用。' })); return; }
    const history = chatHistory(messages);
    const controller = chats.begin(id);
    if (!controller) return;
    followOutput.current = true;
    chats.update(id, chat => ({ ...chat, busy: true, error: '', notice: '', draft: '',
      title: chat.messages.length ? chat.title : Array.from(question.replace(/\s+/g, ' ')).slice(0, 18).join('') + (Array.from(question).length > 18 ? '…' : ''),
      messages: [...chat.messages, { role: 'user', content: question, skillNames: customization.skills.map(skill => skill.name) }, { role: 'assistant', content: '', complete: false }],
    }));
    const updateAnswer = (update: Partial<ChatMessage> | ((message: ChatMessage) => ChatMessage)) => {
      if (!chats.isActive(id, controller)) return;
      chats.update(id, chat => ({ ...chat, messages: chat.messages.map((item, i) => i === chat.messages.length - 1
        ? typeof update === 'function' ? update(item) : { ...item, ...update } : item) }));
    };
    try {
      const response = await fetch('/api/assistant/chat', {
        method: 'POST', cache: 'no-store', credentials: 'omit', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-AI-API-Key': connection.apiKey },
        body: JSON.stringify({
          provider: connection.provider.id, model: connection.model, page: pathname, symbol: pageSymbol, score_model: scoreModel,
          ...customization,
          factor_names: (snapshot?.factor_names || []).slice(0, 12), page_state: snapshot?.page_state || {},
          messages: [...history, { role: 'user', content: question }],
        }),
      });
      await consumeChat(response, event => {
        if (event.type === 'delta') updateAnswer(item => ({ ...item, content: item.content + (event.text || '') }));
        if (event.type === 'context') updateAnswer({ sources: event.sources, notes: event.notes });
        if (event.type === 'done') updateAnswer({ complete: true });
        if (event.type === 'notice' && chats.isActive(id, controller)) chats.update(id, chat => ({ ...chat, notice: event.message || '' }));
      });
    } catch (failure) {
      if (chats.isActive(id, controller)) chats.update(id, chat => ({ ...chat,
        error: failure instanceof Error ? failure.message : '分析失败，请重试。', draft: chat.draft || question }));
    } finally {
      chats.finish(id, controller);
    }
  }

  return <aside ref={sizing.panel} style={sizing.style} id="research-assistant" className={`assistant-panel${sizing.resizing ? ' assistant-panel--resizing' : ''}`} role="dialog" aria-modal="false"
    aria-labelledby="assistant-title" hidden={!open}
    onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); } }}>
    <ResizeHandle label="拖动左上角调整助手大小" className="assistant-resize-handle"
      onStart={sizing.onStart} onStep={sizing.onStep} onReset={sizing.onReset} />
    <header className="assistant-header">
      <h2 id="assistant-title">AI 研究助手</h2>
      <div className="assistant-header-actions">
        <button className="assistant-new-chat" type="button" aria-label="新建对话" onClick={() => { focusNewChat.current = true; chats.create(); }}><span aria-hidden="true">＋</span>新建对话</button>
        <button ref={closeButton} className="assistant-icon-button" type="button" aria-label="关闭助手" title="关闭助手" onClick={onClose}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
        </button>
      </div>
    </header>
    <AssistantChatTabs chats={chats.chats} selected={activeId} onSelect={chats.select} onClose={chats.close} />
    <div key={activeId} id={`assistant-conversation-${activeId}`} className="assistant-conversation" role="tabpanel" aria-labelledby={`assistant-tab-${activeId}`}>
    <div className="assistant-messages" ref={transcript} role="log" aria-label="助手对话" aria-live="polite" aria-busy={busy}
      onScroll={event => { const node = event.currentTarget; followOutput.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80; }}>
      {!messages.length && <div className="assistant-welcome">
        <h3>{connection ? '有什么可以帮你？' : '开始和 AI 聊天'}</h3>
        <p>{connection ? '聊聊当前页面的股票、因子或实验。' : '先在个人设置中配置模型和 API Key。'}</p>
        {!connection && <Link prefetch={false} className="assistant-setup-link" href="/account">前往设置 <span aria-hidden="true">↗</span></Link>}
      </div>}
      {messages.map((message, index) => <article key={index} className={`assistant-message assistant-message--${message.role}`} aria-label={message.role === 'user' ? '你的消息' : '助手回复'}>
        {message.content ? <div className="assistant-message__text">{message.content}</div>
          : busy ? <div className="assistant-typing" aria-label="正在回复"><span /><span /><span /></div>
            : <div className="assistant-message__text">未生成回答。</div>}
        {!!message.skillNames?.length && <div className="assistant-used-skills">{message.skillNames.map((name, i) => <span key={i}>{name}</span>)}</div>}
        {message.role === 'assistant' && message.content && !message.complete && !busy && <small>此回答未完成</small>}
        {!!message.sources?.length && <details className="assistant-sources"><summary>数据来源 · {message.sources.length}</summary>
          {message.sources.map((source, i) => <div key={i}>{safeSourceUrl(source.url)
            ? <a href={source.url}>{source.label}</a> : <span>{source.label}</span>}<small>{source.date || '日期未知'}</small></div>)}
          {message.notes?.map((note, i) => <p key={i}>{note}</p>)}
        </details>}
      </article>)}
      {error && <div className="assistant-error" role="alert">{error}</div>}
      {notice && <p className="assistant-note" role="status">{notice}</p>}
    </div>
    <form className="assistant-compose" onSubmit={event => { event.preventDefault(); void send(); }}>
      <AssistantSkillPicker settings={instructions} selectedIds={current?.selectedSkillIds || []}
        onChange={ids => { if (current) chats.update(current.id, chat => ({ ...chat, selectedSkillIds: ids })); }} />
      <label className="sr-only" htmlFor="assistant-question">向助手提问</label>
      <div className="assistant-input-wrap"><textarea ref={questionInput} id="assistant-question" value={draft} onChange={event => setDraft(event.target.value)}
        placeholder={connection ? '输入消息…' : '配置 API 后开始聊天'} rows={1} maxLength={4000} disabled={!connection}
        onKeyDown={event => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); }
        }} />
        {busy ? <button type="button" className="assistant-send" aria-label="停止生成" title="停止生成" onClick={() => chats.stop(activeId)}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><rect x="3" y="3" width="10" height="10" rx="2" /></svg></button>
          : <button type="submit" className="assistant-send" aria-label="发送消息" title="发送消息" disabled={!draft.trim() || !connection}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6" /></svg></button>}</div>
      <div className="assistant-compose-hint"><span>Enter 发送 · Shift + Enter 换行</span><span>AI 内容请核实</span></div>
    </form>
    </div>
  </aside>;
}
