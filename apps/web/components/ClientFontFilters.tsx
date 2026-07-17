"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { FilterChip } from "./FilterChip";
import { parseFilterQuery, buildFilterQuery, TIER_LABEL } from "@/lib/filters";
import styles from "./FontFilters.module.css";

const CATEGORIES = ["고딕", "명조", "손글씨", "디스플레이"] as const;
const PRICES = ["무료", "유료"] as const;
const USES = ["본문", "제목", "로고"] as const;

export function ClientFontFilters() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { categories, tiers, uses } = parseFilterQuery(searchParams);

  const handleCategoryChange = (category: string, checked: boolean) => {
    const newCategories = new Set(categories);
    if (checked) {
      newCategories.add(category);
    } else {
      newCategories.delete(category);
    }

    const query = buildFilterQuery(newCategories, tiers, uses, "popular");
    router.push(query ? `?${query}` : "?sort=popular");
  };

  const handleTierChange = (tier: "free" | "paid", checked: boolean) => {
    const newTiers = new Set(tiers);
    if (checked) {
      newTiers.add(tier);
    } else {
      newTiers.delete(tier);
    }

    const query = buildFilterQuery(categories, newTiers, uses, "popular");
    router.push(query ? `?${query}` : "?sort=popular");
  };

  const handleUseToggle = (use: string) => {
    const newUses = new Set(uses);
    if (newUses.has(use)) {
      newUses.delete(use);
    } else {
      newUses.add(use);
    }

    const query = buildFilterQuery(categories, tiers, newUses, "popular");
    router.push(query ? `?${query}` : "?sort=popular");
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
            {c}
          </label>
        ))}
      </section>
      <section className={styles.section}>
        <h2 className={styles.title}>가격</h2>
        {PRICES.map((p) => {
          const tier = TIER_LABEL[p === "무료" ? "free" : "paid"];
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
      <section className={styles.section}>
        <h2 className={styles.title}>용도</h2>
        <div className={styles.chips}>
          {USES.map((u) => (
            <FilterChip
              key={u}
              active={uses.has(u)}
              onClick={() => handleUseToggle(u)}
            >
              {u}
            </FilterChip>
          ))}
        </div>
      </section>
    </aside>
  );
}
