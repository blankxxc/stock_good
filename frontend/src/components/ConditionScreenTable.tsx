'use client';

import { useEffect, useMemo, useState } from 'react';
import { formatPercent } from '../lib/formatters';
import { useApiPayload } from '../lib/useApiPayload';

type ConditionRow = Record<string, string | number | boolean | null | undefined>;

type Criterion = { label: string; description: string };
type ColumnSchema = {
  type?: 'number' | 'boolean' | 'category' | 'text';
  operators?: string[];
  options?: Array<string | number | boolean | { label: string; value: string | number | boolean }>;
  min?: number | null;
  max?: number | null;
};
type FilterState = { operator?: string; value?: string; value2?: string };

export type ConditionScreenPayload = {
  status?: string;
  latest_trade_date?: string;
  research_boundary?: string;
  criteria?: Record<string, Criterion>;
  base_columns?: string[];
  available_factor_columns?: string[];
  factor_column_catalog?: Record<string, string>;
  column_schema?: Record<string, ColumnSchema>;
  st_star_rules?: string[];
  rows?: ConditionRow[];
  row_count?: number;
  summary?: Record<string, number | string | string[] | null | undefined>;
  api_note?: string;
};

const COLUMN_LABELS: Record<string, string> = {
  stock_name: '股票名称',
  symbol: '代码',
  trade_date: '信号日期',
  industry_name: '行业',
  non_st: '非ST',
  ma_bullish: '均线多头排列',
  return_10d_gt_15: '10个交易日内涨幅大于15%',
  close_above_ma10: '股价在10日均线上',
  market_cap_gt_100b: '市值大于100亿',
  all_conditions_met: '综合条件通过',
  close: '收盘价',
  pct_change: '当日涨跌幅',
  return_10d: '近10日涨跌幅',
  estimated_market_cap_billion: '估算市值/亿元',
  ma5: 'MA5',
  ma10: 'MA10',
  ma20: 'MA20',
  ma30: 'MA30',
  ma60: 'MA60',
  ma250: 'MA250',
  ma_bullish_order: '均线顺序成立',
  ma_all_up: '均线全部向上',
  turnover_rate: '换手率',
  amount_billion: '成交额/亿元',
  volume: '成交量',
  momentum_20d: '20日动量',
  volatility_20d: '20日波动率',
  reversal_5d: '5日反转',
  amount_percentile_20d: '成交额分位',
  amihud_20d: 'Amihud非流动性',
  volume_shock_20d: '量能冲击',
  price_volume_corr_20d: '价量相关',
  vwap_deviation: 'VWAP偏离',
  ma20_gap: 'MA20偏离',
  ma60_gap: 'MA60偏离',
  market_cap_proxy: '规模代理',
  float_market_cap_proxy: '流通市值代理',
  beta_20d: 'Beta20',
  beta_60d: 'Beta60',
  value_proxy: '价值代理',
  quality_proxy: '质量代理',
  growth_proxy_20d: '成长代理',
  low_volatility_proxy: '低波动代理',
  liquidity_proxy: '流动性代理',
  industry_neutral_return_20d: '行业中性收益',
  cs_rank_return_20d: '截面收益排名',
};

const DEFAULT_FACTOR_COLUMNS = ['return_10d', 'momentum_20d', 'volatility_20d', 'value_proxy', 'quality_proxy', 'growth_proxy_20d', 'beta_20d', 'low_volatility_proxy'];

function formatCell(column: string, value: unknown) {
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (value === null || typeof value === 'undefined') return '—';
  if (typeof value === 'number') {
    if (column.includes('return') || column === 'pct_change') return formatPercent(value);
    if (column === 'estimated_market_cap_billion' || column === 'amount_billion') return value.toFixed(2);
    if (column === 'volume') return value.toFixed(0);
    return value.toFixed(3);
  }
  return String(value);
}

function filterValue(row: ConditionRow, column: string) {
  return formatCell(column, row[column]).toLowerCase();
}

const OPERATOR_LABELS: Record<string, string> = {
  gt: '大于',
  gte: '大于等于',
  lt: '小于',
  lte: '小于等于',
  eq: '等于',
  between: '区间',
  contains: '包含',
};

function normalizedDiscreteValue(value: unknown) {
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (value === null || typeof value === 'undefined') return '';
  return String(value);
}

