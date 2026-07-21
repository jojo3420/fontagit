# 글자 지원 검사 이동 Implementation Plan (#97)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/playground` 하단의 "글자 지원 검사"를 폰트 상세(`/fonts/[slug]`) 페이지의 견본 아래로 이동하고, 검사 가능한 무료 웹폰트에서만 노출한다.

**Architecture:** 상세 페이지(서버 컴포넌트)가 검사 가능 여부를 판정해 클라이언트 컴포넌트 `GlyphChecker`를 조건부 렌더. 판정식은 `lib/glyphSupport.ts`의 공유 함수로 추출해 페이지 게이트와 컴포넌트 내부 게이트가 일치하게 한다. playground에서는 `GlyphCheckerSection`을 제거-삭제한다.

**Tech Stack:** Next.js(App Router, `output: "export"`), React 19, TypeScript, vitest + @testing-library/react, CSS Modules, next/font/google.

## Global Constraints

- 검사 가능 판정식은 정확히 `tier === "free" && fontKey !== null && fontKey !== "pretendard"`. 이 8종만 next/font/google로 전역 로드되어 검사 가능. `resolveFontPreview().stylesheetUrl` 유무로 게이트를 바꾸지 말 것(8종은 stylesheetUrl이 null이라 전부 숨겨짐).
- 검사기는 `SpecimenBox` 로딩에 의존하지 않는다. @font-face는 `app/layout.tsx`의 `<html className={fontClassNames}>`로 전역 활성.
- Docstring/주석 한국어, `console.log` 금지, TypeScript 타입 명시.
- 커밋은 conventional commit + `#97` 포함, 어트리뷰션 없음.
- 테스트는 iteration 중 대상 파일만 실행(apps/web env 취약성 회피), 마지막에 타입체크로 전체 정합 확인.

---

### Task 1: `isGlyphCheckSupported` 판정 함수 추출

검사 가능 판정식을 순수 함수로 빼고 `GlyphChecker`가 이를 쓰게 한다. 동작 불변 리팩터.

**Files:**
- Modify: `apps/web/lib/glyphSupport.ts` (함수 + 타입 import 추가)
- Modify: `apps/web/components/GlyphChecker.tsx` (인라인 판정식 → 함수 호출, 33~35줄)
- Test: `apps/web/lib/glyphSupport.test.ts` (신규)

**Interfaces:**
- Produces: `isGlyphCheckSupported(fontKey: FontKey | null, tier: Tier): boolean` — `@/lib/glyphSupport`에서 export. `FontKey`, `Tier`는 `@/types/font`에서 옴(`Tier = "free" | "paid"`).

- [ ] **Step 1: 실패 테스트 작성**

`apps/web/lib/glyphSupport.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { isGlyphCheckSupported } from "@/lib/glyphSupport";

describe("isGlyphCheckSupported", () => {
  it("무료 웹폰트(fontKey 보유, pretendard 아님)는 지원", () => {
    expect(isGlyphCheckSupported("nanumMyeongjo", "free")).toBe(true);
  });
  it("로컬 폰트 pretendard는 미지원", () => {
    expect(isGlyphCheckSupported("pretendard", "free")).toBe(false);
  });
  it("유료 폰트는 미지원", () => {
    expect(isGlyphCheckSupported("nanumMyeongjo", "paid")).toBe(false);
  });
  it("fontKey 없는 폰트는 미지원", () => {
    expect(isGlyphCheckSupported(null, "free")).toBe(false);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && npx vitest run lib/glyphSupport.test.ts`
Expected: FAIL — `isGlyphCheckSupported` is not exported / not a function.

- [ ] **Step 3: 함수 구현**

`apps/web/lib/glyphSupport.ts` 최상단에 타입 import 추가(파일 첫 줄):

```ts
import type { FontKey, Tier } from "@/types/font";
```

그리고 파일 하단에 함수 추가:

```ts
/** 글자 지원 검사 가능 여부: next/font/google로 전역 로드되는 free 웹폰트만 true. pretendard(로컬)는 제외. */
export function isGlyphCheckSupported(
  fontKey: FontKey | null,
  tier: Tier,
): boolean {
  return tier === "free" && fontKey !== null && fontKey !== "pretendard";
}
```

