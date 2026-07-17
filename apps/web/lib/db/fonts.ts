import { Font } from "@/types/font";
import { FontRow, AliasRow } from "./types";
import { supabaseClient } from "./client";
import { rowToFont } from "./mappers";

export async function getAllFonts(): Promise<Font[]> {
  const { data, error } = await supabaseClient
    .from("fonts")
    .select("*")
    .eq("status", "published")
    .order("created_at", { ascending: false });

  if (error) throw error;
  if (!data || data.length === 0) return [];

  // aliases를 published 폰트 id 청크(50)로 조회: 거대 URL(수천자)과 PostgREST max-rows 무음 절단 동시 방지
  // (RLS anon_read_aliases가 published alias만 반환하지만, 절단은 role 무관하게 발생하므로 청크로 상한 보장)
  const CHUNK = 50;
  const fontIds = data.map((row) => row.id);
  const aliasRows: AliasRow[] = [];
  for (let i = 0; i < fontIds.length; i += CHUNK) {
    const { data: rows, error: aliasError } = await supabaseClient
      .from("aliases")
      .select("*")
      .in("font_id", fontIds.slice(i, i + CHUNK));
    if (aliasError) throw aliasError;
    if (rows) aliasRows.push(...(rows as AliasRow[]));
  }

  // 메모리에서 Map<font_id, alias[]>로 그룹핑
  const aliasMap = new Map<string, string[]>();
  aliasRows.forEach((row: AliasRow) => {
    if (!aliasMap.has(row.font_id)) {
      aliasMap.set(row.font_id, []);
    }
    aliasMap.get(row.font_id)!.push(row.alias);
  });

  return data.map((row: FontRow) =>
    rowToFont(row, aliasMap.get(row.id) ?? [])
  );
}

export async function getFontBySlug(slug: string): Promise<Font | null> {
  const { data, error } = await supabaseClient
    .from("fonts")
    .select("*")
    .eq("slug", slug)
    .eq("status", "published")
    .single();

  // PGRST116: no rows returned
  if (error?.code === "PGRST116") return null;
  if (error) throw error;

  const { data: aliasRows, error: aliasError } = await supabaseClient
    .from("aliases")
    .select("*")
    .eq("font_id", data.id);

  if (aliasError) throw aliasError;

  const aliases = (aliasRows || []).map((row: AliasRow) => row.alias);
  return rowToFont(data, aliases);
}

export async function getAllSlugs(): Promise<string[]> {
  const { data, error } = await supabaseClient
    .from("fonts")
    .select("slug")
    .eq("status", "published");

  if (error) throw error;

  return (data || []).map((row: { slug: string }) => row.slug);
}

export async function resolveFreeAlternatives(
  _font: Font
): Promise<Font[]> {
  // Slice 3에서 구글폰트 매칭 테이블 추가 예정
  return [];
}
