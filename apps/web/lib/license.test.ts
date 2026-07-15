import { describe, it, expect } from "vitest";
import { commercialLabel, licensState, extractHost } from "./license";

describe("commercialLabel", () => {
  it("returns '가능' for 'yes'", () => {
    expect(commercialLabel("yes")).toBe("가능");
  });
  it("returns '구매 시' for 'conditional'", () => {
    expect(commercialLabel("conditional")).toBe("구매 시");
  });
  it("returns '별도 구매' for 'no'", () => {
    expect(commercialLabel("no")).toBe("별도 구매");
  });
});

describe("licensState", () => {
  it("returns 'ok' for OFL licenses with webfont included and redis='yes'", () => {
    expect(
      licensState({
        type: "SIL OFL",
        webfont: "included",
        redistribution: "yes",
      })
    ).toBe("ok");
  });

  it("returns 'cond' for other OFL states", () => {
    expect(
      licensState({
        type: "SIL OFL",
        webfont: "separate",
        redistribution: "yes",
      })
    ).toBe("cond");
  });

  it("returns 'cond' for non-OFL licenses", () => {
    expect(
      licensState({
        type: "Proprietary",
        webfont: "included",
        redistribution: "no",
      })
    ).toBe("cond");
  });
});

describe("extractHost", () => {
  it("extracts github.com from GitHub URL", () => {
    expect(extractHost("https://github.com/orioncactus/pretendard")).toBe(
      "github.com"
    );
  });

  it("extracts fonts.google.com from Google Fonts URL", () => {
    expect(extractHost("https://fonts.google.com/specimen/Pretendard")).toBe(
      "fonts.google.com"
    );
  });

  it("handles domain without www", () => {
    expect(extractHost("https://example.com/path")).toBe("example.com");
  });

  it("throws error for invalid URL", () => {
    expect(() => extractHost("not-a-url")).toThrow();
  });
});
