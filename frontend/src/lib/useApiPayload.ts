'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export function useApiPayload<T>(url: string, initialPayload: T | null = null, initialPayloadUrl?: string) {
  const snapshotUrl = initialPayloadUrl ?? url;
  const matchingInitialPayload = snapshotUrl === url ? initialPayload : null;
  const [payload, setPayload] = useState<T | null>(matchingInitialPayload);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(matchingInitialPayload === null);
  const [requestKey, setRequestKey] = useState(0);
  const seed = useRef({ url: snapshotUrl, payload: initialPayload });
  const previousUrl = useRef(url);
  const previousInitialPayload = useRef(initialPayload);
  const previousInitialUrl = useRef(initialPayloadUrl);

  const reload = useCallback(() => {
    setRequestKey((current) => current + 1);
  }, []);

  useEffect(() => {
    const urlChanged = previousUrl.current !== url;
    previousUrl.current = url;
    if (urlChanged) seed.current.payload = null;
    if (previousInitialPayload.current !== initialPayload || previousInitialUrl.current !== initialPayloadUrl) {
      previousInitialPayload.current = initialPayload;
      previousInitialUrl.current = initialPayloadUrl;
      seed.current = { url: snapshotUrl, payload: initialPayload };
      if (initialPayload !== null && snapshotUrl === url) {
        setPayload(initialPayload);
        setError(null);
        setLoading(false);
        return;
      }
    }
    // The server already fetched this snapshot. Keep explicit reloads and URL
    // changes live, including switching back to the original model or stock.
    if (requestKey === 0 && seed.current.payload !== null && seed.current.url === url) return;
    let cancelled = false;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    if (urlChanged) setPayload(null);
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
  }, [initialPayload, initialPayloadUrl, requestKey, url]);

  return { payload, error, loading, reload };
}
