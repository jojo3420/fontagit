import type { SourceTier } from "@/types/font";

export interface VariantCombination {
  weight: number;
  style: "normal" | "italic";
}

export type ItalicSupport = "supported" | "unsupported" | "unknown";

export interface ItalicSupportResult {
  status: ItalicSupport;
  italicCombos: VariantCombination[];
}

export const WEIGHT_LABELS: Record<number, string> = {
  100: "Thin",
  200: "ExtraLight",
  300: "Light",
  400: "Regular",
  500: "Medium",
  600: "SemiBold",
  700: "Bold",
  800: "ExtraBold",
  900: "Black",
};

export function formatWeightLabel(weight: number): string {
  const label = WEIGHT_LABELS[weight];
  return label ? `${weight} ${label}` : `${weight}`;
}

export function normalizeVariants(variants: string[]): VariantCombination[] {
  const combos = new Map<string, VariantCombination>();

  for (const variant of variants) {
    if (!variant) continue;

    const isItalic = variant.endsWith("italic");
    let weightStr = isItalic ? variant.slice(0, -6) : variant; // Remove "italic" suffix

    // Handle "regular" and empty cases
    if (weightStr === "regular" || weightStr === "") {
      weightStr = "";
    }

    const weight = weightStr ? parseInt(weightStr, 10) : 400;

    if (!Number.isInteger(weight) || weight < 1 || weight > 1000) continue;

    const key = `${weight}-${isItalic ? "italic" : "normal"}`;
    if (!combos.has(key)) {
      combos.set(key, {
        weight,
        style: isItalic ? "italic" : "normal",
      });
    }
  }

  return Array.from(combos.values()).sort((a, b) => {
    if (a.weight !== b.weight) return a.weight - b.weight;
    return a.style === "normal" ? -1 : 1;
  });
}

export function normalizeWeights(weights: number[]): number[] | null {
  const validWeights = new Set<number>();

  for (const weight of weights) {
    if (!(Number.isInteger(weight) && weight >= 1 && weight <= 1000)) continue;
    validWeights.add(weight);
  }

  if (validWeights.size === 0) return null;
  return Array.from(validWeights).sort((a, b) => a - b);
}

export function resolveItalicSupport(font: {
  sourceTier?: SourceTier;
  variants?: string[];
}): ItalicSupportResult {
  const combos = normalizeVariants(font.variants ?? []);
  const italicCombos = combos.filter((c) => c.style === "italic");

  if (italicCombos.length > 0) {
    return {
      status: "supported",
      italicCombos,
    };
  }

  if (font.sourceTier === "A" && combos.length > 0) {
    return {
      status: "unsupported",
      italicCombos: [],
    };
  }

  return {
    status: "unknown",
    italicCombos: [],
  };
}
