import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontCard } from "@/components/FontCard";
import { fonts } from "@/data/fonts";

describe("FontCard", () => {
  it("폰트명/티어배지/상세링크를 렌더한다", () => {
    const font = fonts.find((f) => f.slug === "nanum-myeongjo")!;
    render(<FontCard font={font} />);
    expect(screen.getByText("나눔명조")).toBeInTheDocument();
    expect(screen.getByText("무료")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/fonts/nanum-myeongjo");
  });
  it("견본 pangram을 렌더한다", () => {
    const font = fonts.find((f) => f.slug === "nanum-myeongjo")!;
    render(<FontCard font={font} />);
    expect(screen.getByText(/다람쥐 헌/)).toBeInTheDocument();
  });
  it("커스텀 견본 문구를 렌더한다", () => {
    const font = fonts.find((f) => f.slug === "nanum-myeongjo")!;
    const customText = "커스텀 테스트";
    render(<FontCard font={font} previewText={customText} />);
    expect(screen.getByText(customText)).toBeInTheDocument();
  });
  it("공백-only previewText는 팬그램으로 fallback한다", () => {
    const font = fonts.find((f) => f.slug === "nanum-myeongjo")!;
    render(<FontCard font={font} previewText="   " />);
    expect(screen.getByText(/다람쥐 헌/)).toBeInTheDocument();
  });
  it("4단어 초과 커스텀 문구는 전부 렌더된다", () => {
    const font = fonts.find((f) => f.slug === "nanum-myeongjo")!;
    const longText = "하나 둘 셋 넷 다섯 여섯";
    render(<FontCard font={font} previewText={longText} />);
    expect(screen.getByText(longText)).toBeInTheDocument();
  });
});
