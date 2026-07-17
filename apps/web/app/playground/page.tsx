import { Metadata } from "next";
import { PlaygroundCanvas } from "@/components/PlaygroundCanvas";
import { GlyphCheckerSection } from "@/components/GlyphCheckerSection";
import { fonts } from "@/data/fonts";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "타입 캔버스 - FontAgit",
};

export default function PlaygroundPage() {
  return (
    <main className={styles.main}>
      <PlaygroundCanvas />
      <GlyphCheckerSection fonts={fonts} />
    </main>
  );
}
