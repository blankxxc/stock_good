export default function Page() {
  return (
    <section className="public-page artifact-backed">
      <span className="badge">官网层 · artifact-backed narrative</span>
      <h1>回测与风控</h1>
      <p>强调净值之外的回撤、换手、容量、行业暴露、成本敏感性和边界提示。</p>
      <div className="field-list"><span>drawdown</span><span>turnover</span><span>capacity_curve</span><span>risk attribution</span></div>
      <div className="grid">
        <div className="card"><strong>研究定位</strong><p>智能选股研究平台 / 量化研究控制台 / 投研实验工作台，用于可追溯研究和复盘。</p></div>
        <div className="card"><strong>数据来源</strong><p>主流程通过后端 API 与本地 artifact 展示状态，synthetic/demo 数据会显式标注 data_mode。</p></div>
        <div className="card"><strong>合规边界</strong><p>页面不输出确定性交易指令，不承诺收益，不提供跟单能力。</p></div>
      </div>
    </section>
  );
}
