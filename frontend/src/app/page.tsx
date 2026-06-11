import { MarketOverviewBoard } from '../components/MarketOverviewBoard';

export default function Page() {
  return (
    <>
      <section className="hero artifact-backed home-intro">
        <div className="alpha-hero-grid">
          <div>
            <span className="badge">Obsidian Alpha · 官网层 · 可追溯投研终端</span>
            <h1 className="alpha-hero-title">智能选股<span>研究平台</span></h1>
            <p className="lead">智能选股研究平台 / 量化研究控制台 / 投研实验工作台 / 横截面评分与回测分析平台：把沪深300全景行情、横截面概率评分、条件实验室、回测风险和 RAG 证据压缩在一个黑曜石级研究工作台里，像证券终端一样快，像量化平台一样可审计。</p>
            <div className="alpha-chip-row">
              <span>300 CSI constituents</span>
              <span>1d / 5d / 14d horizon</span>
              <span>factor diagnostics</span>
              <span>no investment advice</span>
            </div>
            <div className="cta-row">
              <a className="button primary" href="/scores">进入横截面评分</a>
              <a className="button" href="/condition-screen">打开条件实验室</a>
              <a className="button" href="/backtests">查看回测风险</a>
            </div>
          </div>
          <div className="alpha-command-deck">
            <div className="alpha-command-line"><b>$</b> load universe --index CSI300 --mode latest_trade_date</div>
            <div className="alpha-command-line"><b>$</b> rank alpha --horizon 1d,5d,14d --explain factors</div>
            <div className="alpha-command-line"><b>$</b> gate candidate_pool --risk backtest --evidence rag</div>
          </div>
        </div>
        <div className="alpha-metric-grid">
          <div className="alpha-metric"><span>研究宇宙</span><strong>沪深300</strong></div>
          <div className="alpha-metric"><span>评分口径</span><strong>3 Horizons</strong></div>
          <div className="alpha-metric"><span>设计原则</span><strong>Traceable</strong></div>
        </div>
      </section>
      <div className="terminal-strip"><span>LIVE</span> market overview binds /api/market; click any stock code to open a securities-software style detail panel.</div>
      <MarketOverviewBoard />
    </>
  );
}
