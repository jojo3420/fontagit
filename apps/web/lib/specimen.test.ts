import { describe, expect, it } from "vitest";
import { resolveSpecimenLanguage } from "./specimen";

describe("resolveSpecimenLanguage", () => {
  it("검증된 korean subset은 한글 견본을 선택한다", () => {
    expect(resolveSpecimenLanguage({
      subsets: ["korean", "latin"],
      scriptStatus: "verified",
      sourceTier: "B",
    })).toBe("korean");
  });

  it("검증된 latin-only subset은 영문 견본을 선택한다", () => {
    expect(resolveSpecimenLanguage({
      subsets: ["latin"],
      scriptStatus: "verified",
      sourceTier: "B",
    })).toBe("english");
  });

  it("빈 subsets는 Tier B여도 혼합 확인 문구를 선택한다", () => {
    expect(resolveSpecimenLanguage({
      subsets: [],
      scriptStatus: "needs_review",
      sourceTier: "B",
    })).toBe("mixed");
  });
});
