import { describe, it, expect, vi, beforeEach } from 'vitest';
import { searchFonts } from './search';
import { supabaseClient } from './client';

vi.mock('./client', () => ({
  supabaseClient: {
    rpc: vi.fn(),
  },
}));

describe('searchFonts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('정상 RPC 응답 → SearchResult 배열로 매핑', async () => {
    const mockData = [
      {
        slug: 'noto-sans-kr',
        name_ko: '노토 산스 KR',
        name_en: 'Noto Sans KR',
        tier: 'free' as const,
        category_ko: '고딕',
        score: 100,
      },
    ];

    vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
      data: mockData,
      error: null,
    } as any);

    const result = await searchFonts('본고딕');

    expect(result).toEqual([
      {
        slug: 'noto-sans-kr',
        nameKo: '노토 산스 KR',
        nameEn: 'Noto Sans KR',
        tier: 'free',
        category: '고딕',
      },
    ]);
  });

  it('빈 쿼리 → RPC 호출 없이 빈 배열 반환', async () => {
    const result = await searchFonts('');

    expect(result).toEqual([]);
    expect(supabaseClient.rpc).not.toHaveBeenCalled();
  });

  it('공백만 있는 쿼리 → RPC 호출 없이 빈 배열 반환', async () => {
    const result = await searchFonts('   ');

    expect(result).toEqual([]);
    expect(supabaseClient.rpc).not.toHaveBeenCalled();
  });

  it('RPC 오류 → throw', async () => {
    const mockError = { message: 'RPC failed' };
    vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
      data: null,
      error: mockError,
    } as any);

    await expect(searchFonts('query')).rejects.toThrow('SEARCH_RPC_FAILED');
  });

  it('쿼리가 100자 초과 → RPC 호출 없이 빈 배열 반환', async () => {
    const longQuery = 'a'.repeat(101);
    const result = await searchFonts(longQuery);

    expect(result).toEqual([]);
    expect(supabaseClient.rpc).not.toHaveBeenCalled();
  });

  it('쿼리가 정확히 100자 → RPC 호출', async () => {
    const query100 = 'a'.repeat(100);
    const mockData = [
      {
        slug: 'test-font',
        name_ko: '테스트',
        name_en: 'Test',
        tier: 'free' as const,
        category_ko: '고딕',
        score: 50,
      },
    ];

    vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
      data: mockData,
      error: null,
    } as any);

    const result = await searchFonts(query100);

    expect(result.length).toBe(1);
    expect(supabaseClient.rpc).toHaveBeenCalled();
  });
});
