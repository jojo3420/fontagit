import { Font } from "@/types/font";

export type SortType = "popular" | "recent";
export type FilterKey = "category" | "tier" | "use";

export interface FilterState {
  categories: Set<string>;
  tiers: Set<"free" | "paid">;
  uses: Set<string>;
  sort: SortType;
}

export const SORT_OPTIONS = {
  popular: "인기순",
  recent: "최신순",
} as const;

export const TIER_MAP: Record<string, "free" | "paid"> = {
  무료: "free",
  유료: "paid",
} as const;

export const TIER_LABEL: Record<"free" | "paid", string> = {
  free: "무료",
  paid: "유료",
} as const;

export function filterFonts(
  fonts: Font[],
  categories: Set<string>,
  tiers: Set<"free" | "paid">,
  uses: Set<string>
): Font[] {
  return fonts.filter((font) => {
    // 분류 필터
    if (categories.size > 0 && !categories.has(font.category)) {
      return false;
    }

    // 가격 필터
    if (tiers.size > 0 && !tiers.has(font.tier)) {
      return false;
    }

    // 용도 필터 (현재 데이터에는 용도 필드가 없으므로 생략)
    // 향후 font에 use 필드 추가 후 구현 가능

    return true;
  });
}

export function sortFonts(fonts: Font[], sortType: SortType): Font[] {
  const sorted = [...fonts];

  if (sortType === "popular") {
    sorted.sort((a, b) => b.moves - a.moves);
  } else if (sortType === "recent") {
    sorted.sort((a, b) => {
      const timeA = new Date(a.license.verifiedAt || 0).getTime();
      const timeB = new Date(b.license.verifiedAt || 0).getTime();
      return timeB - timeA;
    });
  }

  return sorted;
}

export function parseFilterQuery(params: URLSearchParams): FilterState {
  const categories = new Set<string>();
  const tiers = new Set<"free" | "paid">();
  const uses = new Set<string>();

  const categoryParam = params.get("category");
  if (categoryParam) {
    categoryParam.split(",").forEach((c) => {
      if (c.trim()) categories.add(c.trim());
    });
  }

  const tierParam = params.get("tier");
  if (tierParam) {
    tierParam.split(",").forEach((t) => {
      const trimmed = t.trim();
      if (trimmed === "free" || trimmed === "paid") {
        tiers.add(trimmed);
      }
    });
  }

  const useParam = params.get("use");
  if (useParam) {
    useParam.split(",").forEach((u) => {
      if (u.trim()) uses.add(u.trim());
    });
  }

  const sort = (params.get("sort") as SortType) || "popular";

  return { categories, tiers, uses, sort };
}

export function buildFilterQuery(
  categories: Set<string>,
  tiers: Set<"free" | "paid">,
  uses: Set<string>,
  sort: SortType
): string {
  const params = new URLSearchParams();

  if (categories.size > 0) {
    params.set("category", Array.from(categories).join(","));
  }

  if (tiers.size > 0) {
    params.set("tier", Array.from(tiers).join(","));
  }

  if (uses.size > 0) {
    params.set("use", Array.from(uses).join(","));
  }

  params.set("sort", sort);

  return params.toString();
}
