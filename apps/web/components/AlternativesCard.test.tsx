import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AlternativesCard } from "@/components/AlternativesCard";
import { getFontBySlug, resolveFreeAlternatives } from "@/lib/data";

describe("AlternativesCard", () => {
  it("대안 개수를 제목에 반영한다", () => {
    const paid = getFontBySlug("sandoll-gothic-neo")!;
    const alts = resolveFreeAlternatives(paid);
    render(<AlternativesCard category="고딕" items={alts} />);
    expect(screen.getByText(`비슷한 무료 대안 ${alts.length}개`)).toBeInTheDocument();
    expect(screen.getByText("분위기가 가까운 무료 고딕입니다")).toBeInTheDocument();
    expect(screen.getAllByText("무료").length).toBe(alts.length);
  });
  it("items가 비면 렌더하지 않는다", () => {
    const { container } = render(<AlternativesCard category="명조" items={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
