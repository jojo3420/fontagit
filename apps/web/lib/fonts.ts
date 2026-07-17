import {
  Black_Han_Sans, Jua, Do_Hyeon, Gowun_Batang, Nanum_Myeongjo,
  Kirang_Haerang, Gaegu, Song_Myung,
} from "next/font/google";
import type { FontKey } from "@/types/font";

const blackHanSans = Black_Han_Sans({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
  preload: false,
  variable: "--font-black-han-sans",
});

const jua = Jua({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
  preload: false,
  variable: "--font-jua",
});

const doHyeon = Do_Hyeon({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
  preload: false,
  variable: "--font-do-hyeon",
});

const gowunBatang = Gowun_Batang({
  subsets: ["latin"],
  weight: ["400", "700"],
  display: "swap",
  preload: false,
  variable: "--font-gowun-batang",
});

const nanumMyeongjo = Nanum_Myeongjo({
  subsets: ["latin"],
  weight: ["400", "700", "800"],
  display: "swap",
  preload: false,
  variable: "--font-nanum-myeongjo",
});

const kirangHaerang = Kirang_Haerang({
  subsets: ["latin"],
  weight: "400",
  display: "swap",
  preload: false,
  variable: "--font-kirang-haerang",
});

const gaegu = Gaegu({
  subsets: ["latin"],
  weight: ["300", "400", "700"],
  display: "swap",
  preload: false,
  variable: "--font-gaegu",
});

// Song_Myung: next/font/google 타입이 subsets, preload 미지원 — 생략
const songMyung = Song_Myung({
  weight: "400",
  display: "swap",
  variable: "--font-song-myung",
});

export const fontClassNames = [
  blackHanSans.variable,
  jua.variable,
  doHyeon.variable,
  gowunBatang.variable,
  nanumMyeongjo.variable,
  kirangHaerang.variable,
  gaegu.variable,
  songMyung.variable,
].join(" ");

export const fontKeyToVar: Record<FontKey, string> = {
  pretendard: '"Pretendard Variable", "Pretendard", sans-serif',
  blackHanSans: "var(--font-black-han-sans), system-ui, sans-serif",
  jua: "var(--font-jua), system-ui, sans-serif",
  doHyeon: "var(--font-do-hyeon), system-ui, sans-serif",
  gowunBatang: "var(--font-gowun-batang), system-ui, sans-serif",
  nanumMyeongjo: "var(--font-nanum-myeongjo), system-ui, sans-serif",
  kirangHaerang: "var(--font-kirang-haerang), system-ui, sans-serif",
  gaegu: "var(--font-gaegu), system-ui, sans-serif",
  songMyung: "var(--font-song-myung), system-ui, sans-serif",
};

function primaryFamily(fontFamily: string): string {
  return fontFamily.split(",")[0].trim();
}

const fontKeyToCanvasFamily: Record<FontKey, string> = {
  pretendard: '"Pretendard Variable"',
  blackHanSans: primaryFamily(blackHanSans.style.fontFamily),
  jua: primaryFamily(jua.style.fontFamily),
  doHyeon: primaryFamily(doHyeon.style.fontFamily),
  gowunBatang: primaryFamily(gowunBatang.style.fontFamily),
  nanumMyeongjo: primaryFamily(nanumMyeongjo.style.fontFamily),
  kirangHaerang: primaryFamily(kirangHaerang.style.fontFamily),
  gaegu: primaryFamily(gaegu.style.fontFamily),
  songMyung: primaryFamily(songMyung.style.fontFamily),
};

export function familyOf(fontKey: FontKey | null): string {
  return fontKey ? fontKeyToVar[fontKey] : '"Pretendard Variable", "Pretendard", sans-serif';
}

/** Canvas API는 CSS var()를 해석하지 못하므로 실제 생성된 폰트명을 반환한다. */
export function canvasFamilyOf(fontKey: FontKey | null): string | null {
  return fontKey ? fontKeyToCanvasFamily[fontKey] : null;
}
