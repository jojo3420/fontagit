'use client';

import { useState, useEffect, useRef, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import SearchSuggestions from './SearchSuggestions';
import { useDebouncedSuggestions } from '@/hooks/useDebouncedSuggestions';
import styles from './HeaderSearch.module.css';

export function HeaderSearch() {
  const router = useRouter();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isComposing, setIsComposing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const { items, loading, error } = useDebouncedSuggestions(query);
  const listboxId = 'header-suggest-listbox';

  useEffect(() => {
    const handleSlashKey = (e: KeyboardEvent) => {
      if (e.key === '/' && e.target instanceof HTMLElement) {
        const target = e.target;
        if (!['input', 'textarea', 'select'].includes(target.tagName.toLowerCase()) && !target.isContentEditable) {
          e.preventDefault();
          inputRef.current?.focus();
        }
      }
    };

    document.addEventListener('keydown', handleSlashKey);
    return () => document.removeEventListener('keydown', handleSlashKey);
  }, []);

  useEffect(() => {
    if (!dropdownOpen) return;

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setDropdownOpen(false);
      }
    };

    const onMouseDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!formRef.current?.contains(t)) {
        setDropdownOpen(false);
      }
    };

    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('mousedown', onMouseDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('mousedown', onMouseDown);
    };
  }, [dropdownOpen]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.nativeEvent.isComposing) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, items.length - 1));
      setDropdownOpen(true);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, -1));
    } else if (e.key === 'Enter') {
      if (dropdownOpen && activeIndex >= 0 && items[activeIndex]) {
        e.preventDefault();
        router.push(`/fonts/${items[activeIndex].slug}`);
        setDropdownOpen(false);
      }
    } else if (e.key === 'Escape') {
      setDropdownOpen(false);
      setActiveIndex(-1);
      inputRef.current?.blur();
    }
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const q = query.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
    setDropdownOpen(false);
  };

  const handleInputChange = (value: string) => {
    setQuery(value);
    setDropdownOpen(true);
    setActiveIndex(-1);
  };

  return (
    <form className={styles.searchBar} onSubmit={handleSubmit} role="search" ref={formRef}>
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
          onChange={(e) => handleInputChange(e.target.value)}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={(e) => {
            setIsComposing(false);
            handleInputChange(e.currentTarget.value);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => query && setDropdownOpen(true)}
          className={styles.input}
          aria-label="폰트 검색"
          role="combobox"
          aria-expanded={dropdownOpen && items.length > 0}
          aria-controls={listboxId}
          aria-autocomplete="list"
          aria-activedescendant={activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined}
        />
        <kbd className={styles.kbd}>/</kbd>
      </div>
      <button type="submit" className={styles.searchBtn}>
        검색
      </button>
      {dropdownOpen && !isComposing && query.trim().length > 0 && (
        items.length > 0 ? (
          <SearchSuggestions
            items={items}
            activeIndex={activeIndex}
            query={query}
            listboxId={listboxId}
            onSelect={(slug) => {
              router.push(`/fonts/${slug}`);
              setDropdownOpen(false);
            }}
            onHover={setActiveIndex}
          />
        ) : error ? (
          <p className={styles.state} role="status">검색 중 문제가 발생했어요. 잠시 후 다시 시도해주세요.</p>
        ) : loading ? (
          <p className={styles.state} role="status">검색 중...</p>
        ) : (
          <p className={styles.state} role="status">일치하는 폰트가 없어요.</p>
        )
      )}
    </form>
  );
}
