import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { validateSeoBuildOutput, validateSeoOutput } from "./verify-seo-output.mjs";

const requiredUrls = [
  "https://fontagit.com/",
  "https://fontagit.com/fonts/",
  "https://fontagit.com/collections/",
  "https://fontagit.com/trends/",
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

function html(canonical, robots = "index, follow") {
  return `<html><head><link rel="canonical" href="${canonical}"><meta name="robots" content="${robots}"></head></html>`;
}

function outputPath(outputDir, url) {
  const pathname = decodeURIComponent(new URL(url).pathname);
  return pathname === "/"
    ? join(outputDir, "index.html")
    : join(outputDir, pathname.slice(1), "index.html");
}

function createOutputFixture() {
  const outputDir = mkdtempSync(join(tmpdir(), "fontagit-seo-"));
  const urls = [...requiredUrls, ...publishedUrls];
  writeFileSync(join(outputDir, "sitemap.xml"), sitemapXml(urls));
  writeFileSync(join(outputDir, "robots.txt"), robotsText);

  for (const url of urls) {
    const filePath = outputPath(outputDir, url);
    mkdirSync(dirname(filePath), { recursive: true });
    writeFileSync(filePath, html(url));
  }

  const searchPath = join(outputDir, "search", "index.html");
  mkdirSync(dirname(searchPath), { recursive: true });
  writeFileSync(searchPath, html("https://fontagit.com/search/", "noindex, follow"));
  return outputDir;
}

test("사이트맵과 색인 가능한 HTML canonical 집합이 정확히 같으면 통과한다", () => {
  const outputDir = createOutputFixture();
  try {
    assert.deepEqual(validateSeoBuildOutput(outputDir), {
      urlCount: 8,
      fontCount: 1,
      collectionCount: 1,
    });
  } finally {
    rmSync(outputDir, { recursive: true, force: true });
  }
});

test("잘못된 origin이나 canonical 집합 불일치를 거부한다", () => {
  assert.throws(
    () =>
      validateSeoOutput(
        sitemapXml([...requiredUrls, "https://fontagit.pages.dev/fonts/test/"]),
        robotsText,
      ),
    /잘못된 sitemap origin/,
  );

  const outputDir = createOutputFixture();
  try {
    writeFileSync(
      outputPath(outputDir, publishedUrls[0]),
      html("https://fontagit.com/fonts/different/"),
    );
    assert.throws(() => validateSeoBuildOutput(outputDir), /canonical/);
  } finally {
    rmSync(outputDir, { recursive: true, force: true });
  }
});

test("공개 콘텐츠가 비거나 search가 indexable이면 거부한다", () => {
  assert.throws(
    () => validateSeoOutput(sitemapXml(requiredUrls), robotsText),
    /공개 sitemap 콘텐츠가 비었습니다/,
  );

  const outputDir = createOutputFixture();
  try {
    writeFileSync(
      join(outputDir, "search", "index.html"),
      html("https://fontagit.com/search/", "index, follow"),
    );
    assert.throws(() => validateSeoBuildOutput(outputDir), /search.*noindex/i);
  } finally {
    rmSync(outputDir, { recursive: true, force: true });
  }
});
