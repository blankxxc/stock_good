export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 2 Parquet + DuckDB + Spark boundary</span>
      <h1>Lakehouse</h1>
      <p>Bronze/ODS、Silver/DWD、Gold/DWS、ADS 已由 Day 2 本地批处理样例生成；dataset_snapshot_manifest 记录 data_version、row_count、hash 和 upstream_snapshot_ids。</p>
      <div className="grid">
        <div className="card"><strong>稳定研究路径</strong><p>Parquet + DuckDB 查询脚本：lakehouse/duckdb/day2_research_queries.sql。</p></div>
        <div className="card"><strong>Spark 路径</strong><p>bronze_to_silver_market_daily.py 已验证 PySpark local 输出 parquet。</p></div>
        <div className="card"><strong>湖仓格式 PoC</strong><p>Delta connector 未内置时记录 blocked_reason，并生成 fallback Parquet schema-evolution manifest。</p></div>
      </div>
    </section>
  );
}
