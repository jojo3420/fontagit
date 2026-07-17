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

describe('HeaderSearch (헤더 클릭-펼침 검색)', () => {
  beforeEach(() => mockPush.mockClear());

  it('초기에는 검색 패널이 닫혀 있다', () => {
    render(<HeaderSearch />);
    expect(screen.queryByPlaceholderText(/검색/)).not.toBeInTheDocument();
  });

  it('아이콘을 클릭하면 검색 입력창이 펼쳐진다', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    await user.click(screen.getByRole('button', { name: '검색' }));
    expect(screen.getByPlaceholderText(/검색/)).toBeInTheDocument();
  });

  it('검색어 입력 후 제출하면 /search로 이동하고 패널이 닫힌다', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    await user.click(screen.getByRole('button', { name: '검색' }));
    await user.type(screen.getByPlaceholderText(/검색/), '노토{Enter}');
    expect(mockPush).toHaveBeenCalledWith('/search?q=%EB%85%B8%ED%86%A0');
    expect(screen.queryByPlaceholderText(/검색/)).not.toBeInTheDocument();
  });

  it('Escape를 누르면 패널이 닫힌다', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    await user.click(screen.getByRole('button', { name: '검색' }));
    await user.keyboard('{Escape}');
    expect(screen.queryByPlaceholderText(/검색/)).not.toBeInTheDocument();
  });

  it('↓ 후 Enter: 활성 항목 상세로 이동', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    await user.click(screen.getByRole('button', { name: '검색' }));
    const input = screen.getByRole('combobox');
    await user.type(input, '지마켓');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(mockPush).toHaveBeenCalledWith('/fonts/gmarket-sans');
  });

  it('한글 조합 중 Enter(isComposing)는 무시', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    await user.click(screen.getByRole('button', { name: '검색' }));
    const input = screen.getByRole('combobox');
    await user.type(input, '지마켓');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('조합 중에는 드롭다운이 안 열리고, 조합 종료 후 열린다', async () => {
    const user = userEvent.setup();
    render(<HeaderSearch />);
    await user.click(screen.getByRole('button', { name: '검색' }));
    const input = screen.getByRole('combobox');
    fireEvent.compositionStart(input);
    fireEvent.change(input, { target: { value: '지' } });
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
    fireEvent.compositionEnd(input, { target: { value: '지마켓' } });
    expect(screen.getByRole('listbox')).toBeInTheDocument();
  });
});
