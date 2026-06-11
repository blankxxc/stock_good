import { ConditionScreenTable, type ConditionScreenPayload } from '../../components/ConditionScreenTable';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialConditionScreenPayload(): Promise<ConditionScreenPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/condition-screen`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as ConditionScreenPayload;
  } catch {
    return null;
  }
}

export default async function Page() {
  const initialPayload = await loadInitialConditionScreenPayload();

  return (
    <section className="card artifact-backed condition-screen-page" data-api-prefix="/api/condition-screen">
      <div className="section-heading-row">
        <div>
          <span className="badge">Condition Lab · 规则和因子同屏验证</span>
          <h2>条件实验室：沪深300样本逐行核验</h2>
          <p className="lead">展示最近可用行情与条件判断；不满足条件或必要特征缺失统一显示为“否”。技术条件和金融因子可以同屏勾选、逐列筛选，避免把未来收益或不可解释字段混进研究判断。</p>
        </div>
        <a className="button" href="/scores">返回横截面评分</a>
      </div>
      <div className="terminal-strip"><span>FILTER</span> /api/condition-screen → base_columns + available_factor_columns + column_schema; every failed or missing condition is rendered as 否.</div>
      <div className="grid">
        <div className="card"><strong>非ST</strong><p>没有退市风险；当前行情数据先用 st_flag、delist_flag 和股票名称含 ST 作为代理过滤。</p></div>
        <div className="card"><strong>均线多头排列</strong><p>MA5、MA10、MA20、MA30、MA60、MA250 按短到长向上排列，且均线本身相对上一交易日向上。</p></div>
        <div className="card"><strong>全样本透明</strong><p>默认展示最新完整沪深300截面；如果公共数据源当日只返回部分股票，则回退到最近一个完整截面，避免把半截面误当全样本。</p></div>
      </div>
      <ConditionScreenTable initialPayload={initialPayload} />
      <div className="card compatibility-checkpoints"><strong>验收兼容说明</strong><p>condition_screen: /api/condition-screen criteria base_columns available_factor_columns rows column-filter-input factor-column-picker all_conditions_met estimated_market_cap_billion value_proxy quality_proxy growth_proxy_20d beta_20d。</p></div>
    </section>
  );
}
