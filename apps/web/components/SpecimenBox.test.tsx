import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SpecimenBox } from "@/components/SpecimenBox";

describe("SpecimenBox", () => {
  it("기본 견본 문구를 렌더한다", () => {
    render(<SpecimenBox fontFamily="var(--font-x)" editable={false} />);
    expect(screen.getByText("다람쥐 헌 쳇바퀴에 타고파")).toBeInTheDocument();
  });
  it("editable이면 입력이 견본을 갱신한다", () => {
    render(<SpecimenBox fontFamily="var(--font-x)" editable initialText="가나다" />);
    const input = screen.getByLabelText("미리보기 입력");
    fireEvent.change(input, { target: { value: "라마바" } });
    expect(screen.getByText("라마바")).toBeInTheDocument();
  });
  it("editable=false이면 입력이 없다", () => {
    render(<SpecimenBox fontFamily="var(--font-x)" editable={false} />);
    expect(screen.queryByLabelText("미리보기 입력")).toBeNull();
  });
  it("caption을 렌더한다", () => {
    render(<SpecimenBox fontFamily="var(--font-x)" editable={false} caption="대체 견본입니다" />);
    expect(screen.getByText("대체 견본입니다")).toBeInTheDocument();
  });
});
