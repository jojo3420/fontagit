import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { CompareLazy } from "./CompareLazy";

let ioCallback: (entries: Array<{ isIntersecting: boolean }>) => void;

beforeEach(() => {
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(cb: typeof ioCallback) {
        ioCallback = cb;
      }
      observe() {}
      disconnect() {}
    }
  );
});

describe("CompareLazy", () => {
  it("진입 전에는 placeholder만 보이고 비교 보드는 없다", () => {
    render(<CompareLazy placeholder={<div data-testid="ph" />} />);
    expect(screen.getByTestId("ph")).toBeTruthy();
    expect(screen.queryByLabelText("비교 문장 입력")).toBeNull();
  });

  it("뷰포트 진입 시 비교 보드를 마운트한다", async () => {
    render(<CompareLazy placeholder={<div data-testid="ph" />} />);
    await act(async () => {
      ioCallback([{ isIntersecting: true }]);
    });
    expect(await screen.findByLabelText("비교 문장 입력")).toBeTruthy();
  });
});
