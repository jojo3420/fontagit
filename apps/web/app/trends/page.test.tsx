import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import TrendsPage from "@/app/trends/page";
import { getTrends } from "@/lib/data";
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
  beforeEach(() => {
    vi.mocked(getTrends).mockResolvedValue(mockTrendsResult);
  });

  it("source=clicks일 때 H1/설명/주간-월간 탭을 렌더한다", async () => {
    await renderTrendsPage();
    expect(screen.getByRole("heading", { name: "이번 주 인기 폰트" })).toBeInTheDocument();
    expect(screen.getByText(/이동 클릭 기준 인기 순위입니다/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "주간" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "월간" })).toBeInTheDocument();
  });

  it("source=latest일 때 '최신 등록 폰트' 라벨과 설명을 표시한다", async () => {
    vi.mocked(getTrends).mockResolvedValue({
      source: "latest",
      items: mockTrends,
    });
    await renderTrendsPage();
    expect(screen.getByRole("heading", { name: "최신 등록 폰트" })).toBeInTheDocument();
    expect(screen.getByText(/클릭 데이터가 쌓이면 이동 클릭 기준 인기 순위로 전환됩니다/)).toBeInTheDocument();
    expect(screen.queryByText(/이번 주 인기 폰트/)).not.toBeInTheDocument();
    expect(screen.queryByText(/이동 클릭 기준 인기 순위입니다/)).not.toBeInTheDocument();
  });

  it("주간 순위 전체(10행)를 렌더한다", async () => {
    await renderTrendsPage();
    const links = screen.getAllByRole("link");
    // 순위 카드 링크 = mockTrends 길이
    expect(links.length).toBe(mockTrends.length);
  });
});
