import { supabaseClient } from "./client";
import { CollectionItemRow, CollectionRow, FontRow } from "./types";
import { rowToCollection } from "./mappers";
import type { Collection, CollectionFontItem } from "@/types/font";

export async function getAllCollectionSlugs(): Promise<string[]> {
  const slugs: string[] = [];
  const pageSize = 1000;
  let expectedCount: number | null = null;

  for (let from = 0; expectedCount === null || slugs.length < expectedCount; ) {
    const { data, error, count } = await supabaseClient
      .from("collections")
      .select("slug", { count: "exact" })
      .eq("status", "published")
      .order("slug")
      .range(from, from + pageSize - 1);

    if (error) throw error;
    if (count === null) throw new Error("published collection exact count를 확인할 수 없습니다");
    if (expectedCount !== null && count !== expectedCount) {
      throw new Error(
        `published collection count가 조회 중 변경됐습니다: ${expectedCount} -> ${count}`,
      );
    }
    expectedCount ??= count;

    const batch = (data || []).map((row: { slug: string }) => row.slug);
    slugs.push(...batch);
    if (batch.length === 0) break;
    from += batch.length;
  }

  if (slugs.length !== expectedCount) {
    throw new Error(`published collection count=${expectedCount}, 실제 수집=${slugs.length}`);
  }
  if (new Set(slugs).size !== slugs.length) {
    throw new Error("published collection slug가 중복됐습니다");
  }
  return slugs;
}

export async function getCollectionBySlug(
  slug: string
): Promise<Collection | null> {
  const { data: colData, error: colError } = await supabaseClient
    .from("collections")
    .select("*")
    .eq("slug", slug)
    .eq("status", "published")
    .single();

  if (colError) {
    if (colError.code === "PGRST116") {
      return null;
    }
    throw colError;
  }

  const col = colData as CollectionRow;

  const { data: itemRows, error: itemError } = await supabaseClient
    .from("collection_items")
    .select("*")
    .eq("collection_id", col.id)
    .order("sort_order", { ascending: true });

  if (itemError) {
    throw itemError;
  }

  const items = await buildItems(itemRows as CollectionItemRow[]);

  return rowToCollection(col, items);
}

export async function getAllCollections(): Promise<Collection[]> {
  const { data: colRows, error: colError } = await supabaseClient
    .from("collections")
    .select("*")
    .eq("status", "published")
    .order("sort_order", { ascending: true });

  if (colError) {
    throw colError;
  }

  if (!colRows || colRows.length === 0) {
    return [];
  }

  const collections = colRows as CollectionRow[];
  const collectionIds = collections.map((c) => c.id);

  const { data: itemRows, error: itemError } = await supabaseClient
    .from("collection_items")
    .select("*")
    .in("collection_id", collectionIds)
    .order("sort_order", { ascending: true });

  if (itemError) {
    throw itemError;
  }

  if (!itemRows || itemRows.length === 0) {
    return collections.map((col) => rowToCollection(col, []));
  }

  const allFontIds = [
    ...new Set((itemRows as CollectionItemRow[]).map((item) => item.font_id)),
  ];

  const { data: fontRows, error: fontError } = await supabaseClient
    .from("fonts")
    .select("*")
    .in("id", allFontIds)
    .eq("status", "published");

  if (fontError) {
    throw fontError;
  }

  const fontMap = new Map<string, FontRow>();
  (fontRows || []).forEach((font) => {
    fontMap.set(font.id, font as FontRow);
  });

  const itemsByCollectionId = new Map<string, CollectionItemRow[]>();
  (itemRows as CollectionItemRow[]).forEach((item) => {
    if (!itemsByCollectionId.has(item.collection_id)) {
      itemsByCollectionId.set(item.collection_id, []);
    }
    itemsByCollectionId.get(item.collection_id)!.push(item);
  });

  return collections.map((col) => {
    const colItems = itemsByCollectionId.get(col.id) || [];
    const builtItems = buildItemsSync(colItems, fontMap);
    return rowToCollection(col, builtItems);
  });
}

function buildItemsSync(
  itemRows: CollectionItemRow[],
  fontMap: Map<string, FontRow>
): CollectionFontItem[] {
  return itemRows
    .filter((item) => fontMap.has(item.font_id))
    .map((item) => {
      const font = fontMap.get(item.font_id)!;
      return {
        slug: font.slug,
        nameKo: font.name_ko ?? font.name_en,
        fontKey: null,
        tier: font.is_commercial_free ? "free" : ("paid" as const),
        comment: item.comment ?? "",
      };
    });
}

async function buildItems(
  itemRows: CollectionItemRow[]
): Promise<CollectionFontItem[]> {
  if (itemRows.length === 0) {
    return [];
  }

  const fontIds = itemRows.map((item) => item.font_id);

  const { data: fontRows, error: fontError } = await supabaseClient
    .from("fonts")
    .select("*")
    .in("id", fontIds)
    .eq("status", "published");

  if (fontError) {
    throw fontError;
  }

  const fontMap = new Map<string, FontRow>();
  (fontRows || []).forEach((font) => {
    fontMap.set(font.id, font as FontRow);
  });

  return buildItemsSync(itemRows, fontMap);
}
