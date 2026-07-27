import type { Font } from "@/types/font";
import { familyOf } from "@/lib/fonts";
import { normalizeVariants, type VariantCombination } from "@/lib/weightLabels";

const FALLBACK_FAMILY =
  '"Pretendard Variable", "Pretendard", sans-serif';

type PreviewFont = Pick<
  Font,
  "fontKey" | "nameEn" | "sourceTier" | "availableWeights"
>;

export interface FontPreviewResolution {
  fontFamily: string;
  stylesheetUrl: string | null;
}

export interface DetailFontPreviewResolution {
  fontFamily: string;
  stylesheetUrl: string | null;
  combos: VariantCombination[];
}

export function resolveFontPreview(
  font: PreviewFont
): FontPreviewResolution {
  if (font.fontKey) {
    return { fontFamily: familyOf(font.fontKey), stylesheetUrl: null };
  }

  const family = font.nameEn.trim();
  if (font.sourceTier !== "A" || !family) {
    return { fontFamily: FALLBACK_FAMILY, stylesheetUrl: null };
  }

  const previewWeights = [400, 700].filter((weight) =>
    font.availableWeights.includes(weight)
  );
  const familyQuery =
    previewWeights.length > 0
      ? `${family}:wght@${previewWeights.join(";")}`
      : family;
  const query = new URLSearchParams({ family: familyQuery, display: "swap" });

  return {
    fontFamily: `${JSON.stringify(family)}, ${FALLBACK_FAMILY}`,
    stylesheetUrl: `https://fonts.googleapis.com/css2?${query.toString()}`,
  };
}

export function resolveDetailFontPreview(
  font: Pick<Font, "fontKey" | "nameEn" | "sourceTier" | "variants">
): DetailFontPreviewResolution {
  const family = font.nameEn.trim();

  if (font.sourceTier !== "A") {
    return {
      fontFamily: FALLBACK_FAMILY,
      stylesheetUrl: null,
      combos: normalizeVariants(font.variants ?? []),
    };
  }

  const combos = normalizeVariants(font.variants ?? []);

  if (font.fontKey) {
    return {
      fontFamily: familyOf(font.fontKey),
      stylesheetUrl: null,
      combos,
    };
  }

  if (!family || combos.length === 0) {
    return {
      fontFamily: FALLBACK_FAMILY,
      stylesheetUrl: null,
      combos,
    };
  }

  const tuples = [...combos]
    .sort((a, b) =>
      a.style === b.style ? a.weight - b.weight : a.style === "normal" ? -1 : 1
    )
    .map((c) => `${c.style === "italic" ? 1 : 0},${c.weight}`);
  const query = new URLSearchParams({
    family: `${family}:ital,wght@${tuples.join(";")}`,
    display: "swap",
  });

  return {
    fontFamily: `${JSON.stringify(family)}, ${FALLBACK_FAMILY}`,
    stylesheetUrl: `https://fonts.googleapis.com/css2?${query.toString()}`,
    combos,
  };
}
