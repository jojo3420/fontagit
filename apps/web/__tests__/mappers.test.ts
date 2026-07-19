import { describe, it, expect } from "vitest";
import { rowToFont, rowToCollection } from "@/lib/db/mappers";
import { FontRow, CollectionRow } from "@/lib/db/types";

describe("rowToFont", () => {
  it("검증된 감사 필드를 기존 주소보다 우선한다", () => {
    const row = {
      id: "audit-1",
      slug: "verified-font",
      name_en: "Verified Font",
      name_ko: "검증 폰트",
      foundry: "제작사",
      source_tier: "B",
      category_ko: "고딕",
      weights: [400],
      is_commercial_free: true,
      license_type: "무료 라이선스",
      official_url: "https://legacy.example/font",
      last_modified: "2026-07-01T00:00:00Z",
      status: "published",
      subsets: ["korean"],
      foundry_url: "https://maker.example/font",
      download_url: "https://maker.example/font.zip",
      license_source_url: "https://maker.example/license",
      license_summary: "상업적 사용은 허용되며 폰트 자체 판매는 금지됩니다.",
      license_source_kind: "official",
      download_status: "verified",
      license_status: "verified",
      license_checked_at: "2026-07-18T00:00:00Z",
      allow_commercial: "allowed",
      allow_modify: null,
      allow_redistribute: null,
      allow_embedding: "allowed",
      allow_font_sale: "denied",
      attribution_requirement: null,
      script_status: "verified",
    } satisfies FontRow;

    const font = rowToFont(row, []);

    expect(font.downloadUrl).toBe("https://maker.example/font.zip");
    expect(font.licenseAudit!.status).toBe("verified");
    expect(font.licenseAudit!.redistribute).toBe("unknown");
    expect(font.foundryUrl).toBe("https://maker.example/font");
  });

  it("재확인 상태에서는 기존 공식 주소를 다운로드 주소로 쓰지 않는다", () => {
    const row = {
      id: "audit-2",
      slug: "review-font",
      name_en: "Review Font",
      name_ko: "재확인 폰트",
      foundry: null,
      source_tier: "B",
      category_ko: "손글씨",
      weights: [400],
      is_commercial_free: true,
      license_type: null,
      official_url: "https://instagram.com/legacy-font",
      last_modified: null,
      status: "published",
      subsets: [],
      download_status: "needs_review",
      license_status: "needs_review",
      script_status: "needs_review",
    } satisfies FontRow;

    const font = rowToFont(row, []);

    expect(font.downloadUrl).toBeNull();
    expect(font.legacyOfficialUrl).toBeNull();
    expect(font.licenseAudit!.status).toBe("needs_review");
  });

  it("감사 근거가 없는 이전 데이터는 호환 주소를 보존한다", () => {
    const row = {
      id: "legacy-1",
      slug: "legacy-font",
      name_en: "Legacy Font",
      name_ko: "이전 폰트",
      foundry: null,
      source_tier: "A",
      category_ko: "명조",
      weights: [400],
      is_commercial_free: true,
      license_type: "OFL",
      official_url: "https://legacy.example/download",
      last_modified: "2026-07-01T00:00:00Z",
      status: "published",
      subsets: ["latin"],
    } satisfies FontRow;

    const font = rowToFont(row, []);

    expect(font.licenseAudit!.sourceMode).toBe("legacy");
    expect(font.legacyOfficialUrl).toBe("https://legacy.example/download");
  });

  it("should map tier to 'free' when is_commercial_free is true", () => {
    const row: FontRow = {
      id: "1",
      slug: "pretendard",
      name_en: "Pretendard",
      name_ko: "프리텐다드",
      foundry: "Orioncactus",
      category_ko: "고딕",
      weights: [400, 500, 700],
      is_commercial_free: true,
      license_type: "SIL OFL",
      official_url: "https://github.com/orioncactus/pretendard",
      last_modified: "2026-07-12T00:00:00Z",
    };

    const result = rowToFont(row, []);
    expect(result.tier).toBe("free");
  });

  it("should map tier to 'paid' when is_commercial_free is false", () => {
    const row: FontRow = {
      id: "2",
      slug: "notoSerifKr",
      name_en: "Noto Serif KR",
      name_ko: "Noto 세리프 한글",
      foundry: "Google",
      category_ko: "명조",
      weights: [400, 700],
      is_commercial_free: false,
      license_type: "OFL",
      official_url: "https://fonts.google.com/noto/specimen/Noto+Serif+KR",
      last_modified: "2026-07-11T00:00:00Z",
    };

    const result = rowToFont(row, []);
    expect(result.tier).toBe("paid");
  });

  it("should fallback nameKo to name_en when name_ko is null", () => {
    const row: FontRow = {
      id: "3",
      slug: "pretendard",
      name_en: "Pretendard",
      name_ko: null,
      foundry: "Orioncactus",
      category_ko: "고딕",
      weights: [400, 500, 700],
      is_commercial_free: true,
      license_type: "SIL OFL",
      official_url: "https://github.com/orioncactus/pretendard",
      last_modified: "2026-07-12T00:00:00Z",
    };

    const result = rowToFont(row, []);
    expect(result.nameKo).toBe("Pretendard");
    expect(result.nameEn).toBe("Pretendard");
  });

  it("should fallback availableWeights to [400] when weights is empty", () => {
    const row: FontRow = {
      id: "4",
      slug: "someFont",
      name_en: "Some Font",
      name_ko: "어떤 폰트",
      foundry: "Some Foundry",
      category_ko: "손글씨",
      weights: [],
      is_commercial_free: true,
      license_type: null,
      official_url: null,
      last_modified: null,
    };

    const result = rowToFont(row, []);
    expect(result.availableWeights).toEqual([400]);
  });

  it("should map known slug to fontKey (pretendard)", () => {
    const row: FontRow = {
      id: "5",
      slug: "pretendard",
      name_en: "Pretendard",
      name_ko: "프리텐다드",
      foundry: "Orioncactus",
      category_ko: "고딕",
      weights: [400, 500, 700],
      is_commercial_free: true,
      license_type: "SIL OFL",
      official_url: "https://github.com/orioncactus/pretendard",
      last_modified: "2026-07-12T00:00:00Z",
    };

    const result = rowToFont(row, []);
    expect(result.fontKey).toBe("pretendard");
  });

  it("should map known slug to fontKey (black-han-sans)", () => {
    const row: FontRow = {
      id: "5a",
      slug: "black-han-sans",
      name_en: "Black Han Sans",
      name_ko: "검은고딕",
      foundry: "Zess",
      category_ko: "고딕",
      weights: [400],
      is_commercial_free: true,
      license_type: "SIL OFL",
      official_url: "https://fonts.google.com/specimen/Black+Han+Sans",
      last_modified: "2026-07-12T00:00:00Z",
    };

    const result = rowToFont(row, []);
    expect(result.fontKey).toBe("blackHanSans");
  });

  it("should set fontKey to null for unknown slug", () => {
    const row: FontRow = {
      id: "5b",
      slug: "unknown-font",
      name_en: "Unknown Font",
      name_ko: "미지정 폰트",
      foundry: "Unknown",
      category_ko: "고딕",
      weights: [400],
      is_commercial_free: true,
      license_type: "SIL OFL",
      official_url: "https://example.com",
      last_modified: "2026-07-12T00:00:00Z",
    };

    const result = rowToFont(row, []);
    expect(result.fontKey).toBeNull();
  });

  it("should include aliases from parameter", () => {
    const row: FontRow = {
      id: "6",
      slug: "pretendard",
      name_en: "Pretendard",
      name_ko: "프리텐다드",
      foundry: "Orioncactus",
      category_ko: "고딕",
      weights: [400, 500, 700],
      is_commercial_free: true,
      license_type: "SIL OFL",
      official_url: "https://github.com/orioncactus/pretendard",
      last_modified: "2026-07-12T00:00:00Z",
    };

    const aliases = ["프리텐다드", "Pretendard Variable"];
    const result = rowToFont(row, aliases);
    expect(result.aliases).toEqual(aliases);
  });

  it("should map license fields correctly", () => {
    const row: FontRow = {
      id: "7",
      slug: "pretendard",
      name_en: "Pretendard",
      name_ko: "프리텐다드",
      foundry: "Orioncactus",
      category_ko: "고딕",
      weights: [400, 500, 700],
      is_commercial_free: true,
      license_type: "SIL OFL",
      official_url: "https://github.com/orioncactus/pretendard",
      last_modified: "2026-07-12T00:00:00Z",
    };

    const result = rowToFont(row, []);
    expect(result.license.commercial).toBe("yes");
    expect(result.license.type).toBe("SIL OFL");
    expect(result.license.webfont).toBe("included");
    expect(result.license.redistribution).toBe("yes");
    expect(result.license.verifiedAt).toBe("2026-07-12T00:00:00Z");
  });
});

