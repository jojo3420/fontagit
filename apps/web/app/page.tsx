import { Hero } from "@/components/Hero";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { AdFitUnit } from "@/components/AdFitUnit";
import { ADFIT_UNIT_HOME } from "@/lib/analytics/constants";
import { getTrends } from "@/lib/data";
import styles from "./page.module.css";

export default async function Home() {
  const { items, source } = await getTrends();
  return (
    <main className={styles.main}>
      <div className={styles.grid}>
        <Hero />
        <WeeklyRankPanel items={items} source={source} />
      </div>
      <section className={styles.adSection}>
        <div className={styles.container}>
          <AdFitUnit unit={ADFIT_UNIT_HOME ?? ""} width={320} height={100} label />
        </div>
      </section>
    </main>
  );
}
