import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { fonts } from "@/data/fonts";

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(() => new URLSearchParams()),
  useRouter: vi.fn(() => ({
    push: vi.fn(),
  })),
}));

vi.mock("@/lib/data", () => ({
  getAllFonts: vi.fn().mockResolvedValue(fonts),
}));

import FontsPage from "@/app/fonts/page";

describe("폰트 목록 페이지 - 개요/평면 모드 분기", () => {
  it("파라미터 없으면 개요 모드(섹션별 요약)를 렌더한다", async () => {
    const searchParams = Promise.resolve({});
    const ui = await FontsPage({ searchParams });
    render(ui);

    // 개요 모드: 섹션 제목들이 표시된다
    expect(screen.getByText(/본문-긴 글/i)).toBeInTheDocument();
    // 손글씨는 h2 또는 p 여러 곳에서 나타날 수 있으므로 getAllByText 사용
    expect(screen.getAllByText(/손글씨/i).length).toBeGreaterThan(0);
  });

  it("?section=all이면 평면 모드(필터 툴바)를 렌더한다", async () => {
    const searchParams = Promise.resolve({ section: "all" });
    const ui = await FontsPage({ searchParams });
    render(ui);

    // 평면 모드: 정렬 버튼이 표시된다
    expect(screen.getByText("분류")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "최신순" })).toBeInTheDocument();
  });

  it("?section=body면 평면 모드를 렌더하고 섹션 필터를 적용한다", async () => {
    const searchParams = Promise.resolve({ section: "body" });
    const ui = await FontsPage({ searchParams });
    render(ui);

    // 평면 모드: 정렬 버튼이 표시된다
    expect(screen.getByText("분류")).toBeInTheDocument();
  });

  it("?category=고딕이면 평면 모드를 렌더한다", async () => {
    const searchParams = Promise.resolve({ category: "고딕" });
    const ui = await FontsPage({ searchParams });
    render(ui);

    // 평면 모드: 정렬 버튼이 표시된다
    expect(screen.getByText("분류")).toBeInTheDocument();
  });
});
