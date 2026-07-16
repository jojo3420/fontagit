import type { TrendItem } from "@/types/font";
import { getAllFonts } from "./fonts";

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
