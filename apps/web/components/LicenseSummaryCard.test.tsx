import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { LicenseSummaryCard } from "@/components/LicenseSummaryCard";
import { fonts } from "@/data/fonts";
import type { Font } from "@/types/font";

vi.mock("@/lib/db/clicks", () => ({
  recordClick: vi.fn(),
}));

describe("LicenseSummaryCard", () => {
  it("유료 폰트: 3개 라이선스 행 + 가격 CTA + 판매처", () => {
    const paid = fonts.find((f) => f.slug === "sandoll-gothic-neo")!;
    render(<LicenseSummaryCard font={paid} />);
    expect(screen.getByText("라이선스 요약")).toBeInTheDocument();
    expect(screen.getByText("상업적 사용")).toBeInTheDocument();
    expect(screen.getByText("구매 시")).toBeInTheDocument();
    expect(screen.getByText("웹폰트")).toBeInTheDocument();
    expect(screen.getByText("별도 구매")).toBeInTheDocument();
    expect(screen.getByText("재배포")).toBeInTheDocument();
    expect(screen.getByText(/구매하러 가기/)).toBeInTheDocument();
    expect(screen.getByText(/₩99,000~/)).toBeInTheDocument();
    expect(screen.getByText(/sandoll\.co\.kr/)).toBeInTheDocument();
  });
  it("무료 폰트: 내려받기 CTA", () => {
    const free = fonts.find((f) => f.slug === "nanum-myeongjo")!;
    render(<LicenseSummaryCard font={free} />);
    expect(screen.getByText("공식 페이지에서 내려받기")).toBeInTheDocument();
    expect(screen.getAllByText("가능").length).toBeGreaterThan(0);
  });
  it("감사된 폰트 (verified): 6개 감사 권한 행 + 출처 표기 조건 표시", () => {
    const verifiedFont: Font = {
      slug: "test-verified-font",
      nameKo: "테스트 감사됨 폰트",
      nameEn: "Test Verified Font",
      fontKey: null,
      tier: "free",
      category: "고딕",
      foundry: "Test Foundry",
      availableWeights: [400],
      subsets: ["korean", "latin"],
      moves: 0,
      license: {
        commercial: "yes",
        verifiedAt: "2026-07-18",
        type: "OFL",
        webfont: "included",
        redistribution: "yes",
      },
      officialUrl: "https://example.com/font",
      aliases: [],
      licenseAudit: {
        status: "verified",
        sourceMode: "audit",
        summary: null,
        sourceUrl: "https://official-source.com/license",
        sourceKind: "official",
        checkedAt: "2026-07-18",
        commercial: "allowed",
        modify: "conditional",
        redistribute: "denied",
        embedding: "allowed",
        fontSale: "denied",
        attribution: "required",
      },
    };
    render(<LicenseSummaryCard font={verifiedFont} />);
    expect(screen.getByText("라이선스 요약")).toBeInTheDocument();
    expect(screen.queryByText("라이선스 재확인 필요")).not.toBeInTheDocument();

    const commercialRow = screen.getByText("상업적 사용").closest("li");
    expect(within(commercialRow!).getByText("허용")).toBeInTheDocument();

    const modifyRow = screen.getByText("수정").closest("li");
    expect(within(modifyRow!).getByText("조건부")).toBeInTheDocument();

    const redistributeRow = screen.getByText("재배포").closest("li");
    expect(within(redistributeRow!).getByText("금지")).toBeInTheDocument();

    const embeddingRow = screen.getByText("임베딩").closest("li");
    expect(within(embeddingRow!).getByText("허용")).toBeInTheDocument();

    const fontSaleRow = screen.getByText("폰트 판매").closest("li");
    expect(within(fontSaleRow!).getByText("금지")).toBeInTheDocument();

    const attributionRow = screen.getByText("출처 표기").closest("li");
    expect(within(attributionRow!).getByText("필수")).toBeInTheDocument();
  });
  it("감사 검토 필요 폰트 (needs_review): 재확인 필요 안내 표시", () => {
    const needsReviewFont: Font = {
      slug: "test-needs-review-font",
      nameKo: "테스트 검토필요 폰트",
      nameEn: "Test Needs Review Font",
      fontKey: null,
      tier: "free",
      category: "명조",
      foundry: "Test Foundry 2",
      availableWeights: [400, 700],
      subsets: ["korean"],
      moves: 0,
      license: {
        commercial: "yes",
        verifiedAt: "2026-07-17",
        type: "MIT",
        webfont: "included",
        redistribution: "yes",
      },
      officialUrl: "https://example2.com/font",
      aliases: [],
      licenseAudit: {
        status: "needs_review",
        sourceMode: "audit",
        summary: "제작사 문의 대기 중",
        sourceUrl: null,
        sourceKind: null,
        checkedAt: null,
        commercial: "unknown",
        modify: "unknown",
        redistribute: "unknown",
        embedding: "unknown",
        fontSale: "unknown",
        attribution: "unknown",
      },
    };
    render(<LicenseSummaryCard font={needsReviewFont} />);
    expect(screen.getByText("라이선스 요약")).toBeInTheDocument();
    expect(screen.getByText("라이선스 재확인 필요")).toBeInTheDocument();
    expect(screen.queryByText("상업적 사용")).not.toBeInTheDocument();
    expect(screen.queryByText("수정")).not.toBeInTheDocument();
  });
});
