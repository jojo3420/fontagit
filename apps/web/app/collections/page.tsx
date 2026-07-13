import { collections } from "@/data/collections";
import { CollectionCard } from "@/components/CollectionCard";
import styles from "./page.module.css";

export const metadata = { title: "컬렉션 - FontAgit" };

export default function CollectionsPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.h1}>컬렉션</h1>
      <p className={styles.lead}>테마별로 묶은 폰트 모음이에요.</p>
      <div className={styles.grid}>
        {collections.map((c) => (
          <CollectionCard key={c.slug} collection={c} />
        ))}
      </div>
    </main>
  );
}
