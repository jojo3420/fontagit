import { fonts } from "@/data/fonts";
import { collections } from "@/data/collections";
import type { Collection, Font, FontKey } from "@/types/font";

export const FONT_KEYS: FontKey[] = [
  "pretendard",
  "blackHanSans",
  "jua",
  "doHyeon",
  "gowunBatang",
  "nanumMyeongjo",
  "kirangHaerang",
  "gaegu",
  "songMyung",
];

export function getFontBySlug(slug: string): Font | undefined {
  return fonts.find((f) => f.slug === slug);
}

export function getAllSlugs(): string[] {
  return fonts.map((f) => f.slug);
}

export function resolveFreeAlternatives(font: Font): Font[] {
  return (font.freeAlternatives ?? [])
    .map((slug) => getFontBySlug(slug))
    .filter((f): f is Font => f !== undefined && f.tier === "free")
    .slice(0, 3);
}

export function getCollectionBySlug(slug: string): Collection | undefined {
  return collections.find((c) => c.slug === slug);
}

export function getAllCollectionSlugs(): string[] {
  return collections.map((c) => c.slug);
}

export function checkIntegrity(fontList: Font[], collectionList: Collection[], validKeys: FontKey[]): void {
  const keySet = new Set<string>(validKeys);
  const slugs = new Set<string>();
  for (const f of fontList) {
    if (slugs.has(f.slug)) throw new Error(`중복 slug: ${f.slug}`);
    slugs.add(f.slug);
    if (!keySet.has(f.fontKey)) throw new Error(`미매핑 fontKey: ${f.slug} -> ${f.fontKey}`);
  }
  for (const f of fontList) {
    const alts = f.freeAlternatives ?? [];
    if (alts.length > 3) throw new Error(`freeAlternatives 3개 초과: ${f.slug}`);
    for (const alt of alts) {
      if (alt === f.slug) throw new Error(`freeAlternatives 자기참조: ${f.slug}`);
      const target = fontList.find((font) => font.slug === alt);
      if (!target) throw new Error(`freeAlternatives 참조 오류: ${f.slug} -> ${alt}`);
      if (target.tier !== "free") throw new Error(`freeAlternatives가 유료: ${f.slug} -> ${alt}`);
    }
  }
  const collectionSlugs = new Set<string>();
  for (const c of collectionList) {
    if (collectionSlugs.has(c.slug)) throw new Error(`중복 컬렉션 slug: ${c.slug}`);
    collectionSlugs.add(c.slug);
    if (c.items.length === 0) throw new Error(`빈 컬렉션: ${c.slug}`);
    const itemSlugs = new Set<string>();
    for (const it of c.items) {
      if (itemSlugs.has(it.fontSlug)) throw new Error(`컬렉션 내 중복 fontSlug: ${c.slug} -> ${it.fontSlug}`);
      itemSlugs.add(it.fontSlug);
      if (!fontList.find((font) => font.slug === it.fontSlug)) throw new Error(`컬렉션 폰트 참조 오류: ${c.slug} -> ${it.fontSlug}`);
    }
  }
}

export function assertDataIntegrity(validKeys: FontKey[]): void {
  checkIntegrity(fonts, collections, validKeys);
}

// Export for testing
export { fonts };

// Validate mock data at build time
assertDataIntegrity(FONT_KEYS);
