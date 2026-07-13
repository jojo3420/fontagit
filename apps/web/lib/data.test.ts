import { describe, it, expect } from "vitest";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives, assertDataIntegrity, FONT_KEYS, getCollectionBySlug, getAllCollectionSlugs } from "@/lib/data";

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
