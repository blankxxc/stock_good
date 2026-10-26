/** Server-side snapshots use the same internal backend as the API proxy. */
export async function loadInitialApiPayload<T>(path: string): Promise<T | null> {
  const origin = process.env.BACKEND_INTERNAL_ORIGIN
    || process.env.BACKEND_API_BASE_URL
    || 'http://127.0.0.1:8000';
  try {
    const response = await fetch(`${origin}${path}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(15_000),
    });
    return response.ok ? await response.json() as T : null;
  } catch {
    return null;
  }
}
