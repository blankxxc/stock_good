import { AccountSettings } from '../../components/AccountSettings';

export const metadata = {
  title: '个人设置 | Obsidian Alpha',
  description: '管理 AI 助手的模型服务、API Key、全局提示词与 Skill 技能池。',
};

export default function Page() {
  return <AccountSettings />;
}
