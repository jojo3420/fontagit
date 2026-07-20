import Link from "next/link";
import { SECTIONS, groupFontsBySection } from "@/lib/sections";
import type { Font } from "@/types/font";
import { FontSection } from "./FontSection";
import styles from "./SectionOverview.module.css";

/**
 * 섹션 개요: 모든 용도 섹션별로 대표 폰트를 계층화하여 렌더한다.
 * 각 섹션별로 topN개의 폰트를 표시하고, 더보기 링크로 전체를 연결한다.
 *
 * @param fonts - 폰트 목록
 * @param topN - 각 섹션당 표시할 폰트 개수 (기본값: 6)
 * @returns JSX.Element
 */
export function SectionOverview({
  fonts,
  topN = 6,
}: {
  fonts: Font[];
  topN?: number;
}): JSX.Element {
  const groups = groupFontsBySection(fonts);

  return (
    <div className={styles.overview}>
      <div className={styles.top}>
        <Link href="/fonts?section=all" className={styles.viewAll}>
          전체 폰트 보기
        </Link>
      </div>
      {SECTIONS.map((section) => {
        const all = groups[section.slug];
        return (
          <FontSection
            key={section.slug}
            section={section}
            fonts={all.slice(0, topN)}
            totalCount={all.length}
          />
        );
      })}
    </div>
  );
}
