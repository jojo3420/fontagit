import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontCard } from "@/components/FontCard";
import { getFontBySlug } from "@/lib/data";

describe("FontCard", () => {
  it("폰트명/티어배지/상세링크를 렌더한다", () => {
    const font = getFontBySlug("nanum-myeongjo")!;
    render(<FontCard font={font} />);
    expect(screen.getByText("나눔명조")).toBeInTheDocument();
    expect(screen.getByText("무료")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/fonts/nanum-myeongjo");
  });
  it("견본 pangram을 렌더한다", () => {
    const font = getFontBySlug("nanum-myeongjo")!;
    render(<FontCard font={font} />);
    expect(screen.getByText(/다람쥐 헌/)).toBeInTheDocument();
  });
});
