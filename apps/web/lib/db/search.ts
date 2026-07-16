import { supabaseClient } from './client';
import type { SearchResult } from './types';

interface RPCSearchRow {
  slug: string;
  name_ko: string | null;
  name_en: string;
  tier: 'free' | 'paid';
  category_ko: string;
  score: number;
}

export async function searchFonts(q: string): Promise<SearchResult[]> {
  const query = q.trim();

  if (!query) {
    return [];
  }

  try {
    const { data, error } = await supabaseClient.rpc(
      'search_fonts',
      { q: query }
    );

    if (error) {
      console.error('RPC error in searchFonts:', error);
      return [];
    }

    if (!data) {
      return [];
    }

    return (data as RPCSearchRow[]).map((row: RPCSearchRow): SearchResult => ({
      slug: row.slug,
      nameKo: row.name_ko,
      nameEn: row.name_en,
      tier: row.tier,
      category: row.category_ko,
    }));
  } catch (err) {
    console.error('Error in searchFonts:', err);
    return [];
  }
}
