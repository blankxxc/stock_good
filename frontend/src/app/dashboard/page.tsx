export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 5 L2 research loop ready</span>
      <h1>Dashboard</h1>
      <p>
        Day 5 已接入最新研究闭环：label_cross_sectional_return、LightGBM baseline、purged walk-forward、
        Top5 等权可交易回测、风险归因、容量估计和 experiment recorder。页面展示研究信号和回测证据，
        不提供买入/卖出/持有指令。
      </p>
      <div className="grid">
        <div className="card">
          <strong>最新 run</strong>
          <p>run_id=day5_lightgbm_walk_forward_v001，model_version=lightgbm_day5_v001，horizon=5d。</p>
        </div>
        <div className="card">
          <strong>质量门禁</strong>
          <p>leakage_check_status=passed，signal_time 为 t 日收盘后，execution_price_type 固定为 t+1 open。</p>
        </div>
        <div className="card">
          <strong>核心指标</strong>
          <p>展示 IC、RankIC、TopK_return、Turnover、Cost_adjusted_return、Capacity，可从 /api/dashboard 获取。</p>
        </div>
        <div className="card">
          <strong>治理边界</strong>
          <p>research_signals_only_not_investment_advice：仅用于研究信号、排序、解释、回测和证据展示。</p>
        </div>
      </div>
      <p>后端 API：/api/dashboard 返回 Day 5 最新 run 的状态、版本、核心指标和研究边界。</p>
    </section>
  );
}
