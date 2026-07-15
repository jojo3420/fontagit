import { FilterChip } from "./FilterChip";
import styles from "./FontFilters.module.css";

const CATEGORIES = ["고딕", "명조", "손글씨", "디스플레이"] as const;
const PRICES = ["무료", "유료"] as const;
const USES = ["본문", "제목", "로고"] as const;

/** 폰트 목록 좌측 필터 사이드바(디자인 1f). 현재는 시각 매칭(비기능) */
export function FontFilters() {
  return (
    <aside className={styles.sidebar}>
      <section className={styles.section}>
        <h2 className={styles.title}>분류</h2>
        {CATEGORIES.map((c) => (
          <label key={c} className={styles.check}>
            <input type="checkbox" name="category" value={c} /> {c}
          </label>
        ))}
      </section>
      <section className={styles.section}>
        <h2 className={styles.title}>가격</h2>
        {PRICES.map((p) => (
          <label key={p} className={styles.check}>
            <input type="checkbox" name="price" value={p} /> {p}
          </label>
        ))}
      </section>
      <section className={styles.section}>
        <h2 className={styles.title}>용도</h2>
        <div className={styles.chips}>
          {USES.map((u) => (
            <FilterChip key={u}>{u}</FilterChip>
          ))}
        </div>
      </section>
    </aside>
  );
}
