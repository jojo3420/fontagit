import { describe, it, expect } from "vitest";
import { getSiteUrl, BASE_URL, SITE_NAME, SITE_DESCRIPTION } from "@/lib/seo";

describe("SEO utilities", () => {
  describe("getSiteUrl", () => {
    it("path 절대 경로 처리", () => {
      const url = getSiteUrl("/fonts/pretendard/");
      expect(url).toBe(`${BASE_URL}/fonts/pretendard/`);
    });

    it("path 없는 슬래시 자동 추가", () => {
      const url = getSiteUrl("fonts/pretendard/");
      expect(url).toBe(`${BASE_URL}/fonts/pretendard/`);
    });

    it("홈 경로", () => {
      const url = getSiteUrl("/");
      expect(url).toBe(`${BASE_URL}/`);
    });
  });

  describe("BASE_URL", () => {
    it("기본값은 https://fontagit.example.com", () => {
      expect(BASE_URL).toBeDefined();
      expect(BASE_URL).toContain("fontagit");
    });
  });

  describe("SITE_NAME 및 SITE_DESCRIPTION", () => {
    it("상수 정의됨", () => {
      expect(SITE_NAME).toBe("FontAgit");
      expect(SITE_DESCRIPTION).toBeDefined();
      expect(SITE_DESCRIPTION.length).toBeGreaterThan(0);
    });
  });
});
