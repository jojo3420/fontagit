import type { TrendItem } from "@/types/font";
import { TrendRow } from "./TrendRow";
import styles from "./TrendTable.module.css";

export function TrendTable({
  title,
  items,
}: {
  title: string;
  items: TrendItem[];
}) {
  return (
    <div className={styles.table}>
      <h2 className={styles.title}>{title}</h2>
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.rank}>
            <TrendRow item={item} />
          </li>
        ))}
      </ul>
    </div>
  );
}
