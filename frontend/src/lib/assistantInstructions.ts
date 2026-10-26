export type AssistantSkill = { id: string; name: string; description: string; instructions: string; enabled: boolean };
export type AssistantInstructions = { version: 1; prefix: string; prefixEnabled: boolean; skills: AssistantSkill[] };
export const INSTRUCTIONS_KEY = 'stock-good.assistant-instructions.v1';
export const PREFIX_LIMIT = 8000, SKILL_LIMIT = 6000, SKILL_COUNT_LIMIT = 20, SELECTED_SKILL_LIMIT = 3, INSTRUCTION_BUDGET = 20000;

export function defaultInstructions(): AssistantInstructions {
  return { version: 1, prefix: '', prefixEnabled: true, skills: [
    { id: 'factor-analysis', name: '因子解读', description: '解释因子方向、重复信号与失效条件。', enabled: true,
      instructions: '逐一解释当前因子的定义、数值、单位和方向。区分动量、波动、流动性等维度，指出重复或冲突的信号。结合价格判断是否有交叉验证，列出失效条件和缺失数据；不要把单一因子当作确定的买卖信号。' },
    { id: 'price-volume', name: '量价分析', description: '结合日线价格、成交量与风险分析趋势。', enabled: true,
      instructions: '先说明数据日期及复权口径，再结合可用日线与成交量描述趋势、波动和量价关系。仅在数据支持时讨论关键区间；区分已经观察到的事实与推测，并给出反证条件。没有相应历史数据时明确说明，不能自行补全价格。' },
    { id: 'strategy-review', name: '策略复盘', description: '比较策略收益、回撤、成本与回测偏差。', enabled: true,
      instructions: '依据已运行的策略实验比较收益、回撤、波动、换手和交易成本。检查样本区间、再平衡、成分股幸存者偏差和样本外证据。尚未运行的配置只讨论验证方案，不生成收益数字。最后提出下一步可在现有实验功能中验证的对比方案。' },
    { id: 'research-challenge', name: '反证检查', description: '寻找结论的反例、数据缺口与替代解释。', enabled: true,
      instructions: '审查问题或已有结论的证据。分别列出支持依据、反对依据、缺失的数据，以及可能的替代解释。说明哪些新观察会推翻当前结论。保持简洁，避免为了完整而编造证据。' },
  ] };
}

function text(value: unknown, max: number, label: string, required = false): string {
  if (typeof value !== 'string' || value.length > max || (required && !value.trim())) throw new Error(`${label}${required ? '不能为空，且' : ''}最多 ${max} 个字符。`);
  return value;
}

/** Whitelist public prompt fields. Connection credentials never enter this storage object. */
export function parseInstructions(value: unknown): AssistantInstructions {
  if (!value || typeof value !== 'object') throw new Error('提示词与技能配置格式无效。');
  const obj = value as Record<string, unknown>;
  if (obj.version !== 1 || typeof obj.prefixEnabled !== 'boolean' || !Array.isArray(obj.skills) || obj.skills.length > SKILL_COUNT_LIMIT) throw new Error('技能池最多保存 20 个技能，配置版本应为 1。');
  const skills = obj.skills.map((item: unknown): AssistantSkill => {
    if (!item || typeof item !== 'object') throw new Error('技能格式无效。');
    const skill = item as Record<string, unknown>;
    if (typeof skill.id !== 'string' || !/^[a-zA-Z0-9_-]{1,80}$/.test(skill.id) || typeof skill.enabled !== 'boolean') throw new Error('技能标识或启用状态无效。');
    return { id: skill.id, name: text(skill.name, 60, '技能名称', true).trim(), description: text(skill.description, 200, '技能简介'),
      instructions: text(skill.instructions, SKILL_LIMIT, '技能内容', true), enabled: skill.enabled };
  });
  if (new Set(skills.map(skill => skill.id)).size !== skills.length) throw new Error('技能标识不能重复。');
  return { version: 1, prefix: text(obj.prefix, PREFIX_LIMIT, '全局提示词'), prefixEnabled: obj.prefixEnabled, skills };
}

export function restoreInstructions(raw: string): AssistantInstructions {
  if (raw.length > 180000) throw new Error('提示词与技能配置过大。');
  return parseInstructions(JSON.parse(raw));
}

export function instructionPayload(settings: AssistantInstructions, ids: string[]) {
  const selected = [...new Set(ids)].flatMap(id => {
    const skill = settings.skills.find(item => item.id === id && item.enabled);
    return skill ? [{ id: skill.id, name: skill.name, instructions: skill.instructions }] : [];
  });
  if (selected.length > SELECTED_SKILL_LIMIT) throw new Error('每次最多启用 3 个技能。');
  const prefix = settings.prefixEnabled ? settings.prefix : '';
  if (prefix.length + selected.reduce((total, skill) => total + skill.instructions.length, 0) > INSTRUCTION_BUDGET) throw new Error('全局提示词与所选技能合计最多 20000 个字符，请缩短内容或减少技能。');
  return { prompt_prefix: prefix, skills: selected };
}

export function importSkillMarkdown(raw: string, filename: string, id: string): AssistantSkill {
  const content = raw.replace(/^\uFEFF/, '').trim();
  text(content, SKILL_LIMIT, '技能内容', true);
  // Frontmatter stays in the instruction text. Only simple display metadata is extracted.
  const frontmatter = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/.exec(content)?.[1] || '';
  const label = /^name:\s*([^\r\n]+)$/m.exec(frontmatter)?.[1]?.replace(/^['"]|['"]$/g, '').trim();
  const heading = /^#\s+(.+)$/m.exec(content)?.[1]?.trim();
  const description = /^description:\s*([^\r\n]+)$/m.exec(frontmatter)?.[1]?.replace(/^['"]|['"]$/g, '').trim() || '';
  return { id, name: (label || heading || (filename.toLowerCase() === 'skill.md' ? '导入的技能' : filename.replace(/\.(md|txt)$/i, ''))).slice(0, 60),
    description: ['>', '|', '>-', '|-'].includes(description) ? '' : description.slice(0, 200), instructions: content, enabled: true };
}

export function downloadInstruction(content: string, filename: string) {
  const url = URL.createObjectURL(new Blob([content], { type: 'text/markdown;charset=utf-8' }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
