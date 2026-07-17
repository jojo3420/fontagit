import { describe, it, expect, vi, beforeEach } from 'vitest';
import { searchFonts, searchSuggestions } from './search';
import { supabaseClient } from './client';

vi.mock('./client', () => ({
  supabaseClient: {
    rpc: vi.fn(),
    from: vi.fn(),
  },
}));

type RpcBuilder = ReturnType<typeof supabaseClient.rpc>;
type RpcResponse = Awaited<RpcBuilder>;

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
    } as unknown as RpcResponse);

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
    } as unknown as RpcResponse);

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
    } as unknown as RpcResponse);

    const result = await searchFonts(query100);

    expect(result.length).toBe(1);
    expect(supabaseClient.rpc).toHaveBeenCalled();
  });

  it('0건 결과 → logSearchQuery 호출 (supabaseClient.from 검증)', async () => {
    vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
      data: [],
      error: null,
    } as unknown as RpcResponse);

    const mockSelect = vi.fn().mockResolvedValueOnce({
      data: null,
      error: null,
    });
    const mockInsert = vi.fn().mockReturnValueOnce({ select: mockSelect });
    vi.mocked(supabaseClient.from).mockReturnValueOnce({
      insert: mockInsert,
    } as unknown);

    const result = await searchFonts('존재하지않는폰트');

    expect(result).toEqual([]);

    await new Promise(resolve => setTimeout(resolve, 10));

    expect(supabaseClient.from).toHaveBeenCalledWith('search_logs');
    expect(mockInsert).toHaveBeenCalledWith({ query: '존재하지않는폰트' });
  });

  it('결과 있음 → logSearchQuery 호출 안 함', async () => {
    const mockData = [
      {
        slug: 'test-font',
        name_ko: '테스트',
        name_en: 'Test',
        tier: 'free' as const,
        category_ko: '고딕',
        score: 100,
      },
    ];

    vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
      data: mockData,
      error: null,
    } as unknown as RpcResponse);

    const result = await searchFonts('테스트');

    expect(result.length).toBe(1);
    expect(supabaseClient.from).not.toHaveBeenCalled();
  });
});

describe('searchSuggestions - 요청 취소(abort) 처리', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function mockAbortSignalResponse(response: { data: unknown; error: unknown }) {
    const abortSignalMock = vi.fn().mockResolvedValue(response);
    vi.mocked(supabaseClient.rpc).mockReturnValueOnce({
      abortSignal: abortSignalMock,
    } as unknown as RpcBuilder);
  }

  it('signal.aborted 상태의 취소 오류 → console.error 없이 조용히 throw', async () => {
    const controller = new AbortController();
    controller.abort();
    mockAbortSignalResponse({
      data: null,
      error: { message: 'AbortError: signal is aborted without reason', code: '' },
    });
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    await expect(
      searchSuggestions('본고딕', 8, controller.signal)
    ).rejects.toThrow('SEARCH_RPC_FAILED');
    expect(errSpy).not.toHaveBeenCalled();

    errSpy.mockRestore();
  });

  it('취소가 아닌 실제 RPC 오류 → console.error 로깅 + throw', async () => {
    const realError = { message: 'RPC boom', code: 'P0001' };
    mockAbortSignalResponse({ data: null, error: realError });
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    await expect(
      searchSuggestions('본고딕', 8, new AbortController().signal)
    ).rejects.toThrow('SEARCH_RPC_FAILED');
    expect(errSpy).toHaveBeenCalledWith('[search] RPC error:', realError);

    errSpy.mockRestore();
  });

  it('searchSuggestions: 0건 결과 → logSearchQuery 호출 (supabaseClient.from 검증)', async () => {
    const mockSelect = vi.fn().mockResolvedValueOnce({
      data: null,
      error: null,
    });
    const mockInsert = vi.fn().mockReturnValueOnce({ select: mockSelect });
    vi.mocked(supabaseClient.from).mockReturnValueOnce({
      insert: mockInsert,
    } as unknown);

    vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
      data: [],
      error: null,
    } as unknown as RpcResponse);

    const result = await searchSuggestions('정말없는폰트명', 8);

    expect(result).toEqual([]);

    await new Promise(resolve => setTimeout(resolve, 10));

    expect(supabaseClient.from).toHaveBeenCalledWith('search_logs');
    expect(mockInsert).toHaveBeenCalledWith({ query: '정말없는폰트명' });
  });

  it('searchSuggestions: 취소된 요청이라도 0건 결과면 logSearchQuery 호출 안 함', async () => {
    const controller = new AbortController();
    controller.abort();

    mockAbortSignalResponse({
      data: [],
      error: { message: 'AbortError', code: '' },
    });

    const mockInsert = vi.fn();
    vi.mocked(supabaseClient.from).mockReturnValueOnce({
      insert: mockInsert,
    } as unknown);

    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    await expect(
      searchSuggestions('검색어', 8, controller.signal)
    ).rejects.toThrow('SEARCH_RPC_FAILED');

    expect(mockInsert).not.toHaveBeenCalled();
    errSpy.mockRestore();
  });
});
