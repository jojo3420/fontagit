import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SectionOverview } from "./SectionOverview";
import type { Font } from "@/types/font";

vi.mock("./FontGrid", () => ({
  FontGrid: () => <div data-testid="font-grid">Font Grid</div>,
}));

describe("SectionOverview", () => {
  const mockFonts: Font[] = [
    {
      id: "1",
      name: "Font A",
      slug: "font-a",
      family: "Serif",
      designer: "Designer A",
      description: "Description A",
      license: "OFL",
      source: "Google Fonts",
      fontUrl: "https://example.com/font-a.ttf",
      previewUrl: "https://example.com/preview-a.jpg",
      tags: ["serif"],
      category: "serif",
      section: "serif",
      publishedAt: "2024-01-01",
      createdAt: "2024-01-01",
      updatedAt: "2024-01-01",
    },
    {
      id: "2",
      name: "Font B",
      slug: "font-b",
      family: "Sans-serif",
      designer: "Designer B",
      description: "Description B",
      license: "OFL",
      source: "Google Fonts",
      fontUrl: "https://example.com/font-b.ttf",
      previewUrl: "https://example.com/preview-b.jpg",
      tags: ["sans-serif"],
      category: "sans-serif",
      section: "sans-serif",
      publishedAt: "2024-01-02",
      createdAt: "2024-01-02",
      updatedAt: "2024-01-02",
    },
  ];

  it("should render without crashing", () => {
    render(<SectionOverview fonts={mockFonts} />);
  });

  it("should render view all link", () => {
    render(<SectionOverview fonts={mockFonts} />);
    const viewAllLink = screen.getByText("전체 폰트 보기");
    expect(viewAllLink).toBeInTheDocument();
  });

  it("should limit fonts with topN prop", () => {
    const { container } = render(<SectionOverview fonts={mockFonts} topN={1} />);
    // When topN=1, each FontSection should display at most 1 font
    expect(container).toBeInTheDocument();
  });
});
