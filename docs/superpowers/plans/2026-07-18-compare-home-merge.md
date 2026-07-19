# /compare 제거 → 홈 통합 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/compare` 라우트를 제거하고 폰트 비교 기능을 메인 홈("/")에 지연 로드 섹션으로 통합한다.

**Architecture:** 서버 컴포넌트 `app/page.tsx`가 `<section id="compare">`와 자리표시를 SSG HTML로 출력(앵커 상주). 내부 `CompareBoard`는 신규 클라이언트 래퍼 `CompareLazy`가 React.lazy 코드분할 + IntersectionObserver 뷰포트 지연으로 마운트. 네비 "비교" 링크는 홈 앵커 `/#compare`로 전환.

**Tech Stack:** Next.js 16.2.10(output:'export' SSG), React 19, TypeScript, vitest(유닛), Playwright(e2e). 테스트/명령은 모두 `apps/web`에서 실행.

## Global Constraints

- Next.js 16.2.10 + `output:'export'`(정적 익스포트). **`next/dynamic` 사용 금지** — 이 설치에 진입점 파일 없음. 지연 로드는 `React.lazy` + `IntersectionObserver`(프로젝트 기존 패턴 `components/LazyFontPreview.tsx` 준수).
- `apps/web/AGENTS.md`: "이 Next.js는 다르다" — Next API 사용 전 `node_modules/next/dist/docs` 확인. 본 계획은 프레임워크 독립 API(React.lazy/IntersectionObserver)만 사용해 이를 회피.
- 재사용: `CompareBoard.tsx` 로직 무변경. 예외 = heading level(전용 페이지 삭제로 `<h1>`→`<h2>`)만 조정.
- 완료조건 게이트: 활성 `/compare` 링크 0(네비/메타/구조화데이터/테스트/문서/sitemap), 앵커 3경우 동작(홈 내 클릭-타 페이지 이동-주소창 직접), 성능 회귀 없음(홈 mobile Lighthouse 3회 중앙값 LCP≤2.5s-CLS≤0.02-TBT≤100ms), 실배포(Cloudflare Pages)에서 `/compare` 404.
- 작업 제약: worktree 격리(현재 worktree, base=origin/develop), 내 파일만 스테이징, PR base=develop, squash merge.

---

## File Structure

- `components/CompareLazy.tsx` (신규): 비교 보드 지연 마운트 래퍼. 단일 책임 = React.lazy 코드분할 + IntersectionObserver로 뷰포트 진입 시 1회 마운트, 미지원 즉시 렌더, 진입 전 자리표시.
- `components/CompareBoard.tsx` (수정): heading `<h1>`→`<h2 id="compare-heading">`. 그 외 무변경.
- `app/page.tsx` (수정): 주간랭킹 아래-광고 위에 `<section id="compare">` + `CompareLazy` 배치.
- `app/page.module.css` (수정): `.compareSection`(scroll-margin-top + padding), `.comparePlaceholder`(반응형 min-height).
- `app/compare/page.tsx` + `app/compare/` (삭제): 라우트 제거.
- `components/Header.tsx` (수정): 데스크톱 "비교" `/compare`→`/#compare`.
- `components/MobileTabBar.tsx` (수정): 모바일 "비교" `/compare`→`/#compare`(유지).
- `app/sitemap.ts` (수정): 정적 라우트에서 `/compare/` 제거.
- `app/sitemap.test.ts` (수정): 기대 7→6개.
- `scripts/verify-seo-output.mjs`, `scripts/verify-seo-output.node-test.mjs` (수정): 기대 URL에서 `/compare/` 제거.
- `e2e/smoke.spec.ts` (수정): `routes`에서 `/compare` 제거, compare 테스트를 홈 앵커 기준으로 전환, 데스크톱/모바일 네비 href 기대 `/#compare`로.
- `e2e/smoke.spec.ts-snapshots/compare-screenshot-*.png` (삭제): 라우트 제거로 불필요.

---

