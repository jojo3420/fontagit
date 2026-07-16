'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { searchFonts } from '@/lib/db/search';
import type { SearchResult } from '@/lib/db/types';
import styles from './page.module.css';

function SearchContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const q = searchParams.get('q') || '';

  const [query, setQuery] = useState(q);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const timer = setTimeout(() => {
      if (query.trim()) {
        setLoading(true);
        setSearched(true);
        setError(false);
        searchFonts(query)
          .then((data) => {
            if (!cancelled) {
              setResults(data);
              setLoading(false);
            }
          })
          .catch((err) => {
            if (!cancelled) {
              setError(true);
              setResults([]);
              setLoading(false);
            }
          });
        router.replace(query.trim() ? `/search?q=${encodeURIComponent(query)}` : '/search', { scroll: false });
      } else {
        if (!cancelled) {
          setResults([]);
          setSearched(false);
          setLoading(false);
          setError(false);
        }
      }
    }, 250); // debounce

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, router]);

  return (
    <main className={styles.main}>
      <div className={styles.header}>
        <h1>폰트 검색</h1>
        <input
          type="text"
          placeholder="폰트명, 영문명, 별칭으로 검색..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={styles.input}
          autoFocus
          aria-label="폰트 검색"
        />
      </div>

      <div className={styles.results} aria-live="polite">
        {loading && <div className={styles.loading}>검색 중...</div>}
        {!loading && error && (
          <div className={styles.error}>검색에 실패했습니다. 잠시 후 다시 시도해주세요.</div>
        )}
        {!loading && searched && results.length === 0 && !error && (
          <div className={styles.empty}>검색 결과가 없습니다.</div>
        )}
        {!loading && !error && results.length > 0 && (
          <ul className={styles.list}>
            {results.map((item) => (
              <li key={item.slug} className={styles.item}>
                <Link href={`/fonts/${item.slug}`}>
                  <div className={styles.name}>
                    {item.nameKo || item.nameEn}
                  </div>
                  <div className={styles.meta}>
                    <span className={styles.tier}>{item.tier === 'free' ? '무료' : '유료'}</span>
                    <span className={styles.category}>{item.category}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
        {!searched && <div className={styles.prompt}>검색어를 입력하세요.</div>}
      </div>
    </main>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<div>로딩...</div>}>
      <SearchContent />
    </Suspense>
  );
}
