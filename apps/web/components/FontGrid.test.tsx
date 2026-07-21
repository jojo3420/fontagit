import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontGrid } from "@/components/FontGrid";
import type { Font } from "@/types/font";

vi.mock("./FontCard", () => ({
  FontCard: ({
    font,
    previewText,
  }: {
    font: Font;
    previewText?: string;
  }) => (
    <div data-testid={`font-card-${font.slug}`} data-preview-text={previewText || ""}>
      {font.nameKo}
    </div>
  ),
}));

const mockFont: Font = {
  slug: "a",
  nameKo: "가폰트",
  nameEn: "a",
  fontKey: null,
  tier: "free",
  category: "고딕",
  foundry: "f",
  availableWeights: [400],
  moves: 0,
  license: {
    commercial: "yes",
    verifiedAt: "",
    type: "",
    webfont: "included",
    redistribution: "yes",
  },
  officialUrl: "",
  aliases: [],
  subsets: ["korean"],
} as Font;

describe("FontGrid", () => {
  it("폰트 목록을 렌더한다", () => {
    render(<FontGrid fonts={[mockFont]} />);
    expect(screen.getByText("가폰트")).toBeInTheDocument();
  });

  it("previewText를 FontCard로 전파한다", () => {
    const customText = "커스텀 문구";
    render(<FontGrid fonts={[mockFont]} previewText={customText} />);
    const fontCard = screen.getByTestId("font-card-a");
    expect(fontCard).toHaveAttribute("data-preview-text", customText);
  });

  it("previewText가 없으면 빈 값으로 전파한다", () => {
    render(<FontGrid fonts={[mockFont]} />);
    const fontCard = screen.getByTestId("font-card-a");
    expect(fontCard).toHaveAttribute("data-preview-text", "");
  });

  it("여러 폰트가 모두 같은 previewText를 받는다", () => {
    const fonts = [
      { ...mockFont, slug: "a1", nameKo: "폰트1" },
      { ...mockFont, slug: "a2", nameKo: "폰트2" },
    ];
    const customText = "공통 문구";
    render(<FontGrid fonts={fonts} previewText={customText} />);
    expect(screen.getByTestId("font-card-a1")).toHaveAttribute(
      "data-preview-text",
      customText
    );
    expect(screen.getByTestId("font-card-a2")).toHaveAttribute(
      "data-preview-text",
      customText
    );
  });
});
