import { describe, it, expect, vi } from "vitest";
import sitemap from "@/app/sitemap";

vi.mock("@/lib/data", () => ({
  getAllSlugs: vi.fn(() =>
    Promise.resolve(["pretendard", "noto-sans-cjk-kr"])
  ),
  getAllCollectionSlugs: vi.fn(() =>
    Promise.resolve(["dawn-serif", "modern-sans"])
  ),
}));

describe("sitemap", () => {
  it("정적 라우트 포함: /, /fonts, /collections, /trends", async () => {
    const entries = await sitemap();
    const urls = entries.map((e) => e.url);

    expect(urls.some((u) => u.endsWith("/"))).toBe(true);
    expect(urls.some((u) => u.endsWith("/fonts/"))).toBe(true);
    expect(urls.some((u) => u.endsWith("/collections/"))).toBe(true);
    expect(urls.some((u) => u.endsWith("/trends/"))).toBe(true);
  });

  it("폰트 slug 포함 + trailingSlash", async () => {
    const entries = await sitemap();
    const fontUrls = entries
      .filter((e) => e.url.includes("/fonts/") && !e.url.endsWith("/fonts/"))
      .map((e) => e.url);

    expect(fontUrls.length).toBeGreaterThanOrEqual(2);
    expect(fontUrls.some((u) => u.includes("/pretendard/"))).toBe(true);
    expect(fontUrls.some((u) => u.includes("/noto-sans-cjk-kr/"))).toBe(true);
  });

  it("컬렉션 slug 포함 + trailingSlash", async () => {
    const entries = await sitemap();
    const collectionUrls = entries
      .filter((e) => e.url.includes("/collections/") && !e.url.endsWith("/collections/"))
      .map((e) => e.url);

    expect(collectionUrls.length).toBeGreaterThanOrEqual(2);
    expect(collectionUrls.some((u) => u.includes("/dawn-serif/"))).toBe(true);
    expect(collectionUrls.some((u) => u.includes("/modern-sans/"))).toBe(true);
  });

  it("priority 정확함: 홈 1.0 > 컬렉션 0.9 > 폰트 0.8 > 트렌드 0.7", async () => {
    const entries = await sitemap();
    const home = entries.find((e) => e.url.endsWith("/"));
    const fonts = entries.filter((e) => e.url.includes("/fonts/") && !e.url.endsWith("/fonts/"));
    const collections = entries.filter((e) => e.url.includes("/collections/") && !e.url.endsWith("/collections/"));
    const trends = entries.find((e) => e.url.includes("/trends/"));

    expect(home?.priority).toBe(1.0);
    expect(fonts[0]?.priority).toBe(0.8);
    expect(collections[0]?.priority).toBe(0.9);
    expect(trends?.priority).toBe(0.7);
  });

  it("changeFrequency: 홈/폰트 daily, 컬렉션 weekly", async () => {
    const entries = await sitemap();
    const home = entries.find((e) => e.url.endsWith("/"));
    const font = entries.find((e) => e.url.includes("/fonts/pretendard"));
    const collection = entries.find((e) => e.url.includes("/collections/dawn-serif"));

    expect(home?.changeFrequency).toBe("daily");
    expect(font?.changeFrequency).toBe("weekly");
    expect(collection?.changeFrequency).toBe("weekly");
  });
});
