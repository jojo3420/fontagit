import { describe, it, expect } from "vitest";
import { buildHomePreview, badgeFor } from "@/lib/homeCuration";
import { fonts } from "@/data/fonts";
import type { Font, TrendItem } from "@/types/font";

const trend = (slug: string, rank: number): TrendItem => ({
  rank,
  change: "new",
  font: { slug, nameKo: slug, fontKey: null, tier: "free" },
  moves: 100 - rank,
});

describe("buildHomePreview", () => {
  it("주간 클릭 순위 폰트를 앞세우고 나머지는 최신순으로 채운다", () => {
    const trends = [trend("gaegu", 1), trend("jua", 2)];
    const preview = buildHomePreview(fonts, trends, 4);
    expect(preview.chips.all.slice(0, 2).map((f) => f.slug)).toEqual(["gaegu", "jua"]);
    expect(preview.chips.all).toHaveLength(4);
  });

  it("분류 칩에는 해당 분류 폰트만 담는다", () => {
    const preview = buildHomePreview(fonts, [], 8);
    expect(preview.chips["고딕"].every((f) => f.category === "고딕")).toBe(true);
    expect(preview.chips["고딕"].length).toBeGreaterThan(0);
  });

  it("대상이 없으면 빈 배열 (유료 0종 시나리오)", () => {
    const freeOnly = fonts.filter((f) => f.tier === "free");
    const preview = buildHomePreview(freeOnly, [], 8);
    expect(preview.chips.paid).toEqual([]);
  });

  it("perChip 개수를 넘지 않는다", () => {
    const preview = buildHomePreview(fonts, [], 3);
    expect(preview.chips.all).toHaveLength(3);
  });
});

describe("badgeFor", () => {
  const base = fonts[0];

  it("주간 클릭 상위면 인기 뱃지", () => {
    expect(badgeFor(base, [base.slug])).toBe("인기");
  });

  it("14일 이내 등록이면 NEW 뱃지", () => {
    const recent: Font = { ...base, createdAt: new Date().toISOString() };
    expect(badgeFor(recent, [])).toBe("NEW");
  });

  it("오래된 폰트는 뱃지 없음", () => {
    const old: Font = { ...base, createdAt: "2020-01-01T00:00:00Z" };
    expect(badgeFor(old, [])).toBeUndefined();
  });

  it("createdAt 없으면 NEW 판정 안 함", () => {
    const noDate: Font = { ...base, createdAt: undefined };
    expect(badgeFor(noDate, [])).toBeUndefined();
  });
});
