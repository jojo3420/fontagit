import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Breadcrumb } from "@/components/Breadcrumb";

describe("Breadcrumb", () => {
  it("항목 라벨을 모두 렌더한다", () => {
    render(<Breadcrumb items={[{ label: "폰트", href: "/fonts" }, { label: "명조" }, { label: "나눔명조" }]} />);
    expect(screen.getByText("폰트")).toBeInTheDocument();
    expect(screen.getByText("명조")).toBeInTheDocument();
    expect(screen.getByText("나눔명조")).toBeInTheDocument();
  });
  it("href 있는 항목만 링크로 렌더한다", () => {
    render(<Breadcrumb items={[{ label: "폰트", href: "/fonts" }, { label: "나눔명조" }]} />);
    expect(screen.getByRole("link", { name: "폰트" })).toHaveAttribute("href", "/fonts");
    expect(screen.queryByRole("link", { name: "나눔명조" })).toBeNull();
  });
});
