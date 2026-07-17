import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { fonts } from "@/data/fonts";

vi.mock("next/navigation", () => ({
  useSearchParams: vi.fn(() => new URLSearchParams()),
  useRouter: vi.fn(() => ({
    push: vi.fn(),
  })),
}));

vi.mock("@/lib/db/fonts", () => ({
  getAllFonts: vi.fn().mockResolvedValue(fonts),
  getFontBySlug: vi.fn(),
  getAllSlugs: vi.fn(),
  resolveFreeAlternatives: vi.fn(),
}));

vi.mock("@/lib/db/collections", () => ({
  getAllCollections: vi.fn(),
  getCollectionBySlug: vi.fn(),
  getAllCollectionSlugs: vi.fn(),
}));

vi.mock("@/lib/db/trends", () => ({
  getTrends: vi.fn(),
}));

import FontsPage from "@/app/fonts/page";

describe("폰트 목록 페이지", () => {
  it("필터 섹션과 개수/정렬 툴바를 렌더한다", async () => {
    const ui = await FontsPage();
    render(ui);
    expect(screen.getByText("분류")).toBeInTheDocument();
    expect(screen.getByText(`폰트 ${fonts.length}종`)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "인기순" })).toBeInTheDocument();
  });
});
