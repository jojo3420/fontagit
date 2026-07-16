import type { TrendItem } from "@/types/font";
import { supabaseClient } from "./client";
import { getAllFonts } from "./fonts";

export type TrendsSource = "clicks" | "latest";

export interface TrendsResult {
  source: TrendsSource;
  items: TrendItem[];
}

interface RPCTopFontRow {
  slug: string;
  name_ko: string | null;
  name_en: string;
  tier: "free" | "paid";
  clicks: number;
}

/**
 * 빌드타임 Top10 (이동 클릭 기준, get_top_fonts RPC — 기획서 7-4).
 * 클릭 데이터 0건이면 "최신 등록" 폴백(source='latest') — UI 라벨도 함께 전환해야 정직성 유지.
 * RPC 오류는 throw해 SSG 빌드 실패로 드러낸다(조용한 폴백 금지).
 */
export async function getTrends(): Promise<TrendsResult> {
  const { data, error } = await supabaseClient.rpc("get_top_fonts", {});

  if (error) {
    console.error("[trends] get_top_fonts RPC error:", error);
    const err = new Error("TRENDS_RPC_FAILED");
    err.cause = error;
    throw err;
  }

  const rows = (data ?? []) as RPCTopFontRow[];
  if (rows.length === 0) {
    return { source: "latest", items: await getLatestFallback() };
  }

  return {
    source: "clicks",
    items: rows.map((row, index): TrendItem => ({
      rank: index + 1,
      // 전주 비교 데이터가 아직 없어 변동 표기는 전부 "new" (롤업 도입 후 개선)
      change: "new",
      font: {
        slug: row.slug,
        nameKo: row.name_ko ?? row.name_en,
        fontKey: null,
        tier: row.tier,
      },
      moves: row.clicks,
    })),
  };
}

async function getLatestFallback(): Promise<TrendItem[]> {
  const fonts = await getAllFonts();
  return fonts.slice(0, 10).map((font, index): TrendItem => ({
    rank: index + 1,
    change: "new",
    font: {
      slug: font.slug,
      nameKo: font.nameKo,
      fontKey: font.fontKey,
      tier: font.tier,
    },
    moves: font.moves,
  }));
}

/**
 * ⚠️ 슬라이스1 임시 트렌드 (클릭집계 없음, 실제는 최신 등록순)
 * UI는 "인기/이동 클릭 기준"으로 표기하지만 데이터는 최신 등록순이다.
 * 슬라이스3에서 실 클릭집계(get_top_fonts RPC)로 교체해야 표기가 사실이 된다.
 * prod 배포 전 슬라이스3 완료 필수 - 그전 배포 시 인기 표기가 사실과 달라 정직성 위반(기획서 7-1).
 */
export async function getTemporaryTrends(): Promise<TrendItem[]> {
  const fonts = await getAllFonts();
  return fonts.slice(0, 10).map((font, index) => ({
    rank: index + 1,
    change: "new",
    font: {
      slug: font.slug,
      nameKo: font.nameKo,
      fontKey: font.fontKey,
      tier: font.tier,
    },
    moves: font.moves,
  }));
}
