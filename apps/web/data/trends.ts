/**
 * ⚠️ 슬라이스1: 목업 데이터
 * 슬라이스3에서 실 클릭집계(get_top_fonts RPC) 기반으로 교체 예정
 */
import type { TrendItem, TrendChange } from "@/types/font";
import { fonts } from "@/data/fonts";

function row(rank: number, slug: string, change: TrendChange, changeAmount?: number): TrendItem {
  const f = fonts.find((x) => x.slug === slug)!;
  return { rank, change, changeAmount, moves: f.moves, font: { slug: f.slug, nameKo: f.nameKo, fontKey: f.fontKey, tier: f.tier } };
}

export const weeklyTrends: TrendItem[] = [
  row(1, "pretendard", "up", 2), row(2, "black-han-sans", "hold"),
  row(3, "jua", "up", 1), row(4, "do-hyeon", "down", 1),
  row(5, "gowun-batang", "new"), row(6, "nanum-myeongjo", "hold"),
  row(7, "sandoll-gothic-neo", "up", 3), row(8, "kirang-haerang", "down", 2),
  row(9, "gaegu", "new"), row(10, "song-myung", "hold"),
];

export const monthlyTrends: TrendItem[] = [
  row(1, "black-han-sans", "hold"), row(2, "pretendard", "up", 3),
  row(3, "jua", "down", 1), row(4, "nanum-myeongjo", "hold"),
  row(5, "gowun-batang", "up", 2), row(6, "do-hyeon", "down", 2),
  row(7, "gaegu", "new"), row(8, "sandoll-gothic-neo", "hold"),
  row(9, "kirang-haerang", "up", 1), row(10, "song-myung", "new"),
];
