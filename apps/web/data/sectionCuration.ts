import type { SectionSlug } from "@/lib/sections";

/** 섹션별 에디터 추천 폰트 slug(LLM 큐레이션 + 사람 스팟 검수). sectionOf 결과와 일치해야 상단 노출된다. */
export const SECTION_CURATION: Record<SectionSlug, string[]> = {
  body: ["pretendard", "do-hyeon"],
  headline: [],
  brand: ["nanum-myeongjo", "gowun-batang"],
  handwriting: ["kirang-haerang", "gaegu"],
  decorative: ["jua"],
};
