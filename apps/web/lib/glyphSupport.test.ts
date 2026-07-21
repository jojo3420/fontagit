import { describe, expect, it } from "vitest";
import {
  aggregateResults,
  comparePixelData,
  isGlyphSupported,
  normalizeText,
  isGlyphCheckSupported,
} from "./glyphSupport";

function pixels(alphaValues: number[]): Uint8ClampedArray {
  return new Uint8ClampedArray(alphaValues.flatMap((alpha) => [0, 0, 0, alpha]));
}

describe("normalizeText", () => {
  it("모든 공백과 중복을 제거하고 첫 등장 순서를 유지한다", () => {
    expect(normalizeText("  가\n나 가\t다  ")).toEqual(["가", "나", "다"]);
  });

  it("이모지를 한 글자로 처리한다", () => {
    expect(normalizeText("가😀😀나")).toEqual(["가", "😀", "나"]);
  });

  it("한 번에 최대 50개만 검사한다", () => {
    const unique = Array.from({ length: 60 }, (_, index) => String.fromCodePoint(0x3400 + index)).join("");

    expect(normalizeText(unique)).toHaveLength(50);
  });
});

describe("comparePixelData", () => {
  it("차이가 임계값보다 크면 다른 그림으로 판정한다", () => {
    expect(comparePixelData(pixels([100, 100, 100]), pixels([0, 0, 0]), 2)).toBe(true);
  });

  it("차이가 임계값 이하면 같은 그림으로 판정한다", () => {
    expect(comparePixelData(pixels([100, 100]), pixels([100, 0]), 1)).toBe(false);
  });

  it("데이터 크기가 다르면 다른 그림으로 판정한다", () => {
    expect(comparePixelData(pixels([100]), pixels([100, 100]))).toBe(true);
  });
});

describe("isGlyphSupported", () => {
  it("두 대체 글꼴과 모두 다를 때만 지원으로 판정한다", () => {
    const fallbackA = pixels([0, 0, 0]);
    const fallbackB = pixels([20, 20, 20]);
    const target = pixels([100, 100, 100]);

    expect(isGlyphSupported(target, fallbackA, target, fallbackB, 2)).toBe(true);
  });

  it("한 대체 글꼴과 같으면 미지원으로 판정한다", () => {
    const fallbackA = pixels([0, 0, 0]);
    const fallbackB = pixels([20, 20, 20]);
    const target = pixels([100, 100, 100]);

    expect(isGlyphSupported(fallbackA, fallbackA, target, fallbackB, 2)).toBe(false);
  });
});

describe("aggregateResults", () => {
  it("지원과 미지원 글자를 나눈다", () => {
    expect(
      aggregateResults([
        { char: "가", supported: true },
        { char: "나", supported: false },
      ]),
    ).toEqual({ supported: ["가"], unsupported: ["나"] });
  });

  it("결과가 없으면 양쪽 모두 빈 배열이다", () => {
    expect(aggregateResults([])).toEqual({ supported: [], unsupported: [] });
  });
});

describe("isGlyphCheckSupported", () => {
  it("free 티어이고 fontKey가 null이 아니고 pretendard가 아니면 true", () => {
    expect(isGlyphCheckSupported("jua", "free")).toBe(true);
  });

  it("free 티어이지만 fontKey가 pretendard이면 false", () => {
    expect(isGlyphCheckSupported("pretendard", "free")).toBe(false);
  });

  it("free 티어이지만 fontKey가 null이면 false", () => {
    expect(isGlyphCheckSupported(null, "free")).toBe(false);
  });

  it("paid 티어이면 false", () => {
    expect(isGlyphCheckSupported("jua", "paid")).toBe(false);
  });
});
