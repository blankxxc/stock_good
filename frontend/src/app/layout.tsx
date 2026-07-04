import './globals.css';
import type { ReactNode } from 'react';

export const metadata = {
  title: 'Obsidian Alpha | 智能选股平台',
  description: '面向用户的沪深300选股辅助平台：股票全景、概率评分、条件筛选与回测风险提示。'
};

const publicNav = [
  ['股票全景', '/'], ['股票预测选股', '/scores'], ['条件选股', '/condition-screen'], ['回测风险', '/backtests'],
  ['因子库', '/factors'], ['模型表现', '/models'], ['关系图谱', '/graph'], ['登录入口', '/login']
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="professional-shell">
          <header className="topbar">
            <div>
              <strong>Obsidian Alpha</strong>
              <span>沪深300 · 概率评分 · 条件筛选 · 回测风险</span>
            </div>
            <nav>{publicNav.map(([label, href]) => <a key={href} href={href}>{label}</a>)}</nav>
          </header>
          <main>{children}</main>
          <div className="fixed-disclaimer">选股辅助：页面只提供数据展示、概率评分、条件筛选和风险提示，不构成投资建议；内部数据治理和敏感运维信息仅在后台管理界面查看。</div>
          <footer>Obsidian Alpha · 用户选股平台 · 数据安全、权限隔离和后台审计。</footer>
        </div>
      </body>
    </html>
  );
}
