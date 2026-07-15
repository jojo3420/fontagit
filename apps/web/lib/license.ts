import type { Commercial, LicenseState, LicenseType, LicenseWebfont, LicenseRedistribution } from "@/types/font";

export function commercialLabel(c: Commercial): string {
  switch (c) {
    case "yes":
      return "가능";
    case "conditional":
      return "구매 시";
    case "no":
      return "별도 구매";
  }
}

export function licensState(l: {
  type: LicenseType;
  webfont: LicenseWebfont;
  redistribution: LicenseRedistribution;
}): LicenseState {
  if (
    l.type === "SIL OFL" &&
    l.webfont === "included" &&
    l.redistribution === "yes"
  ) {
    return "ok";
  }
  return "cond";
}

export function extractHost(url: string): string {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname;
  } catch {
    throw new Error(`Invalid URL: ${url}`);
  }
}