- [ ] **Step 4: GlyphChecker가 함수 사용하도록 교체**

`apps/web/components/GlyphChecker.tsx` line 6 import에 함수 추가:

```ts
import { detectGlyphSupport, aggregateResults, isGlyphCheckSupported } from "@/lib/glyphSupport";
```

line 33~35의 인라인 판정식:

```ts
  // Tier A(웹폰트) 판정: 구글폰트 free tier만 지원
  const isWebfontAvailable =
    tier === "free" && fontKey !== null && fontKey !== "pretendard";
```

을 다음으로 교체:

```ts
  const isWebfontAvailable = isGlyphCheckSupported(fontKey, tier);
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd apps/web && npx vitest run lib/glyphSupport.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 6: 커밋**

```bash
git add apps/web/lib/glyphSupport.ts apps/web/lib/glyphSupport.test.ts apps/web/components/GlyphChecker.tsx
git commit -m "refactor: #97 글자 지원 검사 판정식 isGlyphCheckSupported 추출"
```

---

### Task 2: 폰트 상세 페이지에 조건부 GlyphChecker 추가

published 상세의 견본 아래에 현재 폰트 하나로 고정된 검사기를 게이트와 함께 렌더.

**Files:**
- Modify: `apps/web/app/fonts/[slug]/page.tsx` (import + `PublishedFontDetail` 렌더)
- Modify: `apps/web/app/fonts/[slug]/page.test.tsx` (노출/숨김 테스트 3건 추가)
- Modify: `apps/web/components/GlyphChecker.module.css` (`.container` 상단 여백)

**Interfaces:**
- Consumes: `isGlyphCheckSupported` (Task 1), `GlyphChecker` from `@/components/GlyphChecker` (props: `fontKey: FontKey | null`, `fontName: string`, `tier: "free" | "paid"`).

- [ ] **Step 1: 실패 테스트 작성**

`apps/web/app/fonts/[slug]/page.test.tsx`의 `describe("폰트 상세 페이지", ...)` 블록 안, 기존 테스트들 뒤에 추가:

```tsx
  it("무료 웹폰트: 글자 지원 검사 노출", async () => {
    await renderDetail("nanum-myeongjo");
    expect(
      screen.getByRole("heading", { name: "글자 지원 검사" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("글자 검사 입력")).toBeInTheDocument();
  });
  it("유료 폰트: 글자 지원 검사 숨김", async () => {
    await renderDetail("sandoll-gothic-neo");
    expect(
      screen.queryByRole("heading", { name: "글자 지원 검사" }),
    ).toBeNull();
  });
  it("로컬 폰트(pretendard): 글자 지원 검사 숨김", async () => {
    await renderDetail("pretendard");
    expect(
      screen.queryByRole("heading", { name: "글자 지원 검사" }),
    ).toBeNull();
  });
```

참고: `GlyphChecker`의 검사 버튼도 `aria-label="글자 지원 검사"`지만 role이 button이라 `getByRole("heading", ...)`는 h3 제목만 잡는다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && npx vitest run "app/fonts/[slug]/page.test.tsx"`
Expected: "무료 웹폰트" 케이스 FAIL(heading 없음). 숨김 2건은 통과(아직 아무데도 렌더 안 됨).

- [ ] **Step 3: 상세 페이지에 import 추가**

`apps/web/app/fonts/[slug]/page.tsx` line 12(`import { ReportForm } ...`) 다음에 추가:

```tsx
import { GlyphChecker } from "@/components/GlyphChecker";
import { isGlyphCheckSupported } from "@/lib/glyphSupport";
```

- [ ] **Step 4: PublishedFontDetail에 조건부 렌더 추가**

`PublishedFontDetail`의 `<SpecimenBox ... />`(line 125) 바로 다음 줄에 삽입:

```tsx
          <SpecimenBox font={font} editable={!isPaid} caption={caption} />
          {isGlyphCheckSupported(font.fontKey, font.tier) && (
            <GlyphChecker
              fontKey={font.fontKey}
              fontName={font.nameKo}
              tier={font.tier}
            />
          )}
          <AdFitUnit unit={ADFIT_UNIT_DETAIL ?? ""} width={300} height={250} label />
```

- [ ] **Step 5: 견본과의 간격 조정**

`apps/web/components/GlyphChecker.module.css`의 `.container`에 `margin-top` 추가:

```css
.container {
  --glyph-success: #2c7a5b;
  --glyph-warning: #8a641f;
  --glyph-danger: #b4564b;

  margin-top: 2rem;
  padding: 1.5rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background-color: var(--surface-2);
}
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd apps/web && npx vitest run "app/fonts/[slug]/page.test.tsx"`
Expected: PASS (기존 + 추가 3건 모두)

- [ ] **Step 7: 커밋**

```bash
git add apps/web/app/fonts/[slug]/page.tsx apps/web/app/fonts/[slug]/page.test.tsx apps/web/components/GlyphChecker.module.css
git commit -m "feat: #97 폰트 상세 페이지에 글자 지원 검사 추가"
```

---

### Task 3: playground에서 GlyphCheckerSection 제거-삭제

이동 완료. playground는 `PlaygroundCanvas`만 남기고 미사용 컴포넌트를 삭제한다.

**Files:**
- Modify: `apps/web/app/playground/page.tsx`
- Delete: `apps/web/components/GlyphCheckerSection.tsx`
- Delete: `apps/web/components/GlyphCheckerSection.module.css`

- [ ] **Step 1: playground 페이지에서 제거**

`apps/web/app/playground/page.tsx` 전체를 다음으로 교체:

```tsx
import { Metadata } from "next";
import { PlaygroundCanvas } from "@/components/PlaygroundCanvas";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "타입 캔버스 - FontAgit",
  alternates: { canonical: "/playground/" },
};

export default function PlaygroundPage() {
  return (
    <main className={styles.main}>
      <PlaygroundCanvas />
    </main>
  );
}
```

- [ ] **Step 2: 미사용 파일 삭제**

```bash
git rm apps/web/components/GlyphCheckerSection.tsx apps/web/components/GlyphCheckerSection.module.css
```

- [ ] **Step 3: 잔여 참조 없음 확인**

Run: `grep -rn "GlyphCheckerSection" apps/web --include="*.tsx" --include="*.ts"`
Expected: 출력 없음(exit 1).

- [ ] **Step 4: 타입체크 + 관련 테스트 통과 확인**

Run: `cd apps/web && npx tsc --noEmit && npx vitest run lib/glyphSupport.test.ts "app/fonts/[slug]/page.test.tsx"`
Expected: 타입 에러 없음, 테스트 PASS.

- [ ] **Step 5: 커밋**

```bash
git add apps/web/app/playground/page.tsx
git commit -m "refactor: #97 playground에서 글자 지원 검사 제거(상세로 이동 완료)"
```

---

## 최종 검증 (전체 게이트)

- [ ] **빌드 확인 (SSG export)**

Run: `cd apps/web && npx next build`
Expected: 빌드 성공. `/fonts/[slug]` 정적 생성 정상.

- [ ] **수동/e2e 검증 (권장, 범위 밖 가능)**

빌드 산출물 또는 dev 서버에서 무료 웹폰트 상세 페이지(예: `/fonts/nanum-myeongjo`) 진입 → "검사할 글자" 입력 후 "검사" 클릭 → 실제 지원 결과가 나오는지 확인(canvas 검출은 jsdom 단위 테스트 불가하므로 실제 브라우저 검증 필요). 유료(`/fonts/sandoll-gothic-neo`)-pretendard 상세에는 검사 섹션이 없는지 확인.

---

## Self-Review

- 스펙 커버리지: (1) playground 제거=Task 3, (2) 드롭다운 제거-현재 폰트 고정=Task 2(GlyphChecker 직접 렌더), (3) 견본 아래 배치=Task 2 Step 4, (4) 미지원 폰트 숨김=Task 2 게이트 + Task 1 판정식. 모두 매핑됨.
- Placeholder: 없음(모든 스텝에 실제 코드/명령/기대 출력).
- 타입 일관성: `isGlyphCheckSupported(fontKey, tier)` 시그니처가 Task 1 정의와 Task 2 호출에서 동일. `GlyphChecker` props(`fontKey`/`fontName`/`tier`)가 실제 인터페이스와 일치.
