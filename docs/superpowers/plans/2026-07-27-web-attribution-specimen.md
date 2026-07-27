# 웹 표기 정리 + 견본 문구 풀 구현 계획 (S4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상세 화면 견본 초기 문구를 폰트 분류별 풀(30개)에서 결정적으로 선택하고(셔플 버튼 포함), 다운로드 CTA를 출처 등급(archive)에 따라 정직하게 라벨링한다.

**Architecture:** 문구 풀은 순수 데이터+선택 유틸(`specimenPhrases.ts`)로 분리하고, DetailSpecimenPanel의 초기 텍스트만 교체한다(SSG 안전: slug 해시 고정 선택, 랜덤은 사용자 액션에서만). 다운로드 등급은 FontRow → mappers → Font 타입으로 1필드 노출 후 LicenseSummaryCard에서 라벨 분기.

**Tech Stack:** Next.js(output: export), TypeScript, Vitest + @testing-library/react

**Spec:** `docs/superpowers/specs/2026-07-27-license-audit-crawl-design.md` (S4)

## Global Constraints

- SSG 정합: 초기 렌더 값은 결정적(slug 해시). `Math.random()`은 초기 렌더에서 금지, 셔플 버튼 핸들러 안에서만 허용
- 견본 문구 풀은 한국어 폰트(resolveSpecimenLanguage === "korean")에만 적용. english/mixed는 기존 로직 유지(글리프 확인 목적 보존)
- 테스트: `pnpm --filter web test` (Vitest). db import 컴포넌트는 db mock 필수(메모리: 웹 테스트 env 함정)
- 스펙의 "태그 그룹별"은 **category 기반 그룹**으로 구현한다(웹 Font 타입에 tags 미노출 실측 — category가 대표 분류)
- Type 100%, 하드코딩 대신 데이터 파일/상수

---

### Task 1: 문구 풀 데이터 + 결정적 선택 유틸

**Files:**
- Create: `apps/web/lib/specimenPhrases.ts`
- Test: `apps/web/lib/specimenPhrases.test.ts`

**Interfaces:**
- Consumes: `Font` 타입(`@/types/font`) 중 `slug`, `category`
- Produces: `pickPhrase(font: Pick<Font, "slug" | "category">): Phrase`, `nextPhrase(font, currentId: string): Phrase`, `type Phrase = { id: string; text: string }`, `PHRASE_GROUPS`(테스트용 export)

- [ ] **Step 1: 실패하는 테스트 작성**

```typescript
import { describe, expect, it } from "vitest";
import { PHRASE_GROUPS, nextPhrase, pickPhrase } from "@/lib/specimenPhrases";

describe("specimenPhrases", () => {
  it("전체 풀은 30개, id 중복 없음", () => {
    const all = Object.values(PHRASE_GROUPS).flat();
    expect(all).toHaveLength(30);
    expect(new Set(all.map((p) => p.id)).size).toBe(30);
  });

  it("같은 slug는 항상 같은 문구(결정적)", () => {
    const font = { slug: "nanum-myeongjo", category: "명조" };
    expect(pickPhrase(font)).toEqual(pickPhrase(font));
  });

  it("category 키워드 매칭: 명조→serif 그룹, 미매칭 category→common 그룹", () => {
    const serif = pickPhrase({ slug: "a", category: "명조" });
    expect(PHRASE_GROUPS.serif.some((p) => p.id === serif.id)).toBe(true);
    const fallback = pickPhrase({ slug: "a", category: "알 수 없음" });
    expect(PHRASE_GROUPS.common.some((p) => p.id === fallback.id)).toBe(true);
  });

  it("nextPhrase는 같은 그룹 안에서 순환하고 현재 문구와 다르다", () => {
    const font = { slug: "jamsil", category: "고딕" };
    const first = pickPhrase(font);
    const second = nextPhrase(font, first.id);
    expect(second.id).not.toBe(first.id);
    expect(PHRASE_GROUPS.sans.some((p) => p.id === second.id)).toBe(true);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `pnpm --filter web test -- specimenPhrases`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현** (`specimenPhrases.ts`)

```typescript
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
```

- [ ] **Step 4: 통과 확인**

Run: `pnpm --filter web test -- specimenPhrases`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/specimenPhrases.ts apps/web/lib/specimenPhrases.test.ts
git commit -m "feat: 견본 문구 풀 30개 + 결정적 선택 유틸"
```

---

### Task 2: 상세 견본 초기 문구 교체 + 셔플 버튼

