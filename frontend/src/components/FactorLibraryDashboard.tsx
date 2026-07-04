'use client';

import { useMemo, useState } from 'react';

type FactorRow = {
  factor_name: string;
  category: string;
  formula?: string;
  economic_hypothesis?: string;
  expected_decay?: string;
  coverage?: number | null;
  missing_rate?: number | null;
  ic_mean?: number | null;
  rank_ic_mean?: number | null;
  icir?: number | null;
  turnover?: number | null;
  capacity_estimate?: number | null;
  cost_adjusted_spread?: number | null;
  admission_status: string;
  risk_notes?: string[];
  detail_anchor: string;
};

type CategorySummary = {
  category: string;
  factor_count: number;
  avg_coverage?: number | null;
  avg_icir?: number | null;
  avg_abs_rank_ic?: number | null;
  avg_turnover?: number | null;
};

type FactorPayload = {
  status?: string;
  factor_count?: number;
  factor_rows?: number;
  feature_matrix_rows?: number;
  data_version?: string;
  factor_version?: string;
  engine?: string;
  factor_catalog_summary?: Record<string, number | string | null | undefined>;
  factor_catalog?: FactorRow[];
  category_summary?: CategorySummary[];
  top_factors_by_icir?: FactorRow[];
  factor_ui_hints?: { status_labels?: Record<string, string> };
  point_in_time_join?: { point_in_time_violations?: number | null; status?: string };
  event_regime?: { status?: string; latest_available_time?: string };
  relation_graph?: { status?: string; relation_factor_rows?: number };
};

function pct(value: unknown, digits = 1) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

function num(value: unknown, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return value.toFixed(digits);
}

