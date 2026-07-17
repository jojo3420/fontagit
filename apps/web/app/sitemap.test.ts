import { describe, it, expect, vi } from "vitest";
import sitemap from "@/app/sitemap";

vi.mock("@/lib/data", () => ({
  getPublishedSlugs: vi.fn(() =>
    Promise.resolve(["pretendard", "noto-sans-cjk-kr", "kbiz한마음고딕체"])
  ),
  getAllCollectionSlugs: vi.fn(() =>
    Promise.resolve(["dawn-serif", "modern-sans"])
  ),
}));

describe("sitemap", () => {
  it("검색 노출 대상 정적 라우트 7개를 포함한다", async () => {
    const entries = await sitemap();
    const urls = entries.map((e) => e.url);

    expect(urls.slice(0, 7)).toEqual([
      "https://fontagit.com/",
      "https://fontagit.com/fonts/",
      "https://fontagit.com/collections/",
      "https://fontagit.com/trends/",
      "https://fontagit.com/compare/",
      "https://fontagit.com/playground/",
      "https://fontagit.com/about/",
    ]);
  });

  it("published 폰트와 컬렉션 slug를 후행 슬래시로 포함한다", async () => {
    const entries = await sitemap();
    const urls = entries.map((entry) => entry.url);

    expect(urls).toContain("https://fontagit.com/fonts/pretendard/");
    expect(urls).toContain("https://fontagit.com/fonts/noto-sans-cjk-kr/");
    expect(urls).toContain("https://fontagit.com/collections/dawn-serif/");
    expect(urls).toContain("https://fontagit.com/collections/modern-sans/");
  });

  it("한글 slug는 URL 인코딩된 형태로 포함한다", async () => {
    const entries = await sitemap();
    const urls = entries.map((entry) => entry.url);

    expect(urls).toContain(
      `https://fontagit.com/fonts/${encodeURIComponent("kbiz한마음고딕체")}/`
    );
  });

  it("Google이 무시하거나 신뢰할 수 없는 선택 메타를 넣지 않는다", async () => {
    const entries = await sitemap();

    expect(entries.every((entry) => entry.priority === undefined)).toBe(true);
    expect(entries.every((entry) => entry.changeFrequency === undefined)).toBe(true);
    expect(entries.every((entry) => entry.lastModified === undefined)).toBe(true);
  });
});
