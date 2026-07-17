import Link from "next/link";
import type { TrendItem } from "@/types/font";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./TrendRankRow.module.css";

const LABEL: Record<TrendItem["change"], (n?: number) => string> = {
  up: (n) => `▲ ${n ?? ""}`.trim(),
  down: (n) => `▼ ${n ?? ""}`.trim(),
  hold: () => "—",
  new: () => "NEW",
};

interface TrendRankRowProps {
  item: TrendItem;
  showMoves?: boolean;
}

/** 트렌드 페이지 전용 카드형 순위 행(디자인 1h). 홈 사이드바 TrendRow와 별개 */
export function TrendRankRow({ item, showMoves = true }: TrendRankRowProps) {
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
        <span className={styles.clicks}>
          <b className={styles.num}>{item.moves.toLocaleString()}</b>
          <em className={styles.label}>이동</em>
        </span>
      )}
      <TierChip tier={item.font.tier} />
    </Link>
  );
}
