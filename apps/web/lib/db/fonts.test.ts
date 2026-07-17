import { beforeEach, describe, it, expect, vi } from "vitest";
import { filterFreeAlternatives, getPublishedSlugs } from "@/lib/db/fonts";
import { fonts } from "@/data/fonts";
import { supabaseClient } from "./client";

vi.mock("./client", () => ({
  supabaseClient: {
    from: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("getPublishedSlugs", () => {
  it("published 상태의 slug만 조회한다", async () => {
    const eq = vi.fn().mockResolvedValue({
      data: [{ slug: "noto-sans-kr" }],
      error: null,
    });
    const select = vi.fn().mockReturnValue({ eq });
    vi.mocked(supabaseClient.from).mockReturnValue({ select } as never);

    await expect(getPublishedSlugs()).resolves.toEqual(["noto-sans-kr"]);
    expect(supabaseClient.from).toHaveBeenCalledWith("fonts");
    expect(select).toHaveBeenCalledWith("slug");
    expect(eq).toHaveBeenCalledWith("status", "published");
  });
});

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
