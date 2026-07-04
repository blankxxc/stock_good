import { BacktestRiskDashboard, type BacktestPayload } from '../../components/BacktestRiskDashboard';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialBacktestPayload(): Promise<BacktestPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/backtests`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as BacktestPayload;
  } catch {
    return null;
  }
}

export default async function Page() {
  const initialBacktestPayload = await loadInitialBacktestPayload();

  return (
    <section className="public-page artifact-backed">
      <span className="badge">官网层 · Backtest & Risk</span>
      <h1>回测与风控</h1>
      <p className="lead">不只展示收益，更把回撤、换手、成本、容量、主动风险和行业/风格归因放到同一个风险驾驶舱里，避免“只看涨幅不看能不能扛”的假繁荣。</p>
      <div className="field-list"><span>drawdown</span><span>turnover</span><span>capacity_curve</span><span>risk attribution</span><span>risk_summary</span><span>risk_flags</span><span>baseline compare</span></div>
      <div className="cta-row"><a className="button primary" href="/backtests">打开回测风险详情</a><a className="button" href="/scores#candidate-pool">查看股票预测选股/候选池</a></div>
      <div className="grid">
        <div className="card"><strong>研究定位</strong><p>回测风险不是看“赚了多少”这么简单，而是看这个选股方法历史上怎么亏、亏多深、能不能承受。</p></div>
        <div className="card"><strong>核心指标</strong><p>最大回撤、夏普、Calmar、胜率、换手率、成本后收益、容量曲线、主动风险和风格暴露。</p></div>
        <div className="card"><strong>合规边界</strong><p>页面不输出确定性交易指令，不承诺收益，不提供跟单能力；只服务研究复核。</p></div>
      </div>
      <BacktestRiskDashboard initialPayload={initialBacktestPayload} />
    </section>
  );
}
