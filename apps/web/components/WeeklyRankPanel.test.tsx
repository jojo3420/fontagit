import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import type { TrendItem } from "@/types/font";

const mockItems: TrendItem[] = [
  {
    rank: 1,
    change: "new",
    font: {
      slug: "noto-sans",
      nameKo: "Noto Sans",
      fontKey: "noto-sans",
      tier: "free",
    },
    moves: 150,
    changeAmount: 0,
  },
  {
    rank: 2,
    change: "new",
    font: {
      slug: "pretendard",
      nameKo: "Pretendard",
      fontKey: "pretendard",
      tier: "free",
    },
    moves: 120,
    changeAmount: 0,
  },
];

describe("WeeklyRankPanel", () => {
  it("source=clicks일 때 '이번 주 인기' 라벨을 표시한다", () => {
    render(<WeeklyRankPanel items={mockItems} source="clicks" />);
    expect(screen.getByText("이번 주 인기 TOP 10")).toBeInTheDocument();
    expect(screen.getByText(/이동 클릭 기준/)).toBeInTheDocument();
  });

  it("source=latest일 때 '최신 등록' 라벨을 표시한다", () => {
    render(<WeeklyRankPanel items={mockItems} source="latest" />);
    expect(screen.getByText("최신 등록 TOP 10")).toBeInTheDocument();
    expect(screen.queryByText(/이동 클릭 기준/)).not.toBeInTheDocument();
  });

  it("전체 링크를 렌더한다", () => {
    render(<WeeklyRankPanel items={mockItems} source="clicks" />);
    expect(screen.getByRole("link", { name: /전체/ })).toHaveAttribute("href", "/trends");
  });

  it("source=clicks일 때 이동수를 표시한다", () => {
    render(<WeeklyRankPanel items={mockItems} source="clicks" />);
    expect(screen.getByText(/150회/)).toBeInTheDocument();
  });

  it("source=latest일 때 이동수를 숨긴다", () => {
    render(<WeeklyRankPanel items={mockItems} source="latest" />);
    expect(screen.queryByText(/150회/)).not.toBeInTheDocument();
  });
});
