import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FontsPage from "@/app/fonts/page";
import { fonts } from "@/data/fonts";

describe("폰트 목록 페이지", () => {
  it("필터 섹션과 개수/정렬 툴바를 렌더한다", () => {
    render(<FontsPage />);
    expect(screen.getByText("분류")).toBeInTheDocument();
    expect(screen.getByText(`폰트 ${fonts.length}종`)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "인기순" })).toBeInTheDocument();
  });
});
