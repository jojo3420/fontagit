import { describe, it, expect } from "vitest";
import { filterFreeAlternatives } from "@/lib/db/fonts";
import { fonts } from "@/data/fonts";

describe("filterFreeAlternatives", () => {
  it("같은 카테고리의 무료 폰트 최대 3개를 반환한다", () => {
    const paid = fonts.find((f) => f.slug === "sandoll-gothic-neo")!;
    const result = filterFreeAlternatives(paid, fonts);

    expect(result.length).toBeLessThanOrEqual(3);
    expect(result.every((f) => f.category === paid.category)).toBe(true);
    expect(result.every((f) => f.tier === "free")).toBe(true);
    expect(result.every((f) => f.slug !== paid.slug)).toBe(true);
  });

  it("가장 인기많은 순서(moves 높은 순서)로 정렬한다", () => {
    const paid = fonts.find((f) => f.slug === "sandoll-gothic-neo")!;
    const result = filterFreeAlternatives(paid, fonts);

    for (let i = 1; i < result.length; i++) {
      expect(result[i - 1].moves).toBeGreaterThanOrEqual(result[i].moves);
    }
  });

  it("무료 폰트 3개 이상이 있을 때는 3개만 반환한다", () => {
    const paid = fonts.find((f) => f.slug === "sandoll-gothic-neo")!;
    const freeCount = fonts.filter(
      (f) => f.category === paid.category && f.tier === "free"
    ).length;

    if (freeCount > 3) {
      const result = filterFreeAlternatives(paid, fonts);
      expect(result.length).toBe(3);
    }
  });

  it("해당 카테고리에 무료 폰트가 없으면 빈 배열을 반환한다", () => {
    const mockFont = {
      ...fonts[0],
      category: "임의카테고리" as any,
      tier: "paid" as const,
    };
    const result = filterFreeAlternatives(mockFont, fonts);

    expect(result.length).toBe(0);
  });
});
