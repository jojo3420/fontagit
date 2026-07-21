import { Metadata } from "next";
import { PlaygroundCanvas } from "@/components/PlaygroundCanvas";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "타입 캔버스 - FontAgit",
  alternates: { canonical: "/playground/" },
};

export default function PlaygroundPage() {
  return (
    <main className={styles.main}>
      <PlaygroundCanvas />
    </main>
  );
}
