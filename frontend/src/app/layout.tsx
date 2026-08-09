import './globals.css';
import type { ReactNode } from 'react';
import { ApplicationShell } from '../components/ApplicationShell';

export const metadata = {
  title: 'Obsidian Alpha | 智能选股平台',
  description: '面向用户的沪深300选股辅助平台：股票全景、概率评分、条件筛选与回测风险提示。'
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body><ApplicationShell>{children}</ApplicationShell></body>
    </html>
  );
}
