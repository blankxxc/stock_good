'use client';

import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { AuthNav } from './AuthNav';

const publicNav = [
  ['股票全景', '/'], ['股票预测选股', '/scores'], ['条件选股', '/condition-screen'], ['回测风险', '/backtests'],
  ['因子库', '/factors'], ['模型表现', '/models'], ['关系图谱', '/graph'], ['我的自选', '/watchlist'],
];

export function ApplicationShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isAdminRoute = pathname === '/admin-console' || pathname.startsWith('/admin-console/');
  const isActiveRoute = (href: string) => (
    href === '/'
      ? pathname === '/' || pathname.startsWith('/stocks/')
      : pathname === href || pathname.startsWith(`${href}/`)
  );

  if (isAdminRoute) {
    return (
      <div className="admin-application-shell">
        <a className="skip-link" href="#admin-main-content">跳到后台主要内容</a>
        <main id="admin-main-content" className="admin-root-main" tabIndex={-1}>{children}</main>
      </div>
    );
  }

  return (
    <div className="professional-shell">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <header className="topbar">
        <a className="topbar__brand" href="/" aria-label="Obsidian Alpha 股票全景首页">
          <span className="topbar__brand-mark" aria-hidden="true">OA</span>
          <span className="topbar__brand-copy">
            <strong>Obsidian Alpha</strong>
            <small>沪深300 · 概率评分 · 条件筛选 · 回测风险</small>
          </span>
        </a>
        <nav aria-label="主导航">
          {publicNav.map(([label, href]) => {
            const active = isActiveRoute(href);
            return (
              <a className={active ? 'active' : undefined} aria-current={active ? 'page' : undefined} key={href} href={href}>
                {label}
              </a>
            );
          })}
          <AuthNav />
        </nav>
      </header>
      <main id="main-content" tabIndex={-1}>{children}</main>
      <div className="fixed-disclaimer">选股辅助：页面只提供数据展示、概率评分、条件筛选和风险提示，不构成投资建议；内部数据治理和敏感运维信息仅在后台管理界面查看。</div>
      <footer>Obsidian Alpha · 用户选股平台 · 数据安全、权限隔离和后台审计。</footer>
    </div>
  );
}
