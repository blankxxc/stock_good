import { ArtifactStatusCard } from '../../../components/ArtifactStatusCard';
import { getConsolePage } from '../../../lib/researchConsoleData';

const config = getConsolePage('settings/users');

export default function Page() {
  return (
    <section className="card artifact-backed" data-api-prefix="/api/">
      <ArtifactStatusCard config={config} />
      <div className="grid">
        <div className="card"><strong>governance_simulation RBAC</strong><p>admin、researcher、reviewer、viewer、compliance、data_owner 六类角色以 action-level permission 控制访问。</p></div>
        <div className="card"><strong>职责分离</strong><p>研究提交人与审批人分离；viewer 只能看已发布内容，不能查看未发布候选池、不能导出完整数据、不能运行实验。</p></div>
        <div className="card"><strong>API</strong><p>{config.apiPath} 返回 rbac_roles、duties_separation 和 research_boundary。</p></div>
      </div>
    </section>
  );
}
