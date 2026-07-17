import type { Metadata } from "next";
import { CompareBoard } from "@/components/CompareBoard";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "폰트 비교 - FontAgit",
  alternates: { canonical: "/compare/" },
};

export default function ComparePage() {
  return (
    <main className={styles.main}>
      <CompareBoard />
    </main>
  );
}
