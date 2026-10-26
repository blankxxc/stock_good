import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import React from 'react';
import TestRenderer, { act, type ReactTestRenderer } from 'react-test-renderer';
import { AssistantPreferencesProvider, useAssistantPreferences } from '../src/components/AssistantPreferences';
import { AssistantInstructionSettings } from '../src/components/AssistantInstructionSettings';
import AssistantPanel from '../src/components/AssistantPanel';
import { defaultInstructions, importSkillMarkdown, INSTRUCTIONS_KEY, instructionPayload, parseInstructions, restoreInstructions } from '../src/lib/assistantInstructions';

Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true, self: globalThis });
const oldFetch = globalThis.fetch;
const oldStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
let renderer: ReactTestRenderer | null = null;
let preferences: ReturnType<typeof useAssistantPreferences>;
afterEach(async () => {
  if (renderer) await act(async () => renderer?.unmount()); renderer = null;
  globalThis.fetch = oldFetch;
  if (oldStorage) Object.defineProperty(globalThis, 'localStorage', oldStorage); else Reflect.deleteProperty(globalThis, 'localStorage');
});
function storage(saved?: string) {
  const values = new Map(saved ? [[INSTRUCTIONS_KEY, saved]] : []);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: {
    getItem: (key: string) => values.get(key) ?? null, setItem: (key: string, value: string) => values.set(key, value),
  } });
  return values;
}
function Capture() { preferences = useAssistantPreferences(); return null; }
function Harness({ settings = false }: { settings?: boolean }) {
  return <AssistantPreferencesProvider pathname={settings ? '/account' : '/strategy-lab'}><Capture />
    {settings ? <AssistantInstructionSettings /> : <AssistantPanel open pathname="/strategy-lab" snapshot={null} onClose={() => {}} />}
  </AssistantPreferencesProvider>;
}
const connection = { provider: { id: 'deepseek', label: 'DeepSeek', base_url: 'https://api.deepseek.com', default_model: 'test-model' }, model: 'test-model', apiKey: 'secret-memory-only' };

test('instruction storage strips unrelated credential fields and rejects invalid or unbounded data', () => {
  const initial = defaultInstructions();
  assert.deepEqual(parseInstructions({ ...initial, apiKey: 'discard', skills: initial.skills.map(skill => ({ ...skill, apiKey: 'discard' })) }), initial);
  for (const patch of [{ version: 2 }, { prefixEnabled: 'true' }, { prefix: 12 }, { prefix: 'x'.repeat(8001) },
    { skills: [...initial.skills, initial.skills[0]] }, { skills: [{ ...initial.skills[0], instructions: ' ' }] },
    { skills: [{ ...initial.skills[0], instructions: 'x'.repeat(6001) }] }, { skills: [{ ...initial.skills[0], enabled: 'false' }] }]) {
    assert.throws(() => parseInstructions({ ...initial, ...patch }));
  }
  assert.throws(() => restoreInstructions('x'.repeat(180001)));
  assert.throws(() => instructionPayload(initial, initial.skills.map(skill => skill.id)), /3/);
  const large = { ...initial, prefix: 'p'.repeat(8000), skills: initial.skills.map(skill => ({ ...skill, instructions: 's'.repeat(6000) })) };
  assert.throws(() => instructionPayload(large, large.skills.slice(0, 3).map(skill => skill.id)), /20000/);
});

test('SKILL.md import preserves instruction text without interpreting scripts or resource links', () => {
  const raw = '---\nname: "自定义研究"\ndescription: 检查反证\n---\n# 研究方法\n读取 references/data.md 然后运行 scripts/demo.py';
  const imported = importSkillMarkdown(raw, 'SKILL.md', 'custom-test');
  assert.equal(imported.name, '自定义研究');
  assert.equal(imported.description, '检查反证');
  assert.equal(imported.instructions, raw);
  assert.equal(importSkillMarkdown('\uFEFF# 标题\n内容', 'SKILL.md', 'plain').name, '标题');
  assert.throws(() => importSkillMarkdown('x'.repeat(6001), 'SKILL.md', 'big'));
});

test('settings save and restore prefix and custom skills without saving or restoring the API key', async () => {
  const values = storage(); let requests = 0;
  globalThis.fetch = async () => { requests++; throw new Error('Settings must not call a model'); };
  await act(async () => { renderer = TestRenderer.create(<Harness settings />); });
  await act(async () => preferences.apply(connection));
  const root = renderer!.root;
  await act(async () => root.findByProps({ 'aria-label': 'CLAUDE.md 全局提示词' }).props.onChange({ target: { value: '使用简洁表格，先给结论。' } }));
  const create = root.findAllByType('button').find(button => button.children.join('') === '＋ 新建技能')!;
  await act(async () => create.props.onClick());
  await act(async () => root.findByProps({ 'aria-label': '技能名称' }).props.onChange({ target: { value: '我的复盘技能' } }));
  await act(async () => root.findByProps({ 'aria-label': '技能指令' }).props.onChange({ target: { value: '检查回撤和样本外表现。' } }));
  assert.equal(values.size, 0, 'editing is not saved until explicit save');
  await act(async () => root.findByProps({ 'aria-label': '提示词与技能设置' }).props.onSubmit({ preventDefault() {} }));
  const saved = values.get(INSTRUCTIONS_KEY)!;
  assert.equal(JSON.parse(saved).prefix, '使用简洁表格，先给结论。');
  assert.equal(JSON.parse(saved).skills.at(-1).name, '我的复盘技能');
  assert.ok(!saved.includes(connection.apiKey));
  assert.equal(requests, 0);
  await act(async () => renderer!.unmount()); renderer = null;
  await act(async () => { renderer = TestRenderer.create(<Harness settings />); });
  assert.equal(preferences.connection, null);
  assert.equal(preferences.instructions.prefix, '使用简洁表格，先给结论。');
  assert.equal(preferences.instructions.skills.at(-1)?.name, '我的复盘技能');
});

