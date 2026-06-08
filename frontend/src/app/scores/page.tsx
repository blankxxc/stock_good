export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 5 LightGBM scores ready</span>
      <h1>横截面评分</h1>
      <p>
        展示 Day 5 LightGBM baseline 输出的 score、rank、percentile、confidence、horizon、model_version 和泄漏检查状态。
        所有分数只表示研究排序信号，不是交易建议。
      </p>
      <div className="grid">
        <div className="card">
          <strong>评分产物</strong>
          <p>reports/day5/predictions.parquet 与 data/gold/model_signal_cross_sectional 已生成。</p>
        </div>
        <div className="card">
          <strong>模型与标签</strong>
          <p>model_version=lightgbm_day5_v001，label_version=label_v005，factor_version=factor_v004。</p>
        </div>
        <div className="card">
          <strong>可解释字段</strong>
          <p>按 trade_date 输出 rank、percentile、industry_name、confidence 和 leakage_check_status=passed。</p>
        </div>
        <div className="card">
          <strong>API</strong>
          <p>/api/scores 返回最新交易日 Top score rows 和 run_id / experiment_id / research_boundary。</p>
        </div>
      </div>
    </section>
  );
}
