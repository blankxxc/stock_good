export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 2 ADS summary ready</span>
      <h1>Dashboard</h1>
      <p>展示 universe、data cutoff、模型版本、质量告警和非投资建议边界。Day 2 已生成 ads_dashboard_summary / ads_score_latest / ads_backtest_summary。</p>
      <div className="grid">
        <div className="card"><strong>数据层</strong><p>Bronze/Silver/Gold/ADS 本地 Parquet 已落地，DuckDB 可查询。</p></div>
        <div className="card"><strong>治理边界</strong><p>仅用于研究信号、排序、解释、回测和证据展示。</p></div>
      </div>
    </section>
  );
}
