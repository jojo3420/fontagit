import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { HomeExplorer } from "@/components/HomeExplorer";
import { buildHomePreview } from "@/lib/homeCuration";
import { fonts } from "@/data/fonts";

const preview = buildHomePreview(fonts, [], 4);

describe("HomeExplorer", () => {
  it("기본으로 전체 칩이 활성화되고 폰트 카드가 보인다", () => {
    render(<HomeExplorer preview={preview} />);
    expect(screen.getByRole("button", { name: "전체" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(preview.chips.all[0].nameKo)).toBeInTheDocument();
  });

  it("칩 클릭 시 활성 칩과 그리드가 즉시 바뀐다", () => {
    render(<HomeExplorer preview={preview} />);
    fireEvent.click(screen.getByRole("button", { name: "고딕" }));
    expect(screen.getByRole("button", { name: "고딕" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "전체" })).toHaveAttribute("aria-pressed", "false");
  });

  it("결과 0건 칩은 EmptyState를 보여준다", () => {
    const empty = { ...preview, chips: { ...preview.chips, paid: [] } };
    render(<HomeExplorer preview={empty} />);
    fireEvent.click(screen.getByRole("button", { name: "유료" }));
    expect(screen.getByText("아직 준비 중이에요")).toBeInTheDocument();
  });

  it("전체 보기 링크가 활성 칩의 필터 쿼리를 담는다", () => {
    render(<HomeExplorer preview={preview} />);
    fireEvent.click(screen.getByRole("button", { name: "고딕" }));
    const link = screen.getByRole("link", { name: /전체 보기/ });
    expect(link.getAttribute("href")).toContain("category=");
  });
});
