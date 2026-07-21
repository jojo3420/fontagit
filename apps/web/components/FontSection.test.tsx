import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontSection } from "./FontSection";
import type { Font } from "@/types/font";
import type { SectionDef } from "@/lib/sections";

const section: SectionDef = { slug: "body", label: "본문-긴 글", guide: "가이드", order: 1 };
const font = { slug: "a", nameKo: "가폰트", nameEn: "a", fontKey: null, tier: "free",
  category: "고딕", foundry: "f", availableWeights: [400], moves: 0,
  license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
  officialUrl: "", aliases: [], subsets: ["korean"] } as Font;

describe("FontSection", () => {
  it("라벨-가이드-카드-더보기 링크를 렌더한다", () => {
    render(<FontSection section={section} fonts={[font]} totalCount={20} />);
    expect(screen.getByText("본문-긴 글")).toBeInTheDocument();
    expect(screen.getByText("가이드")).toBeInTheDocument();
    expect(screen.getByText("가폰트")).toBeInTheDocument();
    const more = screen.getByRole("link", { name: /더보기/ });
    expect(more).toHaveAttribute("href", "/fonts?section=body");
  });
});
