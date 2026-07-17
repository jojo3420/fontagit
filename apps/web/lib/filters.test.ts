import { describe, it, expect } from "vitest";
import {
  filterFonts,
  sortFonts,
  parseFilterQuery,
  buildFilterQuery,
} from "./filters";
import { Font } from "@/types/font";

const mockFont = (overrides: Partial<Font> = {}): Font => ({
  id: "font-1",
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
  freeAlternatives: undefined,
  status: "published",
  ...overrides,
});

describe("filterFonts", () => {
  it("should filter by category", () => {
    const fonts = [
      mockFont({ category: "고딕" }),
      mockFont({ category: "명조" }),
      mockFont({ category: "손글씨" }),
    ];

    const result = filterFonts(fonts, new Set(["고딕"]), new Set(), new Set());
    expect(result).toHaveLength(1);
    expect(result[0].category).toBe("고딕");
  });

  it("should filter by tier", () => {
    const fonts = [
      mockFont({ tier: "free" }),
      mockFont({ tier: "paid" }),
      mockFont({ tier: "free" }),
    ];

    const result = filterFonts(fonts, new Set(), new Set(["paid"]), new Set());
    expect(result).toHaveLength(1);
    expect(result[0].tier).toBe("paid");
  });

  it("should apply multiple filters (AND)", () => {
    const fonts = [
      mockFont({ category: "고딕", tier: "free" }),
      mockFont({ category: "명조", tier: "free" }),
      mockFont({ category: "고딕", tier: "paid" }),
    ];

    const result = filterFonts(
      fonts,
      new Set(["고딕"]),
      new Set(["free"]),
      new Set()
    );
    expect(result).toHaveLength(1);
    expect(result[0].category).toBe("고딕");
    expect(result[0].tier).toBe("free");
  });

  it("should return all fonts when filters are empty", () => {
    const fonts = [
      mockFont({ category: "고딕" }),
      mockFont({ category: "명조" }),
    ];

    const result = filterFonts(fonts, new Set(), new Set(), new Set());
    expect(result).toHaveLength(2);
  });
});

describe("sortFonts", () => {
  it("should sort by popularity (descending moves)", () => {
    const fonts = [
      mockFont({ moves: 50 }),
      mockFont({ moves: 200 }),
      mockFont({ moves: 100 }),
    ];

    const result = sortFonts(fonts, "popular");
    expect(result[0].moves).toBe(200);
    expect(result[1].moves).toBe(100);
    expect(result[2].moves).toBe(50);
  });

  it("should sort by recent (descending verifiedAt)", () => {
    const fonts = [
      mockFont({
        license: { ...mockFont().license, verifiedAt: "2026-01-01" },
      }),
      mockFont({
        license: { ...mockFont().license, verifiedAt: "2026-03-01" },
      }),
      mockFont({
        license: { ...mockFont().license, verifiedAt: "2026-02-01" },
      }),
    ];

    const result = sortFonts(fonts, "recent");
    expect(result[0].license.verifiedAt).toBe("2026-03-01");
    expect(result[1].license.verifiedAt).toBe("2026-02-01");
    expect(result[2].license.verifiedAt).toBe("2026-01-01");
  });
});

describe("parseFilterQuery", () => {
  it("should parse category filter", () => {
    const params = new URLSearchParams("category=고딕,명조");
    const result = parseFilterQuery(params);

    expect(result.categories.has("고딕")).toBe(true);
    expect(result.categories.has("명조")).toBe(true);
    expect(result.categories.size).toBe(2);
  });

  it("should parse tier filter", () => {
    const params = new URLSearchParams("tier=free,paid");
    const result = parseFilterQuery(params);

    expect(result.tiers.has("free")).toBe(true);
    expect(result.tiers.has("paid")).toBe(true);
  });

  it("should parse sort parameter", () => {
    const params = new URLSearchParams("sort=recent");
    const result = parseFilterQuery(params);

    expect(result.sort).toBe("recent");
  });

  it("should default to popular sort", () => {
    const params = new URLSearchParams("");
    const result = parseFilterQuery(params);

    expect(result.sort).toBe("popular");
  });
});

describe("buildFilterQuery", () => {
  it("should build query string from filters", () => {
    const query = buildFilterQuery(
      new Set(["고딕", "명조"]),
      new Set(["free"]),
      new Set(),
      "popular"
    );

    expect(query).toContain("category=");
    expect(query).toContain("tier=free");
    expect(query).toContain("sort=popular");

    const params = new URLSearchParams(query);
    expect(params.get("category")).toBe("고딕,명조");
  });

  it("should omit empty filters", () => {
    const query = buildFilterQuery(new Set(), new Set(), new Set(), "recent");

    expect(query).not.toContain("category");
    expect(query).not.toContain("tier");
    expect(query).toContain("sort=recent");
  });
});