function optionParts(option: NonNullable<ColumnSchema['options']>[number]) {
  if (typeof option === 'object' && option !== null && 'value' in option) {
    return { label: option.label, value: normalizedDiscreteValue(option.value) };
  }
  return { label: String(option), value: normalizedDiscreteValue(option) };
}

function rowMatchesFilter(row: ConditionRow, column: string, schema: ColumnSchema | undefined, filter: FilterState | undefined) {
  const value = (filter?.value ?? '').trim();
  const value2 = (filter?.value2 ?? '').trim();
  if (!value && !value2) return true;
  const type = schema?.type ?? 'text';
  const operator = filter?.operator ?? (type === 'number' ? 'gte' : type === 'text' ? 'contains' : 'eq');

  if (type === 'number') {
    const actual = Number(row[column]);
    const target = Number(value);
    const target2 = Number(value2);
    if (!Number.isFinite(actual) || !Number.isFinite(target)) return false;
    if (operator === 'gt') return actual > target;
    if (operator === 'gte') return actual >= target;
    if (operator === 'lt') return actual < target;
    if (operator === 'lte') return actual <= target;
    if (operator === 'between') return Number.isFinite(target2) && actual >= Math.min(target, target2) && actual <= Math.max(target, target2);
    return actual === target;
  }

  if (type === 'boolean' || type === 'category') {
    return normalizedDiscreteValue(row[column]) === value;
  }

  return filterValue(row, column).includes(value.toLowerCase());
}

function defaultSignalDateFilters(latestTradeDate?: string): Record<string, FilterState> {
  const value = latestTradeDate?.trim();
  return value ? { trade_date: { operator: 'eq', value } } : {};
}

