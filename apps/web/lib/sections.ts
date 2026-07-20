import type { Font, Category } from "@/types/font";

export type SectionSlug = "body" | "headline" | "brand" | "handwriting" | "decorative";

export interface SectionDef {
  slug: SectionSlug;
  label: string;
  guide: string;
  order: number;
}

export const SECTIONS: SectionDef[] = [
  {
    slug: "body",
    label: "본문-긴 글",
    guide: "단편, 뉴스레터, 긴 문단용 가독성 최우선",
    order: 0,
  },
  {
    slug: "headline",
    label: "제목-강조",
    guide: "헤더, 강조 텍스트용 한눈에 띄는 디자인",
    order: 1,
  },
  {
    slug: "brand",
    label: "명조",
    guide: "고급스럽고 전통적인 인상의 명조체",
    order: 2,
  },
  {
    slug: "handwriting",
    label: "손글씨",
    guide: "친근하고 따뜻한 손글씨 스타일",
    order: 3,
  },
  {
    slug: "decorative",
    label: "장식",
    guide: "특별한 상황과 눈에 띄는 장식용",
    order: 4,
  },
];

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
