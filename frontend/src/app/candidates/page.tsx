import { ArtifactStatusCard } from '../../components/ArtifactStatusCard';
import { getConsolePage } from '../../lib/researchConsoleData';

const config = getConsolePage('candidates');

export default function Page() {
  return (
    <section className="card artifact-backed" data-api-prefix="/api/">
      <ArtifactStatusCard config={config} />
      <div className="section-heading-row">
        <div>
          <span className="badge">候选池功能已迁移</span>
          <h2>候选池已放入“股票预测选股”页面</h2>
          <p>为了避免你在“候选池”和“股票预测选股”之间来回切换，候选池 Top20、入池原因、个股详情入口和回测风险入口已经统一放到 /scores 页面。</p>
        </div>
        <a className="button primary" href="/scores#candidate-pool">打开股票预测选股里的候选池</a>
      </div>
      <div className="grid">
        <div className="card"><strong>真实数据入口</strong><p>现在读取 /api/scores 的 candidate_pool 与 candidate_summary；原 {config.apiPath} 入口保留用于兼容旧验收。</p></div>
        <div className="card"><strong>研究边界</strong><p>候选池只是研究候选，不是买入名单；后续必须结合条件测试、回测风险和人工复核。</p></div>
        <div className="card"><strong>可追溯字段</strong><p>candidate_pool · candidate_summary · predicted_relative_change_pct · rank · score · model_version</p></div>
      </div>
    </section>
  );
}
