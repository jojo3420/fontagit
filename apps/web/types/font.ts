export type FontKey =
  | "pretendard" | "blackHanSans" | "jua" | "doHyeon" | "gowunBatang"
  | "nanumMyeongjo" | "kirangHaerang" | "gaegu" | "songMyung";

export type Category = "고딕" | "명조" | "손글씨" | "장식";
export type Tier = "free" | "paid";
export type SourceTier = "A" | "B" | "C";
export type Commercial = "yes" | "conditional" | "no";
export type LicenseWebfont = "included" | "separate" | "no";
export type LicenseRedistribution = "yes" | "no";
export type TrendChange = "up" | "down" | "hold" | "new";
export type AuditPermission = "allowed" | "conditional" | "denied" | "unknown";
export type AuditStatus = "pending" | "verified" | "needs_review" | "broken";
export type ScriptStatus = "pending" | "verified" | "needs_review";

export interface FontLicenseAudit {
  status: AuditStatus;
  sourceMode: "audit" | "legacy";
  summary: string | null;
  sourceUrl: string | null;
  sourceKind: "official" | "public" | null;
  checkedAt: string | null;
  commercial: AuditPermission;
  modify: AuditPermission;
  redistribute: AuditPermission;
  embedding: AuditPermission;
  fontSale: AuditPermission;
  attribution: "required" | "recommended" | "not_required" | "unknown";
}

export interface License {
  commercial: Commercial;
  verifiedAt: string;
  type: string;
  webfont: LicenseWebfont;
  redistribution: LicenseRedistribution;
}

export interface Font {
  id?: string;
  slug: string;
  nameKo: string;
  nameEn: string;
  fontKey: FontKey | null;
  sourceTier?: SourceTier;
  tier: Tier;
  category: Category;
  foundry: string;
  availableWeights: number[]; // 단일 굵기 폰트는 [400]
  moves: number;
  license: License;
  /** 이전 데이터 호환용 주소. 신규 화면은 아래 감사 필드를 우선한다. */
  officialUrl: string;
  downloadUrl?: string | null;
  foundryUrl?: string | null;
  legacyOfficialUrl?: string | null;
  downloadStatus?: AuditStatus;
  licenseAudit?: FontLicenseAudit;
  scriptStatus?: ScriptStatus;
  aliases: string[];
  freeAlternatives?: string[]; // 실제 slug, 최대 3
  priceFrom?: number;
  status?: "draft" | "published" | "archived" | "hold" | "discontinued";
  subsets: string[]; // 예: ["korean"], ["latin"], ["korean", "latin"]
}

export interface TrendItem {
  rank: number;
  change: TrendChange;
  changeAmount?: number;
  font: Pick<Font, "slug" | "nameKo" | "fontKey" | "tier">;
  moves: number;
}

export interface CollectionFontItem {
  slug: string;
  nameKo: string;
  fontKey: FontKey | null;
  tier: Tier;
  comment: string;
}

export interface Collection {
  slug: string;
  title: string;
  intro: string;
  items: CollectionFontItem[];
}
