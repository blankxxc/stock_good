import './globals.css';
import type { ReactNode } from 'react';

export const metadata = {
  title: 'Stock Research Console',
  description: 'Traceable intelligent stock-selection research platform, not investment advice.'
};

const publicNav = [
  ['首页', '/'], ['能力介绍', '/capabilities'], ['方法论', '/methodology'], ['数据与安全', '/data-security'],
  ['回测与风控', '/backtest-risk'], ['RAG 证据', '/rag-evidence'], ['路线图', '/architecture-roadmap'], ['登录入口', '/login']
];
const consoleNav = [
  ['Dashboard', '/dashboard'], ['Scores', '/scores'], ['Candidates', '/candidates'], ['Backtests', '/backtests'],
  ['Factors', '/factors'], ['Experiments', '/experiments'], ['RAG', '/rag'], ['Data Quality', '/data-quality'],
  ['Lineage', '/lineage'], ['Lakehouse', '/lakehouse'], ['Spark Jobs', '/spark-jobs'], ['Realtime', '/realtime'],
  ['Flink Jobs', '/flink-jobs'], ['Graph', '/graph'], ['Models', '/models'], ['Simulation', '/simulation'],
  ['Reports', '/reports'], ['Licenses', '/settings/licenses'], ['Users', '/settings/users'], ['Audit', '/settings/audit'],
  ['Ops', '/ops']
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="professional-shell">
          <header className="topbar">
            <div><strong>Stock Research Console</strong><span>横截面评分 · 因子诊断 · 回测风控 · RAG 证据</span></div>
            <nav>{publicNav.map(([label, href]) => <a key={href} href={href}>{label}</a>)}</nav>
          </header>
          <aside className="sidebar">
            <p>Research Console</p>
            {consoleNav.map(([label, href]) => <a key={href} href={href}>{label}</a>)}
          </aside>
          <main>{children}</main>
          <div className="fixed-disclaimer">研究用途：仅输出研究排序、解释、回测报告和引用证据；正式使用前必须经过样本外验证、风控复核和人工审批。</div>
          <footer>ops_deployment 运维闭环：Research Console + Ops 编排 + 可观测性 + backup/restore smoke。</footer>
        </div>
      </body>
    </html>
  );
}
