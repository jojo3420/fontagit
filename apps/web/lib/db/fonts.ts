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

  // N+1 방지: 폰트 id 수집 후 aliases 한번에 로드
  const fontIds = data.map((row) => row.id);
  const { data: aliasRows, error: aliasError } = await supabaseClient
    .from("aliases")
    .select("*")
    .in("font_id", fontIds);

  if (aliasError) throw aliasError;

  // 메모리에서 Map<font_id, alias[]>로 그룹핑
  const aliasMap = new Map<string, string[]>();
  (aliasRows || []).forEach((row: AliasRow) => {
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
