"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { FilterChip } from "./FilterChip";
import SearchSuggestions from "./SearchSuggestions";
import { useDebouncedSuggestions } from "@/hooks/useDebouncedSuggestions";
import styles from "./Hero.module.css";

const CHIPS = ["한글", "고딕", "명조", "손글씨", "무료", "유료"] as const;

/** 홈 히어로(디자인 1d 좌측 패널). 검색 입력 + 카테고리 칩 */
export function Hero() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [isComposing, setIsComposing] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLFormElement>(null);

  const { items } = useDebouncedSuggestions(query);
  const listboxId = "hero-suggest-listbox";

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (isComposing) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setOpen(true);
        setActiveIndex((prev) => (prev + 1) % (items.length || 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setOpen(true);
        setActiveIndex((prev) => (prev === 0 ? items.length - 1 : prev - 1));
        break;
      case "Enter":
        e.preventDefault();
        if (activeIndex >= 0 && items[activeIndex]) {
          handleSelectSuggestion(items[activeIndex].slug);
        } else {
          handleSubmitSearch();
        }
        break;
      case "Escape":
        setOpen(false);
        inputRef.current?.blur();
        break;
      default:
        break;
    }
  };

  const handleSelectSuggestion = (slug: string) => {
    router.push(`/fonts/${slug}`);
    setOpen(false);
    setQuery("");
    setActiveIndex(-1);
  };

  const handleSubmitSearch = (e?: FormEvent<HTMLFormElement>) => {
    e?.preventDefault();
    const q = query.trim();
    if (!q) return;
    router.push(`/search?q=${encodeURIComponent(q)}`);
    setOpen(false);
    setQuery("");
  };

  return (
    <section className={styles.hero}>
      <h1 className={styles.h1}>당신의 폰트 아지트</h1>
      <p className={styles.sub}>
        설치 없이, 웹에서. 좋은 폰트를 골라두고 지금 뜨는 흐름까지 챙겨드려요.
      </p>
      <form onSubmit={handleSubmitSearch} ref={panelRef} className={styles.form}>
        <input
          ref={inputRef}
          className={styles.input}
          type="search"
          placeholder="폰트 이름을 검색하세요 (예: 프리텐다드)"
          aria-label="폰트 검색"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listboxId}
          aria-activedescendant={
            activeIndex >= 0 ? `${listboxId}-${activeIndex}` : ""
          }
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
            setActiveIndex(-1);
          }}
          onKeyDown={handleKeyDown}
          onFocus={() => query && setOpen(true)}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
        />
        {open && query && (
          <SearchSuggestions
            items={items}
            activeIndex={activeIndex}
            query={query}
            listboxId={listboxId}
            onSelect={handleSelectSuggestion}
            onHover={setActiveIndex}
          />
        )}
      </form>
      <div className={styles.chips}>
        {CHIPS.map((label, i) => (
          <FilterChip key={label} active={i === 0}>
            {label}
          </FilterChip>
        ))}
      </div>
    </section>
  );
}
