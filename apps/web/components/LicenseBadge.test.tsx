import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { LicenseBadge } from "./LicenseBadge";

describe("LicenseBadge", () => {
  it("renders '가능' with icon when commercial='yes'", () => {
    render(<LicenseBadge commercial="yes" />);
    expect(screen.getByText("가능")).toBeInTheDocument();
  });

  it("renders '조건부' with icon when commercial='conditional'", () => {
    render(<LicenseBadge commercial="conditional" />);
    expect(screen.getByText("조건부")).toBeInTheDocument();
  });

  it("renders '불가' with icon when commercial='no'", () => {
    render(<LicenseBadge commercial="no" />);
    expect(screen.getByText("불가")).toBeInTheDocument();
  });
});
