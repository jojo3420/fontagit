import { Hero } from "@/components/Hero";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { AdSlot } from "@/components/AdSlot";
import { weeklyTrends } from "@/data/trends";
import styles from "./page.module.css";

export default function Home() {
  return (
    <main className={styles.main}>
      <div className={styles.grid}>
        <Hero />
        <WeeklyRankPanel items={weeklyTrends} />
      </div>
      <section className={styles.adSection}>
        <div className={styles.container}>
          <AdSlot />
        </div>
      </section>
    </main>
  );
}
