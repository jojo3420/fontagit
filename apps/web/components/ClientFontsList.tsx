"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Font } from "@/types/font";
import { FontGrid } from "./FontGrid";
import {
  filterFonts,
  sortFonts,
  parseFilterQuery,
  buildFilterQuery,
  SORT_OPTIONS,
} from "@/lib/filters";
import styles from "./ClientFontsList.module.css";

interface Props {
  fonts: Font[];
}

export function ClientFontsList({ fonts }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { categories, tiers, uses, sort } = parseFilterQuery(searchParams);

  const filtered = filterFonts(fonts, categories, tiers, uses);
  const sorted = sortFonts(filtered, sort);

  const handleSortChange = (newSort: "popular" | "recent") => {
    if (newSort === sort) return;

    const query = buildFilterQuery(categories, tiers, uses, newSort);
    router.push(query ? `?${query}` : `?sort=${newSort}`);
  };

  return (
    <div className={styles.body}>
      <div className={styles.toolbar}>
        <span className={styles.count}>폰트 {sorted.length}종</span>
        <div className={styles.sorts}>
          <button
            type="button"
            className={`${styles.sort} ${sort === "popular" ? styles.active : ""}`}
            onClick={() => handleSortChange("popular")}
          >
            인기순
          </button>
          <button
            type="button"
            className={`${styles.sort} ${sort === "recent" ? styles.active : ""}`}
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
