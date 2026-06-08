export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 3 L2 data trust ready</span>
      <h1>数据质量</h1>
      <p>Day 3 已接入真实本地 artifact：quality report、quarantine、leakage_check_status 与 synthetic mini market 验收，不再是静态占位。</p>
      <div className="grid">
        <div className="card"><strong>质量报告</strong><p>reports/data_quality_report.json 与 reports/data_quality_report.html 已生成，覆盖 schema、主键重复、缺失、价格、OHLC、成交量、交易日缺口、复权因子、行业、指数成分、ST/停牌/涨跌停、延迟、重复率、修正率和许可证 gate。</p></div>
        <div className="card"><strong>quarantine</strong><p>异常样本写入 data/quarantine/day3_synthetic_market，记录 reason、severity、source_row、detected_at、resolved_status、owner、resolution_note。</p></div>
        <div className="card"><strong>防泄漏</strong><p>leakage_check_status=passed；故意构造的 future_available_time、full_sample_standardization_leak、label_leakage_trap_feature 会被拦截。</p></div>
        <div className="card"><strong>synthetic mini market</strong><p>20 只股票 × 100 个交易日，覆盖停牌、ST、涨停、跌停、退市、新上市、公告晚于收盘、未来成分股和复权陷阱。</p></div>
      </div>
    </section>
  );
}
