import assert from "node:assert/strict";
import test from "node:test";
import { validateSeoOutput } from "./verify-seo-output.mjs";

const requiredUrls = [
  "https://fontagit.com/",
  "https://fontagit.com/fonts/",
  "https://fontagit.com/collections/",
  "https://fontagit.com/trends/",
  "https://fontagit.com/compare/",
  "https://fontagit.com/playground/",
  "https://fontagit.com/about/",
];
const publishedUrls = [
  "https://fontagit.com/fonts/noto-sans-kr/",
  "https://fontagit.com/collections/dawn-serif/",
];

function sitemapXml(urls) {
  return `<?xml version="1.0" encoding="UTF-8"?><urlset>${urls
    .map((url) => `<url><loc>${url}</loc></url>`)
    .join("")}</urlset>`;
}

const robotsText = "User-Agent: *\nAllow: /\n\nSitemap: https://fontagit.com/sitemap.xml\n";

test("정확한 origin과 필수 경로를 통과시킨다", () => {
  assert.deepEqual(validateSeoOutput(sitemapXml([...requiredUrls, ...publishedUrls]), robotsText), {
    urlCount: 9,
    fontCount: 1,
    collectionCount: 1,
  });
});

test("한 URL이라도 다른 origin이면 거부한다", () => {
  const urls = [...requiredUrls, "https://fontagit.pages.dev/fonts/test/"];
  assert.throws(
    () => validateSeoOutput(sitemapXml(urls), robotsText),
    /잘못된 sitemap origin/,
  );
});

test("공개 콘텐츠가 비거나 허용하지 않은 경로가 섞이면 거부한다", () => {
  assert.throws(
    () => validateSeoOutput(sitemapXml(requiredUrls), robotsText),
    /공개 sitemap 콘텐츠가 비었습니다/,
  );

  const urls = [...requiredUrls, "https://fontagit.com/search/"];
  assert.throws(() => validateSeoOutput(sitemapXml(urls), robotsText), /허용되지 않은 sitemap 경로/);
});
