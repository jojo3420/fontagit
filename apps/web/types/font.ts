export type FontKey =
  | "pretendard" | "blackHanSans" | "jua" | "doHyeon" | "gowunBatang"
  | "nanumMyeongjo" | "kirangHaerang" | "gaegu" | "songMyung";

export type Category = "고딕" | "명조" | "손글씨" | "장식";
export type Tier = "free" | "paid";
export type Commercial = "yes" | "conditional" | "no";
export type LicenseWebfont = "included" | "separate" | "no";
export type LicenseRedistribution = "yes" | "no";
export type LicenseType = "SIL OFL" | "Proprietary";
export type LicenseState = "ok" | "cond";
export type TrendChange = "up" | "down" | "hold" | "new";

export interface License {
  commercial: Commercial;
  verifiedAt: string;
  type: LicenseType;
  webfont: LicenseWebfont;
  redistribution: LicenseRedistribution;
}

export interface Font {
  slug: string;
  nameKo: string;
  nameEn: string;
  fontKey: FontKey;
  tier: Tier;
  category: Category;
  foundry: string;
  availableWeights: number[]; // 단일 굵기 폰트는 [400]
  moves: number;
  license: License;
  officialUrl: string;
  aliases: string[];
  freeAlternatives?: string[]; // 실제 slug, 최대 3
  priceFrom?: number;
}

export interface TrendItem {
  rank: number;
  change: TrendChange;
  changeAmount?: number;
  font: Pick<Font, "slug" | "nameKo" | "fontKey" | "tier">;
  moves: number;
}

export interface Collection {
  slug: string; title: string; intro: string;
  items: { fontSlug: string; comment: string }[];
}
