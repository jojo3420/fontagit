import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { fonts } from "@/data/fonts";

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(() => new URLSearchParams()),
  useRouter: vi.fn(() => ({
    push: vi.fn(),
  })),
}));

vi.mock("@/lib/sections", () => ({
  sectionOf: vi.fn((font) => {
    // 간단한 mock: category 기반
    if (font.category === "고딕") return "body";
    if (font.category === "장식") return "decorative";
    return "other";
  }),
}));

import { ClientFontsList } from "./ClientFontsList";
import { useSearchParams } from "next/navigation";
import { sectionOf } from "@/lib/sections";

describe("ClientFontsList 섹션 필터", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("?section이 없으면 모든 폰트를 렌더한다", () => {
    (useSearchParams as any).mockReturnValue(new URLSearchParams());
    render(<ClientFontsList fonts={fonts} />);

    const count = fonts.length;
    expect(screen.getByText(`폰트 ${count}종`)).toBeInTheDocument();
  });

  it("?section=body면 body 섹션 폰트만 필터링한다", () => {
    const params = new URLSearchParams();
    params.set("section", "body");
    (useSearchParams as any).mockReturnValue(params);

    const bodyFonts = fonts.filter((font) => sectionOf(font) === "body");
    const expectedCount = bodyFonts.length;

    render(<ClientFontsList fonts={fonts} />);
    expect(screen.getByText(`폰트 ${expectedCount}종`)).toBeInTheDocument();
  });

  it("?section=decorative면 decorative 섹션 폰트만 필터링한다", () => {
    const params = new URLSearchParams();
    params.set("section", "decorative");
    (useSearchParams as any).mockReturnValue(params);

    const decorativeFonts = fonts.filter(
      (font) => sectionOf(font) === "decorative"
    );
    const expectedCount = decorativeFonts.length;

    render(<ClientFontsList fonts={fonts} />);
    expect(screen.getByText(`폰트 ${expectedCount}종`)).toBeInTheDocument();
  });

  it("?section=all이면 섹션 필터를 무시하고 모든 폰트를 렌더한다", () => {
    const params = new URLSearchParams();
    params.set("section", "all");
    (useSearchParams as any).mockReturnValue(params);

    render(<ClientFontsList fonts={fonts} />);
    expect(screen.getByText(`폰트 ${fonts.length}종`)).toBeInTheDocument();
  });

  it("섹션 필터와 카테고리 필터를 함께 적용한다", () => {
    const params = new URLSearchParams();
    params.set("section", "body");
    params.set("category", "고딕");
    (useSearchParams as any).mockReturnValue(params);

    const filtered = fonts.filter(
      (font) => sectionOf(font) === "body" && font.category === "고딕"
    );
    const expectedCount = filtered.length;

    render(<ClientFontsList fonts={fonts} />);
    expect(screen.getByText(`폰트 ${expectedCount}종`)).toBeInTheDocument();
  });
});
