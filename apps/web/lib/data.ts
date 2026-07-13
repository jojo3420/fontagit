import { fonts } from "@/data/fonts";
import type { Font, FontKey } from "@/types/font";

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

export function assertDataIntegrity(validKeys: FontKey[]): void {
  const keySet = new Set<string>(validKeys);
  const slugs = new Set<string>();
  for (const f of fonts) {
    if (slugs.has(f.slug)) throw new Error(`중복 slug: ${f.slug}`);
    slugs.add(f.slug);
    if (!keySet.has(f.fontKey)) throw new Error(`미매핑 fontKey: ${f.slug} -> ${f.fontKey}`);
  }
  for (const f of fonts) {
    const alts = f.freeAlternatives ?? [];
    if (alts.length > 3) throw new Error(`freeAlternatives 3개 초과: ${f.slug}`);
    for (const alt of alts) {
      if (alt === f.slug) throw new Error(`freeAlternatives 자기참조: ${f.slug}`);
      const target = getFontBySlug(alt);
      if (!target) throw new Error(`freeAlternatives 참조 오류: ${f.slug} -> ${alt}`);
      if (target.tier !== "free") throw new Error(`freeAlternatives가 유료: ${f.slug} -> ${alt}`);
    }
  }
}
