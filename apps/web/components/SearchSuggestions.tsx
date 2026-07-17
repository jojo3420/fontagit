'use client';

import { ReactNode } from 'react';
import type { SuggestItem } from '@/hooks/useDebouncedSuggestions';
import styles from './SearchSuggestions.module.css';

interface SearchSuggestionsProps {
  items: SuggestItem[];
  activeIndex: number;
  query: string;
  listboxId: string;
  onSelect: (slug: string) => void;
  onHover: (index: number) => void;
}

function highlight(text: string, query: string): ReactNode {
  const trimmedQuery = query.trim();
  if (!trimmedQuery || !text) {
    return text;
  }

  const index = text.indexOf(trimmedQuery);
  if (index === -1) {
    return text;
  }

  return (
    <>
      {text.slice(0, index)}
      <mark>{text.slice(index, index + trimmedQuery.length)}</mark>
      {text.slice(index + trimmedQuery.length)}
    </>
  );
}

export default function SearchSuggestions({
  items,
  activeIndex,
  query,
  listboxId,
  onSelect,
  onHover,
}: SearchSuggestionsProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <ul id={listboxId} role="listbox" className={styles.searchSuggestions}>
      {items.map((item, i) => {
        const name = item.nameKo || item.nameEn;
        return (
          <li
            key={item.slug}
            id={`${listboxId}-opt-${i}`}
            role="option"
            aria-selected={i === activeIndex}
            data-active={i === activeIndex}
            onMouseDown={(e) => {
              e.preventDefault();
              onSelect(item.slug);
            }}
            onMouseEnter={() => onHover(i)}
            className={styles.ssItem}
          >
            <div className={styles.ssName}>
              {highlight(name, query)}
            </div>
            {item.foundry && (
              <div className={styles.ssFoundry}>{item.foundry}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
