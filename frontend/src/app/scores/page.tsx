import { loadInitialApiPayload } from '../../lib/serverApi';
import { HorizonProbabilityTable, type ScoresPayload } from '../../components/HorizonProbabilityTable';

export const dynamic = 'force-dynamic';

async function loadInitialScoresPayload(model: string): Promise<ScoresPayload | null> {
  return loadInitialApiPayload<ScoresPayload>(`/api/scores?model=${encodeURIComponent(model)}`);
}

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const rawModel = (await searchParams).model;
  const requestedModel = Array.isArray(rawModel) ? rawModel[0] : rawModel;
  const selectedModel = ['cograsp', 'sentiment_event'].includes(requestedModel ?? '')
    ? requestedModel as string
    : 'cograsp';
  const initialScoresPayload = requestedModel === 'api_llm' ? null : await loadInitialScoresPayload(selectedModel);

  return (
    <section className="scores-page">
      <HorizonProbabilityTable initialPayload={initialScoresPayload} />
    </section>
  );
}
