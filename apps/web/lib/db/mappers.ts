import { Font, Collection, Category, CollectionFontItem } from "@/types/font";
import { FontRow, CollectionRow } from "./types";

export function rowToFont(row: FontRow, aliases: string[]): Font {
  return {
    id: row.id,
    slug: row.slug,
    nameKo: row.name_ko ?? row.name_en,
    nameEn: row.name_en,
    fontKey: null,
    tier: row.is_commercial_free ? "free" : "paid",
    category: row.category_ko as Category,
    foundry: row.foundry ?? "",
    availableWeights: row.weights.length > 0 ? row.weights : [400],
    moves: 0,
    license: {
      commercial: row.is_commercial_free ? "yes" : "no",
      verifiedAt: row.last_modified ?? "",
      type: row.license_type ?? "",
      webfont: "included",
      redistribution: "yes",
    },
    officialUrl: row.official_url ?? "",
    aliases,
    freeAlternatives: undefined,
    status: row.status,
    subsets: row.subsets ?? [],
  };
}

export function rowToCollection(
  row: CollectionRow,
  items: CollectionFontItem[]
): Collection {
  return {
    slug: row.slug,
    title: row.title,
    intro: row.intro,
    items,
  };
}
