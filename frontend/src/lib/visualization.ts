export type Metric = { id: string; label: string; unit: string; group: string; description: string };
export type VisualMetadata = {
  stocks: { symbol: string; stock_name: string }[]; metrics: Metric[];
  market_start: string; market_end: string; default_start: string; factor_end: string | null;
  price_basis: string; data_version: string; notes: string[];
};
export type ChartKind = 'line' | 'bar' | 'area' | 'scatter';
export type ChartConfig = { id: string; title: string; type: ChartKind; metric: string; xMetric: string; wide: boolean; normalize: boolean; columns?: number; height?: number };
export function chartSize(card: ChartConfig) { return { columns: card.columns ?? (card.wide ? 12 : 6), height: card.height ?? 600 }; }
export type Board = { version: 1; title: string; symbols: string[]; start_date: string; end_date: string; cards: ChartConfig[] };
export type VisualSeries = { symbol: string; stock_name: string; metric: string; values: (number | null)[]; observations: number };
export type VisualData = {
  dates: string[]; series: VisualSeries[]; metrics: Metric[]; start_date: string; end_date: string;
  market_end: string; factor_end: string | null; data_version: string; price_basis: string; notes: string[];
};
export const BOARD_KEY = 'stock-good.visual-board.v1';
export const CHART_TYPES: Record<ChartKind, string> = { line: '折线图', bar: '柱状图', area: '面积图', scatter: '散点图' };

export function defaultBoard(meta: VisualMetadata): Board {
  const has = (id: string) => meta.metrics.some(m => m.id === id);
  const first = has('close') ? 'close' : meta.metrics[0]?.id || '';
  return { version: 1, title: '我的研究看板', symbols: [meta.stocks[0]?.symbol].filter(Boolean),
    start_date: meta.default_start, end_date: meta.market_end,
    cards: [
      { id: 'price', title: '价格趋势', type: 'line', metric: first, xMetric: first, wide: true, normalize: false },
      { id: 'volume', title: '成交量观察', type: 'bar', metric: has('volume') ? 'volume' : first, xMetric: first, wide: false, normalize: false },
      { id: 'factor', title: '因子走势', type: 'area', metric: has('return_20d') ? 'return_20d' : first, xMetric: first, wide: false, normalize: false },
    ] };
}

export function boardRequest(board: Board) {
  return { symbols: [...board.symbols].sort(), metrics: [...new Set(board.cards.flatMap(c => c.type === 'scatter' ? [c.metric, c.xMetric] : [c.metric]))].sort(),
    start_date: board.start_date, end_date: board.end_date };
}
export function requestKey(board: Board) { return JSON.stringify(boardRequest(board)); }

export function validateBoard(board: Board, meta: VisualMetadata): string | null {
  if (!board.symbols.length || board.symbols.length > 4) return '请选择 1–4 只股票。';
  if (board.symbols.some(s => !meta.stocks.some(item => item.symbol === s))) return '部分股票已不在本地股票池，请重新选择。';
  if (!board.cards.length || board.cards.length > 8) return '看板需要 1–8 张图表。';
  if (board.cards.some(c => (c.columns !== undefined && (!Number.isInteger(c.columns) || c.columns < 4 || c.columns > 12))
      || (c.height !== undefined && (!Number.isInteger(c.height) || c.height < 400 || c.height > 1200)))) return '图表尺寸无效，宽度应为 4–12 列，高度应为 400–1200 像素。';
  const validDate = (value: string) => /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value;
  if (!validDate(board.start_date) || !validDate(board.end_date) || board.start_date > board.end_date) return '请选择有效的起止日期。';
  if ((Date.parse(board.end_date) - Date.parse(board.start_date)) / 86400000 > 1830) return '一次最多查看五年数据。';
  if (board.start_date < meta.market_start || board.end_date > meta.market_end) return `可选行情范围为 ${meta.market_start} 至 ${meta.market_end}。`;
  const metrics = boardRequest(board).metrics;
  if (metrics.length > 12) return '一个看板最多选择 12 个不同指标。';
  if (metrics.some(id => !meta.metrics.some(m => m.id === id))) return '部分指标暂无历史数据，请重新选择。';
  return null;
}

