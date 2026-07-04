import { FactorLibraryDashboard } from '../../components/FactorLibraryDashboard';

export const dynamic = 'force-dynamic';

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

async function loadFactorPayload() {
  try {
    const response = await fetch(`${apiBase}/api/factors`, { cache: 'no-store' });
    if (!response.ok) return {};
    return await response.json();
  } catch {
    return {};
  }
}

export default async function Page() {
  const payload = await loadFactorPayload();

  return (
    <section className="factors-page">
      <FactorLibraryDashboard payload={payload} />
    </section>
  );
}
