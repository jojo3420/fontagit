import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";
import { getTrends, getAllCollections } from "@/lib/data";
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
  getAllFonts: vi.fn(() => Promise.resolve(fonts)),
  getAllCollections: vi.fn(() =>
    Promise.resolve([
      {
        slug: "dawn-serif",
        title: "새벽 감성 명조 모음",
        intro: "고요한 새벽에 어울리는 명조",
        items: [],
      },
    ])
  ),
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

  it("즉시 필터 칩과 미리보기 그리드를 렌더한다", async () => {
    await renderHome();
    expect(screen.getByRole("button", { name: "전체" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "손글씨" })).toBeInTheDocument();
  });

  it("추천 컬렉션 스트립을 렌더한다", async () => {
    await renderHome();
    expect(screen.getByText("추천 컬렉션")).toBeInTheDocument();
    expect(screen.getByText("새벽 감성 명조 모음")).toBeInTheDocument();
  });

  it("컬렉션이 0개여도 collections-heading 제목은 유지된다 (a11y: aria-labelledby 대상 보존)", async () => {
    vi.mocked(getAllCollections).mockResolvedValueOnce([]);
    await renderHome();
    const heading = screen.getByText("추천 컬렉션");
    expect(heading).toHaveAttribute("id", "collections-heading");
  });
});
