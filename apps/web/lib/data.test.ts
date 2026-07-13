import { describe, it, expect } from "vitest";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives, assertDataIntegrity } from "@/lib/data";
import type { FontKey } from "@/types/font";

const KEYS: FontKey[] = ["pretendard", "blackHanSans", "jua", "doHyeon", "gowunBatang", "nanumMyeongjo", "kirangHaerang", "gaegu", "songMyung"];

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
    expect(() => assertDataIntegrity(KEYS)).not.toThrow();
  });
});
