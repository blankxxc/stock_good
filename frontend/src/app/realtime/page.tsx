export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 6 L1 realtime PoC ready</span>
      <h1>实时链路</h1>
      <p>
        Day 6 已接入 Kafka/Redpanda 标准 topic、本地 replay/simulated producer、在线特征快照、
        realtime_factor_latest 和实时/离线重算偏差报告。数据源明确标注为 replay/simulated feed，不冒充真实行情权限。
      </p>
      <div className="grid">
        <div className="card">
          <strong>API</strong>
          <p>/api/realtime 读取 topic health、events/sec、late data、latest factor timestamp、Redis-compatible online feature cache 和 sink 状态。</p>
        </div>
        <div className="card">
          <strong>核心 topic</strong>
          <p>raw.market.minute、clean.market.minute、factor.realtime.price_volume、feature.online.snapshot、alert.data_quality、alert.risk。</p>
        </div>
        <div className="card">
          <strong>监控指标</strong>
          <p>topic lag、events/sec、late data count、watermark delay、latest factor timestamp、Redis online feature 状态。</p>
        </div>
        <div className="card">
          <strong>治理边界</strong>
          <p>Signal preview 必须标注 PoC / not formal signal；仅用于研究监控、排序解释和模拟盘验证，不提供买卖指令。</p>
        </div>
      </div>
    </section>
  );
}