## Task 1: /compare 라우트 제거 + SEO 동기화

**Files:**
- Modify: `apps/web/app/sitemap.ts:21-29`
- Modify: `apps/web/app/sitemap.test.ts:14-27`
- Modify: `apps/web/scripts/verify-seo-output.mjs:7-15`
- Modify: `apps/web/scripts/verify-seo-output.node-test.mjs:13`
- Delete: `apps/web/app/compare/page.tsx` (+ `apps/web/app/compare/` 디렉터리)

**Interfaces:**
- Produces: sitemap 정적 라우트 6개(홈/fonts/collections/trends/playground/about). `/compare` 미포함.

- [ ] **Step 1: sitemap 테스트를 6개 기대로 수정(실패 유도)**

`apps/web/app/sitemap.test.ts` 라인 14-27을 아래로 교체:

```typescript
  it("검색 노출 대상 정적 라우트 6개를 포함한다", async () => {
    const entries = await sitemap();
    const urls = entries.map((e) => e.url);

    expect(urls.slice(0, 6)).toEqual([
      "https://fontagit.com/",
      "https://fontagit.com/fonts/",
      "https://fontagit.com/collections/",
      "https://fontagit.com/trends/",
      "https://fontagit.com/playground/",
      "https://fontagit.com/about/",
    ]);
  });
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm vitest run app/sitemap.test.ts`
Expected: FAIL — 현재 sitemap이 `/compare/`를 포함해 slice(0,6) 불일치.

- [ ] **Step 3: sitemap.ts에서 /compare 제거**

`apps/web/app/sitemap.ts` 라인 21-29의 `staticEntries` 배열에서 `"/compare/",` 줄을 삭제:

```typescript
  const staticEntries: MetadataRoute.Sitemap = [
    "/",
    "/fonts/",
    "/collections/",
    "/trends/",
    "/playground/",
    "/about/",
  ].map((path) => ({ url: `${BASE_URL}${path}` }));
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm vitest run app/sitemap.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: SEO 검증 스크립트 기대 URL 동기화**

`apps/web/scripts/verify-seo-output.mjs` 라인 12의 `` `${EXPECTED_ORIGIN}/compare/`, `` 줄 삭제.
`apps/web/scripts/verify-seo-output.node-test.mjs` 라인 13의 `"https://fontagit.com/compare/",` 줄 삭제.

- [ ] **Step 6: /compare 라우트 삭제**

```bash
cd apps/web && git rm -r app/compare
```
Expected: `app/compare/page.tsx` 제거됨.

- [ ] **Step 7: node 검증 스크립트 실행**

Run: `cd apps/web && node scripts/verify-seo-output.node-test.mjs`
Expected: PASS (스크립트 자체 단위 테스트 그린).

- [ ] **Step 8: Commit**

```bash
cd apps/web && git add app/sitemap.ts app/sitemap.test.ts scripts/verify-seo-output.mjs scripts/verify-seo-output.node-test.mjs
git commit -m "refactor: sitemap-SEO에서 /compare 제거 및 라우트 삭제"
```

---

## Task 2: 네비 "비교" 링크 홈 앵커 전환

**Files:**
- Modify: `apps/web/components/Header.tsx:19`
- Modify: `apps/web/components/MobileTabBar.tsx:11`
- Modify: `apps/web/e2e/smoke.spec.ts:123,148`

**Interfaces:**
- Consumes: 없음.
- Produces: 데스크톱 헤더-모바일 탭바 "비교" 링크 href = `/#compare`.

- [ ] **Step 1: e2e 네비 기대를 /#compare로 수정(실패 유도)**

`apps/web/e2e/smoke.spec.ts` 라인 123을 교체:
```typescript
  await expect(tabBar.getByRole('link', { name: '비교' })).toHaveAttribute('href', /^\/#compare$/);
```
라인 148을 교체:
```typescript
  await expect(nav.getByRole('link', { name: '비교' })).toHaveAttribute('href', /^\/#compare$/);
```

