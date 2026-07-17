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

vi.mock("@/app/fonts/[slug]/ReportForm", () => ({
  ReportForm: () => null,
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

    const original = mockFonts.get("nanum-myeongjo")!;
    mockFonts.set("꽃길", { ...original, slug: "꽃길", nameKo: "꽃길" });
    try {
      await renderDetail(encodeURIComponent("꽃길"));
      expect(screen.getByRole("heading", { level: 1, name: "꽃길" })).toBeInTheDocument();
    } finally {
      mockFonts.delete("꽃길");
    }
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

    const original = mockFonts.get("nanum-myeongjo")!;
    mockFonts.set("꽃길", { ...original, slug: "꽃길", nameKo: "꽃길" });
    try {
      const koreanMetadata = await generateMetadata({
        params: Promise.resolve({ slug: encodeURIComponent("꽃길") }),
      });
      expect(koreanMetadata.title).toBe("꽃길 - FontAgit");
      expect(new URL(String(koreanMetadata.alternates?.canonical)).href).toBe(
        "https://fontagit.com/fonts/%EA%BD%83%EA%B8%B8/",
      );
    } finally {
      mockFonts.delete("꽃길");
    }

    mockFonts.set("nanum-myeongjo", { ...original, foundry: "" });
    try {
      const emptyFoundryMetadata = await generateMetadata({
        params: Promise.resolve({ slug: "nanum-myeongjo" }),
      });
      expect(emptyFoundryMetadata.description).not.toContain(" 제작 서체");
      expect(emptyFoundryMetadata.description).toContain("무료 라이선스");
    } finally {
      mockFonts.set("nanum-myeongjo", original);
    }
  });

  it("보류 폰트: 접근은 유지하되 검색 색인을 막는다", async () => {
    const original = mockFonts.get("nanum-myeongjo")!;
    mockFonts.set("nanum-myeongjo", { ...original, status: "hold" });

    try {
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: "nanum-myeongjo" }),
      });
      expect(metadata.robots).toEqual({ index: false, follow: true });
    } finally {
      mockFonts.set("nanum-myeongjo", original);
    }
  });

  it("존재하지 않는 폰트: 안전 처리", async () => {
    const metadata = await generateMetadata({
      params: Promise.resolve({ slug: "nonexistent" }),
    });
    expect(metadata.title).toBe("폰트를 찾을 수 없습니다");
    expect(metadata.description).toContain("존재하지 않습니다");
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});
