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

  it("칩에 같은 폰트가 여러 번 들어가도 동일 객체 참조를 공유한다 (RSC flight dedupe 전제 조건)", () => {
    // pretendard는 all/고딕/free 세 칩에 모두 들어갈 수 있는 폰트.
    // pick()이 스프레드/클론 없이 참조를 그대로 담아야 flight 직렬화가 dedupe한다.
    const preview = buildHomePreview(fonts, [], 8);
    expect(preview.chips.all[0]).toBe(preview.chips.free[0]);
  });

  it("클릭 순위가 없는 폰트는 입력 배열 순서와 무관하게 최신 등록순으로 정렬된다", () => {
    const older: Font = { ...fonts[0], slug: "older", createdAt: "2026-01-01T00:00:00Z" };
    const newer: Font = { ...fonts[0], slug: "newer", createdAt: "2026-06-01T00:00:00Z" };
    // 일부러 오래된 것을 먼저 넣어 입력 순서에 기대지 않음을 검증
    const preview = buildHomePreview([older, newer], [], 8);
    expect(preview.chips.all.map((f) => f.slug)).toEqual(["newer", "older"]);
  });

  it("createdAt이 없는 폰트는 최신순 뒤로 밀리고, 동률/미상은 slug로 결정론적으로 정렬된다", () => {
    const dated: Font = { ...fonts[0], slug: "dated", createdAt: "2026-01-01T00:00:00Z" };
    const noDateB: Font = { ...fonts[0], slug: "b-no-date", createdAt: undefined };
    const noDateA: Font = { ...fonts[0], slug: "a-no-date", createdAt: undefined };
    const preview = buildHomePreview([noDateB, dated, noDateA], [], 8);
    expect(preview.chips.all.map((f) => f.slug)).toEqual(["dated", "a-no-date", "b-no-date"]);
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

  it("createdAt이 미래면 NEW 판정 안 함", () => {
    const future: Font = { ...base, createdAt: new Date(Date.now() + 86_400_000).toISOString() };
    expect(badgeFor(future, [])).toBeUndefined();
  });

  it("createdAt이 파싱 불가한 값이면 NEW 판정 안 함", () => {
    const invalid: Font = { ...base, createdAt: "not-a-date" };
    expect(badgeFor(invalid, [])).toBeUndefined();
  });

  it("hotSlugs에도 있고 14일 이내 등록이어도 인기가 우선한다", () => {
    const recentAndHot: Font = { ...base, createdAt: new Date().toISOString() };
    expect(badgeFor(recentAndHot, [recentAndHot.slug])).toBe("인기");
  });
});
