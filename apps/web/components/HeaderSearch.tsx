'use client';

import { useState, useEffect, useRef, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import SearchSuggestions from './SearchSuggestions';
import { useDebouncedSuggestions } from '@/hooks/useDebouncedSuggestions';
import styles from './HeaderSearch.module.css';

export function HeaderSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isComposing, setIsComposing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const { items, loading, error } = useDebouncedSuggestions(query);
  const listboxId = 'header-suggest-listbox';
  const stateStyle: React.CSSProperties = {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: 0,
    zIndex: 10,
    margin: 0,
    padding: '12px 16px',
    fontSize: 14,
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderTop: 'none',
    borderRadius: '0 0 var(--radius-card) var(--radius-card)',
    color: 'var(--text-secondary, #888)',
  };

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (panelRef.current?.contains(t) || toggleRef.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [open]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, items.length - 1));
      setOpen(true);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Enter') {
      if (open && activeIndex >= 0 && items[activeIndex]) {
        e.preventDefault();
        router.push(`/fonts/${items[activeIndex].slug}`);
        setOpen(false);
      }
    } else if (e.key === 'Escape') {
      setOpen(false);
      setActiveIndex(-1);
    }
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
    setOpen(false);
  };

  return (
    <>
      <button
        ref={toggleRef}
        type="button"
        className={styles.iconBtn}
        aria-label={open ? '검색 닫기' : '검색'}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m21 21-4.3-4.3" strokeLinecap="round" />
          </svg>
        )}
      </button>

      {open && (
        <div ref={panelRef} className={styles.panel}>
          <form className={styles.searchBar} onSubmit={handleSubmit} role="search">
            <div className={styles.inputBox}>
              <svg className={styles.searchIcon} width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
                <path d="m20 20-3.5-3.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <input
                ref={inputRef}
                type="text"
                placeholder="폰트 이름을 검색하세요 (예: 프리텐다드)"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setOpen(true);
                  setActiveIndex(-1);
                }}
                onCompositionStart={() => setIsComposing(true)}
                onCompositionEnd={(e) => {
                  setIsComposing(false);
                  setQuery(e.currentTarget.value);
                }}
                onKeyDown={handleKeyDown}
                onBlur={() => setOpen(false)}
                className={styles.input}
                aria-label="폰트 검색"
                role="combobox"
                aria-expanded={open && items.length > 0}
                aria-controls={listboxId}
                aria-autocomplete="list"
                aria-activedescendant={activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined}
              />
            </div>
            <button type="submit" className={styles.searchBtn}>
              검색
            </button>
            {open && !isComposing && query.trim().length > 0 && (
              items.length > 0 ? (
                <SearchSuggestions
                  items={items}
                  activeIndex={activeIndex}
                  query={query}
                  listboxId={listboxId}
                  onSelect={(slug) => {
                    router.push(`/fonts/${slug}`);
                    setOpen(false);
                  }}
                  onHover={setActiveIndex}
                />
              ) : error ? (
                <p style={stateStyle} role="status">검색 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.</p>
              ) : loading ? (
                <p style={stateStyle} role="status">검색 중...</p>
              ) : (
                <p style={stateStyle} role="status">일치하는 폰트가 없어요.</p>
              )
            )}
          </form>
        </div>
      )}
    </>
  );
}
