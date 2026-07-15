import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendRankRow } from "@/components/TrendRankRow";
import { weeklyTrends } from "@/data/trends";

describe("TrendRankRow", () => {
  it("순위/폰트명/클릭수/티어배지/상세링크를 렌더한다", () => {
    const item = weeklyTrends[0]; // 1위 프리텐다드(무료)
    render(<TrendRankRow item={item} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText(item.font.nameKo)).toBeInTheDocument();
    expect(screen.getByText(item.moves.toLocaleString())).toBeInTheDocument();
    expect(screen.getByText("이동")).toBeInTheDocument();
    expect(screen.getByText("무료")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", `/fonts/${item.font.slug}`);
  });
  it("변동 라벨을 렌더한다(up이면 ▲)", () => {
    const item = weeklyTrends[0]; // change up 2
    render(<TrendRankRow item={item} />);
    expect(screen.getByText(/▲/)).toBeInTheDocument();
  });
});
