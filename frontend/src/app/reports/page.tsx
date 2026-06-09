import { ArtifactStatusCard } from '../../components/ArtifactStatusCard';
import { getConsolePage } from '../../lib/researchConsoleData';

const config = getConsolePage('reports');

export default function Page() {
  return (
    <section className="card artifact-backed" data-api-prefix="/api/">
      <ArtifactStatusCard config={config} />
      <div className="grid">
        <div className="card"><strong>Day12 报告状态机</strong><p>draft → review → approved → exportable → exported → revoked，导出前检查 data_quality、leakage、license_gate、RAG citation 和 forbidden_wording。</p></div>
        <div className="card"><strong>export_manifest</strong><p>export_id、report_id、run_id、export_type、data_versions、factor_versions、model_version、label_version、rag_sources、file_hash、audit_id。</p></div>
        <div className="card"><strong>水印与留痕</strong><p>导出产物带 RESEARCH_SIMULATION_ONLY_NOT_INVESTMENT_ADVICE watermark，并写入 append_only audit 事件。</p></div>
      </div>
    </section>
  );
}
