import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TrendsPage from "@/app/trends/page";
import { weeklyTrends } from "@/data/trends";

describe("트렌드 페이지", () => {
  it("H1/설명/주간-월간 탭을 렌더한다", () => {
    render(<TrendsPage />);
    expect(screen.getByRole("heading", { name: "이번 주 인기 폰트" })).toBeInTheDocument();
    expect(screen.getByText(/이동 클릭 기준 인기 순위입니다/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "주간" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "월간" })).toBeInTheDocument();
  });
  it("주간 순위 전체(10행)를 렌더한다", () => {
    render(<TrendsPage />);
    const links = screen.getAllByRole("link");
    // 순위 카드 링크 = weeklyTrends 길이
    expect(links.length).toBe(weeklyTrends.length);
  });
});
