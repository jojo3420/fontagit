'use client';

import { useState, useEffect, useRef } from 'react';
import { searchSuggestions } from '@/lib/db/search';
import type { SearchResult } from '@/lib/db/types';

export type SuggestItem = SearchResult & {
  score?: number;
};

interface UseDebouncedSuggestionsReturn {
  items: SuggestItem[];
  loading: boolean;
  error: boolean;
}

const DEFAULT_DELAY = 200;

/* eslint-disable react-hooks/set-state-in-effect */
export function useDebouncedSuggestions(
  query: string,
  delayMs: number = DEFAULT_DELAY
): UseDebouncedSuggestionsReturn {
  const [result, setResult] = useState<UseDebouncedSuggestionsReturn>({
    items: [],
    loading: false,
    error: false,
  });

  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const sequenceRef = useRef(0);
  const isMountedRef = useRef(true);

  useEffect(() => {
    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      setResult({ items: [], loading: false, error: false });
      return;
    }

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    setResult((prev) => ({ ...prev, loading: true, error: false }));

    const currentSequence = ++sequenceRef.current;

    timeoutRef.current = setTimeout(async () => {
      if (!isMountedRef.current || sequenceRef.current !== currentSequence) {
        return;
      }

      try {
        const data = await searchSuggestions(trimmedQuery, 8);
        if (isMountedRef.current && sequenceRef.current === currentSequence) {
          setResult({
            items: data,
            loading: false,
            error: false,
          });
        }
      } catch (err) {
        if (sequenceRef.current === currentSequence && isMountedRef.current) {
          setResult({ items: [], loading: false, error: true });
        }
      }
    }, delayMs);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, [query, delayMs]);

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  return result;
}
/* eslint-enable react-hooks/set-state-in-effect */
