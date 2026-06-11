import { StockDetailPanel, type StockDetailPayload } from '../../../components/StockDetailPanel';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialStockDetail(symbol: string): Promise<StockDetailPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/stocks/${encodeURIComponent(symbol)}`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as StockDetailPayload;
  } catch {
    return null;
  }
}

export default async function Page({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol: rawSymbol } = await params;
  const symbol = decodeURIComponent(rawSymbol);
  const initialPayload = await loadInitialStockDetail(symbol);
  return <StockDetailPanel symbol={symbol} initialPayload={initialPayload} />;
}
