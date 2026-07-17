"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Font } from "@/types/font";
import { FontGrid } from "./FontGrid";
import {
  filterFonts,
  sortFonts,
  parseFilterQuery,
  buildFilterQuery,
} from "@/lib/filters";
import styles from "./ClientFontsList.module.css";

interface Props {
  fonts: Font[];
}

export function ClientFontsList({ fonts }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { categories, tiers, sort } = parseFilterQuery(searchParams);
  const hasPopularityData = fonts.some((font) => font.moves > 0);
  const effectiveSort = sort === "popular" && !hasPopularityData ? "recent" : sort;

  const filtered = filterFonts(fonts, categories, tiers);
  const sorted = sortFonts(filtered, effectiveSort);

  const handleSortChange = (newSort: "popular" | "recent") => {
    if (newSort === effectiveSort) return;

    const query = buildFilterQuery(categories, tiers, newSort);
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
        <FontGrid fonts={sorted} />
      )}
    </div>
  );
}
