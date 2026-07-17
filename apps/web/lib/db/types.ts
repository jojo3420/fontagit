import type { SourceTier } from "@/types/font";

export interface FontRow {
  id: string;
  slug: string;
  name_en: string;
  name_ko: string | null;
  foundry: string | null;
  source_tier?: SourceTier;
  category_ko: string;
  weights: number[];
  is_commercial_free: boolean;
  license_type: string | null;
  official_url: string | null;
  last_modified: string | null;
  status: "draft" | "published" | "archived" | "hold" | "discontinued";
  subsets: string[];
}

export interface AliasRow {
  id: string;
  font_id: string;
  alias: string;
}

export interface CollectionRow {
  id: string;
  slug: string;
  title: string;
  intro: string;
  status: "draft" | "published" | "archived";
  sort_order: number;
  created_at: string;
}

export interface CollectionItemRow {
  collection_id: string;
  font_id: string;
  comment: string | null;
  sort_order: number;
}

export interface SearchResult {
  slug: string;
  nameKo: string | null;
  nameEn: string;
  tier: 'free' | 'paid';
  category: string;
  foundry?: string | null;
}

export interface ReportRow {
  id: string;
  font_id: string | null;
  reason: string;
  detail: string | null;
  contact: string | null;
  created_at: string;
}
