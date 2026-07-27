import { describe, expect, it } from "vitest";
import { PHRASE_GROUPS, nextPhrase, pickPhrase } from "@/lib/specimenPhrases";

describe("specimenPhrases", () => {
  it("전체 풀은 30개, id 중복 없음", () => {
    const all = Object.values(PHRASE_GROUPS).flat();
    expect(all).toHaveLength(30);
    expect(new Set(all.map((p) => p.id)).size).toBe(30);
  });

  it("같은 slug는 항상 같은 문구(결정적)", () => {
    const font = { slug: "nanum-myeongjo", category: "명조" };
    expect(pickPhrase(font)).toEqual(pickPhrase(font));
  });

  it("category 키워드 매칭: 명조→serif 그룹, 미매칭 category→common 그룹", () => {
    const serif = pickPhrase({ slug: "a", category: "명조" });
    expect(PHRASE_GROUPS.serif.some((p) => p.id === serif.id)).toBe(true);
    const fallback = pickPhrase({ slug: "a", category: "알 수 없음" });
    expect(PHRASE_GROUPS.common.some((p) => p.id === fallback.id)).toBe(true);
  });

  it("nextPhrase는 같은 그룹 안에서 순환하고 현재 문구와 다르다", () => {
    const font = { slug: "jamsil", category: "고딕" };
    const first = pickPhrase(font);
    const second = nextPhrase(font, first.id);
    expect(second.id).not.toBe(first.id);
    expect(PHRASE_GROUPS.sans.some((p) => p.id === second.id)).toBe(true);
  });
});
