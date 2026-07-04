import { ConditionScreenTable, type ConditionScreenPayload } from '../../components/ConditionScreenTable';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadInitialConditionScreenPayload(): Promise<ConditionScreenPayload | null> {
  try {
    const response = await fetch(`${apiBase}/api/condition-screen`, { cache: 'no-store' });
    if (!response.ok) return null;
    return (await response.json()) as ConditionScreenPayload;
  } catch {
    return null;
  }
}

export default async function Page() {
  const initialPayload = await loadInitialConditionScreenPayload();

  return (
    <section className="condition-screen-page">
      <ConditionScreenTable initialPayload={initialPayload} />
    </section>
  );
}
