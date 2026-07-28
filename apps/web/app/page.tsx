import type { Metadata } from "next";
import { Hero } from "@/components/Hero";
import { HomeExplorer } from "@/components/HomeExplorer";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { AdFitUnit } from "@/components/AdFitUnit";
import { CompareLazy } from "@/components/CompareLazy";
import { ADFIT_UNIT_HOME } from "@/lib/analytics/constants";
import { getTrends, getAllFonts } from "@/lib/data";
import { buildHomePreview } from "@/lib/homeCuration";
import styles from "./page.module.css";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

export default async function Home() {
  const [{ items, source }, fonts] = await Promise.all([getTrends(), getAllFonts()]);
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
      <section id="compare" className={styles.compareSection} aria-labelledby="compare-heading">
        <div className={styles.container}>
          <CompareLazy
            placeholder={<div className={styles.comparePlaceholder} />}
          />
        </div>
      </section>
      <section className={styles.adSection}>
        <div className={styles.container}>
          <AdFitUnit unit={ADFIT_UNIT_HOME ?? ""} width={320} height={100} label />
        </div>
      </section>
    </main>
  );
}
