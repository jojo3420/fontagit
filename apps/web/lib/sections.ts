import type { Font, Category } from "@/types/font";

/** /fonts 용도 섹션 slug */
export type SectionSlug = "body" | "headline" | "brand" | "handwriting" | "decorative";

/** 섹션 정의: slug/라벨/가이드 문구/표시 순서 */
export interface SectionDef {
  slug: SectionSlug;
  label: string;
  guide: string;
  order: number;
}

/** /fonts 용도 섹션 정의(표시 순서 order). */
export const SECTIONS: SectionDef[] = [
  {
    slug: "body",
    label: "본문-긴 글",
    guide: "단편, 뉴스레터, 긴 문단용 가독성 최우선",
    order: 1,
  },
  {
    slug: "headline",
    label: "제목-강조",
    guide: "헤더, 강조 텍스트용 한눈에 띄는 디자인",
    order: 2,
  },
  {
    slug: "brand",
    label: "명조",
    guide: "고급스럽고 전통적인 인상의 명조체",
    order: 3,
  },
  {
    slug: "handwriting",
    label: "손글씨",
    guide: "친근하고 따뜻한 손글씨 스타일",
    order: 4,
  },
  {
    slug: "decorative",
    label: "장식",
    guide: "특별한 상황과 눈에 띄는 장식용",
    order: 5,
  },
];

/** 폰트를 대표 용도 섹션 하나로 매핑한다(자동 매핑). 큐레이션은 별도 오버레이. */
export function sectionOf(font: Pick<Font, "category" | "availableWeights">): SectionSlug {
  const { category, availableWeights } = font;

  if (category === "손글씨") return "handwriting";
  if (category === "장식") return "decorative";
  if (category === "명조") return "brand";

  if (category === "고딕") {
    const hasLightWeight = availableWeights.some((w) => w < 700);
    if (hasLightWeight) return "body";
    return "headline";
  }

  return "body";
}

/** 폰트 목록을 섹션별로 그룹핑한다. 빈 섹션은 빈 배열. */
export function groupFontsBySection(fonts: Font[]): Record<SectionSlug, Font[]> {
  const groups: Record<SectionSlug, Font[]> = {
    body: [],
    headline: [],
    brand: [],
    handwriting: [],
    decorative: [],
  };

  for (const font of fonts) {
    const section = sectionOf(font);
    groups[section].push(font);
  }

  return groups;
}
