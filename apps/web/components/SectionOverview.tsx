import Link from "next/link";
import { useMemo } from "react";
import { SECTIONS, groupFontsBySection, orderByCuration } from "@/lib/sections";
import type { Font } from "@/types/font";
import { SECTION_CURATION } from "@/data/sectionCuration";
import { FontSection } from "./FontSection";
import styles from "./SectionOverview.module.css";

const DEFAULT_TOP_N = 12;

/**
 * 섹션 개요: 모든 용도 섹션별로 대표 폰트를 계층화하여 렌더한다.
 * 각 섹션별로 topN개의 폰트를 표시하고, 더보기 링크로 전체를 연결한다.
 *
 * @param fonts - 폰트 목록
 * @param topN - 각 섹션당 표시할 폰트 개수 (기본값: 12)
 * @param previewText - 모든 폰트 카드에 표시할 견본 문구
 */
export function SectionOverview({
  fonts,
  topN = DEFAULT_TOP_N,
  previewText,
}: {
  fonts: Font[];
  topN?: number;
  previewText?: string;
}) {
  const sectionFonts = useMemo(() => {
    const groups = groupFontsBySection(fonts);
    return SECTIONS.map((section) => {
      const sectionFontList = groups[section.slug];
      const all = orderByCuration(sectionFontList, SECTION_CURATION[section.slug]);
      return { section, all };
    }).filter(({ all }) => all.length > 0);
  }, [fonts]);

  return (
    <div className={styles.overview}>
      <div className={styles.top}>
        <Link href="/fonts?section=all" className={styles.viewAll}>
          전체 폰트 보기
        </Link>
      </div>
      {sectionFonts.map(({ section, all }) => (
        <FontSection
          key={section.slug}
          section={section}
          fonts={all.slice(0, topN)}
          totalCount={all.length}
          previewText={previewText}
        />
      ))}
    </div>
  );
}
