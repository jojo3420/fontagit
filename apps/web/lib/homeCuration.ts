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
  // 칩마다 겹치는 폰트가 있어도 pick()이 ranked의 Font 객체 참조를 그대로 담기 때문에
  // (spread/clone 없음) Next.js RSC flight 직렬화가 참조 기반으로 자동 dedupe한다.
  // 실측(pnpm build 후 out/index.html)으로 확인함: slug 배열 + 별도 맵으로 바꿔봤더니
  // 참조당 백레퍼런스보다 slug 문자열 반복 + 맵 키 오버헤드가 더 커서 오히려 페이로드가
  // 커졌다(raw +966B, gzip +252B). 그래서 Font[] 참조 공유 구조를 유지한다.
  // ⚠️ pick()에서 스프레드로 새 객체를 만들면 이 dedupe가 깨지고 실제로 페이로드가 불어난다.
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
  trends.forEach((t) => clickRank.set(t.font.slug, t.rank));
  // 1차: 최신순(동률/미상은 slug)으로 기준선을 명시적으로 만든다.
  // 2차: 클릭 순위 보유 폰트를 앞세운다 — Array.sort는 안정 정렬이라
  // 클릭 순위가 없는(동일 취급) 폰트들끼리는 1차 정렬 결과가 그대로 유지된다.
  const byRecency = (a: Font, b: Font): number => {
    const ta = a.createdAt ? new Date(a.createdAt).getTime() : NaN;
    const tb = b.createdAt ? new Date(b.createdAt).getTime() : NaN;
    const va = Number.isNaN(ta) ? -Infinity : ta;
    const vb = Number.isNaN(tb) ? -Infinity : tb;
    if (va !== vb) return vb - va;
    return a.slug.localeCompare(b.slug);
  };
  const ranked = [...fonts].sort(byRecency).sort((a, b) => {
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
    if (!Number.isNaN(ageDays) && ageDays >= 0 && ageDays <= NEW_BADGE_DAYS) return "NEW";
  }
  return undefined;
}
