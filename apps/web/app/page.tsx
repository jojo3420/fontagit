import { Hero } from "@/components/Hero";
import { TrendTable } from "@/components/TrendTable";
import { AdSlot } from "@/components/AdSlot";
import { weeklyTrends } from "@/data/trends";
import styles from "./page.module.css";

export default function Home() {
  return (
    <main className={styles.main}>
      <Hero />
      <section className={styles.section}>
        <div className={styles.container}>
          <TrendTable title="이번 주 인기 폰트" items={weeklyTrends} />
        </div>
      </section>
      <section className={styles.adSection}>
        <div className={styles.container}>
          <AdSlot />
        </div>
      </section>
    </main>
  );
}
