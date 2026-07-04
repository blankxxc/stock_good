export default function Page() {
  return (
    <section className="public-page artifact-backed">
      <span className="badge">官网层 · artifact-backed narrative</span>
      <h1>能力介绍</h1>
      <p>覆盖股票全景、概率评分、条件筛选、因子解释、回测风险和数据安全边界。</p>
      <div className="field-list"><span>股票全景</span><span>概率评分</span><span>条件筛选</span><span>风险提示</span></div>
      <div className="grid">
        <div className="card"><strong>研究定位</strong><p>智能选股平台，面向用户提供选股辅助、风险提示和数据来源说明。</p></div>
        <div className="card"><strong>数据来源</strong><p>主流程通过后端 API 与本地 artifact 展示状态，synthetic/demo 数据会显式标注 data_mode。</p></div>
        <div className="card"><strong>合规边界</strong><p>页面不输出确定性交易指令，不承诺收益，不提供跟单能力。</p></div>
      </div>
    </section>
  );
}
