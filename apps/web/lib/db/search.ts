import { supabaseClient } from './client';
import type { SearchResult } from './types';

const MAX_QUERY_LENGTH = 100;
const SEARCH_LOG_DEBOUNCE_MS = 1000;

interface RPCSearchRow {
  slug: string;
  name_ko: string | null;
  name_en: string;
  tier: 'free' | 'paid';
  category_ko: string;
  foundry: string | null;
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

    const results = (data as RPCSearchRow[]).map((row: RPCSearchRow): SearchResult => ({
      slug: row.slug,
      nameKo: row.name_ko,
      nameEn: row.name_en,
      tier: row.tier,
      category: row.category_ko,
      foundry: row.foundry,
    }));

    // 0건 결과이면 검색어 로깅 (비동기, 무시)
    if (results.length === 0) {
      logSearchQuery(q).catch(() => {});
    }

    return results;
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

let lastLoggedQuery = '';
let lastLoggedTime = 0;

/**
 * 검색 실패어(0건 결과)를 익명 로그
 * @param query 검색어 (정규화 전)
 * best-effort: 로깅 실패는 무시(검색 UX에 영향 없음)
 */
async function logSearchQuery(query: string): Promise<void> {
  const now = Date.now();
  if (query === lastLoggedQuery && now - lastLoggedTime < SEARCH_LOG_DEBOUNCE_MS) {
    return;
  }

  lastLoggedQuery = query;
  lastLoggedTime = now;

  try {
    await supabaseClient
      .from('search_logs')
      .insert({ query: query.trim() })
      .select();
  } catch {
    // 로깅 실패는 조용히 무시(테이블 미적용 환경 대비, 로깅 인프라 실패 대비)
  }
}

export async function searchSuggestions(
  q: string,
  limit: number = 8,
  signal?: AbortSignal
): Promise<SearchResult[]> {
  const query = q.trim();

  if (!query || query.length > MAX_QUERY_LENGTH) {
    return [];
  }

  try {
    let builder = supabaseClient.rpc('search_fonts', { q: query, lim: limit });
    if (signal) {
      builder = builder.abortSignal(signal);
    }
    const { data, error } = await builder;

    if (error) {
      // 디바운스 취소(signal.aborted)는 정상 흐름 — 에러로 로깅하지 않는다
      if (!signal?.aborted) {
        console.error('[search] RPC error:', error);
      }
      const err = new Error('SEARCH_RPC_FAILED');
      err.cause = error;
      throw err;
    }

    if (!data) {
      return [];
    }

    const results = (data as RPCSearchRow[]).map((row: RPCSearchRow): SearchResult => ({
      slug: row.slug,
      nameKo: row.name_ko,
      nameEn: row.name_en,
      tier: row.tier,
      category: row.category_ko,
      foundry: row.foundry,
    }));

    // 0건 결과이면 검색어 로깅 (비동기, 무시)
    if (results.length === 0) {
      logSearchQuery(q).catch(() => {});
    }

    return results;
  } catch (err) {
    if (err instanceof Error && err.message === 'SEARCH_RPC_FAILED') {
      throw err;
    }
    // 디바운스 취소로 던져진 AbortError는 정상 흐름 — 로깅하지 않는다
    if (!signal?.aborted) {
      console.error('[search] RPC error:', err);
    }
    const e = new Error('SEARCH_RPC_FAILED');
    e.cause = err;
    throw e;
  }
}
