import { describe, it, expect } from "vitest";
import { isKoreanFont, getSpecimenText, getDefaultSpecimenText } from "./specimen";
import type { Font } from "@/types/font";

describe("specimen", () => {
  describe("isKoreanFont", () => {
    it("subsets에 korean이 있으면 한글 폰트로 판정한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: ["korean"],
        sourceTier: "A",
      };
      expect(isKoreanFont(font)).toBe(true);
    });

    it("subsets가 비어있지만 sourceTier가 'B'이면 한글 폰트로 판정한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: [],
        sourceTier: "B",
      };
      expect(isKoreanFont(font)).toBe(true);
    });

    it("subsets에 korean이 없고 sourceTier가 'A'이면 영문 폰트로 판정한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: ["latin"],
        sourceTier: "A",
      };
      expect(isKoreanFont(font)).toBe(false);
    });
  });

  describe("getSpecimenText", () => {
    it("sourceTier='B' + subsets=[]일 때 한글 팬그램을 반환한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: [],
        sourceTier: "B",
      };
      const text = getSpecimenText(font);
      expect(text).toContain("다람쥐 헌 쳇바퀴에 타고파");
    });

    it("subsets=['korean']일 때 한글 팬그램을 반환한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: ["korean"],
        sourceTier: "A",
      };
      const text = getSpecimenText(font);
      expect(text).toContain("다람쥐 헌 쳇바퀴에 타고파");
    });

    it("subsets=['latin'] + sourceTier='A'일 때 영문 팬그램을 반환한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: ["latin"],
        sourceTier: "A",
      };
      const text = getSpecimenText(font);
      expect(text).toContain("The quick brown fox");
    });

    it("includeEnglish=true이고 한글 폰트일 때 한글+영문 섞인 텍스트를 반환한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: ["korean"],
        sourceTier: "A",
      };
      const text = getSpecimenText(font, true);
      expect(text).toContain("다람쥐 헌 쳇바퀴에 타고파");
      expect(text).toContain("ABCabc 12345");
    });

    it("includeEnglish=true이고 영문 폰트일 때 영문+한글 섞인 텍스트를 반환한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: ["latin"],
        sourceTier: "A",
      };
      const text = getSpecimenText(font, true);
      expect(text).toContain("The quick brown fox");
      expect(text).toContain("0123");
    });
  });

  describe("getDefaultSpecimenText", () => {
    it("sourceTier='B' + subsets=[]일 때 한글 팬그램을 반환한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: [],
        sourceTier: "B",
      };
      expect(getDefaultSpecimenText(font)).toBe(
        "다람쥐 헌 쳇바퀴에 타고파"
      );
    });

    it("subsets=['korean']일 때 한글 팬그램을 반환한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: ["korean"],
        sourceTier: "A",
      };
      expect(getDefaultSpecimenText(font)).toBe(
        "다람쥐 헌 쳇바퀴에 타고파"
      );
    });

    it("subsets=['latin'] + sourceTier='A'일 때 영문 팬그램을 반환한다", () => {
      const font: Pick<Font, "subsets" | "sourceTier"> = {
        subsets: ["latin"],
        sourceTier: "A",
      };
      expect(getDefaultSpecimenText(font)).toBe(
        "The quick brown fox jumps over the lazy dog"
      );
    });
  });
});
