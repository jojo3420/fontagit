import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives } from "@/lib/data";
import { familyOf } from "@/lib/fonts";
import { getSiteUrl } from "@/lib/seo";
import { Breadcrumb } from "@/components/Breadcrumb";
import { SpecimenBox } from "@/components/SpecimenBox";
import { LicenseSummaryCard } from "@/components/LicenseSummaryCard";
import { AlternativesCard } from "@/components/AlternativesCard";
import { TierChip } from "@/components/TierChip";
import { ReportForm } from "./ReportForm";
import type { Font } from "@/types/font";
import styles from "./page.module.css";

export const dynamicParams = false;

export async function generateStaticParams() {
  const slugs = await getAllSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const font = await getFontBySlug(slug);

  if (!font) {
    return {
      title: "폰트를 찾을 수 없습니다",
      description: "요청하신 폰트가 존재하지 않습니다.",
    };
  }

  const fontUrl = getSiteUrl(`/fonts/${font.slug}/`);
  const tierLabel = font.tier === "free" ? "무료" : "유료";
  const description = `${font.foundry} 제작 서체. ${tierLabel} 라이선스. ${font.availableWeights.length}가지 굵기.`;

  return {
    title: `${font.nameKo} - FontAgit`,
    description,
    alternates: {
      canonical: fontUrl,
    },
    openGraph: {
      title: `${font.nameKo} - FontAgit`,
      description,
      url: fontUrl,
      type: "website",
    },
  };
}

export default async function FontDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const font = await getFontBySlug(slug);
  if (!font) notFound();

  const status = font.status ?? "published";

  if (status === "published") {
    const isPaid = font.tier === "paid";
    const alternatives = isPaid ? await resolveFreeAlternatives(font) : [];
    return <PublishedFontDetail font={font} alternatives={alternatives} />;
  }

  if (status === "hold") {
    return <HoldFontDetail font={font} />;
  }

  if (status === "discontinued") {
    return <DiscontinuedFontDetail font={font} />;
  }

  notFound();
}

function PublishedFontDetail({ font, alternatives }: { font: Font; alternatives: Font[] }) {
  const family = familyOf(font.fontKey);
  const isPaid = font.tier === "paid";
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
          <SpecimenBox fontFamily={family} font={font} editable={!isPaid} caption={caption} />
          {font.id && <ReportForm fontId={font.id} fontName={font.nameKo} />}
        </div>
        <div className={styles.side}>
          <LicenseSummaryCard font={font} />
          <AlternativesCard category={font.category} items={alternatives} />
        </div>
      </div>
    </main>
  );
}

function HoldFontDetail({ font }: { font: Font }) {
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
          </div>
          <div style={{ padding: "2rem", backgroundColor: "#fff3cd", border: "1px solid #ffc107", borderRadius: "4px" }}>
            <p style={{ margin: 0, color: "#856404" }}>
              <strong>일시 보류 중입니다.</strong>
            </p>
            <p style={{ marginTop: "0.5rem", marginBottom: 0, color: "#856404", fontSize: "0.95em" }}>
              이 폰트는 검토 중입니다. 곧 복구될 예정입니다.
            </p>
          </div>
          <p style={{ marginTop: "1.5rem", color: "#666" }}>
            {font.foundry} {String.fromCharCode(183)} {font.availableWeights.length}가지 굵기
          </p>
        </div>
      </div>
    </main>
  );
}

function DiscontinuedFontDetail({ font }: { font: Font }) {
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
          </div>
          <div style={{ padding: "2rem", backgroundColor: "#f8d7da", border: "1px solid #f5c6cb", borderRadius: "4px" }}>
            <p style={{ margin: 0, color: "#721c24" }}>
              <strong>배포가 종료된 폰트입니다.</strong>
            </p>
            <p style={{ marginTop: "0.5rem", marginBottom: 0, color: "#721c24", fontSize: "0.95em" }}>
              이 폰트는 더 이상 배포되지 않습니다.
            </p>
          </div>
          <p style={{ marginTop: "1.5rem", color: "#666" }}>
            {font.foundry} {String.fromCharCode(183)} {font.availableWeights.length}가지 굵기
          </p>
        </div>
      </div>
    </main>
  );
}
