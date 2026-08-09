import { HorizonProbabilityTable, type ScoresPayload } from '../../components/HorizonProbabilityTable';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialScoresPayload(model: string): Promise<ScoresPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/scores?model=${encodeURIComponent(model)}`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as ScoresPayload;
  } catch {
    return null;
  }
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const rawModel = (await searchParams).model;
  const requestedModel = Array.isArray(rawModel) ? rawModel[0] : rawModel;
  const selectedModel = ['cograsp', 'sentiment_event', 'finmamba'].includes(requestedModel ?? '')
    ? requestedModel as string
    : 'cograsp';
  const initialScoresPayload = await loadInitialScoresPayload(selectedModel);

  return (
    <section className="scores-page">
      <HorizonProbabilityTable initialPayload={initialScoresPayload} />
    </section>
  );
}
