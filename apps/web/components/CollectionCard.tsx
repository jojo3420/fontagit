import Link from "next/link";
import type { Collection } from "@/types/font";
import styles from "./CollectionCard.module.css";

export function CollectionCard({ collection }: { collection: Collection }) {
  return (
    <Link href={`/collections/${collection.slug}`} className={styles.card}>
      <span className={styles.kicker}>컬렉션 - {collection.items.length}종</span>
      <h2 className={styles.title}>{collection.title}</h2>
      <p className={styles.intro}>{collection.intro}</p>
    </Link>
  );
}
