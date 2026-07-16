import Link from "next/link";
import type { TrendItem } from "@/types/font";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./TrendRow.module.css";

const LABEL: Record<TrendItem["change"], (n?: number) => string> = {
  up: (n) => `▲ ${n ?? ""}`.trim(),
  down: (n) => `▼ ${n ?? ""}`.trim(),
  hold: () => "—",
  new: () => "NEW",
};

interface TrendRowProps {
  item: TrendItem;
  showMoves?: boolean;
}

export function TrendRow({ item, showMoves = true }: TrendRowProps) {
  return (
    <Link href={`/fonts/${item.font.slug}`} className={styles.row}>
      <span className={styles.rank}>{item.rank}</span>
      <span className={`${styles.change} ${styles[item.change]}`}>
        {LABEL[item.change](item.changeAmount)}
      </span>
      <span
        className={styles.name}
        style={{ fontFamily: familyOf(item.font.fontKey) }}
      >
        {item.font.nameKo}
      </span>
      {showMoves && (
        <span className={styles.moves}>이동 {item.moves.toLocaleString()}회</span>
      )}
      <TierChip tier={item.font.tier} />
    </Link>
  );
}
