import { describe, expect, it } from "vitest";
import {
  formatWeightLabel,
  normalizeVariants,
  normalizeWeights,
  resolveItalicSupport,
} from "./weightLabels";

describe("normalizeVariants", () => {
  it("Google Fonts 4형태를 정규화하고 불가값은 무시한다", () => {
    expect(
      normalizeVariants(["regular", "italic", "700", "700italic", "wat", "700abc", ""])
    ).toEqual([
      { weight: 400, style: "normal" },
      { weight: 400, style: "italic" },
      { weight: 700, style: "normal" },
      { weight: 700, style: "italic" },
    ]);
    // 중복 제거 + weight 오름차순, 같은 weight는 normal 우선
    expect(normalizeVariants(["700", "300", "700", "300italic"])).toEqual([
      { weight: 300, style: "normal" },
      { weight: 300, style: "italic" },
      { weight: 700, style: "normal" },
    ]);
  });
});

describe("resolveItalicSupport", () => {
  it("italic 조합 존재는 supported, Tier A variants 보유-italic 없음은 unsupported, 그 외 unknown", () => {
    expect(
      resolveItalicSupport({ sourceTier: "A", variants: ["regular", "italic"] })
    ).toEqual({
      status: "supported",
      italicCombos: [{ weight: 400, style: "italic" }],
    });
    expect(
      resolveItalicSupport({ sourceTier: "A", variants: ["regular", "700"] }).status
    ).toBe("unsupported");
    expect(resolveItalicSupport({ sourceTier: "A", variants: [] }).status).toBe("unknown");
    expect(
      resolveItalicSupport({ sourceTier: "B", variants: undefined }).status
    ).toBe("unknown");
  });
});

describe("normalizeWeights", () => {
  it("비정상값-중복 제거, 정렬, 빈 결과는 null", () => {
    expect(normalizeWeights([700, 400, 400, 0, 1001, Number.NaN])).toEqual([400, 700]);
    expect(normalizeWeights([])).toBeNull();
    expect(normalizeWeights([0])).toBeNull();
  });
});

describe("formatWeightLabel", () => {
  it("이름 매핑이 있으면 숫자+이름, 없으면 숫자만", () => {
    expect(formatWeightLabel(400)).toBe("400 Regular");
    expect(formatWeightLabel(350)).toBe("350");
  });
});
