import { beforeEach, describe, it, expect, vi } from "vitest";
import { filterFreeAlternatives, getPublishedSlugs, getAllFonts } from "@/lib/db/fonts";
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

describe("getAllFonts", () => {
  it("1,000종을 넘는 폰트를 페이지네이션으로 전량 조회한다", async () => {
    // 첫 번째 배치: 1,000개
    const firstBatch = Array.from({ length: 1000 }, (_, i) => ({
      id: `id-${i}`,
      slug: `font-${i}`,
      name: `Font ${i}`,
      category: "serif" as const,
      tier: "free" as const,
      status: "published" as const,
      created_at: new Date().toISOString(),
      moves: 0,
    }));

    // 두 번째 배치: 1개
    const secondBatch = [
      {
        id: "id-1000",
        slug: "font-1000",
        name: "Font 1000",
        category: "serif" as const,
        tier: "free" as const,
        status: "published" as const,
        created_at: new Date().toISOString(),
        moves: 0,
      },
    ];

    let rangeCallCount = 0;
    const range = vi.fn().mockImplementation(() => {
      rangeCallCount++;
      if (rangeCallCount === 1) {
        return Promise.resolve({ data: firstBatch, error: null });
      } else {
        return Promise.resolve({ data: secondBatch, error: null });
      }
    });

    const order2 = vi.fn().mockReturnValue({ range });
    const order1 = vi.fn().mockReturnValue({ order: order2 });
    const eq = vi.fn().mockReturnValue({ order: order1 });
    const select = vi.fn().mockReturnValue({ eq });

    const inChain = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });
    const aliasSelect = vi.fn().mockReturnValue({ in: inChain });

    vi.mocked(supabaseClient.from).mockImplementation((table: string) => {
      if (table === "fonts") {
        return { select } as never;
      } else if (table === "aliases") {
        return { select: aliasSelect } as never;
      }
      return {} as never;
    });

    const result = await getAllFonts();

    expect(result).toHaveLength(1001);
  });

  it("결과가 없으면 빈 배열을 반환한다", async () => {
    const range = vi.fn().mockResolvedValue({
      data: [],
      error: null,
    });

    const order2 = vi.fn().mockReturnValue({ range });
    const order1 = vi.fn().mockReturnValue({ order: order2 });
    const eq = vi.fn().mockReturnValue({ order: order1 });
    const select = vi.fn().mockReturnValue({ eq });

    vi.mocked(supabaseClient.from).mockReturnValue({ select } as never);

    const result = await getAllFonts();

    expect(result).toEqual([]);
  });
});
