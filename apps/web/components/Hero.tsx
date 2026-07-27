"use client";

import { FilterChip } from "./FilterChip";
import styles from "./Hero.module.css";

const CHIPS = ["한글", "고딕", "명조", "손글씨", "무료", "유료"] as const;

export function Hero() {
  return (
    <section className={styles.hero}>
      <h1 className={styles.h1}>당신의 폰트 아지트</h1>
      <p className={styles.sub}>
        설치 없이, 웹에서. 좋은 폰트를 골라두고 지금 뜨는 흐름까지 챙겨드려요.
      </p>
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
