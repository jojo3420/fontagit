import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PairingPresets } from "@/components/PairingPresets";
import { PAIRINGS } from "@/data/pairings";
import { fonts } from "@/data/fonts";

describe("PAIRINGS 데이터 무결성", () => {
  // PairingPresets는 slug가 어긋나면 카드를 조용히 숨기므로(런타임 예외 없이),
  // 데이터 오타는 이 테스트로만 잡힌다.
  const freeSlugs = new Set(fonts.filter((f) => f.tier === "free").map((f) => f.slug));

  it.each(PAIRINGS)("$id의 heroSlug/bodySlug가 무료 폰트 목록에 실재한다", (p) => {
    expect(freeSlugs.has(p.heroSlug)).toBe(true);
    expect(freeSlugs.has(p.bodySlug)).toBe(true);
  });
});

describe("PairingPresets", () => {
  it("페어링 3세트를 렌더한다", () => {
    render(<PairingPresets onSelect={vi.fn()} />);
    expect(screen.getAllByRole("button")).toHaveLength(3);
  });

  it("클릭 시 onSelect가 대표+본문 조합으로 호출된다", () => {
    const onSelect = vi.fn();
    render(<PairingPresets onSelect={onSelect} />);
    fireEvent.click(screen.getAllByRole("button")[0]);
    expect(onSelect).toHaveBeenCalledWith({
      heroSlug: "black-han-sans",
      gridSlugs: ["pretendard"],
    });
  });
});
