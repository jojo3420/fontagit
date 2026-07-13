import { Button } from "./Button";
import { FilterChip } from "./FilterChip";
import styles from "./Hero.module.css";

export function Hero() {
  return (
    <section className={styles.hero}>
      <h1 className={styles.h1}>폰트 덕후들의 아지트</h1>
      <p className={styles.sub}>무료-유료-국내외 폰트를 한 곳에서 찾고 비교하세요.</p>
      <div className={styles.searchbox}>
        <input className={styles.input} type="search" placeholder="폰트 이름-분위기로 검색" aria-label="폰트 검색" />
        <Button variant="primary">검색</Button>
      </div>
      <div className={styles.chips}>
        <FilterChip active>전체</FilterChip>
        <FilterChip>고딕</FilterChip>
        <FilterChip>명조</FilterChip>
        <FilterChip>손글씨</FilterChip>
        <FilterChip>장식</FilterChip>
      </div>
    </section>
  );
}
