import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { SearchResult } from '@/lib/db/types';

vi.mock('@/lib/db/search', () => ({
  searchFonts: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(() => {
    const params = new URLSearchParams();
    return {
      get: (key: string) => params.get(key),
    };
  }),
}));

// Import after mocks are defined
import SearchPage from './page';
import { searchFonts } from '@/lib/db/search';

const mockSearchFonts = vi.mocked(searchFonts);

describe('검색 페이지 (page.tsx)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('초기 상태에서 입력 필드와 안내 메시지가 표시된다', async () => {
    mockSearchFonts.mockResolvedValue([]);
    render(await SearchPage());

    const input = screen.getByPlaceholderText(/검색/i);
    expect(input).toBeInTheDocument();
    expect(input).toHaveValue('');

    const prompt = screen.getByText('검색어를 입력하세요.');
    expect(prompt).toBeInTheDocument();
  });

  it('입력 후 debounce(250ms)를 거쳐 검색 결과를 표시한다', async () => {
    const mockResults: SearchResult[] = [
      {
        slug: 'noto-sans-kr',
        nameKo: '노토 산스 KR',
        nameEn: 'Noto Sans KR',
        tier: 'free',
        category: '고딕',
      },
    ];
    mockSearchFonts.mockResolvedValue(mockResults);

    const user = userEvent.setup({ delay: null });
    render(await SearchPage());

    const input = screen.getByPlaceholderText(/검색/i) as HTMLInputElement;
    await user.type(input, '노토');

    await waitFor(
      () => {
        expect(screen.getByText('노토 산스 KR')).toBeInTheDocument();
      },
      { timeout: 1000 }
    );

    expect(mockSearchFonts).toHaveBeenCalledWith('노토');
  });

  it('검색 결과가 없을 때 적절한 메시지를 표시한다', async () => {
    mockSearchFonts.mockResolvedValue([]);

    const user = userEvent.setup({ delay: null });
    render(await SearchPage());

    const input = screen.getByPlaceholderText(/검색/i) as HTMLInputElement;
    await user.type(input, '존재하지않음');

    await waitFor(
      () => {
        expect(screen.getByText(/검색 결과가 없습니다/i)).toBeInTheDocument();
      },
      { timeout: 1000 }
    );
  });

  it('검색 결과 링크가 올바른 href를 가진다', async () => {
    const mockResults: SearchResult[] = [
      {
        slug: 'noto-sans-kr',
        nameKo: '노토 산스 KR',
        nameEn: 'Noto Sans KR',
        tier: 'free',
        category: '고딕',
      },
    ];
    mockSearchFonts.mockResolvedValue(mockResults);

    const user = userEvent.setup({ delay: null });
    render(await SearchPage());

    const input = screen.getByPlaceholderText(/검색/i) as HTMLInputElement;
    await user.type(input, '노토');

    await waitFor(
      () => {
        const link = screen.getByRole('link', { name: /노토/i });
        expect(link).toHaveAttribute('href', '/fonts/noto-sans-kr');
      },
      { timeout: 1000 }
    );
  });

  it('요청 진행 중 입력을 전부 삭제하면 로딩 표시가 사라진다', async () => {
    // 지연된 Promise로 모킹 (수동 resolve)
    let resolveSearch: ((value: SearchResult[]) => void) | null = null;
    const delayedPromise = new Promise<SearchResult[]>((resolve) => {
      resolveSearch = resolve;
    });
    mockSearchFonts.mockReturnValue(delayedPromise);

    const user = userEvent.setup({ delay: null });
    render(await SearchPage());

    const input = screen.getByPlaceholderText(/검색/i) as HTMLInputElement;

    // 1. 입력 후 debounce 경과
    await user.type(input, '노토');
    await new Promise((r) => setTimeout(r, 300)); // debounce 250ms + 여유

    // 2. 로딩 표시 확인
    expect(screen.getByText('검색 중...')).toBeInTheDocument();

    // 3. 입력 전부 삭제
    await user.clear(input);
    await new Promise((r) => setTimeout(r, 300)); // debounce 다시 경과

    // 4. 로딩이 사라지고 초기 안내 메시지가 보여야 함
    expect(screen.queryByText('검색 중...')).not.toBeInTheDocument();
    expect(screen.getByText('검색어를 입력하세요.')).toBeInTheDocument();
  });
});
