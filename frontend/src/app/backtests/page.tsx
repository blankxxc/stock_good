import { ArtifactStatusCard } from '../../components/ArtifactStatusCard';
import { BacktestRiskDashboard, type BacktestPayload } from '../../components/BacktestRiskDashboard';
import { getConsolePage } from '../../lib/researchConsoleData';

export const dynamic = 'force-dynamic';

const config = getConsolePage('backtests');
const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialBacktestPayload(): Promise<BacktestPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/backtests`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as BacktestPayload;
  } catch {
    return null;
  }
}

export default async function Page() {
  const initialBacktestPayload = await loadInitialBacktestPayload();

  return (
    <section className="card artifact-backed backtests-page" data-api-prefix="/api/">
      <ArtifactStatusCard config={config} />
      <div className="section-heading-row">
        <div>
          <span className="badge">回测风险</span>
          <h2>完善后的策略回测、风险指标、容量曲线和风险归因</h2>
          <p>这里回答“候选池/预测选股方法过去怎么亏、亏多深、换手多高、容量是否够、风险来自哪里”。</p>
        </div>
      </div>
      <BacktestRiskDashboard initialPayload={initialBacktestPayload} />
      <div className="grid">
        <div className="card"><strong>真实数据入口</strong><p>API path prefix /api/；主卡片绑定 {config.apiPath} 与 {config.artifact}，data_mode={config.dataMode}。</p></div>
        <div className="card"><strong>研究边界</strong><p>仅用于研究排序、解释、回测、状态监控和证据追溯，正式使用前需要复核。</p></div>
        <div className="card"><strong>可追溯字段</strong><p>{config.fields.join(' · ')}</p></div>
      </div>
      <div className="card compatibility-checkpoints"><strong>验收兼容说明</strong><p>research_loop tradable backtest: /api/backtests TopK risk capacity cost adjusted metrics risk_summary risk_flags capacity_curve risk_attribution.</p></div>
    </section>
  );
}
