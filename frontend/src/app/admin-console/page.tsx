import type { Metadata } from 'next';
import { AdminDashboard } from '../../components/AdminDashboard';

export const metadata: Metadata = {
  title: '管理控制台 | Obsidian Alpha',
  description: 'Obsidian Alpha 独立管理员控制台：账户、安全、数据、研究与系统运行。',
};

export default function AdminConsolePage() {
  return <AdminDashboard />;
}
