import { FilterChip } from "./FilterChip";
import styles from "./FontFilters.module.css";

const CATEGORIES = ["고딕", "명조", "손글씨", "디스플레이"];
const PRICES = ["무료", "유료"];
const USES = ["본문", "제목", "로고"];

export function FontFilters() {
  return (
    <div className={styles.sidebar}>
      <div className={styles.section}>
        <h3 className={styles.title}>분류</h3>
        <div className={styles.chips}>
          {CATEGORIES.map((c) => (
            <label key={c}>
              <input type="checkbox" />
              {c}
            </label>
          ))}
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.title}>가격</h3>
        <div className={styles.chips}>
          {PRICES.map((p) => (
            <label key={p}>
              <input type="checkbox" />
              {p}
            </label>
          ))}
        </div>
      </div>

      <div className={styles.section}>
        <h3 className={styles.title}>용도</h3>
        <div className={styles.chips}>
          {USES.map((u) => (
            <label key={u}>
              <input type="checkbox" />
              {u}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}
