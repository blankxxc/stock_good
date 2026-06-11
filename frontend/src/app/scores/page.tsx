import { ArtifactStatusCard } from '../../components/ArtifactStatusCard';
import { HorizonProbabilityTable, type ScoresPayload } from '../../components/HorizonProbabilityTable';
import { getConsolePage } from '../../lib/researchConsoleData';

export const dynamic = 'force-dynamic';

const config = getConsolePage('scores');
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialScoresPayload(): Promise<ScoresPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/scores`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as ScoresPayload;
  } catch {
    return null;
  }
}

export default async function Page() {
  const initialScoresPayload = await loadInitialScoresPayload();

  return (
    <section className="card artifact-backed scores-page" data-api-prefix="/api/">
      <div className="section-heading-row">
        <div>
          <span className="badge">Alpha Scoring · multi-horizon probability</span>
          <h2>横截面评分台：把300只股票压成可复核候选池</h2>
          <p className="lead">围绕未来1d、未来5d、未来14d 三个 horizon 展示 Top10 上涨概率、下跌概率、score、rank 与 percentile；候选池只代表研究优先级，不代表买入建议。</p>
        </div>
        <a className="button" href="/condition-screen">进入条件实验室</a>
      </div>
      <div className="terminal-strip"><span>QUERY</span> GET /api/scores → available_horizons, horizon_rankings, probability_up, probability_down, candidate_pool, model_version</div>
      <ArtifactStatusCard config={config} />
      <HorizonProbabilityTable initialPayload={initialScoresPayload} />
      <div className="grid">
        <div className="card"><strong>真实数据入口</strong><p>API path prefix /api/；主卡片绑定 {config.apiPath} 与 {config.artifact}，data_mode={config.dataMode}。</p></div>
        <div className="card"><strong>研究边界</strong><p>仅用于研究排序、解释、回测、状态监控和证据追溯，正式使用前需要样本外和风控复核。</p></div>
        <div className="card"><strong>可追溯字段</strong><p>{config.fields.join(' · ')}</p></div>
      </div>
      <div className="card compatibility-checkpoints"><strong>验收兼容说明</strong><p>research_loop LightGBM scores: /api/scores available_horizons horizon_rankings probability_up probability_down score rank percentile horizon model_version；页面展示未来1d、未来5d（保留5d兼容口径）、未来14d。</p></div>
    </section>
  );
}
