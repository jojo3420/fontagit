import { FilterChip } from "./FilterChip";
import styles from "./Hero.module.css";

const CHIPS = ["한글", "고딕", "명조", "손글씨", "무료", "유료"] as const;

/** 홈 히어로(디자인 1d 좌측 패널). 검색 입력 + 카테고리 칩 */
export function Hero() {
  return (
    <section className={styles.hero}>
      <h1 className={styles.h1}>당신의 폰트 아지트</h1>
      <p className={styles.sub}>
        설치 없이, 웹에서. 좋은 폰트를 골라두고 지금 뜨는 흐름까지 챙겨드려요.
      </p>
      <input
        className={styles.input}
        type="search"
        placeholder="폰트 이름을 검색하세요 (예: 프리텐다드)"
        aria-label="폰트 검색"
      />
      <div className={styles.chips}>
        {CHIPS.map((label, i) => (
          <FilterChip key={label} active={i === 0}>{label}</FilterChip>
        ))}
      </div>
    </section>
  );
}
