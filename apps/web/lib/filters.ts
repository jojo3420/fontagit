import { Font, type SourceTier } from "@/types/font";

export type SortType = "popular" | "recent";

export interface FilterState {
  categories: Set<string>;
  tiers: Set<"free" | "paid">;
  sourceTiers: Set<SourceTier>;
  sort: SortType;
}

export function filterFonts(
  fonts: Font[],
  categories: Set<string>,
  tiers: Set<"free" | "paid">,
  sourceTiers: Set<SourceTier> = new Set(),
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

    if (sourceTiers.size > 0 && (!font.sourceTier || !sourceTiers.has(font.sourceTier))) {
      return false;
    }

    return true;
  });
}

export function sortFonts(fonts: Font[], sortType: SortType): Font[] {
  const sorted = [...fonts];

  if (sortType === "popular") {
    sorted.sort((a, b) => b.moves - a.moves);
  }

  // getAllFonts가 created_at 내림차순으로 조회하므로 최신순은 입력 순서를 유지한다.

  return sorted;
}

export function parseFilterQuery(params: URLSearchParams): FilterState {
  const categories = new Set<string>();
  const tiers = new Set<"free" | "paid">();
  const sourceTiers = new Set<SourceTier>();

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

  const sortParam = params.get("sort");
  const sort: SortType = sortParam === "popular" ? "popular" : "recent";

  const sourceParam = params.get("source");
  if (sourceParam) {
    sourceParam.split(",").forEach((value) => {
      const source = value.trim();
      if (source === "A" || source === "B" || source === "C") sourceTiers.add(source);
    });
  }

  return { categories, tiers, sourceTiers, sort };
}

export function buildFilterQuery(
  categories: Set<string>,
  tiers: Set<"free" | "paid">,
  sort: SortType,
  sourceTiers: Set<SourceTier> = new Set(),
): string {
  const params = new URLSearchParams();

  if (categories.size > 0) {
    params.set("category", Array.from(categories).join(","));
  }

  if (tiers.size > 0) {
    params.set("tier", Array.from(tiers).join(","));
  }

  if (sourceTiers.size > 0) {
    params.set("source", Array.from(sourceTiers).join(","));
  }

  params.set("sort", sort);

  return params.toString();
}
