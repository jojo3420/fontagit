import { describe, it, expect, vi } from "vitest";
import { filterFreeAlternatives } from "@/lib/db/fonts";
import { fonts } from "@/data/fonts";

vi.mock("./client", () => ({
  supabaseClient: {
    from: vi.fn(),
  },
}));

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

  it("비교할 무료 폰트가 없으면 빈 배열을 반환한다", () => {
    const paid = { ...fonts[0], tier: "paid" as const };
    const result = filterFreeAlternatives(paid, []);

    expect(result).toEqual([]);
  });
});
