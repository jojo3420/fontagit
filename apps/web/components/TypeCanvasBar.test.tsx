import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TypeCanvasBar } from "./TypeCanvasBar";

describe("TypeCanvasBar", () => {
  it("입력하면 onChange가 호출된다", async () => {
    const onChange = vi.fn();
    render(<TypeCanvasBar value="" onChange={onChange} />);
    await userEvent.type(screen.getByRole("textbox"), "가");
    expect(onChange).toHaveBeenCalledWith("가");
  });
  it("초기화 버튼은 빈 문자열로 onChange를 호출한다", async () => {
    const onChange = vi.fn();
    render(<TypeCanvasBar value="아지트" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /초기화/ }));
    expect(onChange).toHaveBeenCalledWith("");
  });
});
