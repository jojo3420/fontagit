# FontAgit 웹 Phase 3-4 (확장 화면 + 마감) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1-2로 완성한 웹 토대(홈/목록/상세/트렌드/404) 위에 확장 화면(타입 캔버스, 비교, 컬렉션, 창작자 등록, 빈 상태)과 마감 작업(모바일 정밀화, 다크모드 토글, 런칭 자산 OG)을 디자인 95% 재현으로 구현한다.

**Architecture:** Phase 1-2와 동일하게 Next.js 16 App Router를 정적 출력(`output: 'export'`)으로 서빙한다. 기존 컴포넌트(TierChip/LicenseBadge/Button/FilterChip/PreviewInput/Specimen/FontCard/FontGrid)와 데이터 헬퍼(`lib/data.ts`), 폰트 매핑(`lib/fonts.ts` `fontKeyToVar`)을 재사용한다. 라이브 인터랙션이 필요한 화면(캔버스/비교/다크토글/탭바)만 `"use client"` 컴포넌트로 분리하고, 나머지는 서버 컴포넌트로 정적 렌더한다. 컬렉션은 새 데이터 모델(`data/collections.ts`)을 추가하고 빌드 타임 무결성 검사를 확장한다.

**Tech Stack:** Next.js 16.2.10, React 19.2.4, TypeScript 5, CSS Modules, Vitest + React Testing Library, @playwright/test, `next/og`(OG 이미지).

## Global Constraints

Phase 1-2 계획서의 제약을 그대로 승계한다. 아래는 이번 범위에 적용되는 값 그대로다.

- 결과물 위치: `apps/web`. 패키지명은 `web`(루트 `pnpm --filter web`, `web:dev`/`web:build` 스크립트와 정합).
- 스타일은 CSS Modules + CSS 변수만 사용한다. 페이지/컴포넌트의 인라인 `style={{...}}` 금지 — 단, 데이터로 결정되는 `fontFamily`는 예외로 인라인 허용(기존 패턴과 동일).
- 워크스페이스: `apps/web`은 자체 `pnpm-lock.yaml`/`pnpm-workspace.yaml`을 갖는다. 설치/빌드는 `apps/web` 안에서 수행하고, 바뀐 `apps/web/pnpm-lock.yaml`은 반드시 커밋한다.
- 원본 디자인(시각 SSOT): `docs/design/fontagit-v2/project/FontAgit 화면 세트.dc.html`. 화면 ID — 캔버스 `3a`(라인 460-508), 비교 `5a`(257-274), 컬렉션 상세 `8a`(370-385), 등록 `8b`(386-402), 모바일 `4a/4b/4c`(178-254), 다크 `9b`(422-455), 파비콘/OG `7a/7b`(329-367). 픽셀 값은 소스를 옮긴다(그대로 렌더 금지).
- 스펙(SSOT): `docs/superpowers/specs/2026-07-12-fontagit-web-screens-design.md`.
- Next.js 16 주의(AGENTS.md): dynamic route의 `params`는 async — `params: Promise<{ slug: string }>` + `const { slug } = await params`. 코드 전 `apps/web/node_modules/next/dist/docs/`의 해당 가이드 확인. 기존 정본: `app/fonts/[slug]/page.tsx`(`dynamicParams=false` + `generateStaticParams` + `notFound()`).
- 정적 출력: `next.config.ts`에 `output: 'export'`, `images:{unoptimized:true}`, `trailingSlash:true`. 산출물 `out/`. 서버 전용 기능/런타임 리다이렉트 금지.
- 디자인 토큰(값 그대로, `styles/tokens.css`에 이미 정의됨): 배경 `#FAFAF8`, 잉크 `#1A1A1A`, 서브 `#6B6B6B`, 약한서브 `#9A9A96`, 경계 `#E6E6E2`, 표면 `#FFFFFF`, 보조표면 `#F4F4F0`, 포인트 `#2C5545`, 포인트약배경 `rgba(44,85,69,.1)`, on-point `#FFFFFF`. 상태색: 상승 `#2C7A5B`, 하락/불가 `#B4564B`, 유지 `#9A9A96`, 조건부 `#B4863C`. 다크: 배경 `#16171A`, 잉크 `#EDEDEA`, 포인트 `#7FC2A2`. CSS에서는 반드시 변수(`var(--point)` 등)로 참조 — 하드코딩 색 금지.
- 타이포: UI 텍스트는 항상 Pretendard, 견본 텍스트만 견본 폰트(`fontKeyToVar[fontKey]`)로 렌더.
- 포인트색은 액션에만. 라이선스 상태는 색 단독 금지 — `LicenseBadge`(아이콘+텍스트) 재사용.
- 보이스: 브랜드 층(로고/히어로/404/빈상태/등록 안내)은 존댓말 다정 담백, 정보 층은 건조한 사실만("안전/문제없음" 보증 표현 금지). 유료 폰트 견본은 `Specimen`의 `substitute` 라벨로 "대체 견본" 명시.
- 비동작 액션(필터 칩/프리셋/검색 등)은 `type="button"` + 필요 시 `aria-pressed`. 등록 폼은 시맨틱을 위해 `<form onSubmit={(e) => e.preventDefault()}>`(클라이언트 컴포넌트)로 두되 실제 제출/네비게이션은 하지 않는다.
- 95% 시각 판정: Chromium, 데스크톱 1280 / 모바일 390, DPR 1. Playwright 스크린샷 대조.
- 커밋 컨벤션: `<타입>: <설명>`(feat/fix/refactor/chore/test).

**Phase 3-4 추가 제약:**
- 컬렉션 무결성: `data/collections.ts`의 모든 `items[].fontSlug`는 실존 폰트 slug여야 한다. `assertDataIntegrity`를 확장해 컬렉션 slug 중복-빈 컬렉션-미실존 폰트 참조를 빌드 타임에 차단한다(블로커: 컬렉션 무결성 검증).
- 헤더 nav 404 해소(블로커): `/collections`(Task 4)-`/submit`(Task 5) 페이지가 생기면 해당 Task에서 `components/Header.tsx`의 그 링크 `prefetch={false}`를 제거해 정상 링크로 복원한다. 페이지 없는 링크만 `prefetch={false}` 유지.
- PR 리뷰(블로커: agy 리뷰 실패): 이번 PR 검증은 codex 단독 리뷰로 진행한다(agy는 stdin 프롬프트 미처리로 Degraded).
- 검증 원칙: 각 Task는 변경 성격에 맞는 검증으로 자립한다 — 데이터/로직 Task는 Vitest, 화면 Task는 build + Playwright 스모크, 모든 Task는 커밋 전 최소 `tsc --noEmit` + `pnpm build`를 통과한다(전 Task에 full 스위트를 강제하지 않는다).
- OG/아이콘 예외: `next/og`의 `ImageResponse`는 satori 렌더러라 CSS Modules/CSS 변수를 쓸 수 없다. `app/icon.tsx`와 `opengraph-image.tsx` 계열 파일에 한해 인라인 스타일 + 토큰 색상값 하드코딩을 허용한다(이 파일들만 예외). satori는 시스템 폰트에 접근하지 못하므로 한글 텍스트를 렌더하는 OG는 반드시 한글 폰트 파일(otf/ttf/woff, woff2 아님)을 빌드 타임에 읽어 `fonts` 옵션으로 전달해야 한다.

---

## 파일 구조 (이 계획 범위)

