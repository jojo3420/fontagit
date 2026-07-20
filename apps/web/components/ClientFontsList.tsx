"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { Font } from "@/types/font";
import { FontGrid } from "./FontGrid";
import {
  filterFonts,
  sortFonts,
  parseFilterQuery,
  buildFilterQuery,
} from "@/lib/filters";
import { sectionOf } from "@/lib/sections";
import styles from "./ClientFontsList.module.css";

const ITEMS_PER_PAGE = 36;

interface Props {
  fonts: Font[];
}

/**
 * 클라이언트 사이드 폰트 목록 컴포넌트: 필터, 정렬, 무한스크롤 처리
 * ?section 파라미터로 특정 용도의 폰트만 필터링할 수 있다
 */
export function ClientFontsList({ fonts }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { categories, tiers, sourceTiers, sort } = parseFilterQuery(searchParams);
  const section = searchParams.get("section");
  const sentinelRef = useRef<HTMLDivElement>(null);
  const hasPopularityData = fonts.some((font) => font.moves > 0);
  const effectiveSort = sort === "popular" && !hasPopularityData ? "recent" : sort;

  // 섹션 필터: ?section이 없거나 "all"이면 모든 폰트, 아니면 해당 섹션만
  const sectionFiltered =
    section && section !== "all"
      ? fonts.filter((font) => sectionOf(font) === section)
      : fonts;

  const filtered = filterFonts(sectionFiltered, categories, tiers, sourceTiers);
  const sorted = sortFonts(filtered, effectiveSort);
  const filterKey = `${searchParams.toString()}|${effectiveSort}|section=${section}`;

  const [displayCount, setDisplayCount] = useState(ITEMS_PER_PAGE);
  // 필터/정렬이 바뀌면 표시 개수를 첫 페이지로 되돌린다(렌더 중 상태 조정 패턴)
  const [prevKey, setPrevKey] = useState(filterKey);
  if (filterKey !== prevKey) {
    setPrevKey(filterKey);
    setDisplayCount(ITEMS_PER_PAGE);
  }

  const displayedFonts = sorted.slice(0, displayCount);

  // 무한스크롤: sentinel이 보이면 다음 페이지만큼 표시 개수를 늘린다
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setDisplayCount((prev) => Math.min(prev + ITEMS_PER_PAGE, sorted.length));
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
    // filterKey/displayCount 변화로 sentinel이 재생성되면 observer를 다시 연결한다
  }, [sorted.length, filterKey, displayCount]);

  const handleSortChange = (newSort: "popular" | "recent") => {
    if (newSort === effectiveSort) return;

    const query = buildFilterQuery(categories, tiers, newSort, sourceTiers);
    router.push(`?${query}`);
  };

  return (
    <div className={styles.body}>
      <div className={styles.toolbar}>
        <span className={styles.count}>폰트 {sorted.length}종</span>
        <div className={styles.sorts}>
          {hasPopularityData && (
            <button
              type="button"
              className={`${styles.sort} ${effectiveSort === "popular" ? styles.active : ""}`}
              onClick={() => handleSortChange("popular")}
            >
              인기순
            </button>
          )}
          <button
            type="button"
            className={`${styles.sort} ${effectiveSort === "recent" ? styles.active : ""}`}
            onClick={() => handleSortChange("recent")}
          >
            최신순
          </button>
        </div>
      </div>

      {sorted.length === 0 ? (
        <div className={styles.empty}>
          <p>조건에 맞는 폰트가 없습니다</p>
        </div>
      ) : (
        <>
          <FontGrid fonts={displayedFonts} />
          {displayedFonts.length < sorted.length && (
            <div ref={sentinelRef} style={{ height: "1px" }} />
          )}
        </>
      )}
    </div>
  );
}
