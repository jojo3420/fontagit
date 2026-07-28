import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CompareCanvas } from "./CompareCanvas";

describe("CompareCanvas", () => {
  it("기본 문구와 셀렉트 9개(대표 1 + 그리드 8)를 렌더한다", () => {
    render(<CompareCanvas />);
    expect(screen.getAllByRole("combobox")).toHaveLength(9);
    expect(screen.getByTestId("hero-specimen")).toHaveTextContent(
      "다람쥐 헌 쳇바퀴에 타고파 1234 !@#$"
    );
  });

  it("대표 셀렉트 변경 시 대표 견본 폰트와 상세 링크가 바뀐다", async () => {
    render(<CompareCanvas />);
    await userEvent.selectOptions(
      screen.getByLabelText("대표 폰트 선택"),
      "gowun-batang"
    );
    const heroDetail = screen.getAllByRole("link", { name: "상세" })[0];
    expect(heroDetail).toHaveAttribute("href", "/fonts/gowun-batang");
    expect(
      screen.getByTestId("hero-specimen").getAttribute("style") ?? ""
    ).toContain("gowun-batang");
  });
});

describe("CompareCanvas preset", () => {
  it("preset이 주어지면 대표-그리드 선택에 반영된다", () => {
    render(<CompareCanvas preset={{ heroSlug: "jua", gridSlugs: ["gowun-batang"] }} />);
    expect(screen.getByLabelText("대표 폰트 선택")).toHaveValue("jua");
    expect(screen.getByLabelText("1번 폰트 선택")).toHaveValue("gowun-batang");
  });

  it("preset이 없으면 기존 기본값을 유지한다", () => {
    render(<CompareCanvas />);
    expect(screen.getByLabelText("대표 폰트 선택")).toHaveValue("pretendard");
  });
});
