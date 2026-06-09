export default function Page() {
  return (
    <section className="public-page artifact-backed">
      <span className="badge">官网层 · artifact-backed narrative</span>
      <h1>能力介绍</h1>
      <p>覆盖数据湖仓、因子库、横截面评分、回测风控、RAG 证据和 Research Console。</p>
      <div className="field-list"><span>湖仓状态</span><span>因子诊断</span><span>模型实验</span><span>引用证据</span></div>
      <div className="grid">
        <div className="card"><strong>研究定位</strong><p>智能选股研究平台 / 量化研究控制台 / 投研实验工作台，用于可追溯研究和复盘。</p></div>
        <div className="card"><strong>数据来源</strong><p>主流程通过后端 API 与本地 artifact 展示状态，synthetic/demo 数据会显式标注 data_mode。</p></div>
        <div className="card"><strong>合规边界</strong><p>页面不输出确定性交易指令，不承诺收益，不提供跟单能力。</p></div>
      </div>
    </section>
  );
}
