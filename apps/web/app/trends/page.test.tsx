import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import TrendsPage from "@/app/trends/page";
import { fonts } from "@/data/fonts";
import type { TrendItem } from "@/types/font";
import type { TrendsResult } from "@/lib/data";

const mockTrends: TrendItem[] = fonts.slice(0, 10).map((font, index) => ({
  rank: index + 1,
  change: "new",
  font: {
    slug: font.slug,
    nameKo: font.nameKo,
    fontKey: font.fontKey,
    tier: font.tier,
  },
  moves: font.moves,
}));

const mockTrendsResult: TrendsResult = {
  source: "clicks",
  items: mockTrends,
};

vi.mock("@/lib/data", () => ({
  getTrends: vi.fn(() => Promise.resolve(mockTrendsResult)),
}));

async function renderTrendsPage() {
  const ui = await TrendsPage();
  render(ui);
}

describe("트렌드 페이지", () => {
  it("H1/설명/주간-월간 탭을 렌더한다", async () => {
    await renderTrendsPage();
    expect(screen.getByRole("heading", { name: "이번 주 인기 폰트" })).toBeInTheDocument();
    expect(screen.getByText(/이동 클릭 기준 인기 순위입니다/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "주간" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "월간" })).toBeInTheDocument();
  });
  it("주간 순위 전체(10행)를 렌더한다", async () => {
    await renderTrendsPage();
    const links = screen.getAllByRole("link");
    // 순위 카드 링크 = mockTrends 길이
    expect(links.length).toBe(mockTrends.length);
  });
});
