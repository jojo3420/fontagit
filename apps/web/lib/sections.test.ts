import { describe, it, expect } from "vitest";
import { sectionOf, groupFontsBySection, SECTIONS, orderByCuration } from "./sections";
import type { Font } from "@/types/font";

function makeFont(over: Partial<Font>): Font {
  return {
    slug: "s", nameKo: "이름", nameEn: "name", fontKey: null, tier: "free",
    category: "고딕", foundry: "f", availableWeights: [400], moves: 0,
    license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
    officialUrl: "", aliases: [], subsets: ["korean"], ...over,
  } as Font;
}

describe("sectionOf", () => {
  it("손글씨 → handwriting", () => {
    expect(sectionOf(makeFont({ category: "손글씨" }))).toBe("handwriting");
  });
  it("장식 → decorative", () => {
    expect(sectionOf(makeFont({ category: "장식" }))).toBe("decorative");
  });
  it("명조 → brand", () => {
    expect(sectionOf(makeFont({ category: "명조" }))).toBe("brand");
  });
  it("고딕 + 본문 굵기 포함 → body", () => {
    expect(sectionOf(makeFont({ category: "고딕", availableWeights: [400, 700] }))).toBe("body");
  });
  it("고딕 + 굵은 굵기만(700+) → headline", () => {
    expect(sectionOf(makeFont({ category: "고딕", availableWeights: [700, 900] }))).toBe("headline");
  });
});

describe("groupFontsBySection", () => {
  it("섹션별로 분배하고 빈 섹션은 빈 배열", () => {
    const groups = groupFontsBySection([
      makeFont({ slug: "a", category: "명조" }),
      makeFont({ slug: "b", category: "손글씨" }),
    ]);
    expect(groups.brand.map((f) => f.slug)).toEqual(["a"]);
    expect(groups.handwriting.map((f) => f.slug)).toEqual(["b"]);
    expect(groups.body).toEqual([]);
  });
});

describe("SECTIONS", () => {
  it("5개 섹션이 order 순으로 정의됨", () => {
    expect(SECTIONS.map((s) => s.slug)).toEqual(["body", "headline", "brand", "handwriting", "decorative"]);
    expect(SECTIONS.map((s) => s.order)).toEqual([1, 2, 3, 4, 5]);
  });
});

describe("orderByCuration", () => {
  it("추천 slug가 앞으로 오고 나머지는 원래 순서 유지", () => {
    const fonts = [
      makeFont({ slug: "a" }),
      makeFont({ slug: "b" }),
      makeFont({ slug: "c" }),
    ];
    const recommended = ["c"];
    const result = orderByCuration(fonts, recommended);
    expect(result.map((f) => f.slug)).toEqual(["c", "a", "b"]);
  });

  it("추천 slug가 여러 개일 때 순서대로 앞으로 옴", () => {
    const fonts = [
      makeFont({ slug: "a" }),
      makeFont({ slug: "b" }),
      makeFont({ slug: "c" }),
    ];
    const recommended = ["b", "c"];
    const result = orderByCuration(fonts, recommended);
    expect(result.map((f) => f.slug)).toEqual(["b", "c", "a"]);
  });

  it("추천에 없는 폰트는 원래 순서 유지", () => {
    const fonts = [
      makeFont({ slug: "a" }),
      makeFont({ slug: "b" }),
      makeFont({ slug: "c" }),
    ];
    const recommended = ["d"];
    const result = orderByCuration(fonts, recommended);
    expect(result.map((f) => f.slug)).toEqual(["a", "b", "c"]);
  });
});