test('file imports populate drafts, enforce text limits and do not make network requests', async () => {
  storage();
  globalThis.fetch = async () => { throw new Error('No model request during import'); };
  await act(async () => { renderer = TestRenderer.create(<Harness settings />); });
  const root = renderer!.root;
  const file = (name: string, content: string) => ({ name, size: content.length, text: async () => content });
  await act(async () => root.findByProps({ 'aria-label': '导入全局提示词文件' }).props.onChange({ target: { files: [file('CLAUDE.md', '# 偏好\n用中文回答。')] } }));
  assert.equal(root.findByProps({ 'aria-label': 'CLAUDE.md 全局提示词' }).props.value, '# 偏好\n用中文回答。');
  await act(async () => root.findByProps({ 'aria-label': '导入技能文件' }).props.onChange({ target: { files: [file('SKILL.md', '---\nname: 示例技能\n---\n核对数据。')] } }));
  assert.equal(root.findByProps({ 'aria-label': '技能名称' }).props.value, '示例技能');
  await act(async () => root.findByProps({ 'aria-label': '导入全局提示词文件' }).props.onChange({ target: { files: [file('CLAUDE.md', 'x'.repeat(8001))] } }));
  assert.equal(root.findByProps({ 'aria-label': 'CLAUDE.md 全局提示词' }).props.value, '# 偏好\n用中文回答。');
  assert.ok(root.findByProps({ role: 'alert' }));
  assert.equal(preferences.instructions.prefix, '', 'imports remain drafts until saved');
});

test('chat sends selected skills and enabled prefix only; selection is independent in each conversation', async () => {
  const initial = defaultInstructions(); initial.prefix = '先列三条关键结论';
  initial.skills[3].enabled = false;
  storage(JSON.stringify(initial));
  const calls: any[] = [];
  globalThis.fetch = async (_url, init) => { calls.push({ body: JSON.parse(String(init?.body)), headers: init?.headers }); return new Response('{"type":"delta","text":"完成"}\n{"type":"done"}\n'); };
  await act(async () => { renderer = TestRenderer.create(<Harness />); });
  await act(async () => preferences.apply(connection));
  const root = renderer!.root;
  const openSkills = async () => act(async () => root.findByProps({ className: 'assistant-skill-picker' }).props.onToggle({ currentTarget: { open: true } }));
  const ask = async (content: string) => {
    await act(async () => root.findByType('textarea').props.onChange({ target: { value: content } }));
    await act(async () => root.findByType('form').props.onSubmit({ preventDefault() {} }));
  };
  await openSkills();
  assert.equal(root.findAllByProps({ 'aria-label': '使用技能：反证检查' }).length, 0);
  await act(async () => root.findByProps({ 'aria-label': '使用技能：因子解读' }).props.onChange({ target: { checked: true } }));
  await ask('解释当前因子');
  assert.equal(calls[0].body.prompt_prefix, initial.prefix);
  assert.deepEqual(calls[0].body.skills, [{ id: initial.skills[0].id, name: initial.skills[0].name, instructions: initial.skills[0].instructions }]);
  assert.equal(calls[0].headers['X-AI-API-Key'], connection.apiKey);
  assert.ok(!JSON.stringify(calls[0].body).includes(connection.apiKey));
  await act(async () => root.findByProps({ 'aria-label': '新建对话' }).props.onClick());
  await ask('普通问题'); assert.deepEqual(calls[1].body.skills, []);
  await act(async () => root.findAllByProps({ role: 'tab' })[0].props.onClick());
  await openSkills();
  assert.equal(root.findByProps({ 'aria-label': '使用技能：因子解读' }).props.checked, true);
  await act(async () => { preferences.saveInstructions({ ...initial, prefixEnabled: false, skills: initial.skills.filter(skill => skill.id !== 'factor-analysis') }); });
  await ask('删除技能后继续');
  assert.equal(calls[2].body.prompt_prefix, '');
  assert.deepEqual(calls[2].body.skills, []);
});

test('a blocked storage write still applies settings for this tab and reports that persistence failed', async () => {
  storage();
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: { getItem: () => null, setItem: () => { throw new Error('blocked'); } } });
  await act(async () => { renderer = TestRenderer.create(<Harness settings />); });
  await act(async () => { assert.equal(preferences.saveInstructions({ ...defaultInstructions(), prefix: '本次浏览使用' }), false); });
  assert.equal(preferences.instructions.prefix, '本次浏览使用');
  assert.match(preferences.instructionStorageError, /未能保存/);
});
