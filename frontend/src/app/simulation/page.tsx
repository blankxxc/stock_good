import { ArtifactStatusCard } from '../../components/ArtifactStatusCard';
import { getConsolePage } from '../../lib/researchConsoleData';

const config = getConsolePage('simulation');

export default function Page() {
  return (
    <section className="card artifact-backed" data-api-prefix="/api/">
      <ArtifactStatusCard config={config} />
      <div className="grid">
        <div className="card"><strong>Day12 paper trading</strong><p>simulation_account、simulation_order、simulation_position、simulation_nav、simulation_risk 均来自 {config.apiPath} 与 reports/day12 产物；所有 order 均标记 simulated。</p></div>
        <div className="card"><strong>组合风控</strong><p>单票权重、行业权重、turnover、ST/停牌/涨跌停、流动性、max_drawdown、style exposure、tracking error、TopK concentration gate。</p></div>
        <div className="card"><strong>边界</strong><p>research simulation only，不连接券商，不生成真实交易指令；输出只用于研究复盘和人工复核。</p></div>
      </div>
    </section>
  );
}
