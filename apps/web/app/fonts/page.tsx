import type { Metadata } from "next";
import { Suspense } from "react";
import { getAllFonts } from "@/lib/data";
import { ClientFontFilters } from "@/components/ClientFontFilters";
import { FontsViewWrapper } from "@/components/FontsViewWrapper";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "폰트 찾기 - FontAgit",
  alternates: { canonical: "/fonts/" },
};

export default async function FontsPage() {
  const fonts = await getAllFonts();

  return (
    <main className={styles.main}>
      <Suspense fallback={<div />}>
        <ClientFontFilters fonts={fonts} />
      </Suspense>
      <Suspense fallback={<div />}>
        <FontsViewWrapper fonts={fonts} />
      </Suspense>
    </main>
  );
}
