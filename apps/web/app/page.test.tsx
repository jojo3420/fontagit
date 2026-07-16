import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";
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
  it("히어로와 인기 TOP 10 패널을 함께 렌더한다", async () => {
    await renderHome();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("당신의 폰트 아지트");
    expect(screen.getByText("이번 주 인기 TOP 10")).toBeInTheDocument();
  });
});
