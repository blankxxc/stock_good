export function formatNumber(value: number | null | undefined, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return value.toFixed(digits);
}

export function formatPercent(value: number | null | undefined, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(digits)}%`;
}

export function formatAmount(value: number | null | undefined, digits = 2) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${value.toFixed(digits)}亿`;
}

export function compactDate(value?: string | null) {
  if (!value) return '—';
  const parts = value.split('-');
  return parts.length >= 3 ? `${parts[1]}-${parts[2]}` : value;
}
