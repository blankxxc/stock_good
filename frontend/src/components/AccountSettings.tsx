'use client';

import Link from 'next/link';
import { useEffect, useState, type FormEvent } from 'react';
import { getSessionStatus, subscribeSessionInvalidation, type SessionUser } from '../lib/auth';
import { useAssistantPreferences, type AssistantProvider } from './AssistantPreferences';
import { AssistantInstructionSettings } from './AssistantInstructionSettings';

export function AssistantConnectionSettings({ providers }: { providers: AssistantProvider[] }) {
  const { connection, revision, apply, clear, returnPath } = useAssistantPreferences();
  const [providerId, setProviderId] = useState(connection?.provider.id || providers[0]?.id || '');
  const [model, setModel] = useState(connection?.model || providers[0]?.default_model || '');
  const [apiKey, setApiKey] = useState(connection?.apiKey || '');
  const [keyLocked, setKeyLocked] = useState(true);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);
  const provider = providers.find(item => item.id === providerId);
  useEffect(() => {
    setProviderId(connection?.provider.id || providers[0]?.id || '');
    setModel(connection?.model || providers[0]?.default_model || '');
    setApiKey(connection?.apiKey || ''); setKeyLocked(true); setError(''); setSaved(false);
  }, [connection, revision, providers]);
  const unchanged = !!connection && providerId === connection.provider.id && model === connection.model && apiKey === connection.apiKey;

  function save(event: FormEvent) {
    event.preventDefault();
    if (!provider) { setError('请选择模型服务商。'); return; }
    if (!/^[A-Za-z0-9._:/-]{1,120}$/.test(model.trim())) { setError('请填写有效的模型名称。'); return; }
    if (!/^[\x21-\x7e]{8,512}$/.test(apiKey.trim())) { setError('请填写有效的 API Key。'); return; }
    apply({ provider, model, apiKey }); setError(''); setSaved(true);
  }

  return <form className="account-ai-form" onSubmit={save} autoComplete="off">
    <div className="account-field-pair">
      <label htmlFor="account-ai-provider">模型服务
        <select id="account-ai-provider" value={providerId} onChange={event => {
          const next = providers.find(item => item.id === event.target.value);
          setProviderId(event.target.value); setModel(next?.default_model || ''); setApiKey(''); setKeyLocked(true); setSaved(false); setError('');
        }}>{providers.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
      </label>
      <label htmlFor="account-ai-model">模型名称
        <input id="account-ai-model" name="ai-provider-model" value={model} maxLength={120}
          onChange={event => { setModel(event.target.value); setSaved(false); }} placeholder="服务商提供的模型 ID"
          autoComplete="off" data-lpignore="true" data-1p-ignore="true" data-form-type="other" />
      </label>
    </div>
    <label htmlFor="account-ai-key">API Key
      <input id="account-ai-key" name="ai-provider-api-key" type="password" value={apiKey} maxLength={512}
        readOnly={keyLocked} onFocus={() => setKeyLocked(false)} onChange={event => { setApiKey(event.target.value); setSaved(false); }}
        placeholder="点击后输入该服务商的 API Key" autoComplete="new-password" spellCheck={false}
        data-lpignore="true" data-1p-ignore="true" data-form-type="other" />
    </label>
    <p className="account-endpoint">服务地址 <span>{provider?.base_url || '尚未选择'}</span></p>
    <div className="account-connection-note">
      <strong>在当前标签页使用</strong>
      <p>配置后，各研究页的 AI 助手会共用这组设置。密钥仅保留在内存，刷新或退出账号后需要重新填写，不保存到服务器。</p>
    </div>
    {error && <p className="auth-message auth-message--error" role="alert">{error}</p>}
    <div className="account-settings-actions">
      <button className="button" type="submit">应用设置</button>
      <button className="button ghost" type="button" disabled={!connection && !apiKey} onClick={() => { clear(); setApiKey(''); setKeyLocked(true); setSaved(false); }}>清除配置</button>
      {(saved || unchanged) && <span className="account-saved" role="status">已应用，可返回研究页使用</span>}
    </div>
    <Link prefetch={false} className="account-return" href={returnPath}>返回研究页 ↗</Link>
  </form>;
}

