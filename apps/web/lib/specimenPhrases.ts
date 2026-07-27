/** 견본 문구 풀: 분류 그룹별 6개 x 5그룹 = 30개. id는 영구 고정(선택 안정성). */
export type Phrase = { id: string; text: string };
export type PhraseGroupKey = "serif" | "sans" | "hand" | "display" | "common";

export const PHRASE_GROUPS: Record<PhraseGroupKey, Phrase[]> = {
  serif: [
    { id: "serif-01", text: "밤하늘의 별빛이 종이 위에 내려앉았다" },
    { id: "serif-02", text: "오래된 서점에서 발견한 한 권의 시집" },
    { id: "serif-03", text: "겨울 창가에 스며드는 아침 햇살처럼" },
    { id: "serif-04", text: "문장은 마음을 담는 가장 오래된 그릇이다" },
    { id: "serif-05", text: "천천히 읽어도 좋은 글이 있다" },
    { id: "serif-06", text: "강물은 소리 없이 바다로 향한다" },
  ],
  sans: [
    { id: "sans-01", text: "간결한 화면이 좋은 경험을 만든다" },
    { id: "sans-02", text: "오늘의 할 일: 커피, 코드, 산책" },
    { id: "sans-03", text: "정보는 명확하게, 디자인은 담백하게" },
    { id: "sans-04", text: "새로운 프로젝트를 시작하는 가장 좋은 날" },
    { id: "sans-05", text: "지하철 노선도처럼 한눈에 들어오는 글" },
    { id: "sans-06", text: "화면 속 글자에도 온도가 있다" },
  ],
  hand: [
    { id: "hand-01", text: "네가 보고 싶어서 편지를 써" },
    { id: "hand-02", text: "오늘도 수고했어, 내일은 더 잘될 거야" },
    { id: "hand-03", text: "냉장고에 붙여둔 작은 메모 한 장" },
    { id: "hand-04", text: "일기장 첫 페이지에 쓰는 다짐" },
    { id: "hand-05", text: "손으로 꾹꾹 눌러 쓴 생일 축하 카드" },
    { id: "hand-06", text: "비 오는 날엔 따뜻한 코코아 한 잔" },
  ],
  display: [
    { id: "display-01", text: "오늘 단 하루! 전 품목 특가" },
    { id: "display-02", text: "새로운 시즌, 새로운 시작" },
    { id: "display-03", text: "주말엔 팝업 스토어로 놀러 오세요" },
    { id: "display-04", text: "심야 상영회: 별빛 아래 영화 한 편" },
    { id: "display-05", text: "한정판 굿즈 드디어 출시" },
    { id: "display-06", text: "축제의 계절이 돌아왔다" },
  ],
  common: [
    { id: "common-01", text: "다람쥐 헌 쳇바퀴에 타고파" },
    { id: "common-02", text: "맑은 아침, 창을 열고 크게 숨을 쉰다" },
    { id: "common-03", text: "글자는 생각을 옮기는 다리입니다" },
    { id: "common-04", text: "좋아하는 노래를 들으며 걷는 길" },
    { id: "common-05", text: "책상 위 화분에 물을 주는 시간" },
    { id: "common-06", text: "느리게 흘러가는 일요일 오후" },
  ],
};

const CATEGORY_KEYWORD_TO_GROUP: Array<[string, PhraseGroupKey]> = [
  ["명조", "serif"],
  ["바탕", "serif"],
  ["세리프", "serif"],
  ["고딕", "sans"],
  ["돋움", "sans"],
  ["손글씨", "hand"],
  ["손글", "hand"],
  ["캘리", "hand"],
  ["장식", "display"],
  ["디스플레이", "display"],
];

function groupForCategory(category: string): PhraseGroupKey {
  for (const [keyword, group] of CATEGORY_KEYWORD_TO_GROUP) {
    if (category.includes(keyword)) return group;
  }
  return "common";
}

/** djb2 문자열 해시 — 렌더마다 동일해야 하므로 Math.random 금지 */
function hashSlug(slug: string): number {
  let hash = 5381;
  for (let i = 0; i < slug.length; i += 1) {
    hash = (hash * 33) ^ slug.charCodeAt(i);
  }
  return hash >>> 0;
}

export function pickPhrase(font: { slug: string; category: string }): Phrase {
  const pool = PHRASE_GROUPS[groupForCategory(font.category)];
  return pool[hashSlug(font.slug) % pool.length];
}

export function nextPhrase(font: { slug: string; category: string }, currentId: string): Phrase {
  const pool = PHRASE_GROUPS[groupForCategory(font.category)];
  const index = pool.findIndex((p) => p.id === currentId);
  return pool[(index + 1 + pool.length) % pool.length];
}
