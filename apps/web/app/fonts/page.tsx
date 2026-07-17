import { Suspense } from "react";
import { getAllFonts } from "@/lib/data";
import { ClientFontFilters } from "@/components/ClientFontFilters";
import { ClientFontsList } from "@/components/ClientFontsList";
import styles from "./page.module.css";

export default async function FontsPage() {
  const fonts = await getAllFonts();

  return (
    <main className={styles.main}>
      <Suspense fallback={<div />}>
        <ClientFontFilters />
      </Suspense>
      <Suspense fallback={<div />}>
        <ClientFontsList fonts={fonts} />
      </Suspense>
    </main>
  );
}
