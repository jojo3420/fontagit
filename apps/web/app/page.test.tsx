import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";
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

const mockTrendsClicksResult: TrendsResult = {
  source: "clicks",
  items: mockTrends,
};

const mockTrendsLatestResult: TrendsResult = {
  source: "latest",
  items: mockTrends,
};

vi.mock("@/lib/data", () => ({
  getTrends: vi.fn(() => Promise.resolve(mockTrendsClicksResult)),
}));

async function renderHome() {
  const ui = await Home();
  render(ui);
}

describe("홈 페이지", () => {
  beforeEach(() => {
    vi.mocked(getTrends).mockResolvedValue(mockTrendsClicksResult);
  });

  it("히어로와 인기 TOP 10 패널을 함께 렌더한다", async () => {
    await renderHome();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("당신의 폰트 아지트");
    expect(screen.getByText("이번 주 인기 TOP 10")).toBeInTheDocument();
  });

  it("source=latest일 때 '최신 등록 TOP 10' 라벨을 표시하고 인기 라벨은 숨긴다", async () => {
    vi.mocked(getTrends).mockResolvedValue(mockTrendsLatestResult);
    await renderHome();
    expect(screen.getByText("최신 등록 TOP 10")).toBeInTheDocument();
    expect(screen.getByText(/클릭 데이터 수집 중/)).toBeInTheDocument();
    expect(screen.queryByText("이번 주 인기 TOP 10")).not.toBeInTheDocument();
    expect(screen.queryByText(/매주 갱신/)).not.toBeInTheDocument();
  });
});
