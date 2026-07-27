# 홈 비교-캔버스 통합 보드 구현 계획 (#118)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** /playground 타입 캔버스와 홈 비교 섹션을 홈("/")의 통합 비교 보드(CompareCanvas) 하나로 합치고, /playground는 302로 홈에 리다이렉트한다.

**Architecture:** 신규 클라이언트 컴포넌트 `CompareCanvas`(대표 견본 + 8칸 그리드, 칸마다 셀렉트)를 만들어 기존 `CompareLazy`(IntersectionObserver 지연 로딩)가 홈에서 로드한다. PlaygroundCanvas-CompareBoard와 /playground 라우트는 삭제하고 네비-sitemap-SEO 스크립트-E2E를 함께 정리한다.

**Tech Stack:** Next.js(App Router, `output: "export"` 정적 사이트), React useState, CSS Modules, next/font(정적 무료 9종), Vitest + Testing Library, Playwright(E2E), Cloudflare Pages `_redirects`

**Spec:** `docs/superpowers/specs/2026-07-27-compare-canvas-home-merge-design.md`

## Global Constraints

- 작업 루트: 웹 앱은 `apps/web` (npm 명령은 여기서 실행), git 명령은 repo 루트
- base 브랜치: `develop` (main은 release 전용). 작업 브랜치 `feature/118-home-compare-canvas`
- 커밋 형식: `<타입>: <설명>` (feat/fix/refactor/docs/test/chore), 어트리뷰션 없음
- 견본 기본 문구(정확히 이 문자열): `다람쥐 헌 쳇바퀴에 타고파 1234 !@#$`
- 셀렉트 후보는 `data/fonts.ts`의 `tier === "free"` 9종만. slug 목록: pretendard, black-han-sans, jua, do-hyeon, gowun-batang, nanum-myeongjo, kirang-haerang, gaegu, song-myung
- 폰트 적용은 기존 유틸 `familyOf(fontKey)` (`@/lib/fonts`) 재사용. 새 폰트 로딩 코드 금지
- 리다이렉트는 301이 아닌 **302** (#69에서 /playground 재사용 예정)
- 검증 명령: `npm test`(vitest run), `npm run lint`, `npm run build`
- ⚠️ 홈 `app/page.tsx`의 `<section id="compare" aria-labelledby="compare-heading">`가 제목 id에 의존한다. 새 컴포넌트 h2는 반드시 `id="compare-heading"` 유지

---

### Task 1: 브랜치 준비 + #117 잔재 정리 + 문서 커밋

**Files:**
- Modify: 없음 (git 상태 정리만)
- 커밋 대상: `docs/superpowers/specs/2026-07-27-compare-canvas-home-merge-design.md`, `docs/review/review-result-20260727-135101.md`, `docs/superpowers/plans/2026-07-27-home-compare-canvas.md`

**Interfaces:**
- Produces: `feature/118-home-compare-canvas` 브랜치(origin/develop 최신 기준). 이후 모든 Task는 이 브랜치에서 작업

배경: 워킹트리는 현재 `feature/117-header-search-always-on` 브랜치이고 미커밋 변경(Header, HeaderSearch 등)이 있다. #117은 이미 PR #121로 develop에 머지되었으므로 이 변경은 잔재일 가능성이 높다. 내용이 develop에 있음을 확인한 뒤에만 폐기한다.

- [ ] **Step 1: 위치-원격 상태 확인**

```bash
cd /Users/joel.silver/Workspace/gitroom/python/fontagit
pwd && git rev-parse --show-toplevel && git branch --show-current
git fetch origin
git log --oneline origin/develop -3
```

Expected: 현재 브랜치 `feature/117-header-search-always-on`, origin/develop 최근 커밋에 #117(PR #121) 머지 확인

- [ ] **Step 2: 미커밋 변경이 develop에 이미 반영됐는지 대조**

```bash
git diff origin/develop --stat -- apps/web
```

Expected: **출력 없음**(수정된 apps/web 파일들의 내용이 origin/develop과 동일 = 잔재 확정).
⚠️ 출력이 있으면(=develop에 없는 내용) 여기서 **중단하고 사용자에게 보고**한다. 폐기 금지.
`.serena/project.yml`은 도구 상태 파일이라 develop과 달라도 무관 — 대조 대상에서 제외하고 Step 3에서 함께 폐기한다.

- [ ] **Step 3: 잔재 폐기 후 develop 기준 새 브랜치 생성**

```bash
git restore .
git switch develop
git pull --ff-only
git switch -c feature/118-home-compare-canvas
```

Expected: 새 브랜치 생성, `git status --short`에 추적 파일 변경 없음(문서-untracked만 남음). untracked 파일(.playwright-mcp/, docs/mockups/ 등)은 건드리지 않는다

- [ ] **Step 4: 스펙-리뷰-계획 문서 커밋**

```bash
git add docs/superpowers/specs/2026-07-27-compare-canvas-home-merge-design.md docs/review/review-result-20260727-135101.md docs/superpowers/plans/2026-07-27-home-compare-canvas.md
git commit -m "docs: 홈 비교-캔버스 통합 설계 스펙-리뷰-계획 (#118)"
```

---

### Task 2: CompareCanvas 컴포넌트 (TDD)

**Files:**
- Create: `apps/web/components/CompareCanvas.tsx`
- Create: `apps/web/components/CompareCanvas.module.css`
- Test: `apps/web/components/CompareCanvas.test.tsx`

**Interfaces:**
- Consumes: `fonts` (`@/data/fonts`), `familyOf(fontKey)` (`@/lib/fonts`), `TierChip` (`./TierChip`)
- Produces: named export `CompareCanvas`(props 없음). 접근성 계약 — input `aria-label="비교 문장 입력"`, 대표 셀렉트 `aria-label="대표 폰트 선택"`, 그리드 셀렉트 `aria-label="{i+1}번 폰트 선택"`, 제목 `<h2 id="compare-heading">`, 대표 견본 `data-testid="hero-specimen"`. Task 3-5가 이 셀렉터에 의존

- [ ] **Step 1: 실패하는 테스트 작성** — `apps/web/components/CompareCanvas.test.tsx`

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CompareCanvas } from "./CompareCanvas";

