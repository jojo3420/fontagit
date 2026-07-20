import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SectionedFontsView } from "./SectionedFontsView";
import type { Font } from "@/types/font";

function f(slug: string, category: Font["category"]): Font {
  return { slug, nameKo: slug, nameEn: slug, fontKey: null, tier: "free", category,
    foundry: "f", availableWeights: [400], moves: 0,
    license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
    officialUrl: "", aliases: [], subsets: ["korean"] } as Font;
}

describe("SectionedFontsView", () => {
  it("캔버스에 입력하면 폰트 카드 견본이 그 문구로 바뀐다", async () => {
    render(<SectionedFontsView fonts={[f("m", "명조")]} />);
    await userEvent.type(screen.getByRole("textbox"), "아지트");
    expect(await screen.findByText("아지트")).toBeInTheDocument();
  });
});
