export type Strategy = 'momentum' | 'reversal' | 'low_volatility' | 'trend';
export type StrategyConfig = {
  start_date: string; end_date: string; strategies: Strategy[]; lookback: number; top_k: number;
  rebalance_days: number; initial_capital: number; fee_bps: number; slippage_bps: number;
  exclude_st: boolean; exclude_extreme: boolean; exclude_abnormal: boolean;
};
export const STRATEGY_NAMES: Record<Strategy, string> = {
  momentum: '动量策略', reversal: '反转策略', low_volatility: '低波动策略', trend: '均线趋势策略',
};

export function readStrategyConfig(value: unknown): StrategyConfig {
  if (!value || typeof value !== 'object') throw new Error('策略配置格式无效。');
  const c = value as StrategyConfig;
  const validDate = (s: unknown): s is string => typeof s === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(s)
    && Number.isFinite(Date.parse(s)) && new Date(s).toISOString().slice(0, 10) === s;
  if (!validDate(c.start_date) || !validDate(c.end_date) || c.start_date > c.end_date ||
      !Array.isArray(c.strategies) || c.strategies.length < 1 || c.strategies.length > 4 ||
      c.strategies.some(s => !Object.hasOwn(STRATEGY_NAMES, s)) || new Set(c.strategies).size !== c.strategies.length) throw new Error('策略或日期无效。');
  const numeric: [keyof StrategyConfig, number, number, boolean][] = [
    ['lookback', 2, 120, true], ['top_k', 1, 50, true], ['rebalance_days', 1, 60, true],
    ['initial_capital', 1000, 100000000, false], ['fee_bps', 0, 100, false], ['slippage_bps', 0, 100, false],
  ];
  for (const [key, min, max, integer] of numeric) {
    const n = c[key];
    if (typeof n !== 'number' || !Number.isFinite(n) || n < min || n > max || (integer && !Number.isInteger(n))) throw new Error('策略数值参数无效。');
  }
  if (['exclude_st', 'exclude_extreme', 'exclude_abnormal'].some(k => typeof c[k as keyof StrategyConfig] !== 'boolean')) throw new Error('过滤开关无效。');
  return { start_date: c.start_date, end_date: c.end_date, strategies: [...c.strategies], lookback: c.lookback,
    top_k: c.top_k, rebalance_days: c.rebalance_days, initial_capital: c.initial_capital, fee_bps: c.fee_bps,
    slippage_bps: c.slippage_bps, exclude_st: c.exclude_st, exclude_extreme: c.exclude_extreme, exclude_abnormal: c.exclude_abnormal };
}

export function strategyPreview(config: StrategyConfig): [string, string][] {
  return [
    ['比较策略', config.strategies.map(s => STRATEGY_NAMES[s]).join('、')],
    ['历史区间', `${config.start_date} — ${config.end_date}`],
    ['观察期 / 调仓', `${config.lookback} / ${config.rebalance_days} 个交易日`],
    ['持仓 / 资金', `${config.top_k} 只 / ${config.initial_capital.toLocaleString('zh-CN')} 元`],
    ['单边手续费 / 滑点', `${config.fee_bps} / ${config.slippage_bps} 基点`],
    ['排除条件', [config.exclude_st && 'ST 及状态未知', config.exclude_extreme && '十日涨幅 >100%', config.exclude_abnormal && '十日内至少四次异动'].filter(Boolean).join('、') || '未开启排除条件'],
  ];
}
