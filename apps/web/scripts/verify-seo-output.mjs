import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const EXPECTED_ORIGIN = "https://fontagit.com";
const EXPECTED_SITEMAP_LINE = "Sitemap: https://fontagit.com/sitemap.xml";
const REQUIRED_URLS = [
  `${EXPECTED_ORIGIN}/`,
  `${EXPECTED_ORIGIN}/fonts/`,
  `${EXPECTED_ORIGIN}/collections/`,
  `${EXPECTED_ORIGIN}/trends/`,
  `${EXPECTED_ORIGIN}/compare/`,
  `${EXPECTED_ORIGIN}/playground/`,
  `${EXPECTED_ORIGIN}/about/`,
];

export function validateSeoOutput(sitemapXml, robotsText) {
  if (!sitemapXml.trimStart().startsWith("<?xml") || !sitemapXml.includes("<urlset")) {
    throw new Error("sitemap.xml 형식이 올바르지 않습니다");
  }

  const urls = [...sitemapXml.matchAll(/<loc>\s*([^<]+?)\s*<\/loc>/g)].map((match) =>
    match[1].trim(),
  );
  if (urls.length === 0) {
    throw new Error("sitemap URL이 없습니다");
  }

  for (const url of urls) {
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      throw new Error(`잘못된 sitemap URL: ${url}`);
    }
    if (parsed.origin !== EXPECTED_ORIGIN) {
      throw new Error(`잘못된 sitemap origin: ${url}`);
    }
    const isRequiredStaticUrl = REQUIRED_URLS.includes(url);
    const isPublishedContentUrl = /^\/(fonts|collections)\/[^/]+\/$/.test(parsed.pathname);
    if (
      parsed.username ||
      parsed.password ||
      parsed.search ||
      parsed.hash ||
      (!isRequiredStaticUrl && !isPublishedContentUrl)
    ) {
      throw new Error(`허용되지 않은 sitemap 경로: ${url}`);
    }
  }

  if (new Set(urls).size !== urls.length) {
    throw new Error("중복 sitemap URL이 있습니다");
  }

  for (const requiredUrl of REQUIRED_URLS) {
    if (!urls.includes(requiredUrl)) {
      throw new Error(`필수 sitemap URL 누락: ${requiredUrl}`);
    }
  }

  const fontCount = urls.filter((url) => /^https:\/\/fontagit\.com\/fonts\/[^/]+\/$/.test(url))
    .length;
  const collectionCount = urls.filter((url) =>
    /^https:\/\/fontagit\.com\/collections\/[^/]+\/$/.test(url),
  ).length;
  if (fontCount === 0 || collectionCount === 0) {
    throw new Error(
      `공개 sitemap 콘텐츠가 비었습니다: fonts=${fontCount}, collections=${collectionCount}`,
    );
  }

  const sitemapLines = robotsText
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => /^sitemap:/i.test(line));
  if (sitemapLines.length !== 1 || sitemapLines[0] !== EXPECTED_SITEMAP_LINE) {
    throw new Error(`robots.txt Sitemap 행 오류: ${sitemapLines.join(", ") || "없음"}`);
  }

  return { urlCount: urls.length, fontCount, collectionCount };
}

function main() {
  const outputDir = process.argv[2] || "out";
  const result = validateSeoOutput(
    readFileSync(join(outputDir, "sitemap.xml"), "utf8"),
    readFileSync(join(outputDir, "robots.txt"), "utf8"),
  );
  process.stdout.write(
    `SEO 산출물 검증 완료: ${result.urlCount}개 URL (fonts=${result.fontCount}, collections=${result.collectionCount})\n`,
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
