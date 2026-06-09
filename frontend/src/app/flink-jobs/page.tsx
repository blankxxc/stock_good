export default function Page() {
  return (
    <section className="card">
      <span className="badge">Day 6 L1 Flink semantics PoC ready</span>
      <h1>Flink Jobs</h1>
      <p>
        Day 6 已落地五类实时任务：行情清洗、实时价量/微观结构因子、新闻公告事件因子、市场环境因子、关系传播因子。
        本地 PoC 生成 event-time watermark、late-data、checkpoint 和 output topic 状态，后续可替换为真实 Flink 集群执行。
      </p>
      <div className="grid">
        <div className="card">
          <strong>API</strong>
          <p>/api/flink-jobs 返回 job status、input/output topics、窗口、watermark delay、checkpoint/savepoint 状态。</p>
        </div>
        <div className="card">
          <strong>Job 1</strong>
          <p>raw.market.tick/raw.market.minute → clean.market.tick/clean.market.minute，包含 dedup、异常价格过滤和 late data 标记。</p>
        </div>
        <div className="card">
          <strong>Job 2-5</strong>
          <p>输出 factor.realtime.price_volume、microstructure、news_sentiment、market_regime、relation，并写入 factor_intraday_panel。</p>
        </div>
        <div className="card">
          <strong>成熟度</strong>
          <p>L1 PoC：可回放、可验证、可对比离线重算；不承诺生产级低延迟或实盘交易。</p>
        </div>
      </div>
    </section>
  );
}
