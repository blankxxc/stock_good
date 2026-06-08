const sources = [
  { dataset: "market_daily_ohlcv", status: "authorized", adapter: "local_sample_ready", policy: "display_allowed" },
  { dataset: "market_minute_rt", status: "restricted", adapter: "adapter_contract_ready", policy: "aggregate_only" },
  { dataset: "northbound_flow", status: "not_authorized", adapter: "adapter_contract_ready", policy: "no_display" },
  { dataset: "fund_flow", status: "adapter_pending", adapter: "adapter_pending", policy: "metadata_only" },
];

export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 2 license registry ready</span>
      <h1>许可证设置</h1>
      <p>数据许可证、展示范围、license_gate 和审计。Day 2 明确区分 authorized / restricted / not_authorized / adapter_pending，不伪造未授权数据。</p>
      <div className="grid">
        <div className="card"><strong>状态</strong><p>本地 source_license_registry.yaml 已生成；API /api/licenses 可返回数据源状态。</p></div>
        <div className="card"><strong>治理边界</strong><p>仅用于研究信号、排序、解释、回测和证据展示；受限源只展示元数据或聚合状态。</p></div>
      </div>
      <table>
        <thead><tr><th>dataset</th><th>license_status</th><th>adapter_status</th><th>display_policy</th></tr></thead>
        <tbody>
          {sources.map((row) => (
            <tr key={row.dataset}><td>{row.dataset}</td><td>{row.status}</td><td>{row.adapter}</td><td>{row.policy}</td></tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
