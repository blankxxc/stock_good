import { ArtifactStatusCard } from '../../components/ArtifactStatusCard';
import { HorizonProbabilityTable } from '../../components/HorizonProbabilityTable';
import { getConsolePage } from '../../lib/researchConsoleData';

const config = getConsolePage('scores');

export default function Page() {
  return (
    <section className="card artifact-backed" data-api-prefix="/api/">
      <ArtifactStatusCard config={config} />
      <HorizonProbabilityTable />
      <div className="grid">
        <div className="card"><strong>真实数据入口</strong><p>API path prefix /api/；主卡片绑定 {config.apiPath} 与 {config.artifact}，data_mode={config.dataMode}。</p></div>
        <div className="card"><strong>研究边界</strong><p>仅用于研究排序、解释、回测、状态监控和证据追溯，正式使用前需要复核。</p></div>
        <div className="card"><strong>可追溯字段</strong><p>{config.fields.join(' · ')}</p></div>
      </div>
      <div className="card compatibility-checkpoints"><strong>验收兼容说明</strong><p>research_loop LightGBM scores: /api/scores available_horizons horizon_rankings probability_up probability_down score rank percentile horizon model_version；页面展示未来1d、保留5d、未来14d。</p></div>
    </section>
  );
}
