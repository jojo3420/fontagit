import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';

vi.mock('@/lib/db/search', () => ({
  searchSuggestions: vi.fn(),
}));

import { useDebouncedSuggestions } from './useDebouncedSuggestions';
import * as searchModule from '@/lib/db/search';

describe('useDebouncedSuggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  const advanceTimers = async (milliseconds: number) => {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(milliseconds);
    });
  };

  it('빈 쿼리에서 빈 배열 반환', () => {
    const { result } = renderHook(() => useDebouncedSuggestions(''));
    expect(result.current.items).toEqual([]);
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe(false);
  });

  it('쿼리 디바운스 후 searchSuggestions 호출', async () => {
    const mockSearch = vi.spyOn(searchModule, 'searchSuggestions').mockResolvedValueOnce([
      { slug: 'gmarket-sans', nameKo: '지마켓 산스', nameEn: 'Gmarket Sans', tier: 'free', category: '고딕', foundry: 'G마켓' },
    ]);

    const { result, rerender } = renderHook(
      ({ q }: { q: string }) => useDebouncedSuggestions(q),
      { initialProps: { q: '' } }
    );

    rerender({ q: '지마켓' });
    expect(result.current.loading).toBe(true);

    await advanceTimers(200);

    expect(mockSearch).toHaveBeenCalledWith('지마켓', 8, expect.any(AbortSignal));
  });

  it('쿼리 변경 시 이전 타이머 취소', () => {
    const mockSearch = vi.spyOn(searchModule, 'searchSuggestions').mockResolvedValue([]);

    const { rerender } = renderHook(
      ({ q }: { q: string }) => useDebouncedSuggestions(q),
      { initialProps: { q: '' } }
    );

    rerender({ q: '지마켓' });
    vi.advanceTimersByTime(100);

    rerender({ q: '노토' });
    vi.advanceTimersByTime(100);

    expect(mockSearch).toHaveBeenCalledTimes(0);
  });

  it('RPC in-flight 중 빈 쿼리로 지우면 이전 응답이 덮지 않음', async () => {
    vi.spyOn(searchModule, 'searchSuggestions').mockResolvedValueOnce([
      { slug: 'gmarket-sans', nameKo: '지마켓 산스', nameEn: 'Gmarket Sans', tier: 'free', category: '고딕', foundry: null },
    ]);

    const { result, rerender } = renderHook(
      ({ q }: { q: string }) => useDebouncedSuggestions(q),
      { initialProps: { q: '' } }
    );

    rerender({ q: '지마켓' });
    await advanceTimers(200);
    rerender({ q: '' });

    expect(result.current.items).toEqual([]);
  });

  it('레이스: 빠른 연속 입력 후 이전 요청 취소 → 최신 요청만 실행', async () => {
    const mockSearch = vi.spyOn(searchModule, 'searchSuggestions');
    mockSearch.mockResolvedValue([
      { slug: 'noto', nameKo: 'Noto Sans KR', nameEn: 'Noto Sans KR', tier: 'free' as const, category: '고딕', foundry: null },
    ]);

    const { rerender } = renderHook(
      ({ q }: { q: string }) => useDebouncedSuggestions(q),
      { initialProps: { q: '' } }
    );

    rerender({ q: '지마켓' });
    vi.advanceTimersByTime(100);
    rerender({ q: '노토' });
    await advanceTimers(200);

    expect(mockSearch).toHaveBeenCalledTimes(1);
    expect(mockSearch).toHaveBeenCalledWith('노토', 8, expect.any(AbortSignal));
  });

});
