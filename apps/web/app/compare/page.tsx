import { CompareBoard } from "@/components/CompareBoard";
import styles from "./page.module.css";

export const metadata = {
  title: "폰트 비교 - FontAgit",
};

export default function ComparePage() {
  return (
    <main className={styles.main}>
      <CompareBoard />
    </main>
  );
}
