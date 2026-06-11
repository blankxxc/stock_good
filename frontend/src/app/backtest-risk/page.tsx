export default function Page() {
  return (
    <section className="public-page artifact-backed">
      <span className="badge">官网层 · artifact-backed narrative</span>
      <h1>回测与风控</h1>
      <p>这一页解释回测风险的作用；真正可交互的风险指标、风险旗标、容量曲线、最近30个回测点和风险归因已经放到 Research Console 的“回测风险”功能页。</p>
      <div className="field-list"><span>drawdown</span><span>turnover</span><span>capacity_curve</span><span>risk attribution</span><span>risk_summary</span><span>risk_flags</span></div>
      <div className="cta-row"><a className="button primary" href="/backtests">打开回测风险功能页</a><a className="button" href="/scores#candidate-pool">查看股票预测选股/候选池</a></div>
      <div className="grid">
        <div className="card"><strong>研究定位</strong><p>回测风险不是看“赚了多少”这么简单，而是看这个选股方法历史上怎么亏、亏多深、能不能承受。</p></div>
        <div className="card"><strong>核心指标</strong><p>最大回撤、夏普、Calmar、换手率、成本后收益、容量曲线、主动风险和风格暴露。</p></div>
        <div className="card"><strong>合规边界</strong><p>页面不输出确定性交易指令，不承诺收益，不提供跟单能力；只服务研究复核。</p></div>
      </div>
    </section>
  );
}
