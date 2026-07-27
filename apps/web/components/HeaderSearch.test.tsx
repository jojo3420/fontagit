import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mockPush = vi.hoisted(() => vi.fn());
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

vi.mock('@/hooks/useDebouncedSuggestions', () => ({
  useDebouncedSuggestions: vi.fn(() => ({
    items: [
      { slug: 'gmarket-sans', nameKo: '지마켓 산스', nameEn: 'Gmarket Sans', tier: 'free', category: '고딕', foundry: 'G마켓', score: 45 },
    ],
    loading: false,
    error: false,
  })),
}));

import { HeaderSearch } from './HeaderSearch';
import { useDebouncedSuggestions } from '@/hooks/useDebouncedSuggestions';

describe('HeaderSearch (항상 노출 검색바)', () => {
  beforeEach(() => {
    mockPush.mockClear();
    vi.mocked(useDebouncedSuggestions).mockReturnValue({
      items: [
        { slug: 'gmarket-sans', nameKo: '지마켓 산스', nameEn: 'Gmarket Sans', tier: 'free', category: '고딕', foundry: 'G마켓', score: 45 },
      ],
      loading: false,
      error: false,
    });
  });

  it('검색 입력창이 처음부터 보인다', () => {
    render(<HeaderSearch />);
    expect(screen.getByPlaceholderText(/검색/)).toBeInTheDocument();
  });

  it('검색어 입력 후 Enter 제출하면 /search로 이동한다', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    const input = screen.getByPlaceholderText(/검색/);
    await user.type(input, '노토{Enter}');
    expect(mockPush).toHaveBeenCalledWith('/search?q=%EB%85%B8%ED%86%A0');
  });

  it('드롭다운이 열렸을 때 로딩 상태를 표시한다', async () => {
    vi.mocked(useDebouncedSuggestions).mockReturnValue({ items: [], loading: true, error: false });
    const user = userEvent.setup();
    render(<HeaderSearch />);
    const input = screen.getByRole('combobox');
    await user.type(input, 'test');
    expect(screen.getByText(/검색 중/)).toBeInTheDocument();
  });

  it('검색 결과가 없을 때 "일치하는 폰트가 없어요" 메시지를 표시한다', async () => {
    vi.mocked(useDebouncedSuggestions).mockReturnValue({ items: [], loading: false, error: false });
    const user = userEvent.setup();
    render(<HeaderSearch />);
    const input = screen.getByRole('combobox');
    await user.type(input, 'nonexistent');
    expect(screen.getByText(/일치하는 폰트가 없어요/)).toBeInTheDocument();
  });

  it('ArrowDown 후 Enter로 활성 항목 상세로 이동한다', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    const input = screen.getByRole('combobox');
    await user.type(input, '지마켓');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(mockPush).toHaveBeenCalledWith('/fonts/gmarket-sans');
  });

  it('IME 조합 중 Enter 무시 및 조합 종료 후 드롭다운 노출', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    const input = screen.getByRole('combobox');
    await user.type(input, '지마켓');
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
    expect(mockPush).not.toHaveBeenCalled();
    fireEvent.compositionEnd(input, { target: { value: '지마켓' } });
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });

  it('검색 실패 시 실패 안내가 표시된다', async () => {
    vi.mocked(useDebouncedSuggestions).mockReturnValue({ items: [], loading: false, error: true });
    const user = userEvent.setup();
    render(<HeaderSearch />);
    await user.type(screen.getByRole('combobox'), '지마켓');
    expect(screen.getByText(/검색 중 문제/)).toBeInTheDocument();
  });

  it('슬래시 키를 누르면 검색 입력창에 포커스가 간다', () => {
    render(<HeaderSearch />);
    const event = new KeyboardEvent('keydown', { key: '/', bubbles: true });
    document.body.dispatchEvent(event);
    expect(screen.getByRole('combobox')).toHaveFocus();
  });

  it('입력창에 포커스가 있으면 슬래시가 그대로 입력된다', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    const input = screen.getByRole('combobox');
    await user.click(input);
    await user.keyboard('/');
    expect(input).toHaveValue('/');
  });
});
