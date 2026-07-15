import { describe, it, expect } from "vitest";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives, assertDataIntegrity, checkIntegrity, FONT_KEYS, getCollectionBySlug, getAllCollectionSlugs, fonts } from "@/lib/data";

describe("data helpers", () => {
  it("finds a font by slug", () => {
    expect(getFontBySlug("pretendard")?.nameKo).toBe("프리텐다드");
    expect(getFontBySlug("nope")).toBeUndefined();
  });
  it("has at least 10 fonts for TOP 10", () => {
    expect(getAllSlugs().length).toBeGreaterThanOrEqual(10);
  });
  it("resolves free alternatives to real free fonts (max 3)", () => {
    const paid = getFontBySlug("sandoll-gothic-neo")!;
    const alts = resolveFreeAlternatives(paid);
    expect(alts.length).toBeLessThanOrEqual(3);
    expect(alts.every((f) => f.tier === "free")).toBe(true);
    expect(alts.map((f) => f.slug)).toContain("pretendard");
  });
  it("passes integrity check", () => {
    expect(() => assertDataIntegrity(FONT_KEYS)).not.toThrow();
  });
  it("finds a collection by slug", () => {
    expect(getCollectionBySlug("dawn-serif")?.title).toBe("새벽 감성 명조 모음");
    expect(getCollectionBySlug("nope")).toBeUndefined();
  });
  it("lists all collection slugs", () => {
    expect(getAllCollectionSlugs().length).toBeGreaterThanOrEqual(3);
  });
  it("every collection item references a real font", () => {
    for (const slug of getAllCollectionSlugs()) {
      const c = getCollectionBySlug(slug)!;
      expect(c.items.length).toBeGreaterThan(0);
      for (const it of c.items) {
        expect(getFontBySlug(it.fontSlug)).toBeDefined();
      }
    }
  });
});
  it("checkIntegrity throws on collection referencing a non-existent font", () => {
    const badCollections = [{ slug: "x", title: "x", intro: "x", items: [{ fontSlug: "nope", comment: "c" }] }];
    expect(() => checkIntegrity(fonts, badCollections, FONT_KEYS)).toThrow();
  });
  it("checkIntegrity throws on duplicate collection slug", () => {
    const badCollections = [
      { slug: "x", title: "x1", intro: "x1", items: [{ fontSlug: "pretendard", comment: "c" }] },
      { slug: "x", title: "x2", intro: "x2", items: [{ fontSlug: "pretendard", comment: "c" }] },
    ];
    expect(() => checkIntegrity(fonts, badCollections, FONT_KEYS)).toThrow();
  });
  it("checkIntegrity throws on empty collection items", () => {
    const badCollections = [{ slug: "x", title: "x", intro: "x", items: [] }];
    expect(() => checkIntegrity(fonts, badCollections, FONT_KEYS)).toThrow();
  });
  it("checkIntegrity throws on duplicate fontSlug within a collection", () => {
    const badCollections = [{ slug: "x", title: "x", intro: "x", items: [{ fontSlug: "pretendard", comment: "c1" }, { fontSlug: "pretendard", comment: "c2" }] }];
    expect(() => checkIntegrity(fonts, badCollections, FONT_KEYS)).toThrow();
  });
  it("checkIntegrity does not throw on valid inputs", () => {
    const goodCollections = [{ slug: "x", title: "x", intro: "x", items: [{ fontSlug: "pretendard", comment: "c" }] }];
    expect(() => checkIntegrity(fonts, goodCollections, FONT_KEYS)).not.toThrow();
  });
  it("sandoll-gothic-neo should have correct license properties", () => {
    const p = getFontBySlug("sandoll-gothic-neo");
    expect(p).toBeDefined();
    expect(p?.license.type).toBe("Proprietary");
    expect(p?.license.redistribution).toBe("no");
    expect(p?.priceFrom).toBe(99000);
  });
  it("pretendard should have SIL OFL license", () => {
    const p = getFontBySlug("pretendard");
    expect(p).toBeDefined();
    expect(p?.license.type).toBe("SIL OFL");
    expect(p?.license.webfont).toBe("included");
    expect(p?.license.redistribution).toBe("yes");
  });
  it("all free fonts should have SIL OFL license", () => {
    const freeFonts = ["pretendard", "black-han-sans", "jua", "do-hyeon", "gowun-batang", "nanum-myeongjo", "kirang-haerang", "gaegu", "song-myung"];
    for (const slug of freeFonts) {
      const font = getFontBySlug(slug);
      expect(font).toBeDefined();
      expect(font?.license.type).toBe("SIL OFL");
      expect(font?.tier).toBe("free");
    }
  });
});
