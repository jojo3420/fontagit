import { describe, expect, it } from "vitest";
import { resolveFontPreview, resolveDetailFontPreview } from "@/lib/fontPreview";

describe("resolveFontPreview", () => {
  it("미매핑 Tier A 폰트를 Google CSS2 URL과 실제 family로 연결한다", () => {
    expect(
      resolveFontPreview({
        fontKey: null,
        nameEn: "Orbitron",
        sourceTier: "A",
        availableWeights: [400, 700],
      })
    ).toEqual({
      fontFamily:
        '"Orbitron", "Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl:
        "https://fonts.googleapis.com/css2?family=Orbitron%3Awght%40400%3B700&display=swap",
    });
  });

  it("이미 self-host된 폰트는 외부 stylesheet를 요청하지 않는다", () => {
    expect(
      resolveFontPreview({
        fontKey: "jua",
        nameEn: "Jua",
        sourceTier: "A",
        availableWeights: [400],
      }).stylesheetUrl
    ).toBeNull();
  });

  it("Tier B 폰트를 Google에 잘못 요청하지 않는다", () => {
    expect(
      resolveFontPreview({
        fontKey: null,
        nameEn: "경기천년제목",
        sourceTier: "B",
        availableWeights: [400, 700],
      })
    ).toEqual({
      fontFamily: '"Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl: null,
    });
  });
});

describe("resolveDetailFontPreview", () => {
  it("미매핑 Tier A 폰트의 모든 지원 variant를 포함한 Google CSS2 URL을 생성한다", () => {
    expect(
      resolveDetailFontPreview({
        fontKey: null,
        nameEn: "Orbitron",
        sourceTier: "A",
        variants: ["400", "700", "700italic"],
      })
    ).toEqual({
      fontFamily:
        '"Orbitron", "Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl:
        "https://fonts.googleapis.com/css2?family=Orbitron%3Aital%2Cwght%400%2C400%3B0%2C700%3B1%2C700&display=swap",
      combos: [
        { weight: 400, style: "normal" },
        { weight: 700, style: "normal" },
        { weight: 700, style: "italic" },
      ],
    });
  });

  it("이미 self-host된 폰트는 외부 stylesheet를 요청하지 않는다", () => {
    expect(
      resolveDetailFontPreview({
        fontKey: "jua",
        nameEn: "Jua",
        sourceTier: "A",
        variants: ["400"],
      })
    ).toEqual({
      fontFamily: "var(--font-jua), system-ui, sans-serif",
      stylesheetUrl: null,
      combos: [{ weight: 400, style: "normal" }],
    });
  });

  it("Tier B 폰트를 Google에 잘못 요청하지 않는다", () => {
    expect(
      resolveDetailFontPreview({
        fontKey: null,
        nameEn: "경기천년제목",
        sourceTier: "B",
        variants: ["400"],
      })
    ).toEqual({
      fontFamily: '"Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl: null,
      combos: [{ weight: 400, style: "normal" }],
    });
  });

  it("variants가 없으면 빈 combos와 fallback을 반환한다", () => {
    expect(
      resolveDetailFontPreview({
        fontKey: null,
        nameEn: "Orbitron",
        sourceTier: "A",
        variants: undefined,
      })
    ).toEqual({
      fontFamily: '"Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl: null,
      combos: [],
    });
  });

  it("variants가 빈 배열이면 빈 combos와 fallback을 반환한다", () => {
    expect(
      resolveDetailFontPreview({
        fontKey: null,
        nameEn: "Orbitron",
        sourceTier: "A",
        variants: [],
      })
    ).toEqual({
      fontFamily: '"Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl: null,
      combos: [],
    });
  });

  it("nameEn이 공백만 있으면 fallback을 반환한다", () => {
    expect(
      resolveDetailFontPreview({
        fontKey: null,
        nameEn: "   ",
        sourceTier: "A",
        variants: ["400"],
      })
    ).toEqual({
      fontFamily: '"Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl: null,
      combos: [{ weight: 400, style: "normal" }],
    });
  });
});
