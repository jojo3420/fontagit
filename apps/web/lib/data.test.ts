import { describe, it, expect } from "vitest";
import { fonts } from "@/data/fonts";
import { collections } from "@/data/collections";

describe("fixture data integrity", () => {
  it("finds a font by slug in fixture", () => {
    expect(fonts.find((f) => f.slug === "pretendard")?.nameKo).toBe("프리텐다드");
    expect(fonts.find((f) => f.slug === "nope")).toBeUndefined();
  });
  it("has at least 10 fonts for TOP 10", () => {
    expect(fonts.length).toBeGreaterThanOrEqual(10);
  });
  it("resolves free alternatives to real free fonts (max 3)", () => {
    const paid = fonts.find((f) => f.slug === "sandoll-gothic-neo")!;
    const alts = paid.freeAlternatives
      ? paid.freeAlternatives
          .map((slug: string) => fonts.find((f) => f.slug === slug))
          .filter((f): f is typeof fonts[number] => f !== undefined && f.tier === "free")
          .slice(0, 3)
      : [];
    expect(alts.length).toBeLessThanOrEqual(3);
    expect(alts.every((f) => f.tier === "free")).toBe(true);
    expect(alts.map((f) => f.slug)).toContain("pretendard");
  });
  it("finds a collection by slug", () => {
    expect(collections.find((c) => c.slug === "dawn-serif")?.title).toBe("새벽 감성 명조 모음");
    expect(collections.find((c) => c.slug === "nope")).toBeUndefined();
  });
  it("lists all collection slugs", () => {
    expect(collections.length).toBeGreaterThanOrEqual(3);
  });
  it("every collection item references a real font", () => {
    for (const col of collections) {
      expect(col.items.length).toBeGreaterThan(0);
      for (const it of col.items) {
        expect(fonts.find((f) => f.slug === it.slug)).toBeDefined();
      }
    }
  });
  it("모든 폰트에 라이선스 필드가 채워져 있다", () => {
    for (const f of fonts) {
      expect(f.license.type.length).toBeGreaterThan(0);
      expect(["included", "separate", "no"]).toContain(f.license.webfont);
      expect(["yes", "no"]).toContain(f.license.redistribution);
    }
  });
  it("유료 폰트 sandoll-gothic-neo는 구매 시/별도 구매/불가 + 가격", () => {
    const p = fonts.find((f) => f.slug === "sandoll-gothic-neo")!;
    expect(p.license.commercial).toBe("conditional");
    expect(p.license.webfont).toBe("separate");
    expect(p.license.redistribution).toBe("no");
    expect(p.priceFrom).toBe(99000);
  });
});
