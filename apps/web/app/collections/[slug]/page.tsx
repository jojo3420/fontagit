import Link from "next/link";
import { notFound } from "next/navigation";
import { getCollectionBySlug, getAllCollectionSlugs, getFontBySlug } from "@/lib/data";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "@/components/TierChip";
import styles from "./page.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllCollectionSlugs().map((slug) => ({ slug }));
}

export default async function CollectionDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const collection = getCollectionBySlug(slug);

  if (!collection) {
    notFound();
  }

  return (
    <main className={styles.main}>
      <div className={styles.kicker}>컬렉션 - {collection.items.length}종</div>
      <h1 className={styles.title}>{collection.title}</h1>
      <p className={styles.intro}>{collection.intro}</p>
      <div className={styles.list}>
        {collection.items.map((it) => {
          const f = getFontBySlug(it.fontSlug)!;
          return (
            <div key={it.fontSlug} className={styles.item}>
              <div className={styles.itemHead}>
                <Link href={`/fonts/${f.slug}`} className={styles.itemName} style={{ fontFamily: familyOf(f.fontKey) }}>{f.nameKo}</Link>
                <TierChip tier={f.tier} />
              </div>
              <p className={styles.comment}>{it.comment}</p>
            </div>
          );
        })}
      </div>
    </main>
  );
}
