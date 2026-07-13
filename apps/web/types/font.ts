export type FontKey =
  | "pretendard" | "blackHanSans" | "jua" | "doHyeon" | "gowunBatang"
  | "nanumMyeongjo" | "kirangHaerang" | "gaegu" | "songMyung";

export type Category = "고딕" | "명조" | "손글씨" | "장식";
export type Tier = "free" | "paid";
export type Commercial = "yes" | "conditional" | "no";
export type TrendChange = "up" | "down" | "hold" | "new";

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
  license: { commercial: Commercial; verifiedAt: string };
  officialUrl: string;
  aliases: string[];
  freeAlternatives?: string[]; // 실제 slug, 최대 3
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
