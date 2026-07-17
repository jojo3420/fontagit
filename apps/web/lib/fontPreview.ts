import type { Font } from "@/types/font";
import { familyOf } from "@/lib/fonts";

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
