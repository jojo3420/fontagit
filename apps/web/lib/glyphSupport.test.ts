import { describe, it, expect } from "vitest";
import {
  normalizeText,
  comparePixelData,
  aggregateResults,
} from "./glyphSupport";

describe("glyphSupport 순수 로직", () => {
  describe("normalizeText", () => {
    it("공백을 제거하고 고유 글자만 반환한다", () => {
      const result = normalizeText("  abc  ");
      expect(result).toEqual(["a", "b", "c"]);
    });

    it("중복 글자를 제거한다", () => {
      const result = normalizeText("aabbcc");
      expect(result).toEqual(["a", "b", "c"]);
    });

    it("중복 글자를 제거하되 첫 등장 순서를 유지한다", () => {
      const result = normalizeText("abcabc");
      expect(result).toEqual(["a", "b", "c"]);
    });

    it("한글, 숫자, 특수문자를 포함한 입력을 처리한다", () => {
      const result = normalizeText("한글a1!");
      expect(result).toEqual(["한", "글", "a", "1", "!"]);
    });

    it("빈 문자열을 입력하면 빈 배열을 반환한다", () => {
      const result = normalizeText("");
      expect(result).toEqual([]);
    });

    it("공백만 입력하면 빈 배열을 반환한다", () => {
      const result = normalizeText("   ");
      expect(result).toEqual([]);
    });

    it("개행 문자를 포함한 입력을 처리한다", () => {
      const result = normalizeText("a\nb\nc\na");
      expect(result).toEqual(["a", "\n", "b", "c"]);
    });
  });

  describe("comparePixelData", () => {
    it("다른 픽셀이 임계값을 초과하면 true를 반환한다", () => {
      const target = new Uint8ClampedArray([
        255, 255, 255, 100, // 다름 (alpha: 100)
        255, 255, 255, 100,
        255, 255, 255, 100,
        255, 255, 255, 100,
      ]);
      const fallback = new Uint8ClampedArray([
        255, 255, 255, 0, // 다름 (alpha: 0)
        255, 255, 255, 0,
        255, 255, 255, 0,
        255, 255, 255, 0,
      ]);

      const result = comparePixelData(target, fallback, 2);
      expect(result).toBe(true);
    });

    it("다른 픽셀이 임계값 이하이면 false를 반환한다", () => {
      const target = new Uint8ClampedArray([
        255, 255, 255, 100,
        255, 255, 255, 100,
        255, 255, 255, 100,
        255, 255, 255, 100,
      ]);
      const fallback = new Uint8ClampedArray([
        255, 255, 255, 100,
        255, 255, 255, 100,
        255, 255, 255, 100,
        255, 255, 255, 100,
      ]);

      const result = comparePixelData(target, fallback, 50);
      expect(result).toBe(false);
    });

    it("배열 크기가 다르면 true를 반환한다", () => {
      const target = new Uint8ClampedArray([255, 255, 255, 100]);
      const fallback = new Uint8ClampedArray([255, 255, 255, 100, 255]);

      const result = comparePixelData(target, fallback);
      expect(result).toBe(true);
    });
  });

  describe("aggregateResults", () => {
    it("지원/미지원 글자를 분류한다", () => {
      const results = [
        { char: "a", supported: true },
        { char: "b", supported: false },
        { char: "c", supported: true },
        { char: "d", supported: false },
      ];

      const result = aggregateResults(results);
      expect(result.supported).toEqual(["a", "c"]);
      expect(result.unsupported).toEqual(["b", "d"]);
    });

    it("모든 글자가 지원되는 경우를 처리한다", () => {
      const results = [
        { char: "a", supported: true },
        { char: "b", supported: true },
      ];

      const result = aggregateResults(results);
      expect(result.supported).toEqual(["a", "b"]);
      expect(result.unsupported).toEqual([]);
    });

    it("모든 글자가 미지원되는 경우를 처리한다", () => {
      const results = [
        { char: "a", supported: false },
        { char: "b", supported: false },
      ];

      const result = aggregateResults(results);
      expect(result.supported).toEqual([]);
      expect(result.unsupported).toEqual(["a", "b"]);
    });

    it("빈 배열을 입력받으면 빈 결과를 반환한다", () => {
      const result = aggregateResults([]);
      expect(result.supported).toEqual([]);
      expect(result.unsupported).toEqual([]);
    });
  });
});