- [ ] **Step 2: 실패 확인(빌드 없이는 e2e 불가 → 코드 변경 우선)**

Note: e2e는 빌드된 사이트 필요. 이 스텝은 육안 검토로 대체 — 현재 Header/MobileTabBar가 `/compare`라 위 기대와 불일치함을 확인.

- [ ] **Step 3: Header 데스크톱 링크 수정**

`apps/web/components/Header.tsx` 라인 19를 교체:
```tsx
        <Link href="/#compare" className={styles.toolLink}>비교</Link>
```

- [ ] **Step 4: MobileTabBar 탭 href 수정**

`apps/web/components/MobileTabBar.tsx` 라인 11을 교체:
```tsx
  { href: "/#compare", label: "비교" },
```

- [ ] **Step 5: 커밋(빌드 검증은 Task 4/5에서 e2e로)**

```bash
cd apps/web && git add components/Header.tsx components/MobileTabBar.tsx e2e/smoke.spec.ts
git commit -m "refactor: 비교 네비 링크를 홈 앵커(/#compare)로 전환"
```

Note: `MobileTabBar`의 active 판정(`t.href === "/" ? ... : pathname === t.href`)은 `/#compare`에서 `pathname==="/#compare"`가 항상 false라 비교 탭이 활성표시되지 않음 — 홈 앵커라 의도된 동작(별도 활성 페이지 없음). 로직 변경 불필요.

---

## Task 3: CompareLazy 지연 마운트 래퍼

**Files:**
- Create: `apps/web/components/CompareLazy.tsx`
- Test: `apps/web/components/CompareLazy.test.tsx`

**Interfaces:**
- Consumes: `CompareBoard`(named export, `./CompareBoard`).
- Produces: `CompareLazy({ placeholder: React.ReactNode }): JSX.Element` — 뷰포트 진입 전 `placeholder`, 진입 후 `CompareBoard` 렌더.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/components/CompareLazy.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { CompareLazy } from "./CompareLazy";

let ioCallback: (entries: Array<{ isIntersecting: boolean }>) => void;

beforeEach(() => {
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(cb: typeof ioCallback) {
        ioCallback = cb;
      }
      observe() {}
      disconnect() {}
    }
  );
});

