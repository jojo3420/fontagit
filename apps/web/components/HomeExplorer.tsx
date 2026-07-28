"use client";

import { useState } from "react";
import Link from "next/link";
import { CHIP_DEFS, badgeFor, type ChipKey, type HomePreview } from "@/lib/homeCuration";
import { FilterChip } from "./FilterChip";
import { FontCard } from "./FontCard";
import { EmptyState } from "./EmptyState";
import styles from "./HomeExplorer.module.css";

export function HomeExplorer({ preview }: { preview: HomePreview }) {
  const [active, setActive] = useState<ChipKey>("all");
  const chip = CHIP_DEFS.find((c) => c.key === active) ?? CHIP_DEFS[0];
  const fonts = preview.chips[active] ?? [];
  const moreHref = `/fonts?${chip.query}`;

  return (
    <section className={styles.wrap} aria-label="분류별 폰트 미리보기">
      <div className={styles.chips}>
        {CHIP_DEFS.map((c) => (
          <FilterChip key={c.key} active={c.key === active} onClick={() => setActive(c.key)}>
            {c.label}
          </FilterChip>
        ))}
      </div>
      {fonts.length === 0 ? (
        <EmptyState
          title="아직 준비 중이에요"
          description="이 분류의 폰트가 등록되면 바로 보여드릴게요."
          actionHref={moreHref}
          actionLabel="전체 폰트 보기"
        />
      ) : (
        <div className={styles.grid}>
          {fonts.map((f) => (
            <FontCard key={f.slug} font={f} badge={badgeFor(f, preview.hotSlugs)} />
          ))}
          <Link href={moreHref} className={styles.more}>전체 보기 →</Link>
        </div>
      )}
    </section>
  );
}
