import { fonts } from "@/data/fonts";
import { FontGrid } from "@/components/FontGrid";
import { FilterChip } from "@/components/FilterChip";
import styles from "./page.module.css";

export default function FontsPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.h1}>폰트</h1>
      <div className={styles.filters}>
        <FilterChip active>전체</FilterChip>
        <FilterChip>무료</FilterChip>
        <FilterChip>유료</FilterChip>
        <FilterChip>고딕</FilterChip>
        <FilterChip>명조</FilterChip>
        <FilterChip>손글씨</FilterChip>
      </div>
      <FontGrid fonts={fonts} />
    </main>
  );
}
