'use client';

import { useState, useEffect, useRef } from 'react';
import { searchSuggestions } from '@/lib/db/search';
import type { SearchResult } from '@/lib/db/types';

export type SuggestItem = SearchResult & { score?: number };

interface UseDebouncedSuggestionsReturn {
  items: SuggestItem[];
  loading: boolean;
  error: boolean;
}

const DEFAULT_DELAY = 200;

export function useDebouncedSuggestions(
  query: string,
  delayMs: number = DEFAULT_DELAY
): UseDebouncedSuggestionsReturn {
  /* eslint-disable react-hooks/set-state-in-effect */
  const [result, setResult] = useState<UseDebouncedSuggestionsReturn>({
    items: [],
    loading: false,
    error: false,
  });

  const sequenceRef = useRef(0);

  useEffect(() => {
    const trimmed = query.trim();
    const seq = ++sequenceRef.current;

    if (!trimmed) {
      setResult({ items: [], loading: false, error: false });
      return;
    }

    setResult((prev) => ({ ...prev, loading: true, error: false }));

    const controller = new AbortController();

    const timer = setTimeout(async () => {
      try {
        const data = await searchSuggestions(trimmed, 8, controller.signal);

        if (sequenceRef.current === seq) {
          setResult({ items: data, loading: false, error: false });
        }
      } catch {
        if (controller.signal.aborted) return;

        if (sequenceRef.current === seq) {
          setResult({ items: [], loading: false, error: true });
        }
      }
    }, delayMs);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, delayMs]);

  return result;
}
