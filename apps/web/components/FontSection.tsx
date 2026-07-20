import Link from "next/link";
import { FontGrid } from "./FontGrid";
import type { Font } from "@/types/font";
import type { SectionDef } from "@/lib/sections";
import styles from "./FontSection.module.css";

/** 한 용도 섹션 덩어리: 섹션 라벨-가이드-폰트 그리드-더보기 링크를 렌더한다. */
export function FontSection({
  section,
  fonts,
  totalCount,
  previewText,
}: {
  section: SectionDef;
  fonts: Font[];
  totalCount: number;
  previewText?: string;
}) {
  return (
    <section className={styles.section}>
      <h2>{section.label}</h2>
      <p>{section.guide}</p>
      <FontGrid fonts={fonts} previewText={previewText} />
      <Link href={`/fonts?section=${section.slug}`}>
        더보기 ({totalCount}종)
      </Link>
    </section>
  );
}
