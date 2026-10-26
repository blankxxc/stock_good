import { loadInitialApiPayload } from '../../../lib/serverApi';
import { StockDetailPanel, type StockDetailPayload } from '../../../components/StockDetailPanel';

export const dynamic = 'force-dynamic';


async function loadInitialStockDetail(symbol: string): Promise<StockDetailPayload | null> {
  return loadInitialApiPayload<StockDetailPayload>(`/api/stocks/${encodeURIComponent(symbol)}`);
}

const returnDestinations: Record<string, { href: string; label: string }> = {
  market: { href: '/', label: '返回股票全景' },
  scores: { href: '/scores', label: '返回预测选股' },
  'condition-screen': { href: '/condition-screen', label: '返回条件选股' },
  watchlist: { href: '/watchlist', label: '返回我的自选' },
  graph: { href: '/graph', label: '返回关系图谱' },
};

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ symbol: string }>;
  searchParams: Promise<{ from?: string }>;
}) {
  const { symbol: rawSymbol } = await params;
  const { from = 'market' } = await searchParams;
  const symbol = decodeURIComponent(rawSymbol);
  const initialPayload = await loadInitialStockDetail(symbol);
  const returnDestination = returnDestinations[from] ?? returnDestinations.market;
  return <StockDetailPanel symbol={symbol} initialPayload={initialPayload} returnTo={returnDestination.href} returnLabel={returnDestination.label} />;
}
