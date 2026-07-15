import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { weeklyTrends } from "@/data/trends";

describe("WeeklyRankPanel", () => {
  it("패널 헤더/힌트/전체 링크를 렌더한다", () => {
    render(<WeeklyRankPanel items={weeklyTrends} />);
    expect(screen.getByText("이번 주 인기 TOP 10")).toBeInTheDocument();
    expect(screen.getByText(/이동 클릭 기준/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /전체/ })).toHaveAttribute("href", "/trends");
  });
  it("전달된 순위 항목 수만큼 렌더한다", () => {
    render(<WeeklyRankPanel items={weeklyTrends} />);
    expect(screen.getAllByText(/이동 .*회/).length).toBe(weeklyTrends.length);
  });
});
