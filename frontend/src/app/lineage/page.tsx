export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 3 L2 lineage ready</span>
      <h1>数据血缘</h1>
      <p>Day 3 已生成 reports/lineage_report.json 与 reports/lineage_report.html，展示 source_table → transform_job → target_table → snapshot/report/model/backtest 的轻量血缘。</p>
      <div className="grid">
        <div className="card"><strong>source_table 链路</strong><p>ODS 源表通过 day2_materialize_ods 进入 Bronze/ODS，再经 DWD、DWS、ADS transform job 连接到 dataset_snapshot_manifest。</p></div>
        <div className="card"><strong>Spark job run_id</strong><p>Spark job run_id 连接到输出 snapshot_id，用于证明 Spark 输出也进入同一套 quality 与 lineage 检查。</p></div>
        <div className="card"><strong>报告血缘</strong><p>reports/data_quality_report.json、reports/day3/leakage_report.json 和 reports/lineage_report.json 都作为 report 节点入图。</p></div>
        <div className="card"><strong>治理边界</strong><p>血缘只用于研究信号、排序、解释、回测和证据展示，不生成交易指令。</p></div>
      </div>
    </section>
  );
}