/** Parse only the bounded public layout fields, never arbitrary saved state. */
export function restoreBoard(raw: string, meta: VisualMetadata): Board {
  if (raw.length > 16000) throw new Error('看板配置过大。');
  const obj = JSON.parse(raw);
  if (!obj || obj.version !== 1 || typeof obj.title !== 'string' || obj.title.length > 60 ||
      !Array.isArray(obj.symbols) || obj.symbols.some((s: unknown) => typeof s !== 'string') ||
      !Array.isArray(obj.cards) || typeof obj.start_date !== 'string' || typeof obj.end_date !== 'string') throw new Error('看板配置格式无效。');
  const cards: ChartConfig[] = obj.cards.map((c: ChartConfig) => {
    if (!c || typeof c.id !== 'string' || c.id.length > 80 || typeof c.title !== 'string' || c.title.length > 60 ||
        !Object.hasOwn(CHART_TYPES, c.type) || typeof c.metric !== 'string' || typeof c.xMetric !== 'string' ||
        typeof c.wide !== 'boolean' || typeof c.normalize !== 'boolean') throw new Error('图表配置格式无效。');
    return { id: c.id, title: c.title, type: c.type, metric: c.metric, xMetric: c.xMetric, wide: c.wide, normalize: c.normalize,
      ...(c.columns !== undefined ? { columns: c.columns } : {}), ...(c.height !== undefined ? { height: c.height } : {}) };
  });
  if (new Set(cards.map(c => c.id)).size !== cards.length || new Set(obj.symbols).size !== obj.symbols.length) throw new Error('看板包含重复项目。');
  const board: Board = { version: 1, title: obj.title, symbols: obj.symbols, start_date: obj.start_date, end_date: obj.end_date, cards };
  const error = validateBoard(board, meta);
  if (error) throw new Error(error);
  return board;
}

export function normalized(values: (number | null)[]): (number | null)[] {
  const valid = values.filter((v): v is number => v !== null && Number.isFinite(v));
  if (!valid.length) return values.map(() => null);
  const mean = valid.reduce((a, b) => a + b, 0) / valid.length;
  const deviation = Math.sqrt(valid.reduce((sum, n) => sum + (n - mean) ** 2, 0) / valid.length);
  return values.map(n => n === null || !Number.isFinite(n) ? null : deviation > 0 ? (n - mean) / deviation : 0);
}

export function segments(values: (number | null)[]): { index: number; value: number }[][] {
  const result: { index: number; value: number }[][] = [];
  let active: { index: number; value: number }[] = [];
  values.forEach((value, index) => {
    if (value === null || !Number.isFinite(value)) { if (active.length) result.push(active); active = []; }
    else active.push({ index, value });
  });
  if (active.length) result.push(active);
  return result;
}

export function displayValue(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  if (value !== 0 && Math.abs(value) < .0001) return value.toExponential(2);
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 4, notation: Math.abs(value) >= 100000 ? 'compact' : 'standard' }).format(value);
}

export function dataCsv(data: VisualData): string {
  const cell = (value: unknown) => {
    const text = String(value ?? '');
    const safe = /^[\s]*[=+@-]|^[\t\r\n]/.test(text) ? "'" + text : text;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const rows: unknown[][] = [['日期', '股票代码', '股票名称', '指标', '单位', '原始值', '数据版本']];
  const units = new Map(data.metrics.map(m => [m.id, m.unit]));
  for (const s of data.series) data.dates.forEach((day, i) => rows.push([day, s.symbol, s.stock_name, s.metric, units.get(s.metric), s.values[i], data.data_version]));
  // Numeric cells remain numeric; formula protection applies only to text fields.
  return '\uFEFF' + rows.map(row => row.map(v => typeof v === 'number' ? String(v) : cell(v)).join(',')).join('\r\n');
}

export function downloadFile(content: string, filename: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
