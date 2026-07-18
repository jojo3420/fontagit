"use client";

import { useSearchParams, useRouter } from "next/navigation";
import type { Font } from "@/types/font";
import { parseFilterQuery, buildFilterQuery } from "@/lib/filters";
import styles from "./FontFilters.module.css";

const CATEGORIES = ["고딕", "명조", "손글씨", "장식"] as const;
const PRICES = ["무료", "유료"] as const;

interface ClientFontFiltersProps {
  fonts: Font[];
}

export function ClientFontFilters({ fonts }: ClientFontFiltersProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { categories, tiers, sort } = parseFilterQuery(searchParams);

  // 카테고리별 개수 계산
  const categoryCount = new Map<string, number>();
  CATEGORIES.forEach((cat) => {
    categoryCount.set(cat, fonts.filter((f) => f.category === cat).length);
  });

  const handleCategoryChange = (category: string, checked: boolean) => {
    const newCategories = new Set(categories);
    if (checked) {
      newCategories.add(category);
    } else {
      newCategories.delete(category);
    }

    const query = buildFilterQuery(newCategories, tiers, sort);
    router.push(`?${query}`);
  };

  const handleTierChange = (tier: "free" | "paid", checked: boolean) => {
    const newTiers = new Set(tiers);
    if (checked) {
      newTiers.add(tier);
    } else {
      newTiers.delete(tier);
    }

    const query = buildFilterQuery(categories, newTiers, sort);
    router.push(`?${query}`);
  };

  return (
    <aside className={styles.sidebar}>
      <section className={styles.section}>
        <h2 className={styles.title}>분류</h2>
        {CATEGORIES.map((c) => (
          <label key={c} className={styles.check}>
            <input
              type="checkbox"
              name="category"
              value={c}
              checked={categories.has(c)}
              onChange={(e) => handleCategoryChange(c, e.target.checked)}
            />
            {c} {categoryCount.get(c)}
          </label>
        ))}
      </section>
      <section className={styles.section}>
        <h2 className={styles.title}>가격</h2>
        {PRICES.map((p) => {
          const tierKey = p === "무료" ? "free" : ("paid" as const);
          return (
            <label key={p} className={styles.check}>
              <input
                type="checkbox"
                name="price"
                value={p}
                checked={tiers.has(tierKey)}
                onChange={(e) => handleTierChange(tierKey, e.target.checked)}
              />
              {p}
            </label>
          );
        })}
      </section>
    </aside>
  );
}
