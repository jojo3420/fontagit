import { supabaseClient } from "./client";
import { CollectionItemRow, CollectionRow, FontRow } from "./types";
import { rowToCollection } from "./mappers";
import type { Collection, CollectionFontItem } from "@/types/font";

export async function getAllCollectionSlugs(): Promise<string[]> {
  const { data, error } = await supabaseClient
    .from("collections")
    .select("slug")
    .eq("status", "published");

  if (error) {
    throw error;
  }

  return (data || []).map((row) => row.slug);
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
