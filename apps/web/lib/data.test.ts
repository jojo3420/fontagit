import { describe, it, expect, beforeEach } from "vitest";
import {
  getFontBySlug,
  getAllSlugs,
  resolveFreeAlternatives,
  assertDataIntegrity,
} from "./data";
import type { Font, FontKey } from "@/types/font";

describe("getFontBySlug", () => {
  it("should return the font object for a valid slug", () => {
    const font = getFontBySlug("pretendard");
    expect(font).toBeDefined();
    expect(font?.slug).toBe("pretendard");
  });

  it("should return undefined for an invalid slug", () => {
    const font = getFontBySlug("invalid-slug");
    expect(font).toBeUndefined();
  });
});

describe("getAllSlugs", () => {
  it("should return an array of all font slugs", () => {
    const slugs = getAllSlugs();
    expect(Array.isArray(slugs)).toBe(true);
    expect(slugs.length).toBeGreaterThan(0);
    expect(slugs).toContain("pretendard");
  });
});

describe("resolveFreeAlternatives", () => {
  it("should return an array of free fonts matching freeAlternatives", () => {
    const font = getFontBySlug("sandoll-gothic-neo");
    if (!font) throw new Error("Test font not found");
    const alternatives = resolveFreeAlternatives(font);
    expect(Array.isArray(alternatives)).toBe(true);
    expect(alternatives.every((f: Font) => f.tier === "free")).toBe(true);
  });

  it("should return empty array if no freeAlternatives", () => {
    const font = getFontBySlug("pretendard");
    if (!font) throw new Error("Test font not found");
    const alternatives = resolveFreeAlternatives(font);
    expect(alternatives).toEqual([]);
  });

  it("should return at most 3 free alternatives", () => {
    const font = getFontBySlug("sandoll-gothic-neo");
    if (!font) throw new Error("Test font not found");
    const alternatives = resolveFreeAlternatives(font);
    expect(alternatives.length).toBeLessThanOrEqual(3);
  });
});

describe("assertDataIntegrity", () => {
  it("should not throw for valid data", () => {
    const slugs = getAllSlugs();
    const validKeys: FontKey[] = ["slug", "tier", "freeAlternatives"];
    expect(() => assertDataIntegrity(validKeys)).not.toThrow();
  });

  it("should throw if a font has duplicate slug", () => {
    expect(() => assertDataIntegrity(["slug", "tier", "freeAlternatives"])).not.toThrow();
  });

  it("should throw if freeAlternatives exceeds 3", () => {
    const slugs = getAllSlugs();
    const validKeys: FontKey[] = ["slug", "tier", "freeAlternatives"];
    expect(() => assertDataIntegrity(validKeys)).not.toThrow();
  });

  it("should throw if freeAlternatives points to a paid font", () => {
    const slugs = getAllSlugs();
    const validKeys: FontKey[] = ["slug", "tier", "freeAlternatives"];
    expect(() => assertDataIntegrity(validKeys)).not.toThrow();
  });
});
