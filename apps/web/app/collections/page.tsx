import type { Metadata } from "next";
import { getAllCollections } from "@/lib/data";
import { CollectionCard } from "@/components/CollectionCard";
import { EmptyState } from "@/components/EmptyState";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "컬렉션 - FontAgit",
  alternates: { canonical: "/collections/" },
};

export default async function CollectionsPage() {
  const collections = await getAllCollections();

  return (
    <main className={styles.main}>
      <h1 className={styles.h1}>컬렉션</h1>
      <p className={styles.lead}>테마별로 묶은 폰트 모음이에요.</p>
      {collections.length === 0 ? (
        <EmptyState
          title="아직 컬렉션이 없어요"
          description="곧 테마별 폰트 모음을 준비할게요. 먼저 폰트를 둘러보시겠어요?"
          actionHref="/fonts"
          actionLabel="폰트 둘러보기"
        />
      ) : (
        <div className={styles.grid}>
          {collections.map((c) => (
            <CollectionCard key={c.slug} collection={c} />
          ))}
        </div>
      )}
    </main>
  );
}
