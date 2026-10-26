'use client';

import { useEffect, useRef, useState } from 'react';
import { useAssistantPreferences } from './AssistantPreferences';
import { downloadInstruction, importSkillMarkdown, PREFIX_LIMIT, SKILL_LIMIT, SKILL_COUNT_LIMIT, type AssistantSkill } from '../lib/assistantInstructions';

export function AssistantInstructionSettings() {
  const { instructions, saveInstructions, instructionStorageError } = useAssistantPreferences();
  const [draft, setDraft] = useState(instructions);
  const [selected, setSelected] = useState(instructions.skills[0]?.id || '');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [reading, setReading] = useState(false);
  const prefixFile = useRef<HTMLInputElement>(null), skillFile = useRef<HTMLInputElement>(null);
  const editor = draft.skills.find(skill => skill.id === selected);
  const dirty = JSON.stringify(draft) !== JSON.stringify(instructions);
  useEffect(() => {
    setDraft(instructions);
    setSelected(current => instructions.skills.some(skill => skill.id === current) ? current : instructions.skills[0]?.id || '');
  }, [instructions]);
  function changed() { setError(''); setNotice(''); }
  function updateSkill(patch: Partial<AssistantSkill>) {
    changed(); setDraft(current => ({ ...current, skills: current.skills.map(skill => skill.id === selected ? { ...skill, ...patch } : skill) }));
  }
  function add(skill: AssistantSkill) {
    if (draft.skills.length >= SKILL_COUNT_LIMIT) { setError('技能池最多保存 20 个技能，请先删除不用的技能。'); return false; }
    changed(); setDraft(current => ({ ...current, skills: [...current.skills, skill] })); setSelected(skill.id);
    return true;
  }
  async function importFile(file: File | undefined, target: 'prefix' | 'skill') {
    if (!file) return;
    setReading(true); changed();
    try {
      if (file.size > 65536) throw new Error('文本文件不能超过 64 KB。');
      const content = (await file.text()).replace(/^\uFEFF/, '');
      if (target === 'prefix') {
        if (content.length > PREFIX_LIMIT) throw new Error(`全局提示词最多 ${PREFIX_LIMIT} 个字符。`);
        setDraft(current => ({ ...current, prefix: content, prefixEnabled: true }));
      } else if (!add(importSkillMarkdown(content, file.name, crypto.randomUUID()))) return;
      setNotice('文本已导入编辑区，点击“保存提示词与技能”后生效。');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '无法读取文本文件。'); }
    finally { setReading(false); if (prefixFile.current) prefixFile.current.value = ''; if (skillFile.current) skillFile.current.value = ''; }
  }
  return <section className="account-ai-card account-instructions" aria-labelledby="account-instructions-title">
    <header><div><span className="assistant-eyebrow">PROMPTS & SKILLS</span><h2 id="account-instructions-title">提示词与技能</h2></div><span className="account-scope">本机保存</span></header>
    <p className="account-ai-description">为聊天助手设置固定偏好与可选研究技能。保存后，各研究页共用；每段对话可单独选择技能。</p>
    <form aria-label="提示词与技能设置" onSubmit={event => {
      event.preventDefault(); changed();
      try { const saved = saveInstructions(draft); setNotice(saved ? '提示词与技能已保存，下一次发送消息时生效。' : '已在当前标签页应用。'); }
      catch (reason) { setError(reason instanceof Error ? reason.message : '配置无效。'); }
    }}>
      <section className="instruction-section" aria-labelledby="prefix-heading">
        <div className="instruction-section-heading"><h3 id="prefix-heading">CLAUDE.md · 全局提示词</h3>
          <label className="instruction-switch"><input aria-label="启用全局提示词" type="checkbox" checked={draft.prefixEnabled}
            onChange={event => { changed(); setDraft(current => ({ ...current, prefixEnabled: event.target.checked })); }} />启用</label></div>
        <p>填写角色、分析步骤、语言和输出格式。每次聊天都会在问题前加入这些指令。</p>
        <textarea aria-label="CLAUDE.md 全局提示词" rows={7} maxLength={PREFIX_LIMIT} value={draft.prefix}
          placeholder={'例如：\n先给简洁结论，再列出数据依据和反证。\n涉及股票时说明日期与复权口径。\n优先用表格比较不同策略。'}
          onChange={event => { changed(); setDraft(current => ({ ...current, prefix: event.target.value })); }} />
        <div className="instruction-file-actions"><button className="button ghost" type="button" disabled={reading} onClick={() => prefixFile.current?.click()}>导入 CLAUDE.md</button>
          <button className="button ghost" type="button" disabled={!draft.prefix} onClick={() => downloadInstruction(draft.prefix, 'CLAUDE.md')}>导出</button>
          <small>{draft.prefix.length} / {PREFIX_LIMIT}</small></div>
        <input ref={prefixFile} type="file" accept=".md,.txt,text/plain,text/markdown" hidden aria-label="导入全局提示词文件" onChange={event => void importFile(event.target.files?.[0], 'prefix')} />
      </section>
      <section className="instruction-section" aria-labelledby="skills-heading">
        <div className="instruction-section-heading"><h3 id="skills-heading">Skill 技能池 <small>{draft.skills.length} / {SKILL_COUNT_LIMIT}</small></h3>
          <div className="instruction-file-actions"><button className="button ghost" type="button" disabled={reading || draft.skills.length >= SKILL_COUNT_LIMIT}
            onClick={() => add({ id: crypto.randomUUID(), name: '新技能', description: '', instructions: '', enabled: true })}>＋ 新建技能</button>
            <button className="button ghost" type="button" disabled={reading || draft.skills.length >= SKILL_COUNT_LIMIT} onClick={() => skillFile.current?.click()}>导入 SKILL.md</button></div></div>
        <p>文本技能用于约定模型的研究方法；不会执行文件中的脚本或自动加载外部资源。每段对话最多选择 3 个技能。</p>
        <input ref={skillFile} type="file" accept=".md,.txt,text/plain,text/markdown" hidden aria-label="导入技能文件" onChange={event => void importFile(event.target.files?.[0], 'skill')} />
        <div className="skill-manager"><div className="skill-manager-list" aria-label="技能列表">{draft.skills.map(skill => <button key={skill.id} type="button"
          className={skill.id === selected ? 'is-selected' : ''} aria-pressed={skill.id === selected} onClick={() => setSelected(skill.id)}>
          <strong>{skill.name || '未命名技能'}</strong><small>{skill.enabled ? skill.description || '可在聊天中选择' : '已停用'}</small></button>)}
          {!draft.skills.length && <p>暂无技能，点击上方按钮新建或导入。</p>}</div>
          {editor && <div className="skill-editor" key={editor.id}>
            <label>技能名称<input aria-label="技能名称" maxLength={60} value={editor.name} onChange={event => updateSkill({ name: event.target.value })} /></label>
            <label>简介<input aria-label="技能简介" maxLength={200} value={editor.description} onChange={event => updateSkill({ description: event.target.value })} /></label>
            <label>技能指令<textarea aria-label="技能指令" rows={8} maxLength={SKILL_LIMIT} value={editor.instructions} onChange={event => updateSkill({ instructions: event.target.value })} /></label>
            <div className="instruction-file-actions"><label className="instruction-switch"><input aria-label="允许在聊天中使用此技能" type="checkbox" checked={editor.enabled}
              onChange={event => updateSkill({ enabled: event.target.checked })} />允许在聊天中使用</label><small>{editor.instructions.length} / {SKILL_LIMIT}</small></div>
            <div className="instruction-file-actions"><button className="button ghost" type="button" onClick={() => {
                changed(); const rest = draft.skills.filter(skill => skill.id !== editor.id); setDraft(current => ({ ...current, skills: rest })); setSelected(rest[0]?.id || '');
              }}>删除技能</button></div>
          </div>}
        </div>
      </section>
      {error && <p role="alert" className="auth-message auth-message--error">{error}</p>}
      {instructionStorageError && <p role="status" className="account-privacy-note">{instructionStorageError}</p>}
      <div className="account-settings-actions"><button className="button" type="submit" disabled={reading}>保存提示词与技能</button>
        <button className="button ghost" type="button" disabled={!dirty || reading} onClick={() => { setDraft(instructions); setSelected(instructions.skills[0]?.id || ''); changed(); }}>撤销未保存修改</button>
        <span role="status" className="account-saved">{notice || (dirty ? '修改尚未保存' : '')}</span></div>
      <p className="account-privacy-note">提示词和技能保存在当前浏览器，不随账号同步；只在发送聊天消息时传给模型。此处不保存 API Key。</p>
    </form>
  </section>;
}
