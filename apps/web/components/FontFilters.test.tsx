import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontFilters } from "@/components/FontFilters";

describe("FontFilters", () => {
  it("필터 섹션 제목을 렌더한다", () => {
    render(<FontFilters />);
    expect(screen.getByText("분류")).toBeInTheDocument();
    expect(screen.getByText("가격")).toBeInTheDocument();
    expect(screen.getByText("용도")).toBeInTheDocument();
  });
  it("분류/가격 옵션 라벨을 렌더한다", () => {
    render(<FontFilters />);
    for (const label of ["고딕", "명조", "손글씨", "디스플레이", "무료", "유료"]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
  });
});
