import { beforeEach, describe, expect, it, vi } from "vitest";
import { getAllCollectionSlugs } from "@/lib/db/collections";
import { supabaseClient } from "./client";

vi.mock("./client", () => ({
  supabaseClient: {
    from: vi.fn(),
  },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("getAllCollectionSlugs", () => {
  it("1,000개 초과 컬렉션을 exact count와 페이지네이션으로 전량 조회한다", async () => {
    const firstBatch = Array.from({ length: 1000 }, (_, i) => ({ slug: `collection-${i}` }));
    const secondBatch = [{ slug: "collection-1000" }];
    const range = vi
      .fn()
      .mockResolvedValueOnce({ data: firstBatch, error: null, count: 1001 })
      .mockResolvedValueOnce({ data: secondBatch, error: null, count: 1001 });
    const order = vi.fn().mockReturnValue({ range });
    const eq = vi.fn().mockReturnValue({ order });
    const select = vi.fn().mockReturnValue({ eq });
    vi.mocked(supabaseClient.from).mockReturnValue({ select } as never);

    await expect(getAllCollectionSlugs()).resolves.toHaveLength(1001);
    expect(select).toHaveBeenCalledWith("slug", { count: "exact" });
    expect(range).toHaveBeenNthCalledWith(1, 0, 999);
    expect(range).toHaveBeenNthCalledWith(2, 1000, 1999);
  });

  it("exact count와 실제 수집 개수가 다르면 빌드를 중단한다", async () => {
    const range = vi
      .fn()
      .mockResolvedValueOnce({ data: [{ slug: "one" }], error: null, count: 2 })
      .mockResolvedValueOnce({ data: [], error: null, count: 2 });
    const order = vi.fn().mockReturnValue({ range });
    const eq = vi.fn().mockReturnValue({ order });
    const select = vi.fn().mockReturnValue({ eq });
    vi.mocked(supabaseClient.from).mockReturnValue({ select } as never);

    await expect(getAllCollectionSlugs()).rejects.toThrow(/count.*2.*수집.*1/i);
  });
});
