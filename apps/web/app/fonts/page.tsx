import { getAllFonts } from "@/lib/data";
import { FontFilters } from "@/components/FontFilters";
import { FontGrid } from "@/components/FontGrid";
import styles from "./page.module.css";

export default async function FontsPage() {
  const fonts = await getAllFonts();

  return (
    <main className={styles.main}>
      <FontFilters />
      <div className={styles.body}>
        <div className={styles.toolbar}>
          <span className={styles.count}>폰트 {fonts.length}종</span>
          <div className={styles.sorts}>
            <button type="button" className={`${styles.sort} ${styles.active}`}>인기순</button>
            <button type="button" className={styles.sort}>최신순</button>
          </div>
        </div>
        <FontGrid fonts={fonts} />
      </div>
    </main>
  );
}
