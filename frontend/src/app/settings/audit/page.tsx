import { ArtifactStatusCard } from '../../../components/ArtifactStatusCard';
import { getConsolePage } from '../../../lib/researchConsoleData';

const config = getConsolePage('settings/audit');

export default function Page() {
  return (
    <section className="card artifact-backed" data-api-prefix="/api/">
      <ArtifactStatusCard config={config} />
      <div className="grid">
        <div className="card"><strong>governance_simulation append_only audit</strong><p>审计事件只追加不修改不删除，覆盖 submit_report、approve_report、export_report、license_gate 和 simulation action。</p></div>
        <div className="card"><strong>查询字段</strong><p>audit_id、actor、role、action、resource、created_at、trace_id、append_only。</p></div>
        <div className="card"><strong>导出联动</strong><p>export_manifest.audit_id 反向指向导出审计事件，便于追踪文件 hash 和审批链路。</p></div>
      </div>
    </section>
  );
}
