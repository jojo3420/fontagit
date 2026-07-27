import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import type { Font } from "@/types/font";
import * as specimenPhrases from "@/lib/specimenPhrases";
import { DetailSpecimenPanel } from "./DetailSpecimenPanel";

// Mock dependencies
vi.mock("@/lib/specimenPhrases", () => ({
  pickPhrase: vi.fn(),
  nextPhrase: vi.fn(),
}));

vi.mock("@/lib/fontPreview", () => ({
  resolveDetailFontPreview: vi.fn(() => ({
    stylesheetUrl: null,
    fontFamily: "TestFont",
    combos: [],
  })),
  resolveFontPreview: vi.fn(() => ({
    fontFamily: "TestFont",
  })),
}));

vi.mock("@/components/LazyFontPreview", () => ({
  LazyFontPreview: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockKoreanVerifiedFont: Font = {
  slug: "test-font",
  nameKo: "테스트",
  nameEn: "Test Font",
  fontKey: null,
  tier: "free",
  category: "고딕",
  foundry: "Test",
  availableWeights: [400],
  subsets: ["korean"],
  scriptStatus: "verified",
};

const mockMixedFont: Font = {
  ...mockKoreanVerifiedFont,
  scriptStatus: "pending",
};

describe("DetailSpecimenPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("한국어 검증 폰트에 초기 문구를 설정한다", () => {
    const mockPhrase = { id: "serif-01", text: "밤하늘의 별빛이 종이 위에 내려앉았다" };
    vi.mocked(specimenPhrases.pickPhrase).mockReturnValue(mockPhrase);

    render(<DetailSpecimenPanel font={mockKoreanVerifiedFont} editable={false} />);

    expect(specimenPhrases.pickPhrase).toHaveBeenCalledWith(mockKoreanVerifiedFont);
    expect(screen.getByText(mockPhrase.text)).toBeInTheDocument();
  });

  it("한국어 검증 폰트에 셔플 버튼을 표시한다", () => {
    const mockPhrase = { id: "serif-01", text: "밤하늘의 별빛이 종이 위에 내려앉았다" };
    vi.mocked(specimenPhrases.pickPhrase).mockReturnValue(mockPhrase);

    render(<DetailSpecimenPanel font={mockKoreanVerifiedFont} editable={false} />);

    expect(screen.getByRole("button", { name: "다른 문구" })).toBeInTheDocument();
  });

  it("셔플 버튼을 클릭하면 다음 문구로 변경된다", () => {
    const mockPhrase1 = { id: "serif-01", text: "밤하늘의 별빛이 종이 위에 내려앉았다" };
    const mockPhrase2 = { id: "serif-02", text: "오래된 서점에서 발견한 한 권의 시집" };

    vi.mocked(specimenPhrases.pickPhrase).mockReturnValue(mockPhrase1);
    vi.mocked(specimenPhrases.nextPhrase).mockReturnValue(mockPhrase2);

    render(<DetailSpecimenPanel font={mockKoreanVerifiedFont} editable={false} />);

    const shuffleButton = screen.getByRole("button", { name: "다른 문구" });
    fireEvent.click(shuffleButton);

    expect(specimenPhrases.nextPhrase).toHaveBeenCalledWith(
      mockKoreanVerifiedFont,
      mockPhrase1.id
    );
    expect(screen.getByText(mockPhrase2.text)).toBeInTheDocument();
  });

  it("한국어 미검증 폰트에 셔플 버튼을 표시하지 않는다", () => {
    vi.mocked(specimenPhrases.pickPhrase).mockReturnValue({
      id: "serif-01",
      text: "밤하늘의 별빛이 종이 위에 내려앉았다",
    });

    render(<DetailSpecimenPanel font={mockMixedFont} editable={false} />);

    expect(screen.queryByRole("button", { name: "다른 문구" })).not.toBeInTheDocument();
  });

  it("editable 모드에서 입력 필드를 표시한다", () => {
    vi.mocked(specimenPhrases.pickPhrase).mockReturnValue({
      id: "serif-01",
      text: "밤하늘의 별빛이 종이 위에 내려앉았다",
    });

    render(<DetailSpecimenPanel font={mockKoreanVerifiedFont} editable={true} />);

    expect(screen.getByPlaceholderText("미리볼 문장을 입력하세요")).toBeInTheDocument();
  });
});
