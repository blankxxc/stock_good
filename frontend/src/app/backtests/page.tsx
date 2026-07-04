import { BacktestRiskDashboard, type BacktestPayload } from '../../components/BacktestRiskDashboard';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialBacktestPayload(): Promise<BacktestPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/backtests`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as BacktestPayload;
  } catch {
    return null;
  }
}

export default async function Page() {
  const initialBacktestPayload = await loadInitialBacktestPayload();

  return (
    <section className="backtests-page backtests-page--focused">
      <BacktestRiskDashboard initialPayload={initialBacktestPayload} />
    </section>
  );
}