describe("CompareLazy", () => {
  it("진입 전에는 placeholder만 보이고 비교 보드는 없다", () => {
    render(<CompareLazy placeholder={<div data-testid="ph" />} />);
    expect(screen.getByTestId("ph")).toBeTruthy();
    expect(screen.queryByLabelText("비교 문장 입력")).toBeNull();
  });

  it("뷰포트 진입 시 비교 보드를 마운트한다", async () => {
    render(<CompareLazy placeholder={<div data-testid="ph" />} />);
    await act(async () => {
      ioCallback([{ isIntersecting: true }]);
    });
    expect(await screen.findByLabelText("비교 문장 입력")).toBeTruthy();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm vitest run components/CompareLazy.test.tsx`
Expected: FAIL — `CompareLazy` 모듈 없음.

- [ ] **Step 3: CompareLazy 구현**

Create `apps/web/components/CompareLazy.tsx`:
```tsx
"use client";

import { lazy, Suspense, useEffect, useRef, useState } from "react";

const CompareBoard = lazy(() =>
  import("./CompareBoard").then((m) => ({ default: m.CompareBoard }))
);

export function CompareLazy({ placeholder }: { placeholder: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    if (shown || !ref.current) return;
    if (!("IntersectionObserver" in window)) {
      setShown(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [shown]);

  return (
    <div ref={ref}>
      {shown ? (
        <Suspense fallback={placeholder}>
          <CompareBoard />
        </Suspense>
      ) : (
        placeholder
      )}
    </div>
  );
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm vitest run components/CompareLazy.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd apps/web && git add components/CompareLazy.tsx components/CompareLazy.test.tsx
git commit -m "feat: 비교 보드 지연 마운트 래퍼 CompareLazy 추가"
```

---

## Task 4: 홈 비교 섹션 통합

**Files:**
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/app/page.module.css`
- Modify: `apps/web/components/CompareBoard.tsx:26`
- Modify: `apps/web/e2e/smoke.spec.ts:3-14,82-88`
- Delete: `apps/web/e2e/smoke.spec.ts-snapshots/compare-screenshot-*.png`

**Interfaces:**
- Consumes: `CompareLazy`(Task 3), `CompareBoard`.
- Produces: 홈 HTML에 `<section id="compare">` 상주 + 진입 시 비교 보드.

- [ ] **Step 1: e2e를 홈 비교 섹션 기준으로 수정(실패 유도)**

`apps/web/e2e/smoke.spec.ts` 라인 10의 `{ path: '/compare', name: 'Compare' },` 줄 삭제.
라인 82-88 `compare updates...` 테스트를 아래로 교체:
```typescript
test('home compare section: anchor, live update, font swap', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  // 앵커가 초기 HTML에 상주
  await expect(page.locator('#compare')).toHaveCount(1);
  // 비교 섹션으로 스크롤(뷰포트 진입 → 지연 마운트)
  await page.locator('#compare').scrollIntoViewIfNeeded();
  await page.getByLabel('비교 문장 입력').fill('나란히');
  await expect(page.getByText('나란히').first()).toBeVisible();
  await page.getByLabel('2번 폰트 선택').selectOption('nanum-myeongjo');
  await expect(page.getByLabel('2번 폰트 선택')).toHaveValue('nanum-myeongjo');
});

test('compare anchor works from another page', async ({ page }) => {
  await page.goto('/fonts/', { waitUntil: 'networkidle' });
  await page.goto('/#compare', { waitUntil: 'networkidle' });
  await page.locator('#compare').scrollIntoViewIfNeeded();
  await expect(page.getByLabel('비교 문장 입력')).toBeVisible();
});
```

- [ ] **Step 2: CompareBoard heading을 h2로 변경**

`apps/web/components/CompareBoard.tsx` 라인 26을 교체:
```tsx
        <h2 id="compare-heading" className={styles.title}>폰트 비교</h2>
```

- [ ] **Step 3: 홈 page.module.css에 섹션 스타일 추가**

`apps/web/app/page.module.css` 끝에 추가:
```css
.compareSection { scroll-margin-top: 72px; padding: 8px var(--pad-page) 0; max-width: 1180px; margin: 0 auto; width: 100%; }
.comparePlaceholder { min-height: 520px; }
@media (max-width: 720px) { .comparePlaceholder { min-height: 900px; } }
```

Note: `min-height`는 자리표시 CLS 방지용. 실제 보드 렌더 후 높이가 이보다 커도 자연 확장(레이아웃 하단이라 상단 밀림 없음). 값은 Step 6 빌드 후 실측으로 미세조정.

- [ ] **Step 4: 홈에 비교 섹션 배치**

`apps/web/app/page.tsx`를 아래로 교체:
```tsx
import type { Metadata } from "next";
import { Hero } from "@/components/Hero";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { CompareLazy } from "@/components/CompareLazy";
import { AdFitUnit } from "@/components/AdFitUnit";
import { ADFIT_UNIT_HOME } from "@/lib/analytics/constants";
import { getTrends } from "@/lib/data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

export default async function Home() {
  const { items, source } = await getTrends();
  return (
    <main className={styles.main}>
      <div className={styles.grid}>
        <Hero />
        <WeeklyRankPanel items={items} source={source} />
      </div>
      <section id="compare" className={styles.compareSection} aria-labelledby="compare-heading">
        <CompareLazy placeholder={<div className={styles.comparePlaceholder} aria-hidden="true" />} />
      </section>
      <section className={styles.adSection}>
        <div className={styles.container}>
          <AdFitUnit unit={ADFIT_UNIT_HOME ?? ""} width={320} height={100} label />
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 5: compare 스냅샷 삭제**

```bash
cd apps/web && git rm e2e/smoke.spec.ts-snapshots/compare-screenshot-chromium-mobile-darwin.png e2e/smoke.spec.ts-snapshots/compare-screenshot-chromium-desktop-darwin.png
```

- [ ] **Step 6: 빌드 후 홈 통합 확인**

Run: `cd apps/web && pnpm build`
Expected: 빌드 성공. 확인:
```bash
cd apps/web && test ! -e out/compare && echo "OK: /compare 없음"
grep -q 'id="compare"' out/index.html && echo "OK: #compare 상주"
grep -rq '/compare/' out/sitemap.xml && echo "FAIL: sitemap에 /compare" || echo "OK: sitemap 정리"
```
Expected: `OK: /compare 없음`, `OK: #compare 상주`, `OK: sitemap 정리`.

- [ ] **Step 7: e2e 스모크 실행**

Run: `cd apps/web && pnpm test:e2e smoke`
Expected: PASS(홈 비교 섹션-앵커-모바일 탭 href 포함). 스냅샷 신규 생성 필요 시 `--update-snapshots` 1회.

- [ ] **Step 8: Commit**

```bash
cd apps/web && git add app/page.tsx app/page.module.css components/CompareBoard.tsx e2e/smoke.spec.ts
git commit -m "feat: 폰트 비교를 홈 지연 섹션으로 통합"
```

---

## Task 5: 통합 검증 (완료조건 게이트)

**Files:** 없음(검증 전용).

- [ ] **Step 1: /compare 활성 링크 잔존 0 확인**

Run:
```bash
cd apps/web && grep -rn '/compare' app components lib scripts e2e --include='*.ts' --include='*.tsx' --include='*.mjs' | grep -v '/#compare' | grep -vi 'comparePixelData\|localeCompare\|compareUrlSets\|CompareLazy\|CompareBoard\|compareSection\|comparePlaceholder\|compare-heading\|#compare'
```
Expected: 출력 없음(활성 `/compare` 경로 0).

- [ ] **Step 2: 전체 유닛 테스트**

Run: `cd apps/web && pnpm vitest run`
Expected: 전부 PASS.

- [ ] **Step 3: 홈 성능 실측(회귀 없음)**

빌드 산출물을 로컬 서빙 후 홈 mobile Lighthouse 3회:
```bash
cd apps/web && npx serve out -l 4173 &
npx lighthouse http://localhost:4173/ --preset=perf --form-factor=mobile --screenElseEmulation --quiet --chrome-flags="--headless" --only-categories=performance
```
Expected(3회 중앙값): LCP≤2.5s, CLS≤0.02, TBT≤100ms. #25 실측(LCP 2.1s/CLS 0/TBT 40ms) 대비 회귀 없음. 실패 시 `comparePlaceholder` min-height 조정 또는 rootMargin 축소.

- [ ] **Step 4: 앵커 3경우 육안 확인**

로컬 서빙 상태에서: (a) 홈 헤더 "비교" 클릭 → #compare 스크롤, (b) `/fonts/`에서 헤더 "비교" 클릭 → 홈 이동 후 #compare, (c) 주소창 `http://localhost:4173/#compare` 직접 → #compare 위치. 3경우 모두 sticky 헤더에 가리지 않고(scroll-margin) 도달.

- [ ] **Step 5: 배포 후 404 확인(배포 시점)**

배포 후: `curl -I https://fontagit.com/compare/ | head -1`
Expected: `HTTP/2 404`. (배포 전이면 이 스텝은 배포 담당에게 인계.)

---

## 완료 기준 요약
- Task 1~4 커밋 완료 + Task 5 게이트 통과.
- 활성 `/compare` 링크 0, 홈 `#compare` 상주, 성능 회귀 없음, 앵커 3경우 동작.
- 미해결 시 스펙 `docs/superpowers/specs/2026-07-18-compare-home-merge-design.md`의 리스크 절 롤백 절차.
