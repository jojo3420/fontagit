import { describe, it, expect } from "vitest";
import { SECTION_CURATION } from "./sectionCuration";
import { SECTIONS, sectionOf } from "@/lib/sections";
import { fonts } from "./fonts";

describe("SECTION_CURATION", () => {
  it("모든 섹션 slug를 key로 가진다", () => {
    for (const section of SECTIONS) {
      expect(SECTION_CURATION[section.slug]).toBeDefined();
      expect(Array.isArray(SECTION_CURATION[section.slug])).toBe(true);
    }
  });

  it("추천 slug에 중복이 없다", () => {
    const all = Object.values(SECTION_CURATION).flat();
    expect(new Set(all).size).toBe(all.length);
  });

  it("추천 slug는 정적 폰트 데이터에 실존한다", () => {
    const fontSlugs = new Set(fonts.map((f) => f.slug));
    for (const slug of Object.values(SECTION_CURATION).flat()) {
      expect(fontSlugs.has(slug)).toBe(true);
    }
  });

  it("추천 slug의 sectionOf 결과가 자신이 속한 섹션과 일치한다", () => {
    for (const [sectionSlug, recommendedSlugs] of Object.entries(SECTION_CURATION)) {
      for (const fontSlug of recommendedSlugs) {
        const font = fonts.find((f) => f.slug === fontSlug);
        expect(font).toBeDefined();
        if (font) {
          const fontSection = sectionOf(font);
          expect(fontSection).toBe(sectionSlug);
        }
      }
    }
  });
});
