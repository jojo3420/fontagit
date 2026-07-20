import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { SectionOverview } from "./SectionOverview";
import type { Font } from "@/types/font";

vi.mock("./FontGrid", () => ({
  FontGrid: () => <div data-testid="font-grid">Font Grid</div>,
}));

// FontSection을 mock해서 각 호출이 받은 fonts 배열을 capture한다
const fontSectionCalls: Array<{ fonts: Font[]; sectionSlug: string }> = [];
vi.mock("./FontSection", () => ({
  FontSection: ({
    section,
    fonts,
    totalCount,
  }: {
    section: { slug: string; name: string };
    fonts: Font[];
    totalCount: number;
  }) => {
    fontSectionCalls.push({ fonts, sectionSlug: section.slug });
    return (
      <div
        data-testid={`section-${section.slug}`}
        data-fonts-count={fonts.length}
      >
        {section.name} ({fonts.length}/{totalCount})
      </div>
    );
  },
}));

describe("SectionOverview", () => {
  const mockFonts: Font[] = Array.from({ length: 20 }, (_, i) => ({
    id: String(i + 1),
    name: `Font ${i + 1}`,
    slug: `font-${i + 1}`,
    family: "Test Family",
    designer: "Designer",
    description: "Description",
    license: "OFL",
    source: "Google Fonts",
    fontUrl: "https://example.com/font.ttf",
    previewUrl: "https://example.com/preview.jpg",
    tags: ["test"],
    category: "body",
    section: "body",
    publishedAt: "2024-01-01",
    createdAt: "2024-01-01",
    updatedAt: "2024-01-01",
  }));

  beforeEach(() => {
    fontSectionCalls.length = 0;
  });

  it("should render without crashing", () => {
    render(<SectionOverview fonts={mockFonts} />);
  });

  it("should render view all link", () => {
    render(<SectionOverview fonts={mockFonts} />);
    const viewAllLink = screen.getByText("전체 폰트 보기");
    expect(viewAllLink).toBeInTheDocument();
  });

  it("should limit fonts to topN=12 by default", () => {
    render(<SectionOverview fonts={mockFonts} />);
    // topN 기본값 12가 적용되어야 함
    // 20개 폰트를 가진 body 섹션이 12개만 전달받아야 함
    const bodyCall = fontSectionCalls.find((c) => c.sectionSlug === "body");
    expect(bodyCall).toBeDefined();
    expect(bodyCall?.fonts.length).toBe(12);
  });

  it("should limit fonts with custom topN prop", () => {
    render(<SectionOverview fonts={mockFonts} topN={5} />);
    // topN=5로 지정하면 각 섹션이 최대 5개 폰트 받아야 함
    const bodyCall = fontSectionCalls.find((c) => c.sectionSlug === "body");
    expect(bodyCall).toBeDefined();
    expect(bodyCall?.fonts.length).toBe(5);
  });

  it("should not render empty sections", () => {
    // body 섹션에만 폰트 10개, 다른 섹션에는 0개
    const sparseFonts: Font[] = mockFonts.slice(0, 10);
    render(<SectionOverview fonts={sparseFonts} />);
    // body 섹션만 렌더되어야 함
    expect(screen.getByTestId("section-body")).toBeInTheDocument();
    // display 섹션은 렌더되지 않아야 함 (빈 섹션)
    expect(screen.queryByTestId("section-display")).not.toBeInTheDocument();
  });
});
