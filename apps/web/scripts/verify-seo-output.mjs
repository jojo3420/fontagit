import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";
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

function sitemapUrls(sitemapXml) {
  return [...sitemapXml.matchAll(/<loc>\s*([^<]+?)\s*<\/loc>/g)].map((match) =>
    match[1].trim(),
  );
}

export function validateSeoOutput(sitemapXml, robotsText) {
  if (!sitemapXml.trimStart().startsWith("<?xml") || !sitemapXml.includes("<urlset")) {
    throw new Error("sitemap.xml 형식이 올바르지 않습니다");
  }

  const urls = sitemapUrls(sitemapXml);
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

function attribute(tag, name) {
  const match = tag.match(new RegExp(`(?:^|\\s)${name}\\s*=\\s*(["'])(.*?)\\1`, "i"));
  return match?.[2]?.trim() ?? null;
}

function htmlMetadata(html) {
  const metaTags = html.match(/<meta\b[^>]*>/gi) || [];
  const robotsTag = metaTags.find((tag) => attribute(tag, "name")?.toLowerCase() === "robots");
  const robots = robotsTag ? attribute(robotsTag, "content") : null;
  const noindex = robots
    ? robots
        .toLowerCase()
        .split(/[\s,]+/)
        .includes("noindex")
    : false;

  const canonicalTags = (html.match(/<link\b[^>]*>/gi) || []).filter((tag) =>
    (attribute(tag, "rel") || "")
      .toLowerCase()
      .split(/\s+/)
      .includes("canonical"),
  );
  if (canonicalTags.length > 1) {
    throw new Error("canonical link가 중복됐습니다");
  }

  return { noindex, canonical: canonicalTags[0] ? attribute(canonicalTags[0], "href") : null };
}

function outputPathForUrl(outputDir, url) {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(url).pathname);
  } catch {
    throw new Error(`빌드 경로로 변환할 수 없는 URL: ${url}`);
  }
  if (pathname.includes("..")) throw new Error(`허용되지 않은 빌드 경로: ${url}`);
  return pathname === "/"
    ? join(outputDir, "index.html")
    : join(outputDir, pathname.slice(1), "index.html");
}

function normalizedUrl(url, label) {
  try {
    const parsed = new URL(url);
    const pathname = parsed.pathname
      .split("/")
      .map((segment) => encodeURIComponent(decodeURIComponent(segment)))
      .join("/");
    return `${parsed.origin}${pathname}${parsed.search}${parsed.hash}`;
  } catch {
    throw new Error(`${label} URL이 올바르지 않습니다: ${url}`);
  }
}

function inspectIndexableHtml(filePath, expectedUrl) {
  if (!existsSync(filePath)) throw new Error(`sitemap 대상 HTML 누락: ${expectedUrl}`);
  const metadata = htmlMetadata(readFileSync(filePath, "utf8"));
  if (metadata.noindex) return null;
  if (!metadata.canonical) throw new Error(`indexable HTML canonical 누락: ${expectedUrl}`);

  const canonical = normalizedUrl(metadata.canonical, "canonical");
  if (canonical !== normalizedUrl(expectedUrl, "예상 canonical")) {
    throw new Error(`자기참조 canonical 불일치: expected=${expectedUrl}, actual=${canonical}`);
  }
  return canonical;
}

function dynamicHtmlFiles(outputDir, section) {
  const sectionDir = join(outputDir, section);
  if (!existsSync(sectionDir)) return [];
  const files = [];
  const walk = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const entryPath = join(directory, entry.name);
      if (entry.isDirectory()) walk(entryPath);
      if (entry.isFile() && entry.name === "index.html") files.push(entryPath);
    }
  };
  walk(sectionDir);
  return files.filter((filePath) => relative(sectionDir, filePath) !== "index.html");
}

function urlForDynamicHtml(outputDir, filePath) {
  const segments = relative(outputDir, filePath)
    .split(sep)
    .slice(0, -1)
    .map((segment) => {
      try {
        return encodeURIComponent(decodeURIComponent(segment));
      } catch {
        throw new Error(`잘못 인코딩된 빌드 디렉터리: ${segment}`);
      }
    });
  return `${EXPECTED_ORIGIN}/${segments.join("/")}/`;
}

function compareUrlSets(sitemapSet, htmlSet) {
  const missing = [...sitemapSet].filter((url) => !htmlSet.has(url));
  const excess = [...htmlSet].filter((url) => !sitemapSet.has(url));
  if (missing.length || excess.length) {
    const summary = (urls) => {
      const sample = urls.slice(0, 5).join(", ");
      return urls.length > 5 ? `${sample} 외 ${urls.length - 5}개` : sample || "없음";
    };
    throw new Error(
      `sitemap/canonical 집합 불일치: HTML 누락=${summary(missing)}; sitemap 누락=${summary(excess)}`,
    );
  }
}

export function validateSeoBuildOutput(outputDir) {
  const sitemapXml = readFileSync(join(outputDir, "sitemap.xml"), "utf8");
  const robotsText = readFileSync(join(outputDir, "robots.txt"), "utf8");
  const result = validateSeoOutput(sitemapXml, robotsText);
  const sitemapSet = new Set(sitemapUrls(sitemapXml).map((url) => normalizedUrl(url, "sitemap")));
  const htmlSet = new Set();

  for (const url of REQUIRED_URLS) {
    const canonical = inspectIndexableHtml(outputPathForUrl(outputDir, url), url);
    if (!canonical) throw new Error(`sitemap 대상 HTML이 noindex입니다: ${url}`);
    htmlSet.add(canonical);
  }

  for (const section of ["fonts", "collections"]) {
    for (const filePath of dynamicHtmlFiles(outputDir, section)) {
      const expectedUrl = urlForDynamicHtml(outputDir, filePath);
      const canonical = inspectIndexableHtml(filePath, expectedUrl);
      if (canonical) htmlSet.add(canonical);
    }
  }

  const searchUrl = `${EXPECTED_ORIGIN}/search/`;
  const searchPath = outputPathForUrl(outputDir, searchUrl);
  if (!existsSync(searchPath) || !htmlMetadata(readFileSync(searchPath, "utf8")).noindex) {
    throw new Error("search HTML은 noindex여야 합니다");
  }
  if (sitemapSet.has(searchUrl)) throw new Error("search URL은 sitemap에서 제외해야 합니다");

  compareUrlSets(sitemapSet, htmlSet);
  return result;
}

function main() {
  const outputDir = process.argv[2] || "out";
  const result = validateSeoBuildOutput(outputDir);
  process.stdout.write(
    `SEO 산출물 검증 완료: ${result.urlCount}개 URL (fonts=${result.fontCount}, collections=${result.collectionCount})\n`,
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
