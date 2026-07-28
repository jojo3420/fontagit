import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PairingPresets } from "@/components/PairingPresets";

describe("PairingPresets", () => {
  it("페어링 3세트를 렌더한다", () => {
    render(<PairingPresets onSelect={vi.fn()} />);
    expect(screen.getAllByRole("button")).toHaveLength(3);
  });

  it("클릭 시 onSelect가 대표+본문 조합으로 호출된다", () => {
    const onSelect = vi.fn();
    render(<PairingPresets onSelect={onSelect} />);
    fireEvent.click(screen.getAllByRole("button")[0]);
    expect(onSelect).toHaveBeenCalledWith({
      heroSlug: "black-han-sans",
      gridSlugs: ["pretendard"],
    });
  });
});