describe("CompareCanvas", () => {
  it("기본 문구와 셀렉트 9개(대표 1 + 그리드 8)를 렌더한다", () => {
    render(<CompareCanvas />);
    expect(screen.getAllByRole("combobox")).toHaveLength(9);
    expect(screen.getByTestId("hero-specimen")).toHaveTextContent(
      "다람쥐 헌 쳇바퀴에 타고파 1234 !@#$"
    );
  });

  it("대표 셀렉트 변경 시 대표 견본 폰트와 상세 링크가 바뀐다", async () => {
    render(<CompareCanvas />);
    await userEvent.selectOptions(
      screen.getByLabelText("대표 폰트 선택"),
      "gowun-batang"
    );
    const heroDetail = screen.getAllByRole("link", { name: "상세" })[0];
    expect(heroDetail).toHaveAttribute("href", "/fonts/gowun-batang");
    expect(
      screen.getByTestId("hero-specimen").getAttribute("style") ?? ""
    ).toContain("gowun-batang");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && npx vitest run components/CompareCanvas.test.tsx`
Expected: FAIL — "Failed to resolve import ./CompareCanvas" (모듈 없음)

- [ ] **Step 3: 구현** — `apps/web/components/CompareCanvas.tsx`

```tsx
"use client";
import { useState } from "react";
import Link from "next/link";
import { fonts } from "@/data/fonts";
import { familyOf } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./CompareCanvas.module.css";

const DEFAULT_TEXT = "다람쥐 헌 쳇바퀴에 타고파 1234 !@#$";
const PRESETS = [DEFAULT_TEXT, "당신의 폰트 아지트", "가나다라 ABC 0123", "The quick brown fox"];
const OPTIONS = fonts.filter((f) => f.tier === "free");
const DEFAULT_HERO = "pretendard";
const DEFAULT_GRID = OPTIONS.filter((f) => f.slug !== DEFAULT_HERO).map((f) => f.slug);

export function CompareCanvas() {
  const [text, setText] = useState(DEFAULT_TEXT);
  const [heroSlug, setHeroSlug] = useState(DEFAULT_HERO);
  const [gridSlugs, setGridSlugs] = useState<string[]>(DEFAULT_GRID);
  const shown = text || " ";
  const hero = OPTIONS.find((f) => f.slug === heroSlug);

  const changeGrid = (index: number, slug: string) =>
    setGridSlugs((prev) => prev.map((v, i) => (i === index ? slug : v)));

  return (
    <div className={styles.wrap}>
      <div className={styles.head}>
        <h2 id="compare-heading" className={styles.title}>폰트 비교</h2>
        <span className={styles.subtitle}>같은 문장을 모든 폰트에 나란히 놓고 결정하세요</span>
      </div>
      <div className={styles.inputRow}>
        <svg className={styles.icon} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M4 7h16M4 12h10M4 17h13" /></svg>
        <input className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder={DEFAULT_TEXT} aria-label="비교 문장 입력" />
        <button type="button" className={styles.clear} onClick={() => setText("")}>지우기</button>
      </div>
      <div className={styles.presets}>
        {PRESETS.map((p) => (
          <button type="button" key={p} className={styles.preset} onClick={() => setText(p)}>{p}</button>
        ))}
      </div>
      {hero && (
        <div className={styles.hero}>
          <div className={styles.heroLabel}>
            <select className={styles.select} value={heroSlug} onChange={(e) => setHeroSlug(e.target.value)} aria-label="대표 폰트 선택">
              {OPTIONS.map((o) => (
                <option key={o.slug} value={o.slug}>{o.nameKo}</option>
              ))}
            </select>
            <div className={styles.heroRight}>
              <TierChip tier={hero.tier} />
              <Link href={`/fonts/${hero.slug}`} className={styles.cellDetail}>상세</Link>
              <span className={styles.heroSize}>96px</span>
            </div>
          </div>
          <div className={styles.heroSpecimen} data-testid="hero-specimen" style={{ fontFamily: familyOf(hero.fontKey) }}>{shown}</div>
        </div>
      )}
      <div className={styles.gridHead}>무료 폰트 나란히 보기 <span className={styles.count}>- 대표 1 + {gridSlugs.length}종</span></div>
      <div className={styles.grid}>
        {gridSlugs.map((slug, i) => {
          const f = OPTIONS.find((x) => x.slug === slug);
          if (!f) return null;
          return (
            <div key={i} className={styles.cell}>
              <div className={styles.cellHead}>
                <select className={styles.select} value={slug} onChange={(e) => changeGrid(i, e.target.value)} aria-label={`${i + 1}번 폰트 선택`}>
                  {OPTIONS.map((o) => (
                    <option key={o.slug} value={o.slug}>{o.nameKo}</option>
                  ))}
                </select>
                <div className={styles.cellRight}>
                  <TierChip tier={f.tier} />
                  <Link href={`/fonts/${f.slug}`} className={styles.cellDetail}>상세</Link>
                </div>
              </div>
              <div className={styles.cellSpecimen} style={{ fontFamily: familyOf(f.fontKey) }}>{shown}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

`apps/web/components/CompareCanvas.module.css` (PlaygroundCanvas 레이아웃 + CompareBoard 셀렉트 스타일 병합):

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
.select { border: 1px solid var(--border); border-radius: 8px; padding: 5px 8px; font-family: inherit; font-size: 13px; font-weight: 700; color: var(--ink); background: var(--bg); cursor: pointer; min-width: 0; }
.hero { padding: 44px 0; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); margin-top: 26px; }
.heroLabel { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; gap: 8px; flex-wrap: wrap; }
.heroRight { display: flex; gap: 10px; align-items: center; }
.heroSize { font-size: 12px; font-weight: 600; color: var(--sub-2); }
.heroSpecimen { font-weight: 800; font-size: 96px; line-height: 1; color: var(--ink); letter-spacing: -.03em; word-break: break-all; overflow-wrap: anywhere; }
.gridHead { font-size: 13px; font-weight: 700; color: var(--ink); margin: 28px 0 16px; }
.count { font-size: 12px; font-weight: 400; color: var(--sub-2); }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.cell { border: 1px solid var(--border); border-radius: 12px; background: var(--surface); padding: 18px 20px; }
.cellHead { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; gap: 8px; }
.cellRight { display: flex; gap: 10px; align-items: center; flex: none; }
.cellDetail { font-size: 11px; font-weight: 500; color: var(--sub-2); }
.cellSpecimen { font-size: 36px; line-height: 1.1; color: var(--ink); word-break: break-all; overflow-wrap: anywhere; }
@media (max-width: 620px) {
  .heroSpecimen { font-size: 60px; }
  .grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && npx vitest run components/CompareCanvas.test.tsx`
Expected: PASS 2건

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/CompareCanvas.tsx apps/web/components/CompareCanvas.module.css apps/web/components/CompareCanvas.test.tsx
git commit -m "feat: 대표+8칸 셀렉트를 갖춘 CompareCanvas 통합 비교 보드 (#118)"
```

---

### Task 3: 홈 연결 — CompareLazy 로드 대상 교체

**Files:**
- Modify: `apps/web/components/CompareLazy.tsx` (lazy import 1곳)
- Test(기존 그대로 통과 확인): `apps/web/components/CompareLazy.test.tsx`, `apps/web/app/page.test.tsx`

**Interfaces:**
- Consumes: Task 2의 `CompareCanvas`(aria-label "비교 문장 입력" — CompareLazy.test.tsx가 이 라벨로 마운트를 검증하므로 테스트 수정 불필요)
- Produces: 홈 비교 섹션이 CompareCanvas를 지연 로드. `app/page.tsx`는 무변경(기존 `<CompareLazy placeholder=... />` 그대로)

- [ ] **Step 1: CompareLazy.tsx의 lazy import 교체**

변경 전:

```tsx
const CompareBoard = lazy(() =>
  import("./CompareBoard").then((m) => ({ default: m.CompareBoard }))
);
```

변경 후(JSX 사용부 `<CompareBoard />`도 `<CompareCanvas />`로 함께 변경):

```tsx
const CompareCanvas = lazy(() =>
  import("./CompareCanvas").then((m) => ({ default: m.CompareCanvas }))
);
```

- [ ] **Step 2: 관련 테스트 통과 확인**

Run: `cd apps/web && npx vitest run components/CompareLazy.test.tsx app/page.test.tsx`
Expected: PASS (CompareLazy 2건 + 홈 2건). "비교 문장 입력" 라벨을 CompareCanvas가 그대로 제공하므로 수정 없이 통과

- [ ] **Step 3: 커밋**

```bash
git add apps/web/components/CompareLazy.tsx
git commit -m "feat: 홈 비교 섹션 로드 대상을 CompareCanvas로 교체 (#118)"
```

---

### Task 4: 구화면 제거 + 네비-sitemap-SEO 스크립트 정리

**Files:**
- Delete: `apps/web/app/playground/page.tsx`, `apps/web/app/playground/page.module.css`, `apps/web/components/PlaygroundCanvas.tsx`, `apps/web/components/PlaygroundCanvas.module.css`, `apps/web/components/CompareBoard.tsx`, `apps/web/components/CompareBoard.module.css`
- Modify: `apps/web/app/sitemap.ts`, `apps/web/app/sitemap.test.ts`, `apps/web/components/Header.tsx`, `apps/web/components/MobileTabBar.tsx`, `apps/web/scripts/verify-seo-output.mjs`, `apps/web/scripts/verify-seo-output.node-test.mjs`

**Interfaces:**
- Consumes: Task 3 완료 상태(CompareBoard를 참조하는 코드 없음)
- Produces: apps/web 코드에서 /playground-CompareBoard-PlaygroundCanvas 참조 0건(e2e 제외, e2e는 Task 5)

- [ ] **Step 1: 파일 삭제**

```bash
git rm -r apps/web/app/playground
git rm apps/web/components/PlaygroundCanvas.tsx apps/web/components/PlaygroundCanvas.module.css
git rm apps/web/components/CompareBoard.tsx apps/web/components/CompareBoard.module.css
```

(PlaygroundCanvas-CompareBoard 전용 테스트 파일은 존재하지 않음 — CompareLazy.test가 커버했음)

- [ ] **Step 2: sitemap.ts에서 playground 제거**

`apps/web/app/sitemap.ts`의 staticEntries 배열에서 `"/playground/",` 한 줄 삭제:

```ts
  const staticEntries: MetadataRoute.Sitemap = [
    "/",
    "/fonts/",
    "/collections/",
    "/trends/",
    "/about/",
  ].map((path) => ({ url: `${BASE_URL}${path}` }));
```

- [ ] **Step 3: sitemap.test.ts 기대값 갱신**

첫 테스트를 다음으로 교체(6개 → 5개, playground 제거):

```ts
  it("검색 노출 대상 정적 라우트 5개를 포함한다", async () => {
    const entries = await sitemap();
    const urls = entries.map((e) => e.url);

    expect(urls.slice(0, 5)).toEqual([
      "https://fontagit.com/",
      "https://fontagit.com/fonts/",
      "https://fontagit.com/collections/",
      "https://fontagit.com/trends/",
      "https://fontagit.com/about/",
    ]);
  });
```

- [ ] **Step 4: Header.tsx 네비 링크 2개 제거**

nav 안에서 아래 2줄 삭제(폰트-트렌드-컬렉션-등록은 유지):

```tsx
          <Link href="/playground" className={styles.mobileTabLink}>캔버스</Link>
          <Link href="/#compare" className={styles.mobileTabLink}>비교</Link>
```

- [ ] **Step 5: MobileTabBar.tsx 탭 2개 제거**

TABS 배열에서 아래 2줄 삭제(홈-폰트-트렌드 3탭 유지):

```tsx
  { href: "/playground", label: "캔버스" },
  { href: "/#compare", label: "비교" },
```

- [ ] **Step 6: SEO 검증 스크립트 2곳에서 playground 제거**

`apps/web/scripts/verify-seo-output.mjs`의 REQUIRED_URLS에서 `` `${EXPECTED_ORIGIN}/playground/`, `` 한 줄 삭제.
`apps/web/scripts/verify-seo-output.node-test.mjs`의 requiredUrls에서 `"https://fontagit.com/playground/",` 한 줄 삭제.

- [ ] **Step 7: 단위 테스트-노드 테스트-린트 전체 확인**

```bash
cd apps/web
npm test
node --test scripts/verify-seo-output.node-test.mjs
npm run lint
```

Expected: 모두 PASS. 실패 시 원인 파악 후 수정(특히 삭제 파일을 import하는 잔존 참조)

- [ ] **Step 8: 커밋**

```bash
git add -A apps/web/app apps/web/components apps/web/scripts
git commit -m "refactor: playground 라우트-구 비교 보드 제거, 네비-sitemap-SEO 검증 정리 (#118)"
```

---

### Task 5: E2E 스모크 갱신

**Files:**
- Modify: `apps/web/e2e/smoke.spec.ts`
- Delete: `apps/web/e2e/smoke.spec.ts-snapshots/` 내 playground 스크린샷 파일들

**Interfaces:**
- Consumes: Task 2의 접근성 계약(aria-label "비교 문장 입력", 프리셋 버튼 텍스트), Task 4 완료 상태(네비에 캔버스-비교 없음)

- [ ] **Step 1: routes 배열에서 playground 항목 삭제**

```ts
  { path: '/playground', name: 'Playground' },
```

위 한 줄을 삭제한다.

- [ ] **Step 2: playground 테스트 2건을 홈 비교 보드 테스트로 교체**

기존 `playground canvas updates all specimens live`-`playground preset fills the input` 2건을 삭제하고 다음으로 교체:

```ts
test('home compare canvas updates specimens live', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.locator('#compare').scrollIntoViewIfNeeded();
  const input = page.getByLabel('비교 문장 입력');
  await input.fill('불꽃');
  await expect(page.getByText('불꽃').first()).toBeVisible();
});

test('home compare preset fills the input', async ({ page }) => {
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.locator('#compare').scrollIntoViewIfNeeded();
  await page.getByRole('button', { name: '당신의 폰트 아지트' }).click();
  await expect(page.getByLabel('비교 문장 입력')).toHaveValue('당신의 폰트 아지트');
});
```

- [ ] **Step 3: 네비 테스트를 부정 검증으로 교체**

기존 `header nav contains canvas and compare links (desktop)` 테스트를 다음으로 교체:

```ts
test('header nav no longer contains canvas and compare links (desktop)', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await page.goto('/', { waitUntil: 'networkidle' });
  const nav = page.getByRole('navigation').first();
  await expect(nav.getByRole('link', { name: '캔버스' })).toHaveCount(0);
  await expect(nav.getByRole('link', { name: '비교' })).toHaveCount(0);
});
```

- [ ] **Step 4: 스테일 스냅샷 삭제 후 E2E 실행(스냅샷 갱신)**

```bash
cd apps/web
rm -f e2e/smoke.spec.ts-snapshots/playground-*.png
npm run e2e -- --update-snapshots --workers=1
```

Expected: 전체 PASS. 홈 스크린샷은 새 보드 반영으로 갱신됨(diff 확인 후 커밋). 빌드 포함이라 수 분 소요

- [ ] **Step 5: 커밋**

```bash
git add apps/web/e2e
git commit -m "test: E2E 스모크를 홈 통합 비교 보드 기준으로 갱신 (#118)"
```

---

### Task 6: /playground 302 리다이렉트 + 최종 검증

**Files:**
- Create: `apps/web/public/_redirects`

**Interfaces:**
- Consumes: Task 4 완료 상태(out/에 playground 산출물 없음)

- [ ] **Step 1: _redirects 생성** — `apps/web/public/_redirects` (아래 2줄 그대로)

```
/playground/ / 302
/playground / 302
```

- [ ] **Step 2: 빌드 및 산출물 확인**

```bash
cd apps/web
npm run build
test -f out/_redirects && echo "redirects OK"
test ! -d out/playground && echo "no playground OK"
npm run verify:seo
```

Expected: 빌드 그린, "redirects OK", "no playground OK", verify:seo PASS(Task 4에서 기대 URL 갱신됨)

- [ ] **Step 3: 참조 0건 최종 확인**

```bash
cd /Users/joel.silver/Workspace/gitroom/python/fontagit
grep -rn "playground\|PlaygroundCanvas\|CompareBoard" apps/web/app apps/web/components apps/web/lib apps/web/scripts apps/web/e2e --include="*.ts" --include="*.tsx" --include="*.mjs"
```

Expected: 출력 없음(0건). 출력이 있으면 해당 참조 정리 후 재확인

- [ ] **Step 4: 전체 테스트 최종 확인 및 커밋**

```bash
cd apps/web && npm test
cd /Users/joel.silver/Workspace/gitroom/python/fontagit
git add apps/web/public/_redirects
git commit -m "chore: /playground를 홈으로 302 리다이렉트 (#118)"
```

- [ ] **Step 5: 배포 후 확인 항목 기록(이 브랜치에서는 실행 불가)**

release로 main 배포된 뒤: `curl -I https://fontagit.com/playground/` → 302 + `location: /` 확인, 데스크톱-모바일 실화면에서 홈 보드-네비 확인. PR 본문 TODO에 포함할 것
