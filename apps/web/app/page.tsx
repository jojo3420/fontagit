import { Hero } from "@/components/Hero";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { AdSlot } from "@/components/AdSlot";
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
          <AdSlot />
        </div>
      </section>
    </main>
  );
}
