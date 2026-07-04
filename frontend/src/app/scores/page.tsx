import { HorizonProbabilityTable, type ScoresPayload } from '../../components/HorizonProbabilityTable';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialScoresPayload(): Promise<ScoresPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/scores`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as ScoresPayload;
  } catch {
    return null;
  }
}

export default async function Page() {
  const initialScoresPayload = await loadInitialScoresPayload();

  return (
    <section className="scores-page">
      <HorizonProbabilityTable initialPayload={initialScoresPayload} />
    </section>
  );
}
