import './globals.css';
import type { ReactNode } from 'react';

export const metadata = {
  title: 'Stock Research Console',
  description: 'Traceable intelligent stock-selection research platform, not investment advice.'
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="topbar">
          <strong>Stock Research Console</strong>
          <span>横截面评分 · 因子诊断 · 回测风控 · RAG 证据</span>
        </header>
        <main>{children}</main>
        <footer>研究用途：仅输出研究信号、排序、解释和回测报告，不提供确定性交易指令。</footer>
      </body>
    </html>
  );
}