```
apps/web/
  app/
    playground/page.tsx + page.module.css        타입 캔버스 (3a, 신규)
    compare/page.tsx + page.module.css           비교 (5a, 신규)
    collections/page.tsx + page.module.css       컬렉션 목록 (신규)
    collections/[slug]/page.tsx + page.module.css 컬렉션 상세 (8a, 신규)
    submit/page.tsx + page.module.css            창작자 등록 (8b, 신규)
    icon.tsx                                     파비콘 (7a, 신규)
    opengraph-image.tsx                          기본 OG (7, 신규)
    fonts/[slug]/opengraph-image.tsx             폰트별 동적 OG (7b, 신규)
    layout.tsx                                   MobileTabBar 추가 (수정)
    globals.css                                  모바일 하단 패딩/safe-area (수정)
  components/                                    각 *.tsx + *.module.css
    PlaygroundCanvas (신규, use client)
    CompareBoard (신규, use client)
    CollectionCard (신규)
    EmptyState (신규)
    MobileTabBar (신규, use client)
    ThemeToggle (신규, use client)
    Header.tsx                                   ThemeToggle + nav 복원 (수정)
  data/  collections.ts                          컬렉션 3종 (신규)
  lib/   data.ts                                 컬렉션 헬퍼 + 무결성 확장 (수정)
         data.test.ts                            컬렉션 테스트 추가 (수정)
  e2e/   smoke.spec.ts                           신규 라우트 + 인터랙션 (수정)
```

**재사용(수정하지 않음):** `lib/fonts.ts`(`fontKeyToVar`), `data/fonts.ts`, `types/font.ts`(`Collection` 이미 정의), 원자 컴포넌트 전부, `app/fonts/[slug]/page.tsx`(동적 라우트 참고).

---

## Task 1: 타입 캔버스 `/playground` (3a)

