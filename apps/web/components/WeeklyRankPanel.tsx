import Link from "next/link";
import type { TrendItem } from "@/types/font";
import type { TrendsSource } from "@/lib/data";
import { TrendRow } from "./TrendRow";
import styles from "./WeeklyRankPanel.module.css";

interface WeeklyRankPanelProps {
  items: TrendItem[];
  source: TrendsSource;
}

/** 홈 우측 패널. source에 따라 라벨 동적 전환:
 * - source="clicks": "이번 주 인기 TOP 10" + 이동수 표시
 * - source="latest": "최신 등록 TOP 10" + 이동수 숨김
 */
export function WeeklyRankPanel({ items, source }: WeeklyRankPanelProps) {
  const isClicks = source === "clicks";
  const title = isClicks ? "이번 주 인기 TOP 10" : "최신 등록 TOP 10";
  const hint = isClicks ? "이동 클릭 기준" : null;

  return (
    <aside className={styles.panel}>
      <div className={styles.head}>
        <div>
          <h2 className={styles.title}>{title}</h2>
          {hint && <p className={styles.hint}>{hint} {String.fromCharCode(183)} 매주 갱신</p>}
        </div>
        <Link href="/trends" className={styles.all}>전체 →</Link>
      </div>
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.rank}>
            <TrendRow item={item} showMoves={isClicks} />
          </li>
        ))}
      </ul>
    </aside>
  );
}
