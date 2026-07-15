import { describe, it, expect } from "vitest";
import { rowToFont, rowToCollection } from "@/lib/db/mappers";
import { FontRow, CollectionRow } from "@/lib/db/types";

describe("rowToFont", () => {
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

  it("should set fontKey to null", () => {
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

    const items: { fontSlug: string; comment: string }[] = [
      {
        fontSlug: "pretendard",
        comment: "현대적이고 깔끔한 고딕",
      },
      {
        fontSlug: "notoSerifKr",
        comment: "우아한 세리프 폰트",
      },
    ];

    const result = rowToCollection(row, items);

    expect(result.slug).toBe("korean-display");
    expect(result.title).toBe("한글 디스플레이");
    expect(result.intro).toBe("한글 디스플레이 폰트 모음");
    expect(result.items).toHaveLength(2);
    expect(result.items[0].comment).toBe("현대적이고 깔끔한 고딕");
    expect(result.items[1].fontSlug).toBe("notoSerifKr");
  });
});