**Files:**
- Create: `apps/web/components/PlaygroundCanvas.tsx` + `PlaygroundCanvas.module.css`
- Create: `apps/web/app/playground/page.tsx` + `app/playground/page.module.css`
- Modify: `apps/web/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: `fonts`(`@/data/fonts`), `fontKeyToVar`(`@/lib/fonts`), `TierChip`.
- Produces: `PlaygroundCanvas`(named export) — 입력 한 곳이 대표 견본(96px)과 무료 폰트 그리드를 라이브로 바꾸는 클라이언트 컴포넌트. 프리셋 3종 버튼, 지우기 버튼.

- [ ] **Step 1: 캔버스 컴포넌트 CSS**

`apps/web/components/PlaygroundCanvas.module.css`:

```css
.wrap { display: flex; flex-direction: column; }
.head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 18px; flex-wrap: wrap; }
.title { margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -.02em; color: var(--ink); }
.subtitle { font-size: 13px; color: var(--sub); }
.inputRow { display: flex; align-items: center; gap: 12px; height: 60px; padding: 0 20px; background: var(--surface); border: 1.5px solid var(--point); border-radius: 14px; max-width: 720px; }
.icon { flex: none; color: var(--point); }
.input { flex: 1; min-width: 0; border: none; outline: none; background: transparent; font-size: 20px; font-weight: 600; color: var(--ink); }
.clear { flex: none; border: none; background: transparent; font-size: 12px; font-weight: 500; color: var(--sub-2); cursor: pointer; }
.presets { display: flex; gap: 8px; margin-top: 14px; flex-wrap: wrap; }
.preset { padding: 7px 14px; border: 1px solid var(--border); border-radius: var(--radius-pill); font-size: 12.5px; font-weight: 500; color: var(--ink); background: var(--surface); cursor: pointer; }
.hero { padding: 44px 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); margin-top: 26px; }
.heroLabel { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 14px; }
.heroLabel span { font-size: 12px; font-weight: 600; color: var(--sub-2); }
.heroLabel a { font-size: 12px; font-weight: 600; color: var(--point); }
.heroSpecimen { font-weight: 800; font-size: 96px; line-height: 1; color: var(--ink); letter-spacing: -.03em; word-break: break-all; }
.gridHead { font-size: 13px; font-weight: 700; color: var(--ink); margin: 28px 0 16px; }
.count { font-size: 12px; font-weight: 400; color: var(--sub-2); }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.cell { border: 1px solid var(--border); border-radius: 12px; background: var(--surface); padding: 18px 20px; }
.cellHead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.cellName { font-size: 13px; font-weight: 600; color: var(--ink); }
.cellRight { display: flex; gap: 10px; align-items: center; }
.cellDetail { font-size: 11px; font-weight: 500; color: var(--sub-2); }
.cellSpecimen { font-size: 36px; line-height: 1.1; color: var(--ink); word-break: break-all; }
@media (max-width: 620px) {
  .heroSpecimen { font-size: 60px; }
  .grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 2: 캔버스 컴포넌트**

`apps/web/components/PlaygroundCanvas.tsx`:

```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { fonts } from "@/data/fonts";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./PlaygroundCanvas.module.css";

const PRESETS = ["다람쥐 헌 쳇바퀴에 타고파", "당신의 폰트 아지트", "가나다라 ABC 0123"];
const HERO = fonts.find((f) => f.slug === "pretendard")!;
const GRID = fonts.filter((f) => f.tier === "free" && f.slug !== HERO.slug);

export function PlaygroundCanvas() {
  const [text, setText] = useState("아지트");
  const shown = text || " ";
  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h1 className={styles.title}>타입 캔버스</h1>
        <span className={styles.subtitle}>아무 글자나 입력하면 모든 폰트가 그 글자로 바뀝니다</span>
      </div>
      <div className={styles.inputRow}>
        <svg className={styles.icon} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 7h16M4 12h10M4 17h13" /></svg>
        <input className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder="아지트" aria-label="캔버스 입력" />
        <button type="button" className={styles.clear} onClick={() => setText("")}>지우기</button>
      </div>
      <div className={styles.presets}>
        {PRESETS.map((p) => (
          <button type="button" key={p} className={styles.preset} onClick={() => setText(p)}>{p}</button>
        ))}
      </div>
      <div className={styles.hero}>
        <div className={styles.heroLabel}>
          <span>대표 - {HERO.nameKo} - 96px</span>
          <Link href={`/fonts/${HERO.slug}`}>상세 →</Link>
        </div>
        <div className={styles.heroSpecimen} style={{ fontFamily: fontKeyToVar[HERO.fontKey] }}>{shown}</div>
      </div>
      <div className={styles.gridHead}>무료 폰트에서 보기 <span className={styles.count}>- 대표 1 + {GRID.length}종</span></div>
      <div className={styles.grid}>
        {GRID.map((f) => (
          <div key={f.slug} className={styles.cell}>
            <div className={styles.cellHead}>
              <span className={styles.cellName}>{f.nameKo}</span>
              <div className={styles.cellRight}>
                <TierChip tier={f.tier} />
                <Link href={`/fonts/${f.slug}`} className={styles.cellDetail}>상세</Link>
              </div>
            </div>
            <div className={styles.cellSpecimen} style={{ fontFamily: fontKeyToVar[f.fontKey] }}>{shown}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 페이지**

`apps/web/app/playground/page.module.css`:

```css
.main { max-width: 1180px; margin: 0 auto; width: 100%; padding: var(--pad-page); }
```

`apps/web/app/playground/page.tsx`:

```tsx
import { PlaygroundCanvas } from "@/components/PlaygroundCanvas";
import styles from "./page.module.css";

export const metadata = { title: "타입 캔버스 - FontAgit" };

export default function PlaygroundPage() {
  return (
    <main className={styles.main}>
      <PlaygroundCanvas />
    </main>
  );
}
```

- [ ] **Step 4: 스모크 라우트 + 인터랙션 추가**

`apps/web/e2e/smoke.spec.ts`의 `routes` 배열에 추가:

```ts
  { path: '/playground', name: 'Playground' },
```

파일 하단(`preview input updates specimen live` 테스트 아래)에 추가:

```ts
test('playground canvas updates all specimens live', async ({ page }) => {
  await page.goto('/playground/', { waitUntil: 'networkidle' });
  await page.getByLabel('캔버스 입력').fill('불꽃');
  await expect(page.getByText('불꽃').first()).toBeVisible();
});

test('playground preset fills the input', async ({ page }) => {
  await page.goto('/playground/', { waitUntil: 'networkidle' });
  await page.getByRole('button', { name: '당신의 폰트 아지트' }).click();
  await expect(page.getByLabel('캔버스 입력')).toHaveValue('당신의 폰트 아지트');
});
```

- [ ] **Step 5: 타입 체크 + 빌드 + 스모크**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build && pnpm exec playwright test smoke.spec.ts -g "Playground|playground"`
Expected: 성공. `out/playground/index.html` 생성. 신규 스모크 통과(첫 스크린샷은 baseline 생성).

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/PlaygroundCanvas.tsx apps/web/components/PlaygroundCanvas.module.css apps/web/app/playground/ apps/web/e2e/smoke.spec.ts apps/web/e2e/*-snapshots/ 2>/dev/null
git commit -m "feat(web): type canvas /playground (live specimen)"
```

---

## Task 2: 비교 `/compare` (5a)

**Files:**
- Create: `apps/web/components/CompareBoard.tsx` + `CompareBoard.module.css`
- Create: `apps/web/app/compare/page.tsx` + `app/compare/page.module.css`
- Modify: `apps/web/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: `fonts`, `fontKeyToVar`, `TierChip`.
- Produces: `CompareBoard`(named export) — 문장 입력 하나가 3칸 견본을 라이브로 바꾸고, 각 칸 폰트를 `<select>`로 교체하는 클라이언트 컴포넌트(무료 폰트만 후보, 고정 3슬롯).

인터랙션 범위(결정 사항 준수): 문장 라이브 반영은 동작, 폰트 슬롯은 3개 고정 + select 교체까지만 동작한다. 슬롯 추가/삭제는 범위 밖(스펙 "최대 3종"에 3 고정으로 부합).

- [ ] **Step 1: 비교 보드 CSS**

`apps/web/components/CompareBoard.module.css`:

```css
.wrap { display: flex; flex-direction: column; }
.head { display: flex; align-items: baseline; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.title { margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -.02em; color: var(--ink); }
.subtitle { font-size: 13px; color: var(--sub); }
.inputRow { display: flex; align-items: center; gap: 12px; height: 52px; padding: 0 18px; background: var(--surface); border: 1.5px solid var(--point); border-radius: 12px; max-width: 640px; margin-bottom: 24px; }
.inputLabel { flex: none; font-size: 12px; color: var(--sub-2); }
.input { flex: 1; min-width: 0; border: none; outline: none; background: transparent; font-size: 16px; font-weight: 500; color: var(--ink); }
.board { display: grid; grid-template-columns: 1fr 1fr 1fr; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; background: var(--surface); }
.col { padding: 26px 24px; border-right: 1px solid var(--border); }
.col:last-child { border-right: none; }
.colHead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; gap: 8px; }
.select { border: 1px solid var(--border); border-radius: 8px; padding: 5px 8px; font-family: inherit; font-size: 13px; font-weight: 700; color: var(--ink); background: var(--bg); cursor: pointer; }
.specimen { font-size: 48px; line-height: 1.3; color: var(--ink); word-break: break-all; }
.sample { font-size: 14px; line-height: 1.8; color: var(--sub); margin-top: 20px; }
@media (max-width: 720px) {
  .board { grid-template-columns: 1fr; }
  .col { border-right: none; border-bottom: 1px solid var(--border); }
  .col:last-child { border-bottom: none; }
}
```

- [ ] **Step 2: 비교 보드 컴포넌트**

`apps/web/components/CompareBoard.tsx`:

```tsx
"use client";
import { useState } from "react";
import { fonts } from "@/data/fonts";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./CompareBoard.module.css";

const SAMPLE = "좋은 폰트는 말을 걸지 않고 뜻을 전한다. ABCabc 0123";
const OPTIONS = fonts.filter((f) => f.tier === "free");
const DEFAULT_SLOTS = ["pretendard", "gowun-batang", "black-han-sans"];

export function CompareBoard() {
  const [text, setText] = useState("아지트");
  const [slots, setSlots] = useState<string[]>(DEFAULT_SLOTS);
  const shown = text || " ";

  function change(index: number, slug: string) {
    setSlots((prev) => prev.map((v, i) => (i === index ? slug : v)));
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h1 className={styles.title}>폰트 비교</h1>
        <span className={styles.subtitle}>같은 문장으로 나란히 놓고 결정하세요</span>
      </div>
      <div className={styles.inputRow}>
        <span className={styles.inputLabel}>문장</span>
        <input className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder="아지트" aria-label="비교 문장 입력" />
      </div>
      <div className={styles.board}>
        {slots.map((slug, i) => {
          const f = fonts.find((x) => x.slug === slug)!;
          const family = fontKeyToVar[f.fontKey];
          return (
            <div key={i} className={styles.col}>
              <div className={styles.colHead}>
                <select className={styles.select} value={slug} onChange={(e) => change(i, e.target.value)} aria-label={`${i + 1}번 폰트 선택`}>
                  {OPTIONS.map((o) => (
                    <option key={o.slug} value={o.slug}>{o.nameKo}</option>
                  ))}
                </select>
                <TierChip tier={f.tier} />
              </div>
              <div className={styles.specimen} style={{ fontFamily: family }}>{shown}</div>
              <div className={styles.sample} style={{ fontFamily: family }}>{SAMPLE}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 페이지**

`apps/web/app/compare/page.module.css`:

```css
.main { max-width: 1180px; margin: 0 auto; width: 100%; padding: var(--pad-page); }
```

`apps/web/app/compare/page.tsx`:

```tsx
import { CompareBoard } from "@/components/CompareBoard";
import styles from "./page.module.css";

export const metadata = { title: "폰트 비교 - FontAgit" };

export default function ComparePage() {
  return (
    <main className={styles.main}>
      <CompareBoard />
    </main>
  );
}
```

- [ ] **Step 4: 스모크 라우트 + 인터랙션**

`routes` 배열에 추가:

```ts
  { path: '/compare', name: 'Compare' },
```

파일 하단에 추가:

```ts
test('compare updates all columns live and swaps a font', async ({ page }) => {
  await page.goto('/compare/', { waitUntil: 'networkidle' });
  await page.getByLabel('비교 문장 입력').fill('나란히');
  await expect(page.getByText('나란히').first()).toBeVisible();
  await page.getByLabel('2번 폰트 선택').selectOption('nanum-myeongjo');
  await expect(page.getByLabel('2번 폰트 선택')).toHaveValue('nanum-myeongjo');
});
```

- [ ] **Step 5: 타입 체크 + 빌드 + 스모크**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build && pnpm exec playwright test smoke.spec.ts -g "Compare|compare"`
Expected: 성공. `out/compare/index.html` 생성.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/CompareBoard.tsx apps/web/components/CompareBoard.module.css apps/web/app/compare/ apps/web/e2e/smoke.spec.ts apps/web/e2e/*-snapshots/ 2>/dev/null
git commit -m "feat(web): font compare /compare (live sentence + select swap)"
```

---

## Task 3: 컬렉션 데이터 + 무결성 + 헬퍼 (TDD)

**Files:**
- Create: `apps/web/data/collections.ts`
- Modify: `apps/web/lib/data.ts`
- Modify: `apps/web/lib/data.test.ts`

**Interfaces:**
- Consumes: `Collection`(`@/types/font`, 이미 정의: `{ slug, title, intro, items: {fontSlug, comment}[] }`), `getFontBySlug`.
- Produces: `collections: Collection[]`(3종), `getCollectionBySlug(slug): Collection | undefined`, `getAllCollectionSlugs(): string[]`. `assertDataIntegrity`는 컬렉션 slug 중복-빈 컬렉션-미실존 `fontSlug` 참조를 추가로 검사한다.

- [ ] **Step 1: 컬렉션 데이터 작성**

`apps/web/data/collections.ts`(모든 `fontSlug`는 `data/fonts.ts`의 실존 slug):

```ts
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
```

- [ ] **Step 2: 실패 테스트 추가**

`apps/web/lib/data.test.ts` 상단 import에 헬퍼 추가하고(`getCollectionBySlug`, `getAllCollectionSlugs`), `describe` 블록 안에 케이스 추가:

```ts
  it("finds a collection by slug", () => {
    expect(getCollectionBySlug("dawn-serif")?.title).toBe("새벽 감성 명조 모음");
    expect(getCollectionBySlug("nope")).toBeUndefined();
  });
  it("lists all collection slugs", () => {
    expect(getAllCollectionSlugs().length).toBeGreaterThanOrEqual(3);
  });
  it("every collection item references a real font", () => {
    for (const slug of getAllCollectionSlugs()) {
      const c = getCollectionBySlug(slug)!;
      expect(c.items.length).toBeGreaterThan(0);
      for (const it of c.items) {
        expect(getFontBySlug(it.fontSlug)).toBeDefined();
      }
    }
  });
```

`import`에 `getFontBySlug`가 이미 없으면 함께 추가.

- [ ] **Step 3: 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/data.test.ts`
Expected: FAIL(`getCollectionBySlug`/`getAllCollectionSlugs` 없음).

- [ ] **Step 4: 헬퍼 + 무결성 확장 구현**

`apps/web/lib/data.ts` 수정. 상단 import에 추가:

```ts
import { collections } from "@/data/collections";
import type { Collection } from "@/types/font";
```

기존 `Font, FontKey` import 줄에 `Collection`을 합치거나 별도 줄로 둔다(중복 import 주의 — 한 줄로 `import type { Collection, Font, FontKey } from "@/types/font";`).

헬퍼 추가(`resolveFreeAlternatives` 아래):

```ts
export function getCollectionBySlug(slug: string): Collection | undefined {
  return collections.find((c) => c.slug === slug);
}

export function getAllCollectionSlugs(): string[] {
  return collections.map((c) => c.slug);
}
```

`assertDataIntegrity` 함수 끝(마지막 `}` 직전)에 컬렉션 검사 추가:

```ts
  const collectionSlugs = new Set<string>();
  for (const c of collections) {
    if (collectionSlugs.has(c.slug)) throw new Error(`중복 컬렉션 slug: ${c.slug}`);
    collectionSlugs.add(c.slug);
    if (c.items.length === 0) throw new Error(`빈 컬렉션: ${c.slug}`);
    for (const it of c.items) {
      if (!getFontBySlug(it.fontSlug)) throw new Error(`컬렉션 폰트 참조 오류: ${c.slug} -> ${it.fontSlug}`);
    }
  }
```

(`assertDataIntegrity(FONT_KEYS)` 모듈 로드 호출은 그대로 두면 빌드 타임에 컬렉션까지 검증된다.)

- [ ] **Step 5: 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/data.test.ts`
Expected: PASS(기존 4 + 신규 3 = 7 케이스).

- [ ] **Step 6: 타입 체크**

Run: `cd apps/web && pnpm exec tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 7: Commit**

```bash
git add apps/web/data/collections.ts apps/web/lib/data.ts apps/web/lib/data.test.ts
git commit -m "feat(web): collections data + build-time integrity check"
```

---

## Task 4: 컬렉션 화면 — 목록 + 상세 (8a)

**Files:**
- Create: `apps/web/components/CollectionCard.tsx` + `CollectionCard.module.css`
- Create: `apps/web/app/collections/page.tsx` + `app/collections/page.module.css`
- Create: `apps/web/app/collections/[slug]/page.tsx` + `app/collections/[slug]/page.module.css`
- Modify: `apps/web/components/Header.tsx`(nav `/collections` prefetch 복원)
- Modify: `apps/web/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: `collections`(`@/data/collections`), `getCollectionBySlug`/`getAllCollectionSlugs`/`getFontBySlug`(`@/lib/data`), `fontKeyToVar`, `TierChip`, `Collection` 타입.
- Produces: `CollectionCard`(named export, 목록 카드). 목록 `/collections`와 상세 `/collections/[slug]`(동적 라우트, `dynamicParams=false` + `generateStaticParams`).

- [ ] **Step 1: CollectionCard**

`apps/web/components/CollectionCard.module.css`:

```css
.card { display: flex; flex-direction: column; gap: 8px; padding: 24px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); }
.kicker { font-size: 12px; font-weight: 600; color: var(--point); }
.title { margin: 0; font-size: 20px; font-weight: 800; letter-spacing: -.02em; color: var(--ink); }
.intro { margin: 0; font-size: 13px; line-height: 1.7; color: var(--sub); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
```

`apps/web/components/CollectionCard.tsx`:

```tsx
import Link from "next/link";
import type { Collection } from "@/types/font";
import styles from "./CollectionCard.module.css";

export function CollectionCard({ collection }: { collection: Collection }) {
  return (
    <Link href={`/collections/${collection.slug}`} className={styles.card}>
      <span className={styles.kicker}>컬렉션 - {collection.items.length}종</span>
      <h2 className={styles.title}>{collection.title}</h2>
      <p className={styles.intro}>{collection.intro}</p>
    </Link>
  );
}
```

- [ ] **Step 2: 목록 페이지**

`apps/web/app/collections/page.module.css`:

```css
.main { max-width: 1180px; margin: 0 auto; width: 100%; padding: var(--pad-page); }
.h1 { font-size: 24px; font-weight: 800; margin: 0 0 6px; }
.lead { font-size: 14px; color: var(--sub); margin: 0 0 24px; }
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 960px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 620px) { .grid { grid-template-columns: 1fr; } }
```

`apps/web/app/collections/page.tsx`:

```tsx
import { collections } from "@/data/collections";
import { CollectionCard } from "@/components/CollectionCard";
import styles from "./page.module.css";

export const metadata = { title: "컬렉션 - FontAgit" };

export default function CollectionsPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.h1}>컬렉션</h1>
      <p className={styles.lead}>테마별로 묶은 폰트 모음이에요.</p>
      <div className={styles.grid}>
        {collections.map((c) => (
          <CollectionCard key={c.slug} collection={c} />
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 3: 상세 페이지 (동적 라우트)**

`apps/web/app/collections/[slug]/page.module.css`:

```css
.main { max-width: 720px; margin: 0 auto; width: 100%; padding: var(--pad-page); }
.kicker { font-size: 12px; font-weight: 600; color: var(--point); margin-bottom: 8px; }
.title { margin: 0 0 10px; font-size: 28px; font-weight: 800; letter-spacing: -.02em; color: var(--ink); }
.intro { margin: 0 0 26px; font-size: 14px; line-height: 1.7; color: var(--sub); }
.list { display: flex; flex-direction: column; }
.item { padding: 18px 0; border-top: 1px solid var(--border); }
.item:last-child { border-bottom: 1px solid var(--border); }
.itemHead { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 6px; }
.itemName { font-size: 26px; line-height: 1; color: var(--ink); }
.comment { margin: 0; font-size: 12.5px; color: var(--sub); }
```

`apps/web/app/collections/[slug]/page.tsx`(정본 동적 라우트 패턴 준수):

```tsx
import Link from "next/link";
import { notFound } from "next/navigation";
import { getCollectionBySlug, getAllCollectionSlugs, getFontBySlug } from "@/lib/data";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "@/components/TierChip";
import styles from "./page.module.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllCollectionSlugs().map((slug) => ({ slug }));
}

export default async function CollectionDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const collection = getCollectionBySlug(slug);

  if (!collection) {
    notFound();
  }

  return (
    <main className={styles.main}>
      <div className={styles.kicker}>컬렉션 - {collection.items.length}종</div>
      <h1 className={styles.title}>{collection.title}</h1>
      <p className={styles.intro}>{collection.intro}</p>
      <div className={styles.list}>
        {collection.items.map((it) => {
          const f = getFontBySlug(it.fontSlug)!;
          return (
            <div key={it.fontSlug} className={styles.item}>
              <div className={styles.itemHead}>
                <Link href={`/fonts/${f.slug}`} className={styles.itemName} style={{ fontFamily: fontKeyToVar[f.fontKey] }}>{f.nameKo}</Link>
                <TierChip tier={f.tier} />
              </div>
              <p className={styles.comment}>{it.comment}</p>
            </div>
          );
        })}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: 헤더 nav `/collections` 복원 (블로커 #1)**

`apps/web/components/Header.tsx`에서 컬렉션 링크를 정상 링크로 되돌린다:

```tsx
        <Link href="/collections">컬렉션</Link>
```

(기존 `prefetch={false}`와 바로 아래 주석 줄을 제거. `/submit` 링크는 Task 5까지 `prefetch={false}` 유지.)

- [ ] **Step 5: 스모크 라우트 추가**

`routes` 배열에 추가:

```ts
  { path: '/collections', name: 'Collections' },
  { path: '/collections/dawn-serif', name: 'Collection Detail' },
```

파일 하단에 nav 검증 추가:

```ts
test('header collections link navigates without 404', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.getByRole('navigation').getByRole('link', { name: '컬렉션' }).click();
  await expect(page).toHaveURL(/\/collections\/?$/);
  await expect(page.getByRole('heading', { name: '컬렉션', level: 1 })).toBeVisible();
});
```

- [ ] **Step 6: 타입 체크 + 빌드 + 스모크**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build && pnpm exec playwright test smoke.spec.ts -g "Collection|collections"`
Expected: 성공. `out/collections/index.html`, `out/collections/dawn-serif/index.html` 등 3개 상세 생성.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/CollectionCard.tsx apps/web/components/CollectionCard.module.css apps/web/app/collections/ apps/web/components/Header.tsx apps/web/e2e/smoke.spec.ts apps/web/e2e/*-snapshots/ 2>/dev/null
git commit -m "feat(web): collections list + detail, restore nav link"
```

---

## Task 5: 창작자 등록 `/submit` (8b)

**Files:**
- Create: `apps/web/components/SubmitForm.tsx` + `SubmitForm.module.css`
- Create: `apps/web/app/submit/page.tsx` + `app/submit/page.module.css`
- Modify: `apps/web/components/Header.tsx`(nav `/submit` prefetch 복원)
- Modify: `apps/web/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: `FilterChip`(라이선스 선택 시각 칩, 비동작).
- Produces: 시맨틱 `<form>`(`SubmitForm`, `"use client"`)이 `onSubmit`에서 `preventDefault`로 제출을 막는 등록 폼 UI. `page.tsx`는 서버 컴포넌트로 metadata + `<SubmitForm />`를 렌더(metadata는 서버 컴포넌트 전용이라 폼을 클라이언트 컴포넌트로 분리).

정보 검증(coding-style Defensive Input)은 이번 범위 밖이다: 폼은 UI 목업이며 제출 로직이 없다. 실제 제출/검증은 백엔드 연동 시점에 추가한다(스펙 결정: 목업 데이터/비동작). 시맨틱은 `<form>`으로 두되 동작만 비활성화한다.

- [ ] **Step 1: 폼 CSS**

`apps/web/components/SubmitForm.module.css`:

```css
.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 7px; }
.row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.label { font-size: 12px; font-weight: 600; color: var(--ink); }
.req { color: var(--point); }
.input { height: 44px; border: 1px solid var(--border); border-radius: var(--radius-btn); background: var(--surface); padding: 0 14px; font-family: inherit; font-size: 13px; color: var(--ink); }
.input::placeholder { color: var(--sub-2); }
.chips { display: flex; gap: 8px; flex-wrap: wrap; }
.submit { height: 48px; margin-top: 6px; background: var(--point); color: var(--on-point); border: none; border-radius: 11px; font-family: inherit; font-size: 14px; font-weight: 600; cursor: pointer; }
@media (max-width: 480px) { .row { grid-template-columns: 1fr; } }
```

- [ ] **Step 2: 폼 컴포넌트 (클라이언트, 제출 비활성)**

`apps/web/components/SubmitForm.tsx`:

```tsx
"use client";
import { FilterChip } from "./FilterChip";
import styles from "./SubmitForm.module.css";

export function SubmitForm() {
  return (
    <form className={styles.form} onSubmit={(e) => e.preventDefault()}>
      <label className={styles.field}>
        <span className={styles.label}>폰트 이름 <span className={styles.req}>*</span></span>
        <input className={styles.input} type="text" placeholder="예: 아지트 고딕" />
      </label>
      <div className={styles.row}>
        <label className={styles.field}>
          <span className={styles.label}>제작자 <span className={styles.req}>*</span></span>
          <input className={styles.input} type="text" placeholder="이름/팀" />
        </label>
        <label className={styles.field}>
          <span className={styles.label}>분류</span>
          <select className={styles.input} defaultValue="고딕">
            <option>고딕</option>
            <option>명조</option>
            <option>손글씨</option>
            <option>장식</option>
          </select>
        </label>
      </div>
      <label className={styles.field}>
        <span className={styles.label}>공식 페이지 URL <span className={styles.req}>*</span></span>
        <input className={styles.input} type="url" placeholder="https://" />
      </label>
      <div className={styles.field}>
        <span className={styles.label}>라이선스</span>
        <div className={styles.chips}>
          <FilterChip active>무료</FilterChip>
          <FilterChip>유료</FilterChip>
          <FilterChip>조건부</FilterChip>
        </div>
      </div>
      <button type="submit" className={styles.submit}>신청 보내기</button>
    </form>
  );
}
```

- [ ] **Step 3: 페이지 (서버, metadata + 폼)**

`apps/web/app/submit/page.module.css`:

```css
.main { max-width: 520px; margin: 0 auto; width: 100%; padding: var(--pad-page); }
.title { margin: 0 0 6px; font-size: 24px; font-weight: 800; letter-spacing: -.02em; color: var(--ink); }
.lead { margin: 0 0 24px; font-size: 13px; line-height: 1.6; color: var(--sub); }
```

`apps/web/app/submit/page.tsx`:

```tsx
import { SubmitForm } from "@/components/SubmitForm";
import styles from "./page.module.css";

export const metadata = { title: "폰트 등록 신청 - FontAgit" };

export default function SubmitPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.title}>폰트 등록 신청</h1>
      <p className={styles.lead}>만드신 폰트를 아지트에 소개해 주세요. 검토 후 등록됩니다.</p>
      <SubmitForm />
    </main>
  );
}
```

- [ ] **Step 4: 헤더 nav `/submit` 복원 (블로커 #1 완결)**

`apps/web/components/Header.tsx`에서 등록 링크를 정상 링크로:

```tsx
        <Link href="/submit">등록</Link>
```

(`prefetch={false}` 제거. 이제 Header에 `prefetch={false}`가 남지 않는다.)

- [ ] **Step 5: 스모크 라우트 + 제출 비활성 검증**

`routes` 배열에 추가:

```ts
  { path: '/submit', name: 'Submit' },
```

파일 하단에 추가:

```ts
test('submit form is a non-submitting mockup', async ({ page }) => {
  await page.goto('/submit/', { waitUntil: 'networkidle' });
  await expect(page.getByRole('heading', { name: '폰트 등록 신청' })).toBeVisible();
  await page.getByRole('button', { name: '신청 보내기' }).click();
  await expect(page).toHaveURL(/\/submit\/?$/); // preventDefault로 제출/네비게이션 없음
});
```

- [ ] **Step 6: 타입 체크 + 빌드 + 스모크**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build && pnpm exec playwright test smoke.spec.ts -g "Submit|submit"`
Expected: 성공. `out/submit/index.html` 생성.

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/SubmitForm.tsx apps/web/components/SubmitForm.module.css apps/web/app/submit/ apps/web/components/Header.tsx apps/web/e2e/smoke.spec.ts apps/web/e2e/*-snapshots/ 2>/dev/null
git commit -m "feat(web): creator submit form (semantic form, non-submitting), restore nav link"
```

---

## Task 6: 빈 상태 컴포넌트 + 목록 empty 분기 (1i)

**Files:**
- Create: `apps/web/components/EmptyState.tsx` + `EmptyState.module.css`
- Modify: `apps/web/app/collections/page.tsx`(빈 컬렉션 분기)

**Interfaces:**
- Consumes: (없음, 순수 프레젠테이션).
- Produces: `EmptyState`(named export) — `{ title, description, actionHref?, actionLabel? }`. 브랜드 층 보이스(다정)로 빈 목록을 안내한다. `actionHref`+`actionLabel` 둘 다 있을 때만 링크 노출.

- [ ] **Step 1: EmptyState CSS**

`apps/web/components/EmptyState.module.css`:

```css
.wrap { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 10px; padding: 64px 24px; border: 1px dashed var(--border); border-radius: var(--radius-card); background: var(--surface-2); }
.title { font-size: 16px; font-weight: 700; color: var(--ink); }
.desc { margin: 0; font-size: 13px; line-height: 1.6; color: var(--sub); }
.action { margin-top: 6px; padding: 10px 18px; border-radius: var(--radius-btn); background: var(--point); color: var(--on-point); font-size: 12.5px; font-weight: 600; }
```

- [ ] **Step 2: EmptyState 컴포넌트**

`apps/web/components/EmptyState.tsx`:

```tsx
import Link from "next/link";
import styles from "./EmptyState.module.css";

export function EmptyState({
  title,
  description,
  actionHref,
  actionLabel,
}: {
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className={styles.wrap}>
      <div className={styles.title}>{title}</div>
      <p className={styles.desc}>{description}</p>
      {actionHref && actionLabel && (
        <Link href={actionHref} className={styles.action}>{actionLabel}</Link>
      )}
    </div>
  );
}
```

- [ ] **Step 3: 컬렉션 목록에 빈 상태 분기 (UI 상태 완전성)**

`apps/web/app/collections/page.tsx`를 수정해 `EmptyState`를 import하고 그리드를 조건 분기한다:

```tsx
import { collections } from "@/data/collections";
import { CollectionCard } from "@/components/CollectionCard";
import { EmptyState } from "@/components/EmptyState";
import styles from "./page.module.css";

export const metadata = { title: "컬렉션 - FontAgit" };

export default function CollectionsPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.h1}>컬렉션</h1>
      <p className={styles.lead}>테마별로 묶은 폰트 모음이에요.</p>
      {collections.length === 0 ? (
        <EmptyState
          title="아직 컬렉션이 없어요"
          description="곧 테마별 폰트 모음을 준비할게요. 먼저 폰트를 둘러보시겠어요?"
          actionHref="/fonts"
          actionLabel="폰트 둘러보기"
        />
      ) : (
        <div className={styles.grid}>
          {collections.map((c) => (
            <CollectionCard key={c.slug} collection={c} />
          ))}
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 4: 타입 체크 + 빌드**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build`
Expected: 성공(현재 데이터는 3종이라 정상 그리드 렌더, empty 분기는 방어적).

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/EmptyState.tsx apps/web/components/EmptyState.module.css apps/web/app/collections/page.tsx
git commit -m "feat(web): EmptyState component + collections empty branch"
```

---

## Task 7: 모바일 정밀화 — MobileTabBar + safe-area (4a/4b/4c)

**Files:**
- Create: `apps/web/components/MobileTabBar.tsx` + `MobileTabBar.module.css`
- Modify: `apps/web/app/layout.tsx`(탭바 마운트)
- Modify: `apps/web/app/globals.css`(모바일 하단 여백)
- Modify: `apps/web/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: `usePathname`(next/navigation).
- Produces: `MobileTabBar`(named export, `"use client"`) — 모바일 뷰포트에서만 보이는 하단 고정 탭바(홈/폰트/트렌드/캔버스). 현재 경로에 해당하는 탭을 포인트색으로 강조.

- [ ] **Step 1: 탭바 CSS (하단 고정 + safe-area, 데스크톱 숨김)**

`apps/web/components/MobileTabBar.module.css`:

```css
.bar { display: none; }
@media (max-width: 620px) {
  .bar {
    display: flex;
    position: fixed;
    left: 0; right: 0; bottom: 0;
    height: 56px;
    padding-bottom: env(safe-area-inset-bottom);
    background: var(--surface);
    border-top: 1px solid var(--border);
    align-items: center;
    justify-content: space-around;
    z-index: 20;
  }
  .tab, .active { flex: 1; height: 100%; display: flex; align-items: center; justify-content: center; text-align: center; font-size: 11px; font-weight: 500; color: var(--sub-2); }
  .active { color: var(--point); font-weight: 600; }
}
```

- [ ] **Step 2: 탭바 컴포넌트**

`apps/web/components/MobileTabBar.tsx`:

```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import styles from "./MobileTabBar.module.css";

const TABS = [
  { href: "/", label: "홈" },
  { href: "/fonts", label: "폰트" },
  { href: "/trends", label: "트렌드" },
  { href: "/playground", label: "캔버스" },
];

export function MobileTabBar() {
  const pathname = usePathname();
  return (
    <nav className={styles.bar} aria-label="모바일 탭">
      {TABS.map((t) => {
        const active = t.href === "/" ? pathname === "/" : pathname.startsWith(t.href);
        return (
          <Link key={t.href} href={t.href} className={active ? styles.active : styles.tab} aria-current={active ? "page" : undefined}>
            {t.label}
          </Link>
        );
      })}
    </nav>
  );
}
```

- [ ] **Step 3: layout에 탭바 마운트**

`apps/web/app/layout.tsx`의 `<body>` 안, `<Footer />` 아래에 추가하고 import 추가:

```tsx
import { MobileTabBar } from "@/components/MobileTabBar";
```

```tsx
      <body>
        <Header />
        {children}
        <Footer />
        <MobileTabBar />
      </body>
```

- [ ] **Step 4: 모바일 하단 여백 (탭바가 콘텐츠 가리지 않게)**

`apps/web/app/globals.css` 끝에 추가:

```css
@media (max-width: 620px) {
  body { padding-bottom: calc(56px + env(safe-area-inset-bottom)); }
}
```

- [ ] **Step 5: 스모크 — 모바일 탭바 노출 확인**

`apps/web/e2e/smoke.spec.ts` 하단에 추가:

```ts
test('mobile tab bar shows on small viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/', { waitUntil: 'networkidle' });
  await expect(page.getByRole('navigation', { name: '모바일 탭' })).toBeVisible();
});
```

- [ ] **Step 6: 타입 체크 + 빌드 + 스모크**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build && pnpm exec playwright test smoke.spec.ts -g "mobile tab"`
Expected: 성공. 데스크톱 스크린샷 baseline은 탭바가 안 보여 변화 없음(있으면 `--update-snapshots`로 갱신 후 커밋).

- [ ] **Step 7: Commit**

```bash
git add apps/web/components/MobileTabBar.tsx apps/web/components/MobileTabBar.module.css apps/web/app/layout.tsx apps/web/app/globals.css apps/web/e2e/smoke.spec.ts apps/web/e2e/*-snapshots/ 2>/dev/null
git commit -m "feat(web): mobile tab bar + safe-area bottom padding"
```

---

## Task 8: 다크모드 토글 UI (9b)

**Files:**
- Create: `apps/web/components/ThemeToggle.tsx` + `ThemeToggle.module.css`
- Modify: `apps/web/components/Header.tsx`(actions에 토글 추가)
- Modify: `apps/web/e2e/smoke.spec.ts`

**Interfaces:**
- Consumes: (DOM `documentElement` `data-theme`, `localStorage`).
- Produces: `ThemeToggle`(named export, `"use client"`) — 클릭 시 `data-theme`를 light↔dark 토글하고 `localStorage.theme`에 저장. 초기 상태는 layout의 FOUC 스크립트가 이미 세팅한 `data-theme`를 `useEffect`로 읽어 동기화(hydration mismatch 방지).

layout의 인라인 테마 스크립트(`localStorage.theme` → `data-theme`)는 이미 존재하므로 재사용한다. 토글은 그 값을 바꾸기만 한다.

- [ ] **Step 1: 토글 CSS (기존 iconBtn과 동일 톤)**

`apps/web/components/ThemeToggle.module.css`:

```css
.btn { width: 36px; height: 36px; border-radius: 8px; border: 1px solid var(--border); background: transparent; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; color: var(--sub); }
```

- [ ] **Step 2: 토글 컴포넌트**

`apps/web/components/ThemeToggle.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";
import styles from "./ThemeToggle.module.css";

type Theme = "light" | "dark";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    const current = document.documentElement.getAttribute("data-theme");
    if (current === "dark" || current === "light") setTheme(current);
  }, []);

  function toggle() {
    // 초기 클릭 경쟁 방지: state가 아닌 실제 DOM data-theme를 기준으로 다음 값을 계산.
    const current = document.documentElement.getAttribute("data-theme");
    const next: Theme = current === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    setTheme(next);
    try {
      localStorage.setItem("theme", next);
    } catch {}
  }

  return (
    <button type="button" className={styles.btn} onClick={toggle} aria-label="다크모드 전환" aria-pressed={theme === "dark"}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round"><path d="M20 13a7 7 0 1 1-9-9 6 6 0 0 0 9 9Z" /></svg>
    </button>
  );
}
```

- [ ] **Step 3: 헤더 actions에 토글 추가**

`apps/web/components/Header.tsx`의 `.actions` div 안, 검색 버튼 옆에 추가하고 import 추가:

```tsx
import { ThemeToggle } from "./ThemeToggle";
```

```tsx
      <div className={styles.actions}>
        <ThemeToggle />
        <button type="button" className={styles.iconBtn} aria-label="검색">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
        </button>
      </div>
```

- [ ] **Step 4: 스모크 — 토글 동작**

`apps/web/e2e/smoke.spec.ts` 하단에 추가:

```ts
test('theme toggle switches data-theme', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  const html = page.locator('html');
  const before = await html.getAttribute('data-theme');
  await page.getByLabel('다크모드 전환').click();
  const after = await html.getAttribute('data-theme');
  expect(after).not.toBe(before);
  expect(['light', 'dark']).toContain(after);
});
```

- [ ] **Step 5: 타입 체크 + 빌드 + 스모크**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build && pnpm exec playwright test smoke.spec.ts -g "theme toggle"`
Expected: 성공. 헤더에 토글이 추가돼 기존 데스크톱 스크린샷 baseline이 바뀌므로 `pnpm exec playwright test smoke.spec.ts --update-snapshots` 후 변경된 `*-snapshots/`를 함께 커밋.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/ThemeToggle.tsx apps/web/components/ThemeToggle.module.css apps/web/components/Header.tsx apps/web/e2e/smoke.spec.ts apps/web/e2e/*-snapshots/ 2>/dev/null
git commit -m "feat(web): dark mode toggle in header"
```

---

## Task 9: 런칭 자산 — 파비콘 + OG 이미지 (7a/7b)

**Files:**
- Create: `apps/web/app/icon.tsx`
- Create: `apps/web/app/opengraph-image.tsx`
- Create: `apps/web/app/fonts/[slug]/opengraph-image.tsx`

**Interfaces:**
- Consumes: `ImageResponse`(next/og), `getAllSlugs`/`getFontBySlug`(폰트별 OG), 빌드 타임 한글 폰트 파일(`node:fs/promises` readFile).
- Produces: 빌드 타임 정적 생성 파비콘(`icon.tsx`, 한글 없음 → 폰트 로드 불필요), 한글 폰트를 임베드한 기본 OG(`opengraph-image.tsx`)와 폰트별 OG(`fonts/[slug]/opengraph-image.tsx`, `generateStaticParams`로 전 slug 사전 생성).

리스크와 제약:
- `output: 'export'`는 런타임 동적 OG를 지원하지 않는다 → 동적 OG는 `generateStaticParams`로 전 slug를 빌드 타임 사전 생성한다.
- `next/og`의 satori 렌더러는 시스템 폰트에 접근하지 못한다 → 한글 텍스트가 있는 OG는 반드시 한글 폰트 파일을 `fonts` 옵션으로 전달해야 하며, 안 하면 한글이 네모(tofu)로 깨진다. satori는 woff2를 지원하지 않으므로 otf/ttf/woff를 쓴다.
- 이 Task의 OG/아이콘 파일은 Global Constraints의 "OG/아이콘 예외"에 따라 인라인 스타일 + 색상 하드코딩을 허용한다.

- [ ] **Step 1: Next 16 문서 + 폰트 파일 경로 확인 (AGENTS.md 지침)**

Run:
```bash
cd apps/web
ls node_modules/next/dist/docs/ 2>/dev/null; grep -rl "opengraph-image\|ImageResponse" node_modules/next/dist/docs/ 2>/dev/null | head
find node_modules/pretendard -type f \( -name "*.otf" -o -name "*.ttf" -o -name "*.woff" \) | grep -iE "bold|700" | head
```
확인 사항: (1) `size`/`contentType` export 규약, (2) 동적 세그먼트 OG에 `generateStaticParams` 필요 여부, (3) `output:'export'`에서 `ImageResponse` 정적 렌더 지원 여부, (4) Pretendard의 otf/ttf/woff(700 굵기) 실제 경로. 아래 코드의 `FONT_PATH`를 그 경로로 맞춘다. 문서에서 정적 export 미지원이 확인되면 대체안(Step 4 주석)으로 전환하고 사용자에게 보고한다.

- [ ] **Step 2: 파비콘** (한글 없음 → 폰트 로드 불필요)

`apps/web/app/icon.tsx`(딥 그린 배경 + 흰 A 워드마크 축약):

```tsx
import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", background: "#2C5545", color: "#FFFFFF", fontSize: 22, fontWeight: 800, fontFamily: "sans-serif" }}>
        A
      </div>
    ),
    size,
  );
}
```

- [ ] **Step 3: 기본 OG** (한글 폰트 임베드)

`apps/web/app/opengraph-image.tsx`:

```tsx
import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "FontAgit 폰트 아지트";

// Step 1에서 확인한 실제 경로로 맞춘다(otf/ttf/woff, woff2 아님).
const FONT_PATH = "node_modules/pretendard/dist/public/static/Pretendard-Bold.otf";

export default async function OgImage() {
  const pretendardBold = await readFile(join(process.cwd(), FONT_PATH));
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 20, background: "#FAFAF8", fontFamily: "Pretendard" }}>
        <div style={{ fontSize: 84, fontWeight: 800, color: "#1A1A1A", letterSpacing: "-0.03em" }}>
          Font<span style={{ color: "#2C5545" }}>A</span>git
        </div>
        <div style={{ fontSize: 30, color: "#6B6B6B" }}>당신의 폰트 아지트</div>
      </div>
    ),
    { ...size, fonts: [{ name: "Pretendard", data: pretendardBold, weight: 700, style: "normal" }] },
  );
}
```

- [ ] **Step 4: 폰트별 동적 OG (정적 사전 생성 + 한글 폰트 임베드)**

`apps/web/app/fonts/[slug]/opengraph-image.tsx`:

```tsx
import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { getAllSlugs, getFontBySlug } from "@/lib/data";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const FONT_PATH = "node_modules/pretendard/dist/public/static/Pretendard-Bold.otf";

export function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export default async function FontOgImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const font = getFontBySlug(slug);
  const nameKo = font?.nameKo ?? "FontAgit";
  const tierLabel = font?.tier === "paid" ? "유료" : "무료";
  const pretendardBold = await readFile(join(process.cwd(), FONT_PATH));

  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "flex-start", justifyContent: "center", padding: 80, gap: 24, background: "#FAFAF8", fontFamily: "Pretendard" }}>
        <div style={{ fontSize: 28, fontWeight: 700, color: "#2C5545" }}>FontAgit 폰트 상세</div>
        <div style={{ fontSize: 92, fontWeight: 800, color: "#1A1A1A", letterSpacing: "-0.03em" }}>{nameKo}</div>
        <div style={{ fontSize: 30, color: "#6B6B6B" }}>{tierLabel} - 공식 페이지에서 라이선스 확인</div>
      </div>
    ),
    { ...size, fonts: [{ name: "Pretendard", data: pretendardBold, weight: 700, style: "normal" }] },
  );
}
```

주의: OG 텍스트는 Pretendard(UI 폰트)로만 렌더한다 — 견본 웹폰트는 OG에 임베드하지 않는다(라이선스-빌드 복잡도 회피). "공식 페이지에서 라이선스 확인"은 보증 표현("안전")을 피한 정보층 카피다. 대체안(정적 export가 `ImageResponse`를 미지원할 때): 로컬 스크립트로 각 OG를 PNG로 생성해 `public/og/`에 두고, 각 페이지 `metadata.openGraph.images`(폰트 상세는 `generateMetadata`)로 그 경로를 연결한다.

- [ ] **Step 5: 빌드 + OG 검증**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build && find out -name "opengraph-image*" -o -name "icon*" | head && grep -o 'og:image[^>]*' out/fonts/pretendard/index.html | head`
Expected: 성공. `out/`에 파비콘-기본 OG-폰트별 OG PNG 생성. 폰트 상세 HTML의 `<meta property="og:image">`가 생성된 PNG를 가리킴. 생성된 OG PNG를 하나 열어 한글(nameKo)이 네모 없이 렌더됐는지 육안 확인. (Step 1에서 정적 export 미지원 확인 시 사용자 보고 후 대체안으로 전환.)

- [ ] **Step 6: Commit** (zsh 글로빙 방지 — `[slug]` 경로 따옴표 필수)

```bash
git add apps/web/app/icon.tsx apps/web/app/opengraph-image.tsx "apps/web/app/fonts/[slug]/opengraph-image.tsx"
git commit -m "feat(web): favicon + default/per-font OG images (static, korean font embedded)"
```

---

## 최종 검증 (전체 Task 완료 후)

- [ ] **전체 스위트 그린 확인**

```bash
cd apps/web
pnpm exec tsc --noEmit          # 0 errors
pnpm test                       # vitest (data 7 + LicenseBadge 3 = 10) 통과
pnpm build                      # SSG, out/ 신규 라우트 포함 (playground/compare/collections[+3]/submit)
pnpm exec playwright test       # 스모크 전체 통과 (신규 라우트 + 인터랙션 + nav + 토글 + 탭바)
pnpm exec eslint .              # clean
```

- [ ] **블로커 해소 확인**
  - 헤더 nav 404(#1): `components/Header.tsx`에 `prefetch={false}` 없음 → `grep -n "prefetch" apps/web/components/Header.tsx` 결과 0줄.
  - 컬렉션 무결성(#3): `assertDataIntegrity`가 컬렉션 참조를 검사 → 빌드 성공이 곧 무결성 통과.
  - agy 리뷰(#2): PR 리뷰는 codex 단독으로 요청(Global Constraints 참조).

- [ ] **95% 시각 대조 (원본 육안 승인)**
  - 신규 핵심 화면(playground/compare/collections 목록-상세/submit)을 데스크톱 1280 / 모바일 390에서 실행하고, 원본 디자인(3a/5a/8a/8b)과 다크모드를 육안 5% 이내로 대조한다. baseline 스크린샷은 회귀 감지용일 뿐 디자인 일치 판정이 아니다.

- [ ] **progress 문서 갱신**
  - `docs/progress.md` + 상세 히스토리(`docs/progress-002.md` 신규)에 Phase 3-4 완료 기록(무엇을/결정/남은 일/커밋).

- [ ] **PR 생성**
  - `git diff main...HEAD` 요약 + 테스트 계획. codex 단독 리뷰(agy 제외).

---

## Self-Review (계획 작성자 체크)

**스펙 커버리지:** 스펙 4장 13화면 중 Phase 3-4 대상 — 캔버스(3a)=Task1, 비교(5a)=Task2, 컬렉션 목록/상세(8a)=Task3+4, 등록(8b)=Task5, 빈상태(1i)=Task6, 모바일(4a/4b/4c)=Task7, 다크토글(9b)=Task8, 파비콘/OG(7a/7b)=Task9. 커버 완료.

**플레이스홀더 스캔:** TBD/TODO/"적절한 처리" 없음. 모든 코드 스텝에 완전한 코드 포함.

**타입 일관성:** `Collection`은 `types/font.ts` 기존 정의(`{slug,title,intro,items:{fontSlug,comment}[]}`) 사용. `getCollectionBySlug`/`getAllCollectionSlugs`는 Task3에서 정의 후 Task4에서 동일 시그니처로 소비(Task9는 `getAllSlugs`/`getFontBySlug`만 사용). `fontKeyToVar[fontKey]`, `TierChip tier=`, `FilterChip active=` 모두 기존 시그니처와 일치. 동적 라우트는 `params: Promise<{slug}>` + `await params` 정본 준수.

**범위 체크:** 인터랙션은 결정 사항(핵심만 동작) 준수 — 캔버스/비교 라이브 반영과 다크토글만 실동작. 등록 폼은 시맨틱 `<form>` + `preventDefault`로 접근성을 확보하되 실제 제출은 없고, 필터/검색은 비동작 목업. compare 폰트 슬롯은 3 고정 + select 교체까지만(추가/삭제 제외).
