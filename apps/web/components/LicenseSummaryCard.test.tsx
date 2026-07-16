import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LicenseSummaryCard } from "@/components/LicenseSummaryCard";
import { fonts } from "@/data/fonts";

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
});
