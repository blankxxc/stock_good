import { ArtifactStatusCard } from '../../../components/ArtifactStatusCard';
import { getConsolePage } from '../../../lib/researchConsoleData';

const config = getConsolePage('settings/licenses');

export default function Page() {
  return (
    <section className="card artifact-backed" data-api-prefix="/api/">
      <ArtifactStatusCard config={config} />
      <div className="grid">
        <div className="card"><strong>Day 2 兼容状态</strong><p>保留 not_authorized、restricted、adapter_pending 等 Day 2 license registry 语义，同时新增 Day12 license_gate。</p></div>
        <div className="card"><strong>license_gate</strong><p>未 approved、过期、不可导出、不可外部分享或不可派生的来源会被阻断或进入脱敏规则。</p></div>
        <div className="card"><strong>最小展示</strong><p>redisplay_allowed=false 时不展示原文或长摘录；snippet 受 max_snippet_chars 控制。</p></div>
      </div>
    </section>
  );
}
