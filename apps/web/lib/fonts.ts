import {
  Black_Han_Sans, Jua, Do_Hyeon, Gowun_Batang, Nanum_Myeongjo,
  Kirang_Haerang, Gaegu, Song_Myung,
} from "next/font/google";
import type { FontKey } from "@/types/font";

const base = { subsets: ["latin"] as const, display: "swap" as const, preload: false };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const blackHanSans = Black_Han_Sans({ ...base, weight: "400", variable: "--font-black-han-sans" } as any);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const jua = Jua({ ...base, weight: "400", variable: "--font-jua" } as any);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const doHyeon = Do_Hyeon({ ...base, weight: "400", variable: "--font-do-hyeon" } as any);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const gowunBatang = Gowun_Batang({ ...base, weight: ["400", "700"], variable: "--font-gowun-batang" } as any);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const nanumMyeongjo = Nanum_Myeongjo({ ...base, weight: ["400", "700", "800"], variable: "--font-nanum-myeongjo" } as any);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const kirangHaerang = Kirang_Haerang({ ...base, weight: "400", variable: "--font-kirang-haerang" } as any);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const gaegu = Gaegu({ ...base, weight: ["300", "400", "700"], variable: "--font-gaegu" } as any);
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const songMyung = Song_Myung({ ...base, weight: "400", variable: "--font-song-myung" } as any);

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const fontClassNames = [
  (blackHanSans as any).variable, (jua as any).variable, (doHyeon as any).variable, (gowunBatang as any).variable,
  (nanumMyeongjo as any).variable, (kirangHaerang as any).variable, (gaegu as any).variable, (songMyung as any).variable,
].join(" ");

export const fontKeyToVar: Record<FontKey, string> = {
  pretendard: '"Pretendard Variable", "Pretendard", sans-serif',
  blackHanSans: "var(--font-black-han-sans)",
  jua: "var(--font-jua)",
  doHyeon: "var(--font-do-hyeon)",
  gowunBatang: "var(--font-gowun-batang)",
  nanumMyeongjo: "var(--font-nanum-myeongjo)",
  kirangHaerang: "var(--font-kirang-haerang)",
  gaegu: "var(--font-gaegu)",
  songMyung: "var(--font-song-myung)",
};
