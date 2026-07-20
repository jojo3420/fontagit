import type { Metadata } from "next";
import { Suspense } from "react";
import { getAllFonts } from "@/lib/data";
import { ClientFontFilters } from "@/components/ClientFontFilters";
import { ClientFontsList } from "@/components/ClientFontsList";
import { SectionedFontsView } from "@/components/SectionedFontsView";
import type { SearchParams } from "next/server";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "폰트 찾기 - FontAgit",
  alternates: { canonical: "/fonts/" },
};

/**
 * 개요 모드 판정: section/category/tier/source 파라미터가 모두 없으면 true
 */
function isOverviewMode(params: SearchParams): boolean {
  return !params.section && !params.category && !params.tier && !params.source;
}

export default async function FontsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const fonts = await getAllFonts();
  const overview = isOverviewMode(params);

  if (overview) {
    return (
      <main className={styles.main}>
        <Suspense fallback={<div />}>
          <SectionedFontsView fonts={fonts} />
        </Suspense>
      </main>
    );
  }

  return (
    <main className={styles.main}>
      <Suspense fallback={<div />}>
        <ClientFontFilters fonts={fonts} />
      </Suspense>
      <Suspense fallback={<div />}>
        <ClientFontsList fonts={fonts} />
      </Suspense>
    </main>
  );
}
