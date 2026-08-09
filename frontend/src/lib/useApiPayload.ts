'use client';

import { useCallback, useEffect, useState } from 'react';

export function useApiPayload<T>(url: string, initialPayload: T | null = null) {
  const [payload, setPayload] = useState<T | null>(initialPayload);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(initialPayload === null);
  const [requestKey, setRequestKey] = useState(0);

  const reload = useCallback(() => {
    setRequestKey((current) => current + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetch(url, { cache: 'no-store', signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json() as Promise<T>;
      })
      .then((data) => {
        if (!cancelled) {
          setPayload(data);
          setError(null);
        }
      })
      .catch((exc: Error) => {
        if (!cancelled && exc.name !== 'AbortError') setError(exc.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [requestKey, url]);

  return { payload, error, loading, reload };
}
