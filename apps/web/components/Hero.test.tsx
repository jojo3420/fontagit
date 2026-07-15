import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Hero } from "@/components/Hero";

describe("Hero", () => {
  it("디자인 1d 문구를 렌더한다", () => {
    render(<Hero />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("당신의 폰트 아지트");
    expect(screen.getByPlaceholderText("폰트 이름을 검색하세요 (예: 프리텐다드)")).toBeInTheDocument();
  });
  it("카테고리 칩을 순서대로 렌더한다", () => {
    render(<Hero />);
    for (const label of ["한글", "고딕", "명조", "손글씨", "무료", "유료"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });
});
