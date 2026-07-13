import TrendTable from "@/components/TrendTable";
import { weeklyTrends, monthlyTrends } from "@/data/trends";
import { FilterChip } from "@/components/FilterChip";
import styles from "./page.module.css";

export default function TrendsPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.h1}>트렌드</h1>
      <div className={styles.filters}>
        <FilterChip active>주간</FilterChip>
        <FilterChip>월간</FilterChip>
      </div>
      <TrendTable title="주간 트렌드" items={weeklyTrends} />
      <TrendTable title="월간 트렌드" items={monthlyTrends} />
    </main>
  );
}
