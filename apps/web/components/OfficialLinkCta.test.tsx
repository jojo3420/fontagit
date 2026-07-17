import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const recordClickMock = vi.fn();
vi.mock("@/lib/db/clicks", () => ({
  recordClick: (slug: string) => recordClickMock(slug),
}));

import { OfficialLinkCta } from "./OfficialLinkCta";

describe("OfficialLinkCta", () => {
  beforeEach(() => {
    recordClickMock.mockReset();
  });

  it("href/target/rel을 유지한 앵커를 렌더한다", () => {
    render(
      <OfficialLinkCta slug="noto-sans-kr" href="https://example.com" className="cta">
        공식 페이지에서 내려받기
      </OfficialLinkCta>
    );
    const link = screen.getByRole("link", { name: "공식 페이지에서 내려받기" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("클릭 시 recordClick(slug)을 호출한다 (이동 차단 없음)", () => {
    render(
      <OfficialLinkCta slug="noto-sans-kr" href="https://example.com" className="cta">
        이동
      </OfficialLinkCta>
    );
    fireEvent.click(screen.getByRole("link", { name: "이동" }));
    expect(recordClickMock).toHaveBeenCalledWith("noto-sans-kr");
  });
});
