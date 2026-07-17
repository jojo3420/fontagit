import { describe, expect, it } from "vitest";
import type { Font } from "@/types/font";
import {
  buildFilterQuery,
  filterFonts,
  parseFilterQuery,
  sortFonts,
} from "./filters";

const mockFont = (overrides: Partial<Font> = {}): Font => ({
  slug: "test-font",
  nameKo: "테스트",
  nameEn: "Test",
  fontKey: null,
  tier: "free",
  category: "고딕",
  foundry: "Test Foundry",
  availableWeights: [400],
  moves: 100,
  license: {
    commercial: "yes",
    verifiedAt: "2026-01-01",
    type: "OFL",
    webfont: "included",
    redistribution: "yes",
  },
  officialUrl: "https://example.com",
  aliases: [],
  status: "published",
  ...overrides,
});

describe("filterFonts", () => {
  it("선택한 분류와 가격을 모두 만족하는 폰트만 반환한다", () => {
    const fonts = [
      mockFont({ category: "장식", tier: "free" }),
      mockFont({ category: "장식", tier: "paid" }),
      mockFont({ category: "고딕", tier: "free" }),
    ];

    const result = filterFonts(fonts, new Set(["장식"]), new Set(["free"]));

    expect(result).toEqual([fonts[0]]);
  });

  it("같은 종류의 여러 선택은 OR 조건으로 처리한다", () => {
    const fonts = [mockFont({ category: "고딕" }), mockFont({ category: "명조" })];

    expect(filterFonts(fonts, new Set(["고딕", "명조"]), new Set())).toEqual(fonts);
  });

  it("선택이 없으면 전체 폰트를 반환한다", () => {
    const fonts = [mockFont(), mockFont({ category: "명조" })];

    expect(filterFonts(fonts, new Set(), new Set())).toEqual(fonts);
  });
});

describe("sortFonts", () => {
  it("실제 이동 수가 있으면 인기순으로 정렬한다", () => {
    const fonts = [mockFont({ moves: 50 }), mockFont({ moves: 200 })];

    expect(sortFonts(fonts, "popular").map((font) => font.moves)).toEqual([200, 50]);
  });

  it("최신순은 DB가 내려준 등록일 순서를 유지한다", () => {
    const fonts = [
      mockFont({ slug: "new", license: { ...mockFont().license, verifiedAt: "2020-01-01" } }),
      mockFont({ slug: "old", license: { ...mockFont().license, verifiedAt: "2030-01-01" } }),
    ];

    expect(sortFonts(fonts, "recent").map((font) => font.slug)).toEqual(["new", "old"]);
  });
});

describe("parseFilterQuery", () => {
  it("분류, 가격, 정렬 조건을 함께 읽는다", () => {
    const result = parseFilterQuery(
      new URLSearchParams("category=장식,명조&tier=free&sort=recent"),
    );

    expect(result.categories).toEqual(new Set(["장식", "명조"]));
    expect(result.tiers).toEqual(new Set(["free"]));
    expect(result.sort).toBe("recent");
  });

  it("알 수 없는 정렬값은 최신순으로 되돌린다", () => {
    expect(parseFilterQuery(new URLSearchParams("sort=broken")).sort).toBe("recent");
  });

  it("정렬값이 없으면 최신순을 사용한다", () => {
    expect(parseFilterQuery(new URLSearchParams()).sort).toBe("recent");
  });
});

describe("buildFilterQuery", () => {
  it("선택된 조건만 URL 쿼리로 만든다", () => {
    const query = buildFilterQuery(new Set(["장식"]), new Set(["free"]), "recent");
    const params = new URLSearchParams(query);

    expect(params.get("category")).toBe("장식");
    expect(params.get("tier")).toBe("free");
    expect(params.get("sort")).toBe("recent");
  });

  it("빈 필터는 URL에 넣지 않는다", () => {
    const query = buildFilterQuery(new Set(), new Set(), "recent");

    expect(query).toBe("sort=recent");
  });
});
