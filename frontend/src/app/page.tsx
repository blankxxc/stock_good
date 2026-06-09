export default function Page() {
  return (
    <section className="hero artifact-backed">
      <span className="badge">官网层 · Day11 productized</span>
      <h1>智能选股研究平台</h1>
      <p className="lead">量化研究控制台 · 投研实验工作台 · 横截面评分与回测分析平台</p>
      <p>
        把数据湖仓、因子工程、模型实验、回测风控、RAG 引用证据和系统状态统一为一个专业、克制、可复现的研究入口。
      </p>
      <div className="cta-row">
        <a className="button primary" href="/dashboard">进入 Research Console</a>
        <a className="button" href="/architecture-roadmap">查看架构路线图</a>
      </div>
      <div className="grid kpi-grid">
        <div className="card"><strong>可信研究闭环</strong><p>数据 → 因子 → 模型 → 回测 → RAG → 风控，所有正式结果保留版本和时间语义。</p></div>
        <div className="card"><strong>artifact-backed</strong><p>核心工作台页面绑定 /api/* 与本地 artifact，synthetic/demo 数据显式标注 data_mode。</p></div>
        <div className="card"><strong>固定边界</strong><p>仅用于研究排序、解释、回测和证据展示，不输出确定性交易指令。</p></div>
      </div>
    </section>
  );
}
