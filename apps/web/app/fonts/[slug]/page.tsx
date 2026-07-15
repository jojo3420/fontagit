import { notFound } from "next/navigation";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives } from "@/lib/data";
import { fontKeyToVar } from "@/lib/fonts";
import { Breadcrumb } from "@/components/Breadcrumb";
import { SpecimenBox } from "@/components/SpecimenBox";
import { LicenseSummaryCard } from "@/components/LicenseSummaryCard";
import { AlternativesCard } from "@/components/AlternativesCard";
import { TierChip } from "@/components/TierChip";
import styles from "./page.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export default async function FontDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const font = getFontBySlug(slug);
  if (!font) notFound();

  const family = fontKeyToVar[font.fontKey];
  const isPaid = font.tier === "paid";
  const alternatives = isPaid ? resolveFreeAlternatives(font) : [];
  const caption = isPaid
    ? "견본은 유사 서체로 대체 표시 — 실제 서체는 공식 페이지에서 확인하세요."
    : undefined;

  return (
    <main className={styles.wrap}>
      <Breadcrumb
        items={[
          { label: "폰트", href: "/fonts" },
          { label: font.category, href: `/fonts?category=${encodeURIComponent(font.category)}` },
          { label: font.nameKo },
        ]}
      />
      <div className={styles.grid}>
        <div className={styles.main}>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>{font.nameKo}</h1>
            <TierChip tier={font.tier} />
          </div>
          <p className={styles.meta}>
            {font.foundry} {String.fromCharCode(183)} {font.availableWeights.length}가지 굵기 {String.fromCharCode(183)} 이동 {font.moves.toLocaleString()}회
          </p>
          <SpecimenBox fontFamily={family} editable={!isPaid} caption={caption} />
        </div>
        <div className={styles.side}>
          <LicenseSummaryCard font={font} />
          <AlternativesCard category={font.category} items={alternatives} />
        </div>
      </div>
    </main>
  );
}
