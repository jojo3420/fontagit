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
  blackHanSans: "var(--font-black-han-sans)",
  jua: "var(--font-jua)",
  doHyeon: "var(--font-do-hyeon)",
  gowunBatang: "var(--font-gowun-batang)",
  nanumMyeongjo: "var(--font-nanum-myeongjo)",
  kirangHaerang: "var(--font-kirang-haerang)",
  gaegu: "var(--font-gaegu)",
  songMyung: "var(--font-song-myung)",
};
