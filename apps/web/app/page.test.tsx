import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

describe("홈 페이지", () => {
  it("히어로와 인기 TOP 10 패널을 함께 렌더한다", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("당신의 폰트 아지트");
    expect(screen.getByText("이번 주 인기 TOP 10")).toBeInTheDocument();
  });
});