describe("rowToCollection", () => {
  it("should create Collection from CollectionRow and items", () => {
    const row: CollectionRow = {
      id: "col1",
      slug: "korean-display",
      title: "한글 디스플레이",
      intro: "한글 디스플레이 폰트 모음",
      status: "published",
      sort_order: 1,
      created_at: "2026-07-01T00:00:00Z",
    };

    const items = [
      {
        slug: "pretendard",
        nameKo: "프리텐다드",
        fontKey: null,
        tier: "free" as const,
        comment: "현대적이고 깔끔한 고딕",
      },
      {
        slug: "notoSerifKr",
        nameKo: "Noto 세리프 한글",
        fontKey: null,
        tier: "free" as const,
        comment: "우아한 세리프 폰트",
      },
    ];

    const result = rowToCollection(row, items);

    expect(result.slug).toBe("korean-display");
    expect(result.title).toBe("한글 디스플레이");
    expect(result.intro).toBe("한글 디스플레이 폰트 모음");
    expect(result.items).toHaveLength(2);
    expect(result.items[0].comment).toBe("현대적이고 깔끔한 고딕");
    expect(result.items[0].nameKo).toBe("프리텐다드");
    expect(result.items[0].fontKey).toBeNull();
    expect(result.items[0].tier).toBe("free");
    expect(result.items[1].slug).toBe("notoSerifKr");
    expect(result.items[1].comment).toBe("우아한 세리프 폰트");
  });
});