**Files:**
- Modify: `apps/web/components/DetailSpecimenPanel.tsx` (83행 `useState(getDefaultSpecimenText(font))` 부근과 SpecimenBox 렌더부)
- Modify: `apps/web/components/DetailSpecimenPanel.module.css` (셔플 버튼 스타일 1클래스)
- Test: `apps/web/components/DetailSpecimenPanel.test.tsx` (기존 파일에 추가, 없으면 생성)

**Interfaces:**
- Consumes: `pickPhrase`/`nextPhrase` (Task 1), `resolveSpecimenLanguage` (`@/lib/specimen`), 기존 `SpecimenBox` controlled props(`text`, `onTextChange`)
- Produces: UI 변경만(신규 export 없음)

- [ ] **Step 1: 실패하는 테스트 작성**

기존 웹 테스트 패턴(vi.mock, data/fonts) 준수. 한국어 verified 폰트와 mixed 폰트 케이스:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DetailSpecimenPanel } from "@/components/DetailSpecimenPanel";
import { pickPhrase } from "@/lib/specimenPhrases";
import { fonts } from "@/data/fonts";

vi.mock("@/lib/db/clicks", () => ({ recordClick: vi.fn() }));

describe("DetailSpecimenPanel 견본 문구 풀", () => {
  it("한국어 verified 폰트는 slug 해시로 고른 풀 문구가 초기값", () => {
    const korean = fonts.find((f) => f.scriptStatus === "verified" && f.subsets.includes("korean"))!;
    render(<DetailSpecimenPanel font={korean} editable caption={undefined} />);
    expect(screen.getByDisplayValue(pickPhrase(korean).text)).toBeInTheDocument();
  });

  it("scriptStatus 미검증 폰트는 기존 글리프 확인 문구 유지", () => {
    const mixed = fonts.find((f) => f.scriptStatus !== "verified")!;
    render(<DetailSpecimenPanel font={mixed} editable caption={undefined} />);
    expect(screen.getByDisplayValue("가나다 ABCabc 12345")).toBeInTheDocument();
  });

  it("다른 문구 버튼을 누르면 같은 그룹의 다음 문구로 바뀐다", () => {
    const korean = fonts.find((f) => f.scriptStatus === "verified" && f.subsets.includes("korean"))!;
    render(<DetailSpecimenPanel font={korean} editable caption={undefined} />);
    const first = pickPhrase(korean);
    fireEvent.click(screen.getByRole("button", { name: "다른 문구" }));
    expect(screen.queryByDisplayValue(first.text)).not.toBeInTheDocument();
  });
});
```

주의: SpecimenBox의 텍스트 입력이 `getByDisplayValue`로 안 잡히는 마크업(contentEditable 등)이면 기존 SpecimenBox 테스트의 조회 방식을 그대로 따른다.

- [ ] **Step 2: 실패 확인**

Run: `pnpm --filter web test -- DetailSpecimenPanel`
Expected: FAIL (초기값이 기존 팬그램)

- [ ] **Step 3: 구현**

DetailSpecimenPanel.tsx:

```tsx
import { nextPhrase, pickPhrase } from "@/lib/specimenPhrases";
import { getDefaultSpecimenText, resolveSpecimenLanguage } from "@/lib/specimen";

// 컴포넌트 내부
const usePhrasePool = resolveSpecimenLanguage(font) === "korean";
const initialPhrase = usePhrasePool ? pickPhrase(font) : null;
const [phraseId, setPhraseId] = useState<string | null>(initialPhrase?.id ?? null);
const [text, setText] = useState(initialPhrase?.text ?? getDefaultSpecimenText(font));

const handleShuffle = () => {
  if (!phraseId) return;
  const phrase = nextPhrase(font, phraseId);
  setPhraseId(phrase.id);
  setText(phrase.text);
};
```

SpecimenBox 아래(또는 caption 영역 옆)에 버튼 추가 — 문구 풀 사용 시에만 노출:

```tsx
{usePhrasePool && (
  <button type="button" className={styles.shuffle} onClick={handleShuffle}>
    다른 문구
  </button>
)}
```

module.css에 `.shuffle` 클래스(기존 버튼 토큰 재사용, 신규 색상 하드코딩 금지).

- [ ] **Step 4: 통과 확인 + 전체 회귀**

Run: `pnpm --filter web test`
Expected: 전체 PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/DetailSpecimenPanel.tsx apps/web/components/DetailSpecimenPanel.module.css apps/web/components/DetailSpecimenPanel.test.tsx
git commit -m "feat: 상세 견본 초기 문구 풀 적용 + 다른 문구 버튼"
```

---

