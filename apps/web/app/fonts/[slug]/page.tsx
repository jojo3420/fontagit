import { notFound } from "next/navigation";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives } from "@/lib/data";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "@/components/TierChip";
import { LicenseBadge } from "@/components/LicenseBadge";
import { Button } from "@/components/Button";
import { FontCard } from "@/components/FontCard";
import { PreviewInput } from "@/components/PreviewInput";
import { Specimen } from "@/components/Specimen";
import styles from "./page.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export default async function FontDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const font = getFontBySlug(slug);

  if (!font) {
    notFound();
  }

  const family = fontKeyToVar[font.fontKey];
  const isPaid = font.tier === "paid";
  const specimenWeights = font.availableWeights;

  return (
    <main className={styles.wrap}>
      <header className={styles.header}>
        <h1 className={styles.title}>{font.nameKo}</h1>
        <div className={styles.meta}>
          <TierChip tier={font.tier} />
          <LicenseBadge commercial={font.license.commercial} />
          <span>{specimenWeights.length}가지 굵기</span>
          <span>{font.foundry}</span>
        </div>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>미리보기</h2>
        <PreviewInput fontFamily={family} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>견본</h2>
        <Specimen fontFamily={family} weights={specimenWeights} substitute={isPaid} />
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>라이선스 및 다운로드</h2>
        <div className={styles.actions}>
          {isPaid ? (
            <Button href={font.officialUrl}>구매 페이지로 이동</Button>
          ) : (
            <Button href={font.officialUrl}>공식 페이지에서 내려받기</Button>
          )}
        </div>
      </section>

      {isPaid && (
        <section className={styles.section}>
          <h2 className={styles.sectionTitle}>비슷한 무료 대안</h2>
          <div className={styles.alternatives}>
            {resolveFreeAlternatives(font).map((alt) => (
              <FontCard key={alt.slug} font={alt} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
