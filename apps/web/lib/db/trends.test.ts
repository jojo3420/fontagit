import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Font } from "@/types/font";

const rpcMock = vi.fn();
vi.mock("./client", () => ({
  supabaseClient: { rpc: (...args: unknown[]) => rpcMock(...args) },
}));

const getAllFontsMock = vi.fn();
vi.mock("./fonts", () => ({
  getAllFonts: () => getAllFontsMock(),
}));

import { getTrends } from "./trends";

const rpcRow = {
  slug: "noto-sans-kr",
  name_ko: "본고딕",
  name_en: "Noto Sans KR",
  tier: "free",
  clicks: 42,
};

const fallbackFont: Partial<Font> = {
  slug: "latest-font",
  nameKo: "최신폰트",
  fontKey: null,
  tier: "free",
  moves: 0,
};

describe("getTrends", () => {
  beforeEach(() => {
    rpcMock.mockReset();
    getAllFontsMock.mockReset();
  });

  it("클릭 데이터가 있으면 source=clicks로 TrendItem 매핑", async () => {
    rpcMock.mockResolvedValue({ data: [rpcRow], error: null });
    const result = await getTrends();
    expect(result.source).toBe("clicks");
    expect(result.items[0]).toEqual({
      rank: 1,
      change: "new",
      font: { slug: "noto-sans-kr", nameKo: "본고딕", fontKey: null, tier: "free" },
      moves: 42,
    });
    expect(getAllFontsMock).not.toHaveBeenCalled();
  });

  it("name_ko가 null이면 name_en으로 대체", async () => {
    rpcMock.mockResolvedValue({ data: [{ ...rpcRow, name_ko: null }], error: null });
    const result = await getTrends();
    expect(result.items[0].font.nameKo).toBe("Noto Sans KR");
  });

  it("0건이면 source=latest 폴백 (최신 등록 상위 10)", async () => {
    rpcMock.mockResolvedValue({ data: [], error: null });
    getAllFontsMock.mockResolvedValue(
      Array.from({ length: 12 }, (_, i) => ({ ...fallbackFont, slug: `f-${i}` }))
    );
    const result = await getTrends();
    expect(result.source).toBe("latest");
    expect(result.items).toHaveLength(10);
    expect(result.items[0].rank).toBe(1);
  });

  it("RPC 오류면 throw (조용한 폴백 금지 — 빌드 실패로 드러냄)", async () => {
    rpcMock.mockResolvedValue({ data: null, error: { message: "boom" } });
    await expect(getTrends()).rejects.toThrow("TRENDS_RPC_FAILED");
  });

  it("data가 배열이 아니면 throw (null은 오류로 드러냄)", async () => {
    rpcMock.mockResolvedValue({ data: null, error: null });
    await expect(getTrends()).rejects.toThrow("TRENDS_RPC_INVALID_PAYLOAD");
  });
});
