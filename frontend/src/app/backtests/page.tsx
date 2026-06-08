export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 5 tradable backtest ready</span>
      <h1>回测报告</h1>
      <p>
        Day 5 已生成可交易 TopK 研究回测：t+1 open 执行、固定滑点/交易成本、换手、净值曲线、
        最大回撤、IC/RankIC、baseline 对比、风险归因和容量曲线。
      </p>
      <div className="grid">
        <div className="card">
          <strong>回测 artifacts</strong>
          <p>holdings.parquet / equity_curve.csv / risk_report.parquet / backtest_report.html 已落地到 reports/day5。</p>
        </div>
        <div className="card">
          <strong>成本与容量</strong>
          <p>transaction_cost_bp=10，slippage_model=fixed_bp，capacity_curve 覆盖 1%/5%/10%/20% ADV 情景。</p>
        </div>
        <div className="card">
          <strong>风险归因</strong>
          <p>portfolio_risk_report 包含 industry_attribution、style_attribution、transaction_cost_attribution、implementation_shortfall。</p>
        </div>
        <div className="card">
          <strong>API</strong>
          <p>/api/backtests 返回核心指标、baseline_metrics、curve_tail 和 artifact 路径。</p>
        </div>
      </div>
    </section>
  );
}
