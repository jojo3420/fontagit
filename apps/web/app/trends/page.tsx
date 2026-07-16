import { getTrends } from "@/lib/data";
import { FilterChip } from "@/components/FilterChip";
import { TrendRankRow } from "@/components/TrendRankRow";
import styles from "./page.module.css";

export default async function TrendsPage() {
  const { items, source } = await getTrends();
  const isClicks = source === "clicks";

  return (
    <main className={styles.main}>
      <div className={styles.head}>
        <h1 className={styles.h1}>{isClicks ? "이번 주 인기 폰트" : "최신 등록 폰트"}</h1>
        <p className={styles.lead}>
          {isClicks
            ? "이동 클릭 기준 인기 순위입니다 (다운로드 순위 아님)."
            : "클릭 데이터가 쌓이면 이동 클릭 기준 인기 순위로 전환됩니다."}
        </p>
        <div className={styles.filters}>
          <FilterChip active>주간</FilterChip>
          <FilterChip>월간</FilterChip>
        </div>
      </div>
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.rank}>
            <TrendRankRow item={item} showMoves={isClicks} />
          </li>
        ))}
      </ul>
    </main>
  );
}
