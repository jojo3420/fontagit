import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getCollectionBySlug, getAllCollectionSlugs } from "@/lib/data";
import { getSiteUrl } from "@/lib/seo";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "@/components/TierChip";
import styles from "./page.module.css";

export const dynamicParams = false;

export async function generateStaticParams() {
  const slugs = await getAllCollectionSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const collection = await getCollectionBySlug(slug);

  if (!collection) {
    return {
      title: "컬렉션을 찾을 수 없습니다",
      robots: { index: false, follow: false },
    };
  }

  return {
    title: `${collection.title} - FontAgit`,
    description: collection.intro,
    alternates: { canonical: getSiteUrl(`/collections/${collection.slug}/`) },
  };
}

export default async function CollectionDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const collection = await getCollectionBySlug(slug);

  if (!collection) {
    notFound();
  }

  return (
    <main className={styles.main}>
      <div className={styles.kicker}>컬렉션 - {collection.items.length}종</div>
      <h1 className={styles.title}>{collection.title}</h1>
      <p className={styles.intro}>{collection.intro}</p>
      <div className={styles.list}>
        {collection.items.map((it) => (
          <div key={it.slug} className={styles.item}>
            <div className={styles.itemHead}>
              <Link href={`/fonts/${it.slug}`} className={styles.itemName} style={{ fontFamily: familyOf(it.fontKey) }}>{it.nameKo}</Link>
              <TierChip tier={it.tier} />
            </div>
            <p className={styles.comment}>{it.comment}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
