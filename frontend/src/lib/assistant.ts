export type ChatEvent = { type: string; text?: string; message?: string; sources?: Source[]; notes?: string[] };
export type Source = { label: string; date?: string | null; url: string };
export type ChatMessage = { role: 'user' | 'assistant'; content: string; complete?: boolean; sources?: Source[]; notes?: string[]; skillNames?: string[] };

export const PAGE_NAMES: Record<string, string> = {
  '/visualization': '数据可视化',
  '/': '股票全景', '/scores': '股票预测选股', '/condition-screen': '条件选股', '/strategy-lab': '策略实验',
  '/graph': '关系图谱', '/watchlist': '我的自选',
};

export function chatHistory(messages: ChatMessage[]) {
  let budget = 16000;
  const selected: { role: 'user' | 'assistant'; content: string }[] = [];
  // Keep complete question/answer pairs; failed or interrupted generations aren't evidence.
  for (let i = messages.length - 2; i >= 0 && selected.length < 10; i -= 2) {
    const user = messages[i], answer = messages[i + 1];
    if (user?.role !== 'user' || answer?.role !== 'assistant' || !answer.complete) continue;
    const size = user.content.length + answer.content.length;
    if (size > budget) break;
    selected.unshift({ role: 'user', content: user.content }, { role: 'assistant', content: answer.content.slice(0, 6000) });
    budget -= size;
  }
  return selected;
}

export async function consumeChat(response: Response, onEvent: (event: ChatEvent) => void) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : '请求未成功，请检查设置后重试。');
  }
  if (!response.body) throw new Error('浏览器未收到响应，请重试。');
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', done = false;
  const handle = (line: string) => {
    if (!line.trim()) return;
    const event = JSON.parse(line) as ChatEvent;
    if (event.type === 'error') throw new Error(event.message || '分析中断，请重试。');
    if (event.type === 'done') done = true;
    onEvent(event);
  };
  try {
    for (;;) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) handle(line);
      if (buffer.length > 100000) throw new Error('响应格式异常，请重试。');
      if (chunk.done) break;
    }
    if (buffer.trim()) handle(buffer);
    if (!done) throw new Error('连接已中断，回答不完整，请重试。');
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function safeSourceUrl(value: string) {
  return /^\/(?:stocks\/\d{6}\.(?:SH|SZ|BJ)|scores(?:\?model=(?:cograsp|sentiment_event|api_llm))?|strategy-lab|visualization)?$/.test(value)
    ? value : null;
}
