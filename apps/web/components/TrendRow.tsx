import Link from "next/link";
import type { TrendItem } from "@/types/font";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./TrendRow.module.css";

const LABEL: Record<TrendItem["change"], (n?: number) => string> = {
  up: (n) => `▲ ${n ?? ""}`.trim(),
  down: (n) => `▼ ${n ?? ""}`.trim(),
  hold: () => "—",
  new: () => "NEW",
};

export default function TrendRow({ item }: { item: TrendItem }) {
  return (
    <Link href={`/fonts/${item.font.slug}`} className={styles.row}>
      <span className={styles.rank}>{item.rank}</span>
      <span className={`${styles.change} ${styles[item.change]}`}>
        {LABEL[item.change](item.changeAmount)}
      </span>
      <span
        className={styles.name}
        style={{ fontFamily: fontKeyToVar[item.font.fontKey] }}
      >
        {item.font.nameKo}
      </span>
      <span className={styles.moves}>이동 {item.moves.toLocaleString()}회</span>
      <TierChip tier={item.font.tier} />
    </Link>
  );
}
