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
    const range = vi.fn().mockResolvedValue({
      data: [{ slug: "noto-sans-kr" }],
      error: null,
      count: 1,
    });
    const order = vi.fn().mockReturnValue({ range });
    const eq = vi.fn().mockReturnValue({ order });
    const select = vi.fn().mockReturnValue({ eq });
    vi.mocked(supabaseClient.from).mockReturnValue({ select } as never);

    await expect(getPublishedSlugs()).resolves.toEqual(["noto-sans-kr"]);
    expect(supabaseClient.from).toHaveBeenCalledWith("fonts");
    expect(select).toHaveBeenCalledWith("slug", { count: "exact" });
    expect(eq).toHaveBeenCalledWith("status", "published");
    expect(order).toHaveBeenCalledWith("slug");
    expect(range).toHaveBeenCalledWith(0, 999);
  });

  it("1000개 초과 폰트는 페이지네이션으로 전량 조회한다", async () => {
    const firstBatch = Array.from({ length: 1000 }, (_, i) => ({
      slug: `font-${String(i).padStart(4, "0")}`,
    }));
    const secondBatch = [{ slug: "font-1000" }];

    const range = vi
      .fn()
      .mockResolvedValueOnce({ data: firstBatch, error: null, count: 1001 })
      .mockResolvedValueOnce({ data: secondBatch, error: null, count: 1001 });
    const order = vi.fn().mockReturnValue({ range });
    const eq = vi.fn().mockReturnValue({ order });
    const select = vi.fn().mockReturnValue({ eq });
    vi.mocked(supabaseClient.from).mockReturnValue({ select } as never);

    const result = await getPublishedSlugs();

    expect(result).toHaveLength(1001);
    expect(result).toContain("font-1000");
    expect(range).toHaveBeenCalledTimes(2);
    expect(range).toHaveBeenNthCalledWith(1, 0, 999);
    expect(range).toHaveBeenNthCalledWith(2, 1000, 1999);
  });

  it("exact count와 실제 수집 개수가 다르면 빌드를 중단한다", async () => {
    const range = vi
      .fn()
      .mockResolvedValueOnce({ data: [{ slug: "font-0000" }], error: null, count: 2 })
      .mockResolvedValueOnce({ data: [], error: null, count: 2 });
    const order = vi.fn().mockReturnValue({ range });
    const eq = vi.fn().mockReturnValue({ order });
    const select = vi.fn().mockReturnValue({ eq });
    vi.mocked(supabaseClient.from).mockReturnValue({ select } as never);

    await expect(getPublishedSlugs()).rejects.toThrow(/count.*2.*수집.*1/i);
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
