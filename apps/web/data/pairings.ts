export interface ComparePreset {
  heroSlug: string;
  gridSlugs: string[];
}

export interface FontPairing {
  id: string;
  title: string;
  description: string;
  heroSlug: string;
  bodySlug: string;
}

/** 비교 보드에 로드할 제목+본문 추천 조합. slug는 data/fonts.ts 무료 폰트만 사용 */
export const PAIRINGS: FontPairing[] = [
  {
    id: "impact-title",
    title: "임팩트 헤드라인",
    description: "포스터-배너에 어울리는 조합",
    heroSlug: "black-han-sans",
    bodySlug: "pretendard",
  },
  {
    id: "warm-essay",
    title: "포근한 에세이",
    description: "블로그-에세이에 어울리는 조합",
    heroSlug: "jua",
    bodySlug: "gowun-batang",
  },
  {
    id: "classic-editorial",
    title: "고전 에디토리얼",
    description: "잡지-아티클에 어울리는 조합",
    heroSlug: "do-hyeon",
    bodySlug: "nanum-myeongjo",
  },
];
