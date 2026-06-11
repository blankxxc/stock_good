import './globals.css';
import type { ReactNode } from 'react';

export const metadata = {
  title: 'Obsidian Alpha | 智能选股研究终端',
  description: '沪深300横截面评分、条件实验室、回测风险与 RAG 证据的一体化投研研究终端。'
};

const publicNav = [
  ['首页', '/'], ['能力介绍', '/capabilities'], ['方法论', '/methodology'], ['数据与安全', '/data-security'],
  ['回测与风控', '/backtest-risk'], ['RAG 证据', '/rag-evidence'], ['路线图', '/architecture-roadmap'], ['登录入口', '/login']
];

const navSections = [
  {
    title: 'Alpha Workbench',
    items: [['股票全景', '/'], ['股票预测选股/候选池', '/scores'], ['条件测试', '/condition-screen'], ['回测风险', '/backtests']]
  },
  {
    title: '因子与模型',
    items: [['因子库', '/factors'], ['模型对比', '/models'], ['实验记录', '/experiments'], ['关系图谱', '/graph']]
  },
  {
    title: 'Data Fabric',
    items: [['Dashboard', '/dashboard'], ['数据质量', '/data-quality'], ['数据血缘', '/lineage'], ['Lakehouse', '/lakehouse'], ['Spark Jobs', '/spark-jobs'], ['Realtime', '/realtime'], ['Flink Jobs', '/flink-jobs']]
  },
  {
    title: 'Governance',
    items: [['RAG 证据', '/rag'], ['模拟盘', '/simulation'], ['报告导出', '/reports'], ['Licenses', '/settings/licenses'], ['Users', '/settings/users'], ['Audit', '/settings/audit'], ['Ops', '/ops']]
  }
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="professional-shell">
          <header className="topbar">
            <div>
              <strong>Obsidian Alpha</strong>
              <span>CSI300 · Factor Lab · Multi-Horizon Scores · Risk Replay · Evidence Graph</span>
            </div>
            <nav>{publicNav.map(([label, href]) => <a key={href} href={href}>{label}</a>)}</nav>
          </header>
          <aside className="sidebar">
            <p>Research Console</p>
            {navSections.map((section) => (
              <div className="console-nav-section" key={section.title}>
                <strong>{section.title}</strong>
                {section.items.map(([label, href]) => <a key={href} href={href}>{label}</a>)}
              </div>
            ))}
          </aside>
          <main>{children}</main>
          <div className="fixed-disclaimer">研究用途：所有信号仅用于排序、解释、回测与证据追溯；正式交易前必须经过样本外验证、风控复核和人工审批。</div>
          <footer>Obsidian Alpha Console · Research pipeline, data governance, audit trail and backup/restore smoke checks.</footer>
        </div>
      </body>
    </html>
  );
}
