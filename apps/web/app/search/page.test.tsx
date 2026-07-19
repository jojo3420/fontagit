import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { SearchResult } from '@/lib/db/types';

vi.mock('@/lib/db/search', () => ({
  searchFonts: vi.fn(),
}));

const { mockReplace } = vi.hoisted(() => ({ mockReplace: vi.fn() }));

vi.mock('next/navigation', () => ({
  useSearchParams: vi.fn(() => {
    const params = new URLSearchParams();
    return {
      get: (key: string) => params.get(key),
    };
  }),
  useRouter: vi.fn(() => ({
    replace: mockReplace,
  })),
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
    // 완료되지 않는 Promise로 진행 중 요청을 재현
    const delayedPromise = new Promise<SearchResult[]>(() => {});
    mockSearchFonts.mockReturnValue(delayedPromise);

    const user = userEvent.setup({ delay: null });
    render(await SearchPage());

    const input = screen.getByPlaceholderText(/검색/i) as HTMLInputElement;

    // 1. 입력 후 debounce 경과
    await user.type(input, '노토');

    // 2. 로딩 표시 확인
    await waitFor(() => {
      expect(screen.getByText('검색 중...')).toBeInTheDocument();
    });

    // 3. 입력 전부 삭제
    await user.clear(input);

    // 4. 로딩이 사라지고 초기 안내 메시지가 보여야 함
    await waitFor(() => {
      expect(screen.queryByText('검색 중...')).not.toBeInTheDocument();
      expect(screen.getByText('검색어를 입력하세요.')).toBeInTheDocument();
    });
  });

  it('searchFonts reject → error message displayed', async () => {
    mockSearchFonts.mockRejectedValue(new Error('SEARCH_RPC_FAILED'));

    const user = userEvent.setup({ delay: null });
    render(await SearchPage());

    const input = screen.getByPlaceholderText(/검색/i) as HTMLInputElement;
    await user.type(input, '테스트');

    await waitFor(
      () => {
        expect(screen.getByText(/검색에 실패했습니다/i)).toBeInTheDocument();
      },
      { timeout: 1000 }
    );
  });



  // PR#16 Review H2: 성공 결과가 실패 후에도 남아있으면 안 됨
  it('성공한 검색 뒤 다음 검색이 실패하면 이전 결과가 사라지고 오류가 표시된다', async () => {
    mockSearchFonts.mockResolvedValueOnce([
      { slug: 'noto-sans-kr', nameKo: '노토 산스 KR', nameEn: 'Noto Sans KR', tier: 'free', category: '고딕' },
    ]);

    const user = userEvent.setup({ delay: null });
    render(await SearchPage());
    const input = screen.getByPlaceholderText(/검색/i) as HTMLInputElement;

    await user.type(input, '노토');
    await waitFor(
      () => expect(screen.getByText('노토 산스 KR')).toBeInTheDocument(),
      { timeout: 1000 }
    );

    mockSearchFonts.mockRejectedValueOnce(new Error('SEARCH_RPC_FAILED'));
    await user.clear(input);
    await user.type(input, '본고딩');

    await waitFor(
      () => {
        expect(screen.getByText(/검색에 실패했습니다/i)).toBeInTheDocument();
        expect(screen.queryByText('노토 산스 KR')).not.toBeInTheDocument();
      },
      { timeout: 1000 }
    );
  });

  // PR#16 Review H1: URL 동기화 — 입력 반영 + 삭제 시 q 제거
  it('debounce 후 URL이 검색어와 동기화되고, 입력을 지우면 /search로 정리된다', async () => {
    mockSearchFonts.mockResolvedValue([]);

    const user = userEvent.setup({ delay: null });
    render(await SearchPage());
    const input = screen.getByPlaceholderText(/검색/i) as HTMLInputElement;

    await user.type(input, '노토 산스');
    await waitFor(() => {
      expect(mockReplace).toHaveBeenLastCalledWith(
        `/search?q=${encodeURIComponent('노토 산스')}`,
        { scroll: false }
      );
    });

    await user.clear(input);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenLastCalledWith('/search', { scroll: false });
    });
  });

});
