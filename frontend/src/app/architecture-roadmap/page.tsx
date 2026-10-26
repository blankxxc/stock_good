export default function Page() {
  return (
    <section className="public-page artifact-backed">
      <span className="badge">官网层 · artifact-backed narrative</span>
      <h1>架构与路线图</h1>
      <p>围绕日频数据，完善因子、关系图、模型评估、回测和模拟研究。</p>
      <div className="field-list"><span>foundation-research_site</span><span>Lakehouse</span><span>日频研究</span><span>V2 backlog</span></div>
      <div className="grid">
        <div className="card"><strong>研究定位</strong><p>智能选股研究平台 / 量化研究控制台 / 投研实验工作台，用于可追溯研究和复盘。</p></div>
        <div className="card"><strong>数据来源</strong><p>主流程通过后端 API 与本地 artifact 展示状态，synthetic/demo 数据会显式标注 data_mode。</p></div>
        <div className="card"><strong>合规边界</strong><p>页面不输出确定性交易指令，不承诺收益，不提供跟单能力。</p></div>
      </div>
    </section>
  );
}
