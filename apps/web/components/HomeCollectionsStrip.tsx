import type { Collection } from "@/types/font";
import { CollectionCard } from "./CollectionCard";
import styles from "./HomeCollectionsStrip.module.css";

export function HomeCollectionsStrip({ collections }: { collections: Collection[] }) {
  if (collections.length === 0) return null;
  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h2 id="collections-heading" className={styles.title}>추천 컬렉션</h2>
        <span className={styles.hint}>테마별로 골라 담은 폰트 모음</span>
      </div>
      <div className={styles.strip}>
        {collections.map((c) => (
          <div key={c.slug} className={styles.item}>
            <CollectionCard collection={c} />
          </div>
        ))}
      </div>
    </div>
  );
}
