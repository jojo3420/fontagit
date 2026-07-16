import { supabaseClient } from './client';
import type { SearchResult } from './types';

const MAX_QUERY_LENGTH = 100;

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

  if (!query || query.length > MAX_QUERY_LENGTH) {
    return [];
  }

  try {
    const { data, error } = await supabaseClient.rpc(
      'search_fonts',
      { q: query }
    );

    if (error) {
      console.error('[search] RPC error:', error);
      const err = new Error('SEARCH_RPC_FAILED');
      err.cause = error;
      throw err;
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
    if (err instanceof Error && err.message === 'SEARCH_RPC_FAILED') {
      throw err;
    }
    console.error('[search] RPC error:', err);
    const e = new Error('SEARCH_RPC_FAILED');
    e.cause = err;
    throw e;
  }
}
