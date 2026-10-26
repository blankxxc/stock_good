export type PredictionInput = { symbol: string; horizon_days: number; neutral_band_pct: number; factors: string[] };
export type FactorEvidence = { id: string; label: string; formula: string; value: number | null; value_date: string | null; recent: { date: string; value: number | null }[] };
export type AIPrediction = {
  status: 'estimated' | 'insufficient_data'; probability_up: number | null; probability_flat: number | null; probability_down: number | null;
  rationale: string; evidence: { factor: string; impact: 'supports_up' | 'supports_down' | 'mixed'; explanation: string }[]; risks: string[];
  provider: string; model: string; generated_at: string; calibration_status: 'uncalibrated'; notice: string;
  input: Omit<PredictionInput, 'factors'> & { stock_name: string; as_of: string; event_definition: string; price_basis: string; data_version: string; snapshot_id: string;
    factors: FactorEvidence[]; prices: { date: string; close: number | null; volume: number | null }[];
    history_reference: { sample_count: number; probability_up: number | null; probability_flat: number | null; probability_down: number | null; note: string } };
};

export const DEFAULT_PREDICTION_FACTORS = ['return_5d', 'return_20d', 'momentum_20d', 'volatility_20d', 'vwap_deviation', 'volume_shock_20d', 'amihud_20d', 'abnormal_move_4_times_10d'];
const finite = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);
const nullableNumber = (v: unknown) => v === null || finite(v);
const record = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const strings = (v: Record<string, any>, keys: string[]) => keys.every(k => typeof v[k] === 'string');

/** Validate the response before rendering; never normalize malformed probabilities. */
export function readPrediction(value: unknown, query: PredictionInput): AIPrediction {
  const fail = () => { throw new Error('预测结果格式或概率无效，请重新生成。'); };
  if (!record(value) || !record(value.input)) return fail();
  const v = value;
  const input: Record<string, any> = v.input;
  if (v.calibration_status !== 'uncalibrated' || !['estimated', 'insufficient_data'].includes(v.status) ||
      !strings(v, ['rationale', 'provider', 'model', 'generated_at', 'notice']) ||
      !strings(input, ['symbol', 'stock_name', 'as_of', 'event_definition', 'price_basis', 'data_version', 'snapshot_id']) ||
      input.symbol !== query.symbol || input.horizon_days !== query.horizon_days || input.neutral_band_pct !== query.neutral_band_pct) return fail();
  const probabilities = [v.probability_up, v.probability_flat, v.probability_down];
  if (v.status === 'estimated' ? probabilities.some(p => !finite(p) || p < 0 || p > 1) || Math.abs(probabilities.reduce((a, b) => a + b, 0) - 1) > 1e-6 : probabilities.some(p => p !== null)) return fail();
  if (!Array.isArray(input.factors) || input.factors.length !== query.factors.length ||
      input.factors.some(f => !record(f) || !strings(f, ['id', 'label', 'formula']) || !query.factors.includes(f.id) || !nullableNumber(f.value) ||
        (f.value_date !== null && typeof f.value_date !== 'string') || !Array.isArray(f.recent) || f.recent.some((r: unknown) => !record(r) || typeof r.date !== 'string' || !nullableNumber(r.value))) ||
      new Set(input.factors.map(f => f.id)).size !== query.factors.length) return fail();
  const observed = new Set(input.factors.filter(f => f.value !== null).map(f => f.id));
  if (!Array.isArray(v.evidence) || (v.status === 'estimated' && !v.evidence.length) || v.evidence.some(e => !record(e) || !observed.has(e.factor) ||
      !['supports_up', 'supports_down', 'mixed'].includes(e.impact) || typeof e.explanation !== 'string') ||
      new Set(v.evidence.map(e => e.factor)).size !== v.evidence.length ||
      !Array.isArray(v.risks) || !v.risks.length || v.risks.some(r => typeof r !== 'string')) return fail();
  const history = input.history_reference;
  if (!record(history) || !Number.isInteger(history.sample_count) || history.sample_count < 0 || typeof history.note !== 'string' ||
      ['probability_up', 'probability_flat', 'probability_down'].some(k => !nullableNumber(history[k])) ||
      !Array.isArray(input.prices) || input.prices.some(p => !record(p) || typeof p.date !== 'string' || !nullableNumber(p.close) || !nullableNumber(p.volume))) return fail();
  return v as AIPrediction;
}

export function probabilityText(value: number | null) { return value === null ? '—' : `${(value * 100).toFixed(1)}%`; }