### Task 3: downloadSourceKind 노출 + 다운로드 CTA 라벨 분기

**Files:**
- Modify: `apps/web/lib/db/types.ts:23` (`download_source_kind` union에 "archive" 추가)
- Modify: `apps/web/types/font.ts` (Font에 `downloadSourceKind` 필드)
- Modify: `apps/web/lib/db/mappers.ts:78` 부근 (downloadSourceKind 노출)
- Modify: `apps/web/components/LicenseSummaryCard.tsx:55` (ctaLabel 분기)
- Test: `apps/web/components/LicenseSummaryCard.test.tsx`

**Interfaces:**
- Consumes: `FontRow.download_source_kind`, 기존 `downloadHref` 계산식(LicenseSummaryCard.tsx:58-62)
- Produces: `Font.downloadSourceKind?: "official" | "public" | "archive" | null` (옵셔널 — data/fonts 정적 데이터 무수정)

- [ ] **Step 1: 실패하는 테스트 작성** (LicenseSummaryCard.test.tsx에 추가)

```tsx
it("archive 등급 다운로드는 아카이브 라벨, official은 기존 라벨", () => {
  const base = fonts.find((f) => f.slug === "nanum-myeongjo") ?? fonts[0];
  const verified: Font = {
    ...base,
    tier: "free",
    downloadStatus: "verified",
    downloadUrl: "https://fonts.google.com/specimen/Nanum+Myeongjo",
    downloadSourceKind: "archive",
    licenseAudit: { ...base.licenseAudit!, status: "verified" },
  };
  const { rerender } = render(<LicenseSummaryCard font={verified} />);
  expect(screen.getByText("다운로드 페이지로 이동(아카이브 제공)")).toBeInTheDocument();

  rerender(<LicenseSummaryCard font={{ ...verified, downloadSourceKind: "official" }} />);
  expect(screen.getByText("공식 페이지에서 내려받기")).toBeInTheDocument();
});
```

주의: `licenseAudit` 실제 필드명-필수 여부는 `types/font.ts:39-67` 확인 후 fixture를 맞춘다(임의 필드 추가 금지).

- [ ] **Step 2: 실패 확인**

Run: `pnpm --filter web test -- LicenseSummaryCard`
Expected: FAIL (타입 오류 또는 라벨 없음)

- [ ] **Step 3: 구현**

types.ts:23:

```typescript
download_source_kind?: "official" | "public" | "archive" | null;
```

types/font.ts(Font 인터페이스):

```typescript
downloadSourceKind?: "official" | "public" | "archive" | null;
```

mappers.ts(downloadUrl 줄 바로 아래):

```typescript
downloadSourceKind: row.download_source_kind ?? null,
```

LicenseSummaryCard.tsx:55 교체:

```typescript
const ctaLabel = isPaid
  ? "구매하러 가기"
  : font.downloadSourceKind === "archive"
    ? "다운로드 페이지로 이동(아카이브 제공)"
    : "공식 페이지에서 내려받기";
```

- [ ] **Step 4: 통과 확인 + lint**

Run: `pnpm --filter web test && pnpm --filter web lint`
Expected: PASS / 경고 없음

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/db/types.ts apps/web/types/font.ts apps/web/lib/db/mappers.ts apps/web/components/LicenseSummaryCard.tsx apps/web/components/LicenseSummaryCard.test.tsx
git commit -m "feat: 다운로드 출처 등급 노출 + CTA 라벨 분기 (#120)"
```

---

### 수용 기준 (파이프라인 데이터 적용 후 최종 확인)

- 나눔명조 상세: 제작사 표기 "네이버"(제작사 홈페이지 링크 = hangeul.naver.com 계열), 다운로드 CTA가 등급에 맞는 라벨, 원문 보기가 실제 약관 페이지
- 한국어 폰트 상세 2곳 이상에서 서로 다른 초기 견본 문구 확인(SSG 빌드 산출물 기준)
- `pnpm --filter web build` 통과(2,508페이지 회귀 없음)

## Self-Review 결과

- 스펙 S4 커버: 견본 풀→Task1-2, 표기 정리(CTA 등급 라벨)→Task3, 제작사/원문 데이터 정정은 파이프라인 계획(Task7)과 수용 기준에서 연결
- "태그 그룹별"→category 기반으로 구현 확정(웹에 tags 미노출 실측). 스펙 의도(폰트 성격별 문구)는 유지
- 타입 일관성: downloadSourceKind 옵셔널로 정적 data/fonts 회귀 없음. Phrase/PhraseGroupKey는 Task1 정의를 Task2가 소비
