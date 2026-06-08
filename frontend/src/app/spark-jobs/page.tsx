export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 4 PySpark factor materialization ready</span>
      <h1>Spark Jobs</h1>
      <p>
        Day 4 已新增 spark/jobs/day4_factor_materialization.py：从 Day3 synthetic mini market 重新计算核心离线因子，
        写入 data/gold/model_feature_matrix_spark_check，并与 Polars factor engine 的 data/gold/model_feature_matrix_wide 做一致性验收。
      </p>
      <div className="grid">
        <div className="card">
          <strong>一致性状态</strong>
          <p>reports/day4/spark_factor_materialization_report.json：status=ok，consistency_status=passed，row_count=1960。</p>
        </div>
        <div className="card">
          <strong>对齐因子</strong>
          <p>return_5d、momentum_20d、volatility_20d、ma20_gap、volume/amount rolling mean、volume shock、intraday、range、turnover、size、VWAP deviation。</p>
        </div>
        <div className="card">
          <strong>治理边界</strong>
          <p>仅用于研究信号、排序、解释、回测和证据展示；真实供应商数据接入前不输出实盘交易建议。</p>
        </div>
      </div>
    </section>
  );
}