export function AccountSettings() {
  const { connection, returnPath } = useAssistantPreferences();
  const [providers, setProviders] = useState<AssistantProvider[]>([]);
  const [providerError, setProviderError] = useState('');
  const [retry, setRetry] = useState(0);
  const [user, setUser] = useState<SessionUser | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [sessionError, setSessionError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setProviderError('');
    fetch('/api/assistant/config', { cache: 'no-store', credentials: 'omit', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error();
        const payload = await response.json();
        if (!Array.isArray(payload.providers) || !payload.providers.length) throw new Error();
        if (!controller.signal.aborted) setProviders(payload.providers);
      }).catch(() => { if (!controller.signal.aborted) setProviderError('暂时无法读取模型服务配置。'); });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    let sequence = 0;
    async function load() {
      const current = ++sequence;
      setSessionLoading(true); setSessionError('');
      try {
        const status = await getSessionStatus();
        if (current === sequence) setUser(status.user ?? null);
      } catch {
        if (current === sequence) { setUser(null); setSessionError('暂时无法读取账户信息。'); }
      } finally { if (current === sequence) setSessionLoading(false); }
    }
    void load();
    const unsubscribe = subscribeSessionInvalidation(() => { void load(); });
    return () => { ++sequence; unsubscribe(); };
  }, [retry]);

  return <section className="account-page">
    <div className="account-page-heading"><div><span className="badge">个人空间</span><h1>个人设置</h1>
      <p>在这里连接你的 AI 模型，回到研究页面即可开始分析。</p></div>
      <Link prefetch={false} className="button secondary" href={returnPath}>返回研究页</Link>
    </div>
    <div className="account-settings-grid">
      <aside className="account-profile-card">
        <span className="account-avatar" aria-hidden="true">{user?.display_name.slice(0, 1).toUpperCase() || 'OA'}</span>
        <h2>{sessionLoading ? '正在读取账户…' : user?.display_name || '我的个人空间'}</h2>
        {user ? <p>@{user.username} · {user.role === 'admin' ? '管理员' : '普通用户'}</p>
          : <p>{sessionError || '未登录也可以配置本次浏览的 AI 助手。'}</p>}
        {sessionError && <button className="button ghost" type="button" onClick={() => setRetry(value => value + 1)}>重试</button>}
        {!sessionLoading && (user ? <Link prefetch={false} href="/watchlist">我的自选 ↗</Link>
          : <Link prefetch={false} href="/login?next=/account">登录 / 注册 ↗</Link>)}
        <div className="account-profile-status"><span className={connection ? 'account-status-dot is-ready' : 'account-status-dot'} />AI 助手{connection ? '已配置' : '尚未配置'}</div>
      </aside>
      <div className="account-ai-sections"><section className="account-ai-card" aria-labelledby="account-ai-title">
        <header><div><span className="assistant-eyebrow">AI ASSISTANT</span><h2 id="account-ai-title">AI 助手设置</h2></div>
          <span className="account-scope">当前标签页</span></header>
        <p className="account-ai-description">选择服务商，并填写该服务商的模型名称与 API Key。</p>
        {providers.length ? <AssistantConnectionSettings providers={providers} />
          : providerError ? <p role="alert">{providerError} <button className="button ghost" type="button" onClick={() => setRetry(value => value + 1)}>重试</button></p>
            : <p role="status">正在加载模型服务…</p>}
        <p className="account-privacy-note">只有在聊天中点击发送，研究数据与问题才会转发给所选服务商；调用费用由你的 API 账户承担。</p>
      </section>
      <AssistantInstructionSettings /></div>
    </div>
  </section>;
}
