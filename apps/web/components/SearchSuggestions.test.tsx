import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SearchSuggestions from './SearchSuggestions';
import type { SuggestItem } from '@/hooks/useDebouncedSuggestions';

const item: SuggestItem = {
  slug: 'gmarket-sans',
  nameKo: '지마켓 산스',
  nameEn: 'Gmarket Sans',
  tier: 'free',
  category: '고딕',
  foundry: 'G마켓',
  score: 45,
};

describe('SearchSuggestions', () => {
  it('항목이 없으면 렌더하지 않는다', () => {
    const { container } = render(
      <SearchSuggestions
        items={[]}
        activeIndex={-1}
        query="지마켓"
        listboxId="lb"
        onSelect={vi.fn()}
        onHover={vi.fn()}
      />
    );
    expect(container.firstChild).toBeNull();
  });

  it('항목 목록을 렌더한다', () => {
    render(
      <SearchSuggestions
        items={[item]}
        activeIndex={-1}
        query=""
        listboxId="lb"
        onSelect={vi.fn()}
        onHover={vi.fn()}
      />
    );
    expect(screen.getByText(/산스/)).toBeInTheDocument();
    expect(screen.getByText('G마켓')).toBeInTheDocument();
  });

  it('쿼리로 매칭 텍스트를 하이라이트한다', () => {
    render(
      <SearchSuggestions
        items={[item]}
        activeIndex={-1}
        query="지마켓"
        listboxId="lb"
        onSelect={vi.fn()}
        onHover={vi.fn()}
      />
    );
    expect(screen.getByText(/산스/)).toBeInTheDocument();
    const mark = screen.getByRole('option').querySelector('mark');
    expect(mark).toBeInTheDocument();
    expect(mark?.textContent).toBe('지마켓');
  });

  it('마우스다운 시 항목 선택 콜백 호출', () => {
    const onSelect = vi.fn();
    render(
      <SearchSuggestions
        items={[item]}
        activeIndex={-1}
        query="지마켓"
        listboxId="lb"
        onSelect={onSelect}
        onHover={vi.fn()}
      />
    );
    fireEvent.mouseDown(screen.getByRole('option'));
    expect(onSelect).toHaveBeenCalledWith('gmarket-sans');
  });

  it('마우스엔터 시 호버 콜백 호출', () => {
    const onHover = vi.fn();
    render(
      <SearchSuggestions
        items={[item]}
        activeIndex={-1}
        query="지마켓"
        listboxId="lb"
        onSelect={vi.fn()}
        onHover={onHover}
      />
    );
    fireEvent.mouseEnter(screen.getByRole('option'));
    expect(onHover).toHaveBeenCalledWith(0);
  });

  it('활성 항목에 data-active 속성 설정', () => {
    render(
      <SearchSuggestions
        items={[item]}
        activeIndex={0}
        query="지마켓"
        listboxId="lb"
        onSelect={vi.fn()}
        onHover={vi.fn()}
      />
    );
    expect(screen.getByRole('option')).toHaveAttribute('data-active', 'true');
  });

  it('활성 항목에 aria-selected 속성 설정', () => {
    render(
      <SearchSuggestions
        items={[item]}
        activeIndex={0}
        query="지마켓"
        listboxId="lb"
        onSelect={vi.fn()}
        onHover={vi.fn()}
      />
    );
    expect(screen.getByRole('option')).toHaveAttribute('aria-selected', 'true');
  });
});
