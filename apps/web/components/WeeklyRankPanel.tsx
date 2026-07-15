import Link from "next/link";
import type { TrendItem } from "@/types/font";
import { TrendRow } from "./TrendRow";
import styles from "./WeeklyRankPanel.module.css";

/** 홈 우측 "이번 주 인기 TOP 10" 패널. 순위 항목은 TrendRow 재사용 */
export function WeeklyRankPanel({ items }: { items: TrendItem[] }) {
  return (
    <aside className={styles.panel}>
      <div className={styles.head}>
        <div>
          <h2 className={styles.title}>이번 주 인기 TOP 10</h2>
          <p className={styles.hint}>이동 클릭 기준 {String.fromCharCode(183)} 매주 갱신</p>
        </div>
        <Link href="/trends" className={styles.all}>전체 →</Link>
      </div>
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.rank}>
            <TrendRow item={item} />
          </li>
        ))}
      </ul>
    </aside>
  );
}
