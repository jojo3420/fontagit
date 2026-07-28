import type { Metadata } from "next";
import { Hero } from "@/components/Hero";
import { HomeExplorer } from "@/components/HomeExplorer";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { HomeCollectionsStrip } from "@/components/HomeCollectionsStrip";
import { AdFitUnit } from "@/components/AdFitUnit";
import { HomeCompareSection } from "@/components/HomeCompareSection";
import { ADFIT_UNIT_HOME } from "@/lib/analytics/constants";
import { getTrends, getAllFonts, getAllCollections } from "@/lib/data";
import { buildHomePreview } from "@/lib/homeCuration";
import styles from "./page.module.css";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

export default async function Home() {
  const [{ items, source }, fonts, collections] = await Promise.all([
    getTrends(),
    getAllFonts(),
    getAllCollections(),
  ]);
  const preview = buildHomePreview(fonts, items);
  return (
    <main className={styles.main}>
      <div className={styles.grid}>
        <div className={styles.left}>
          <Hero />
          <HomeExplorer preview={preview} />
        </div>
        <WeeklyRankPanel items={items} source={source} />
      </div>
      <section id="collections" className={styles.collectionsSection} aria-labelledby="collections-heading">
        <div className={styles.container}>
          <HomeCollectionsStrip collections={collections} />
        </div>
      </section>
      <HomeCompareSection />
      <section className={styles.adSection}>
        <div className={styles.container}>
          <AdFitUnit unit={ADFIT_UNIT_HOME ?? ""} width={320} height={100} label />
        </div>
      </section>
    </main>
  );
}
