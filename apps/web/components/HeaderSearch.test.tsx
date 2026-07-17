import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const mockPush = vi.hoisted(() => vi.fn());
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
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
});
