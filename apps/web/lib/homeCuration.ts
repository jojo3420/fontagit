import type { Font, TrendItem } from "@/types/font";

export type ChipKey = "all" | "고딕" | "명조" | "손글씨" | "장식" | "free" | "paid";

export interface ChipDef {
  key: ChipKey;
  label: string;
  /** /fonts로 넘길 쿼리스트링 */
  query: string;
}

// 기존 lib/filters.ts buildFilterQuery와 동일하게 URLSearchParams로 인코딩 통일
const toQuery = (params: Record<string, string>): string =>
  new URLSearchParams(params).toString();

export const CHIP_DEFS: ChipDef[] = [
  { key: "all", label: "전체", query: toQuery({ sort: "popular" }) },
  { key: "고딕", label: "고딕", query: toQuery({ category: "고딕", sort: "popular" }) },
  { key: "명조", label: "명조", query: toQuery({ category: "명조", sort: "popular" }) },
  { key: "손글씨", label: "손글씨", query: toQuery({ category: "손글씨", sort: "popular" }) },
  { key: "장식", label: "장식", query: toQuery({ category: "장식", sort: "popular" }) },
  { key: "free", label: "무료", query: toQuery({ tier: "free", sort: "popular" }) },
  { key: "paid", label: "유료", query: toQuery({ tier: "paid", sort: "popular" }) },
];

export const PER_CHIP = 8;
const NEW_BADGE_DAYS = 14;
const HOT_BADGE_COUNT = 10;

export interface HomePreview {
  chips: Record<ChipKey, Font[]>;
  /** 주간 클릭 상위 slug — 인기 뱃지 기준 */
  hotSlugs: string[];
}

export function buildHomePreview(
  fonts: Font[],
  trends: TrendItem[],
  perChip: number = PER_CHIP,
): HomePreview {
  const clickRank = new Map<string, number>();
  trends.forEach((t, i) => clickRank.set(t.font.slug, i));
  // fonts는 getAllFonts의 최신 등록순. 클릭 순위 보유 폰트를 앞세우고
  // 미보유는 stable sort 특성으로 최신순이 유지된다.
  const ranked = [...fonts].sort((a, b) => {
    const ra = clickRank.get(a.slug) ?? Number.MAX_SAFE_INTEGER;
    const rb = clickRank.get(b.slug) ?? Number.MAX_SAFE_INTEGER;
    return ra - rb;
  });
  const pick = (pred: (f: Font) => boolean): Font[] =>
    ranked.filter(pred).slice(0, perChip);
  return {
    chips: {
      all: pick(() => true),
      고딕: pick((f) => f.category === "고딕"),
      명조: pick((f) => f.category === "명조"),
      손글씨: pick((f) => f.category === "손글씨"),
      장식: pick((f) => f.category === "장식"),
      free: pick((f) => f.tier === "free"),
      paid: pick((f) => f.tier === "paid"),
    },
    hotSlugs: trends.slice(0, HOT_BADGE_COUNT).map((t) => t.font.slug),
  };
}

export function badgeFor(
  font: Font,
  hotSlugs: string[],
  now: Date = new Date(),
): "인기" | "NEW" | undefined {
  if (hotSlugs.includes(font.slug)) return "인기";
  if (font.createdAt) {
    const ageDays = (now.getTime() - new Date(font.createdAt).getTime()) / 86_400_000;
    if (ageDays <= NEW_BADGE_DAYS) return "NEW";
  }
  return undefined;
}