export function ConditionScreenTable({ initialPayload = null }: { initialPayload?: ConditionScreenPayload | null }) {
  const { payload, error, loading, reload } = useApiPayload<ConditionScreenPayload>('/api/condition-screen', initialPayload);
  const [filters, setFilters] = useState<Record<string, FilterState>>(() => defaultSignalDateFilters(initialPayload?.latest_trade_date));
  const [selectedFactors, setSelectedFactors] = useState<string[]>(DEFAULT_FACTOR_COLUMNS);
  const [signalDateFilterTouched, setSignalDateFilterTouched] = useState(false);
  const [factorQuery, setFactorQuery] = useState('');
  const [onlyMatched, setOnlyMatched] = useState(false);

  const baseColumns = payload?.base_columns ?? [];
  const availableFactors = payload?.available_factor_columns ?? [];
  const visibleColumns = useMemo(() => Array.from(new Set([...baseColumns, ...selectedFactors])), [baseColumns, selectedFactors]);
  const columnSchema = payload?.column_schema ?? {};

  const rows = payload?.rows ?? [];
  const filteredRows = useMemo(() => rows.filter((row) => visibleColumns.every((column) => {
    return rowMatchesFilter(row, column, columnSchema[column], filters[column]);
  })), [rows, filters, visibleColumns, columnSchema]);
  const displayedRows = useMemo(
    () => onlyMatched ? filteredRows.filter((row) => row.all_conditions_met === true) : filteredRows,
    [filteredRows, onlyMatched],
  );
  const filteredFactorOptions = useMemo(() => {
    const keyword = factorQuery.trim().toLowerCase();
    if (!keyword) return availableFactors;
    return availableFactors.filter((factor) => `${COLUMN_LABELS[factor] ?? factor} ${factor} ${payload?.factor_column_catalog?.[factor] ?? ''}`.toLowerCase().includes(keyword));
  }, [availableFactors, factorQuery, payload?.factor_column_catalog]);
  const activeFilterCount = Object.values(filters).filter((filter) => Boolean(filter.value?.trim() || filter.value2?.trim())).length;

  const summary = payload?.summary ?? {};

  useEffect(() => {
    const latestTradeDate = payload?.latest_trade_date?.trim();
    if (!latestTradeDate || signalDateFilterTouched) return;
    setFilters((state) => {
      const current = state.trade_date;
      if (current?.operator === 'eq' && current.value === latestTradeDate) return state;
      return { ...state, trade_date: { ...current, operator: 'eq', value: latestTradeDate } };
    });
  }, [payload?.latest_trade_date, signalDateFilterTouched]);

  const updateColumnFilter = (column: string, updater: (current: FilterState) => FilterState) => {
    if (column === 'trade_date') setSignalDateFilterTouched(true);
    setFilters((state) => ({ ...state, [column]: updater(state[column] ?? {}) }));
  };

  const resetScreen = () => {
    setFilters(defaultSignalDateFilters(payload?.latest_trade_date));
    setSelectedFactors(DEFAULT_FACTOR_COLUMNS);
    setSignalDateFilterTouched(false);
    setFactorQuery('');
    setOnlyMatched(false);
  };

  return (
    <section className="condition-screen" aria-busy={loading && !payload}>
      <div className="workflow-page-header">
        <div className="workflow-page-heading workflow-page-heading--compact">
          <span className="workflow-page-heading__eyebrow">条件筛选</span>
          <h1>构建你的股票筛选条件</h1>
          <p>从核心条件开始，再按需添加因子列；结果数量会随每一项筛选即时更新。</p>
        </div>
        <div className="workflow-page-actions">
          <button className={`button${onlyMatched ? ' primary' : ''}`} type="button" onClick={() => setOnlyMatched((current) => !current)} aria-pressed={onlyMatched}>只看综合通过</button>
          <button className="button button--secondary" type="button" onClick={resetScreen}>恢复默认</button>
        </div>
      </div>
      {error ? (
        <div className="data-state data-state--error" role="alert">
          <span>暂时无法读取条件选股数据：{error}</span>
          <button className="button table-button" type="button" onClick={reload} disabled={loading}>重新加载</button>
        </div>
      ) : null}
      {loading && !payload ? <p className="data-state" role="status" aria-live="polite">正在加载条件选股数据…</p> : null}
      <div className="market-ticker-row">
        <div><strong>{payload?.row_count ?? rows.length}</strong><span>最新完整沪深300截面</span></div>
        <div><strong>{String(summary.matched_count ?? 0)}</strong><span>预设综合条件通过</span></div>
        <div><strong>{displayedRows.length}</strong><span>当前显示结果</span></div>
        <div><strong>{payload?.latest_trade_date ?? '加载中'}</strong><span>最新行情日期</span></div>
      </div>

      <div className="card factor-column-picker">
        <div className="artifact-card__topline">
          <div>
            <strong>选择要分析的因子列</strong>
            <p className="muted">已选 {selectedFactors.length} 项 · 当前表格共 {visibleColumns.length} 列</p>
          </div>
          <span className="muted">搜索或使用快捷操作，避免在 70+ 因子中逐项查找。</span>
        </div>
        <div className="factor-picker-toolbar">
          <label className="factor-picker-search">
            <span>搜索因子</span>
            <input type="search" value={factorQuery} onChange={(event) => setFactorQuery(event.target.value)} placeholder="名称、代码或分类" />
          </label>
          <div className="factor-picker-actions" aria-label="因子列快捷选择">
            <button type="button" onClick={() => setSelectedFactors(DEFAULT_FACTOR_COLUMNS)}>核心因子</button>
            <button type="button" onClick={() => setSelectedFactors(availableFactors)}>选择全部</button>
            <button type="button" onClick={() => setSelectedFactors([])}>清空选择</button>
          </div>
        </div>
        <div className="factor-checkbox-grid">
          {filteredFactorOptions.map((factor) => (
            <label key={factor}>
              <input
                type="checkbox"
                checked={selectedFactors.includes(factor)}
                onChange={(event) => {
                  setSelectedFactors((current) => event.target.checked
                    ? Array.from(new Set([...current, factor]))
                    : current.filter((item) => item !== factor));
                }}
              />
              <span>{COLUMN_LABELS[factor] ?? factor}</span>
              <small>{payload?.factor_column_catalog?.[factor] ?? factor}</small>
            </label>
          ))}
          {!filteredFactorOptions.length ? <p className="factor-picker-empty">没有找到匹配的因子，请换一个关键词。</p> : null}
        </div>
      </div>

      <div className="condition-result-bar" role="status" aria-live="polite">
        <span>当前显示 <strong>{displayedRows.length}</strong> / {rows.length} 只股票</span>
        <span>{activeFilterCount} 个列筛选{onlyMatched ? ' · 仅综合通过' : ''}</span>
        {activeFilterCount || onlyMatched ? <button type="button" onClick={resetScreen}>清除全部筛选</button> : null}
      </div>

      <div className="stock-table-shell condition-table-shell" role="region" aria-label="条件选股结果表格，可横向滚动" tabIndex={0}>
        <table className="stock-table condition-table">
          <caption className="sr-only">条件选股结果及每列筛选控件</caption>
          <thead>
            <tr>
              {visibleColumns.map((column) => <th id={`condition-column-${column}`} scope="col" key={column}>{COLUMN_LABELS[column] ?? column}</th>)}
            </tr>
            <tr>
              {visibleColumns.map((column) => {
                const columnLabel = COLUMN_LABELS[column] ?? column;
                return (
                <th aria-label={`${columnLabel}筛选`} key={`${column}-filter`}>
                  {(() => {
                    const schema = columnSchema[column] ?? { type: 'text', operators: ['contains'] };
                    const current = filters[column] ?? {};
                    if (schema.type === 'number') {
                      const operator = current.operator ?? 'gte';
                      return (
                        <div className="column-filter-control numeric-filter-control">
                          <select
                            className="numeric-filter-operator"
                            aria-label={`${columnLabel}筛选条件`}
                            value={operator}
                            onChange={(event) => updateColumnFilter(column, (current) => ({ ...current, operator: event.target.value }))}
                          >
                            {(schema.operators ?? ['gt', 'gte', 'lt', 'lte', 'eq', 'between']).map((op) => <option key={op} value={op}>{OPERATOR_LABELS[op] ?? op}</option>)}
                          </select>
                          <input
                            className="column-filter-input numeric-filter-value"
                            aria-label={operator === 'between' ? `${columnLabel}下限` : `${columnLabel}筛选数值`}
                            type="number"
                            value={current.value ?? ''}
                            onChange={(event) => updateColumnFilter(column, (current) => ({ ...current, value: event.target.value }))}
                            placeholder={operator === 'between' ? '下限' : `数值筛选${COLUMN_LABELS[column] ?? column}`}
                          />
                          {operator === 'between' ? (
                            <input
                              className="column-filter-input numeric-filter-value"
                              aria-label={`${columnLabel}上限`}
                              type="number"
                              value={current.value2 ?? ''}
                              onChange={(event) => updateColumnFilter(column, (current) => ({ ...current, value2: event.target.value }))}
                              placeholder="上限"
                            />
                          ) : null}
                        </div>
                      );
                    }
                    if (schema.type === 'boolean' || schema.type === 'category') {
                      return (
                        <select
                          className="discrete-filter-select column-filter-input"
                          aria-label={`${columnLabel}筛选值`}
                          value={current.value ?? ''}
                          onChange={(event) => updateColumnFilter(column, () => ({ operator: 'eq', value: event.target.value }))}
                        >
                          <option value="">全部</option>
                          {(schema.options ?? []).map((option) => {
                            const item = optionParts(option);
                            return <option key={item.value} value={item.value}>{item.label}</option>;
                          })}
                        </select>
                      );
                    }
                    return (
                      <input
                        className="column-filter-input text-filter-input"
                        aria-label={`${columnLabel}包含文本`}
                        value={current.value ?? ''}
                        onChange={(event) => updateColumnFilter(column, () => ({ operator: 'contains', value: event.target.value }))}
                        placeholder={`包含${COLUMN_LABELS[column] ?? column}`}
                      />
                    );
                  })()}
                </th>
              );})}
            </tr>
          </thead>
          <tbody>
            {displayedRows.map((row, index) => (
              <tr key={`${row.symbol}-${row.trade_date}-${index}`}>
                {visibleColumns.map((column) => (
                  <td key={column} className={typeof row[column] === 'number' && String(column).includes('return') ? ((row[column] as number) >= 0 ? 'positive' : 'negative') : ''}>
                    {column === 'symbol' && row.symbol ? <a className="code-link" href={`/stocks/${row.symbol}?from=condition-screen`}>{formatCell(column, row[column])}</a> : formatCell(column, row[column])}
                  </td>
                ))}
              </tr>
            ))}
            {!displayedRows.length ? <tr><td className="table-empty-cell" colSpan={visibleColumns.length || 1}>暂无匹配记录，请调整筛选条件或恢复默认设置。</td></tr> : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
