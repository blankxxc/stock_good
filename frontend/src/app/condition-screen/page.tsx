import { loadInitialApiPayload } from '../../lib/serverApi';
import { ConditionScreenTable, type ConditionScreenPayload } from '../../components/ConditionScreenTable';

export const dynamic = 'force-dynamic';

async function loadInitialConditionScreenPayload(): Promise<ConditionScreenPayload | null> {
  return loadInitialApiPayload<ConditionScreenPayload>(`/api/condition-screen`);
}

export default async function Page() {
  const initialPayload = await loadInitialConditionScreenPayload();

  return (
    <section className="condition-screen-page">
      <ConditionScreenTable initialPayload={initialPayload} />
    </section>
  );
}