function compact(value: unknown) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  if (Math.abs(value) >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}亿`;
  if (Math.abs(value) >= 10_000) return `${(value / 10_000).toFixed(1)}万`;
  return value.toLocaleString('zh-CN');
}

function statusClass(status: string) {
  return `factor-status factor-status--${status.replace(/_/g, '-')}`;
}

function signedClass(value?: number | null) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '';
  return value >= 0 ? 'positive' : 'negative';
}

export function FactorLibraryDashboard({ payload }: { payload: FactorPayload }) {
  const factors = payload.factor_catalog ?? [];
  const categories = payload.category_summary ?? [];
  const statusLabels = payload.factor_ui_hints?.status_labels ?? {};
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [status, setStatus] = useState('all');
  const [sort, setSort] = useState('ICIR_desc');
  const [selectedName, setSelectedName] = useState(factors[0]?.factor_name ?? '');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const rows = factors.filter((factor) => {
      const text = [factor.factor_name, factor.category, factor.formula, factor.economic_hypothesis].join(' ').toLowerCase();
      return (!q || text.includes(q)) && (category === 'all' || factor.category === category) && (status === 'all' || factor.admission_status === status);
    });
    const sorted = [...rows].sort((a, b) => {
      if (sort === 'coverage_desc') return (b.coverage ?? -Infinity) - (a.coverage ?? -Infinity);
      if (sort === 'rank_ic_abs_desc') return Math.abs(b.rank_ic_mean ?? 0) - Math.abs(a.rank_ic_mean ?? 0);
      if (sort === 'turnover_asc') return (a.turnover ?? Infinity) - (b.turnover ?? Infinity);
      return Math.abs(b.icir ?? 0) - Math.abs(a.icir ?? 0);
    });
    return sorted;
  }, [category, factors, query, sort, status]);

  const selected = factors.find((factor) => factor.factor_name === selectedName) ?? filtered[0] ?? factors[0];
  const statusOptions = Array.from(new Set(factors.map((factor) => factor.admission_status))).sort();

  return (
    <div className="factor-library-dashboard">
      <section className="card factor-command-center">
        <div className="artifact-card__topline">
          <span className="badge">因子库</span>
        </div>
        <div className="factor-hero-grid factor-hero-grid--simple">
          <div>
            <h2>因子库</h2>
            <p className="lead">搜索、筛选并查看 74 个因子的质量、分类和用途。</p>
          </div>
        </div>
      </section>

      <section className="factor-kpi-grid factor-kpi-grid--compact">
        <div><span>因子总数</span><strong>{payload.factor_count ?? factors.length}</strong><small>可筛选查看</small></div>
        <div><span>历史因子记录</span><strong>{compact(payload.factor_rows)}</strong><small>用于计算质量指标</small></div>
        <div><span>可建模样本</span><strong>{compact(payload.feature_matrix_rows)}</strong><small>横截面样本</small></div>
        <div><span>可复核因子</span><strong>{payload.factor_catalog_summary?.admission_ready_count ?? '—'}</strong><small>当前可用</small></div>
      </section>

      <section className="card factor-controls">
        <label><span>因子搜索</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索因子名称 / 公式 / 含义" /></label>
        <label><span>分类筛选</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">全部分类</option>{categories.map((item) => <option value={item.category} key={item.category}>{item.category} ({item.factor_count})</option>)}</select></label>
        <label><span>准入状态</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">全部状态</option>{statusOptions.map((item) => <option value={item} key={item}>{statusLabels[item] ?? item}</option>)}</select></label>
        <label><span>排序</span><select value={sort} onChange={(event) => setSort(event.target.value)}><option value="ICIR_desc">ICIR 排序</option><option value="coverage_desc">覆盖率</option><option value="rank_ic_abs_desc">|RankIC|</option><option value="turnover_asc">低换手优先</option></select></label>
      </section>

      <section className="grid factor-category-grid">
        {categories.map((item) => (
          <div className="card factor-category-card" key={item.category}>
            <div className="panel-title-row"><strong>{item.category}</strong><span>{item.factor_count} 个因子</span></div>
            <dl className="meta-grid compact-meta-grid">
              <div><dt>覆盖率</dt><dd>{pct(item.avg_coverage)}</dd></div>
              <div><dt>平均 ICIR</dt><dd>{num(item.avg_icir, 2)}</dd></div>
              <div><dt>|RankIC|</dt><dd>{num(item.avg_abs_rank_ic, 3)}</dd></div>
              <div><dt>换手</dt><dd>{pct(item.avg_turnover, 2)}</dd></div>
            </dl>
          </div>
        ))}
      </section>

      <section className="factor-main-grid">
        <div className="card">
          <div className="panel-title-row"><strong>因子目录</strong><span>{filtered.length}/{factors.length}</span></div>
          <div className="factor-table-shell">
            <table className="mini-score-table factor-table">
              <thead><tr><th>因子</th><th>分类</th><th>准入状态</th><th>覆盖率</th><th>ICIR</th><th>RankIC</th><th>换手</th><th>容量</th></tr></thead>
              <tbody>
                {filtered.map((factor) => (
                  <tr className={selected?.factor_name === factor.factor_name ? 'selected-row' : ''} key={factor.factor_name} onClick={() => setSelectedName(factor.factor_name)}>
                    <td><button className="factor-name-button" type="button">{factor.factor_name}</button></td>
                    <td>{factor.category}</td>
                    <td><span className={statusClass(factor.admission_status)}>{statusLabels[factor.admission_status] ?? factor.admission_status}</span></td>
                    <td>{pct(factor.coverage)}</td>
                    <td className={signedClass(factor.icir)}>{num(factor.icir, 2)}</td>
                    <td className={signedClass(factor.rank_ic_mean)}>{num(factor.rank_ic_mean, 3)}</td>
                    <td>{pct(factor.turnover, 2)}</td>
                    <td>{compact(factor.capacity_estimate)}</td>
                  </tr>
                ))}
                {!filtered.length ? <tr><td colSpan={8}>暂无匹配因子，请调整搜索或筛选条件。</td></tr> : null}
              </tbody>
            </table>
          </div>
        </div>

        <aside className="card factor-detail-card" id={selected?.detail_anchor ?? 'factor-detail'}>
          <div className="panel-title-row"><strong>因子详情</strong><span>{selected?.category ?? '—'}</span></div>
          {selected ? (
            <>
              <h3>{selected.factor_name}</h3>
              <span className={statusClass(selected.admission_status)}>{statusLabels[selected.admission_status] ?? selected.admission_status}</span>
              <p>{selected.economic_hypothesis ?? '暂无假设说明'}</p>
              <p className="factor-formula-line"><b>计算口径：</b>{selected.formula ?? '—'}</p>
              <dl className="meta-grid compact-meta-grid">
                <div><dt>预期衰减</dt><dd>{selected.expected_decay ?? '—'}</dd></div>
                <div><dt>平均 IC</dt><dd className={signedClass(selected.ic_mean)}>{num(selected.ic_mean, 4)}</dd></div>
                <div><dt>成本后价差</dt><dd className={signedClass(selected.cost_adjusted_spread)}>{num(selected.cost_adjusted_spread, 4)}</dd></div>
                <div><dt>缺失率</dt><dd>{pct(selected.missing_rate)}</dd></div>
              </dl>
              <strong>主要风险</strong>
              <div className="factor-risk-list">{(selected.risk_notes ?? []).map((risk) => <span key={risk}>{risk}</span>)}</div>
            </>
          ) : <p>请选择一个因子查看详情。</p>}
        </aside>
      </section>

      <section className="grid factor-support-grid">
        <div className="card"><strong>Top ICIR 因子</strong><div className="factor-chip-list">{(payload.top_factors_by_icir ?? []).slice(0, 8).map((factor) => <button type="button" key={factor.factor_name} onClick={() => setSelectedName(factor.factor_name)}>{factor.factor_name}<small>{num(factor.icir, 2)}</small></button>)}</div></div>
        <div className="card"><strong>事件/市场环境因子</strong><p>最新可用时间：{payload.event_regime?.latest_available_time ?? '—'}</p></div>
        <div className="card"><strong>关系图谱因子</strong><p>已接入 {compact(payload.relation_graph?.relation_factor_rows)} 行关系因子。</p></div>
      </section>
    </div>
  );
}
