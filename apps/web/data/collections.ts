import type { Collection } from "@/types/font";

export const collections: Collection[] = [
  {
    slug: "dawn-serif",
    title: "새벽 감성 명조 모음",
    intro: "긴 글에 어울리는, 획이 차분한 명조들을 모았어요. 에세이-브랜드 소개문-전자책 본문에 특히 잘 맞습니다.",
    items: [
      { fontSlug: "gowun-batang", comment: "공기 같은 가벼움. 본문 15px에서 눈이 편해요." },
      { fontSlug: "nanum-myeongjo", comment: "묵직한 제목용. 굵기 대비가 또렷합니다." },
      { fontSlug: "song-myung", comment: "고전적인 인상. 표지-인용구에 잘 어울려요." },
    ],
  },
  {
    slug: "brand-gothic",
    title: "브랜드 첫인상 고딕",
    intro: "로고와 헤드라인에서 또렷하게 읽히는 고딕을 모았어요. 포스터-배너-앱 UI에 두루 쓰기 좋습니다.",
    items: [
      { fontSlug: "pretendard", comment: "군더더기 없는 표준. 어디에 놔도 안정적이에요." },
      { fontSlug: "black-han-sans", comment: "굵고 강한 임팩트. 큰 제목에서 빛납니다." },
      { fontSlug: "do-hyeon", comment: "둥근 획의 친근함. 캐주얼한 브랜드에 잘 맞아요." },
    ],
  },
  {
    slug: "playful-hand",
    title: "손끝의 온기 손글씨",
    intro: "사람 손으로 쓴 듯한 따뜻함을 담은 서체 모음이에요. 카드-굿즈-SNS 문구에 잘 어울립니다.",
    items: [
      { fontSlug: "gaegu", comment: "삐뚤빼뚤 정겨움. 짧은 문구에 특히 좋아요." },
      { fontSlug: "kirang-haerang", comment: "붓끝의 여운. 감성적인 인용구에 어울립니다." },
      { fontSlug: "jua", comment: "동글동글 명랑함. 이벤트 배너에 활기를 더해요." },
    ],
  },
];
