import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Hero } from "@/components/Hero";

describe("Hero", () => {
  it("디자인 1d 문구를 렌더한다", () => {
    render(<Hero />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("당신의 폰트 아지트");
    expect(screen.queryByPlaceholderText("폰트 이름을 검색하세요")).not.toBeInTheDocument();
  });
});
