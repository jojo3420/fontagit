import { describe, expect, it } from "vitest";
import { resolveFontPreview } from "@/lib/fontPreview";

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
