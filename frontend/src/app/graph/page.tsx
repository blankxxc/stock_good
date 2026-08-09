import { RelationNetwork, StockRelationNetwork } from '../../components/StockRelationNetwork';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';
type AblationItem = { rank_ic_smoke?: number | null };
type GraphPayload = {
  relation_types?: string[];
  network?: RelationNetwork;
  ablation_summary?: {
    base_event_regime?: AblationItem;
    base_plus_relation_graph?: AblationItem;
  };
};

async function loadGraphPayload(): Promise<GraphPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/graph`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as GraphPayload;
  } catch {
    return null;
  }
}

function formatRankIc(value: number | null | undefined, signed = false) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return `${signed && value > 0 ? '+' : ''}${value.toFixed(4)}`;
}

export default async function Page() {
  const payload = await loadGraphPayload();
  const network = payload?.network;
  const relationTypes = payload?.relation_types ?? [];
  const baseline = payload?.ablation_summary?.base_event_regime?.rank_ic_smoke;
  const withRelations = payload?.ablation_summary?.base_plus_relation_graph?.rank_ic_smoke;
  const improvement = typeof baseline === 'number' && Number.isFinite(baseline)
    && typeof withRelations === 'number' && Number.isFinite(withRelations)
    ? withRelations - baseline
    : null;

  return (
    <section className="graph-page">
      <header className="graph-hero graph-hero--compact">
        <div>
          <span className="graph-hero-kicker">RELATION INTELLIGENCE</span>
          <h1>股票关系洞察</h1>
          <p>直接查看股票节点、真实关系连线和社区结构；筛选关系后点击股票，可追踪它的一跳关联。</p>
        </div>
        {network?.as_of_date ? <div className="graph-hero-live"><i />关系数据日期 · {network.as_of_date}</div> : null}
      </header>

      {!payload || !network || !network.nodes.length ? (
        <div className="graph-empty" role="status">关系网络暂时不可用，请稍后重试。</div>
      ) : (
        <>
          <StockRelationNetwork network={network} relationTypes={relationTypes} />

          <article className="graph-panel graph-factor-panel">
            <div className="graph-panel-heading">
              <div><span className="relation-eyebrow">FACTOR IMPACT</span><h2>关系因子效果</h2></div>
              <span>RankIC</span>
            </div>
            <p className="graph-factor-intro">
              RankIC 衡量因子排序与后续收益排序的一致性，绝对值越大代表排序相关性越强。这里对比加入关系因子前后的变化，用于观察关系信息是否带来增量。
            </p>
            <dl className="graph-effect-grid">
              <div><dt>基础因子</dt><dd>{formatRankIc(baseline)}</dd></div>
              <div><dt>加入关系因子</dt><dd>{formatRankIc(withRelations)}</dd></div>
              <div className={typeof improvement === 'number' && improvement > 0 ? 'is-positive' : undefined}>
                <dt>指标改善</dt><dd>{formatRankIc(improvement, true)}</dd>
              </div>
            </dl>
            <p className="graph-research-note">当前结果用于研究验证，指标改善不代表未来收益。</p>
          </article>
        </>
      )}
    </section>
  );
}
