'use client';

import Link from 'next/link';
import { useState } from 'react';
import { SELECTED_SKILL_LIMIT, type AssistantInstructions } from '../lib/assistantInstructions';

export function AssistantSkillPicker({ settings, selectedIds, onChange }: {
  settings: AssistantInstructions; selectedIds: string[]; onChange: (ids: string[]) => void;
}) {
  const [open, setOpen] = useState(false);
  const available = settings.skills.filter(skill => skill.enabled);
  const selected = selectedIds.filter(id => available.some(skill => skill.id === id));
  return <div className="assistant-instruction-tools">
    <details className="assistant-skill-picker" onToggle={event => setOpen(event.currentTarget.open)}>
      <summary aria-label="选择聊天技能">技能{selected.length ? ` · ${selected.length}` : ''}<span aria-hidden="true">⌄</span></summary>
      {open && <div className="assistant-skill-options">
        <header><strong>选择技能</strong><span>{selected.length} / {SELECTED_SKILL_LIMIT}</span></header>
        {available.map(skill => <label key={skill.id}><input type="checkbox" aria-label={`使用技能：${skill.name}`} checked={selected.includes(skill.id)}
          disabled={!selected.includes(skill.id) && selected.length >= SELECTED_SKILL_LIMIT}
          onChange={event => onChange(event.target.checked ? [...selected, skill.id] : selected.filter(id => id !== skill.id))} />
          <span>{skill.name}<small>{skill.description}</small></span></label>)}
        {!available.length && <p>暂无启用的技能，可以在个人设置中添加。</p>}
        <footer><button type="button" disabled={!selected.length} onClick={() => onChange([])}>清空选择</button><Link prefetch={false} href="/account#account-instructions-title">管理技能 ↗</Link></footer>
      </div>}
    </details>
    {settings.prefixEnabled && settings.prefix.trim() && <span className="assistant-prefix-badge" title="使用个人设置中保存的全局提示词">CLAUDE.md 已启用</span>}
  </div>;
}
