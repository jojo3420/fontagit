import { describe, it, expect } from "vitest";
import {
  commercialLabel, webfontLabel, redistributionLabel,
  commercialState, webfontState, redistributionState,
  deriveSellerHost, type LicenseState,
} from "./license";

describe("license 라벨 매핑", () => {
  describe("commercialLabel", () => {
    it('returns "가능" for yes', () => {
      expect(commercialLabel("yes")).toBe("가능");
    });
    it('returns "구매 시" for conditional', () => {
      expect(commercialLabel("conditional")).toBe("구매 시");
    });
    it('returns "불가" for no', () => {
      expect(commercialLabel("no")).toBe("불가");
    });
  });

  describe("webfontLabel", () => {
    it('returns "포함" for included', () => {
      expect(webfontLabel("included")).toBe("포함");
    });
    it('returns "별도 구매" for separate', () => {
      expect(webfontLabel("separate")).toBe("별도 구매");
    });
    it('returns "불가" for no', () => {
      expect(webfontLabel("no")).toBe("불가");
    });
  });

  describe("redistributionLabel", () => {
    it('returns "가능" for yes', () => {
      expect(redistributionLabel("yes")).toBe("가능");
    });
    it('returns "불가" for no', () => {
      expect(redistributionLabel("no")).toBe("불가");
    });
  });
});

describe("license 상태 파생", () => {
  describe("commercialState", () => {
    it('returns "ok" for yes', () => {
      expect(commercialState("yes")).toBe("ok");
    });
    it('returns "cond" for conditional', () => {
      expect(commercialState("conditional")).toBe("cond");
    });
    it('returns "no" for no', () => {
      expect(commercialState("no")).toBe("no");
    });
  });

  describe("webfontState", () => {
    it('returns "ok" for included', () => {
      expect(webfontState("included")).toBe("ok");
    });
    it('returns "cond" for separate', () => {
      expect(webfontState("separate")).toBe("cond");
    });
    it('returns "no" for no', () => {
      expect(webfontState("no")).toBe("no");
    });
  });

  describe("redistributionState", () => {
    it('returns "ok" for yes', () => {
      expect(redistributionState("yes")).toBe("ok");
    });
    it('returns "no" for no', () => {
      expect(redistributionState("no")).toBe("no");
    });
  });
});

describe("deriveSellerHost", () => {
  it("extracts example.com from URL", () => {
    expect(deriveSellerHost("https://www.example.com/path")).toBe("example.com");
  });
  it("removes www. prefix", () => {
    expect(deriveSellerHost("https://www.sandoll.co.kr/")).toBe("sandoll.co.kr");
  });
  it('returns null for invalid URL', () => {
    expect(deriveSellerHost("not-a-url")).toBe(null);
  });
  it('returns null for empty host', () => {
    expect(deriveSellerHost("https://")).toBe(null);
  });
});
