import type { TrendItem } from "@/types/font";
import { getAllFonts } from "./fonts";

/**
 * ⚠️ 슬라이스1 임시 트렌드 (클릭집계 없음)
 * 슬라이스3에서 실 클릭집계(get_top_fonts RPC) 기반으로 교체 예정
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
