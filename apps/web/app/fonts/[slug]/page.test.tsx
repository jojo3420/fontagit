import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import FontDetail, { generateMetadata } from "@/app/fonts/[slug]/page";
import { fonts } from "@/data/fonts";
import type { Font } from "@/types/font";

const mockFonts = new Map(fonts.map((f) => [f.slug, f]));

vi.mock("@/lib/data", () => ({
  getFontBySlug: vi.fn((slug: string) =>
    Promise.resolve(mockFonts.get(slug) || null)
  ),
  resolveFreeAlternatives: vi.fn((font: Font) => {
    if (!font.freeAlternatives) return Promise.resolve([]);
    const alts = font.freeAlternatives
      .map((slug: string) => mockFonts.get(slug))
      .filter((f): f is Font => f !== undefined && f.tier === "free")
      .slice(0, 3);
    return Promise.resolve(alts);
  }),
}));

vi.mock("@/lib/db/clicks", () => ({
  recordClick: vi.fn(),
}));

async function renderDetail(slug: string) {
  const ui = await FontDetail({ params: Promise.resolve({ slug }) });
  render(ui);
}

describe("폰트 상세 페이지", () => {
  it("무료 폰트: 브레드크럼/제목/견본/라이선스 카드, 대안 카드는 없음", async () => {
    await renderDetail("nanum-myeongjo");
    expect(screen.getByText("폰트")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("나눔명조");
    expect(screen.getByText("라이선스 요약")).toBeInTheDocument();
    expect(screen.getByText("공식 페이지에서 내려받기")).toBeInTheDocument();
    expect(screen.getByLabelText("미리보기 입력")).toBeInTheDocument();
    expect(screen.queryByText(/비슷한 무료 대안/)).toBeNull();
  });
  it("유료 폰트: 대체 견본 캡션 + 대안 카드 + 구매 CTA, 입력 없음", async () => {
    await renderDetail("sandoll-gothic-neo");
    expect(screen.getByText("폰트")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("산돌 고딕 Neo");
    expect(screen.getByText(/견본은 유사 서체로 대체 표시/)).toBeInTheDocument();
    expect(screen.getByText(/구매하러 가기/)).toBeInTheDocument();
    expect(screen.getByText(/비슷한 무료 대안/)).toBeInTheDocument();
    expect(screen.queryByLabelText("미리보기 입력")).toBeNull();
  });
});

describe("generateMetadata", () => {
  it("무료 폰트: title/description/canonical 포함", async () => {
    const metadata = await generateMetadata({
      params: Promise.resolve({ slug: "nanum-myeongjo" }),
    });
    expect(metadata.title).toBe("나눔명조 - FontAgit");
    expect(metadata.description).toContain("무료");
    expect(metadata.description).toContain("가지 굵기");
    expect(metadata.alternates?.canonical).toContain("/fonts/nanum-myeongjo/");
    expect(metadata.openGraph?.title).toBe("나눔명조 - FontAgit");
  });

  it("유료 폰트: tier 표시 (유료)", async () => {
    const metadata = await generateMetadata({
      params: Promise.resolve({ slug: "sandoll-gothic-neo" }),
    });
    expect(metadata.title).toBe("산돌 고딕 Neo - FontAgit");
    expect(metadata.description).toContain("유료");
  });

  it("존재하지 않는 폰트: 안전 처리", async () => {
    const metadata = await generateMetadata({
      params: Promise.resolve({ slug: "nonexistent" }),
    });
    expect(metadata.title).toBe("폰트를 찾을 수 없습니다");
    expect(metadata.description).toContain("존재하지 않습니다");
  });
});
