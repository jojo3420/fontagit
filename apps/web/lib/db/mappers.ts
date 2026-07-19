import {
  Font,
  Collection,
  Category,
  CollectionFontItem,
  FontKey,
  type AuditPermission,
} from "@/types/font";
import { FontRow, CollectionRow } from "./types";

const SLUG_TO_FONTKEY: Record<string, FontKey | null> = {
  pretendard: "pretendard",
  "black-han-sans": "blackHanSans",
  jua: "jua",
  "do-hyeon": "doHyeon",
  "gowun-batang": "gowunBatang",
  "nanum-myeongjo": "nanumMyeongjo",
  "kirang-haerang": "kirangHaerang",
  gaegu: "gaegu",
  "song-myung": "songMyung",
};

export function rowToFont(row: FontRow, aliases: string[]): Font {
  const hasLicenseAuditEvidence = Boolean(
    row.license_source_url
      || row.license_summary
      || row.license_source_kind
      || row.license_checked_at
      || row.license_evidence_id
      || row.allow_commercial
      || row.allow_modify
      || row.allow_redistribute
      || row.allow_embedding
      || row.allow_font_sale
      || row.attribution_requirement,
  );
  const licenseStatus = row.license_status ?? "pending";
  const licenseSourceMode = licenseStatus === "pending" && !hasLicenseAuditEvidence
    ? "legacy"
    : "audit";
  const hasDownloadAuditEvidence = Boolean(
    row.download_url
      || row.download_source_kind
      || row.download_checked_at
      || row.download_evidence_id,
  );
  const downloadStatus = row.download_status ?? "pending";
  const legacyOfficialUrl = licenseSourceMode === "legacy"
    && downloadStatus === "pending"
    && !hasDownloadAuditEvidence
    ? row.official_url
    : null;
  const permission = (value: FontRow["allow_commercial"]): AuditPermission => value ?? "unknown";

  return {
    id: row.id,
    slug: row.slug,
    nameKo: row.name_ko ?? row.name_en,
    nameEn: row.name_en,
    fontKey: SLUG_TO_FONTKEY[row.slug] ?? null,
    sourceTier: row.source_tier,
    tier: row.is_commercial_free ? "free" : "paid",
    category: row.category_ko as Category,
    foundry: row.foundry ?? "",
    availableWeights: row.weights.length > 0 ? row.weights : [400],
    moves: 0,
    license: {
      commercial: row.is_commercial_free ? "yes" : "no",
      verifiedAt: row.last_modified ?? "",
      type: row.license_type ?? "",
      webfont: "included",
      redistribution: "yes",
    },
    officialUrl: row.official_url ?? "",
    downloadUrl: downloadStatus === "verified" ? row.download_url ?? null : null,
    foundryUrl: row.foundry_url ?? null,
    legacyOfficialUrl,
    downloadStatus,
    licenseAudit: {
      status: licenseStatus,
      sourceMode: licenseSourceMode,
      summary: row.license_summary ?? null,
      sourceUrl: row.license_source_url ?? null,
      sourceKind: row.license_source_kind ?? null,
      checkedAt: row.license_checked_at ?? null,
      commercial: permission(row.allow_commercial),
      modify: permission(row.allow_modify),
      redistribute: permission(row.allow_redistribute),
      embedding: permission(row.allow_embedding),
      fontSale: permission(row.allow_font_sale),
      attribution: row.attribution_requirement ?? "unknown",
    },
    scriptStatus: row.script_status ?? "pending",
    aliases,
    freeAlternatives: undefined,
    status: row.status,
    subsets: row.subsets ?? [],
  };
}

export function rowToCollection(
  row: CollectionRow,
  items: CollectionFontItem[]
): Collection {
  return {
    slug: row.slug,
    title: row.title,
    intro: row.intro,
    items,
  };
}
