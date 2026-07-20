import Link from "next/link";
import { FontGrid } from "./FontGrid";
import type { Font } from "@/types/font";
import type { SectionDef } from "@/lib/sections";
import styles from "./FontSection.module.css";

export function FontSection({
  section,
  fonts,
  totalCount,
}: {
  section: SectionDef;
  fonts: Font[];
  totalCount: number;
}): JSX.Element {
  return (
    <section className={styles.section}>
      <h2>{section.label}</h2>
      <p>{section.guide}</p>
      <FontGrid fonts={fonts} />
      <Link href={`/fonts?section=${section.slug}`}>
        더보기 ({totalCount}종)
      </Link>
    </section>
  );
}
