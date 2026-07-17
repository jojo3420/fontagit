# FontAgit 웹 토대 + 핵심 화면 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 `apps/web` 스캐폴드를 스펙 토대(CSS 변수 토큰 + CSS Modules + self-host 폰트)로 재정비하고, 핵심 4화면(홈/목록/상세/트렌드)을 디자인 95% 재현으로 구현한다.

**Architecture:** Next.js 16 App Router를 정적 출력(`output: 'export'`)으로 서빙한다. 스타일은 `styles/tokens.css`의 CSS 변수 + 컴포넌트/페이지별 CSS Modules(인라인 스타일 금지). 콘텐츠는 `data/`의 타입 지정 목업. 폰트는 Pretendard Variable(npm 패키지, 로컬 self-host) + 견본 한글 폰트(next/font/google, preload 비활성)로 self-host. 로직 있는 부분만 Vitest 단위 테스트, 화면은 build + Playwright 스모크로 검증.

**Tech Stack:** Next.js 16.2.10, React 19.2.4, TypeScript 5, CSS Modules, Vitest + React Testing Library, @playwright/test, pretendard(npm), next/font/google.

## Global Constraints

- 결과물 위치: `apps/web`. 패키지명은 반드시 `web`(기존 `pnpm --filter web`, 루트 `web:dev`/`web:build` 스크립트와 정합). 기존 스캐폴드를 수정하며, 이 세션 결정(CSS Modules)이 Tailwind보다 우선한다 — Tailwind는 제거한다.
- 스타일은 CSS Modules + CSS 변수만 사용한다. 페이지/컴포넌트의 인라인 `style={{...}}` 사용 금지(단, 견본 폰트 적용처럼 데이터로 결정되는 `fontFamily`는 예외로 인라인 허용).
- 워크스페이스 주의: `apps/web`은 create-next-app이 자체 `pnpm-lock.yaml`과 `pnpm-workspace.yaml`을 갖고 있다. 설치/빌드는 `apps/web` 안에서 수행하고, `pnpm install`로 바뀐 `apps/web/pnpm-lock.yaml`은 반드시 커밋한다.
- 원본 디자인(시각 SSOT): `docs/design/fontagit-v2/project/FontAgit 화면 세트.dc.html`. 화면 마크업은 이 파일의 해당 섹션을 번역해 재현한다(그대로 렌더하지 말고 소스를 읽어 픽셀 값을 옮긴다).
- 스펙: `docs/superpowers/specs/2026-07-12-fontagit-web-screens-design.md`. 토큰/컴포넌트/데이터/검증 기준의 SSOT.
- Next.js 16 주의(AGENTS.md): dynamic route의 `params`는 async다 — `params: Promise<{ slug: string }>` + `const { slug } = await params`. 코드 전 `apps/web/node_modules/next/dist/docs/`의 해당 가이드 확인.
- 정적 출력: `next.config.ts`에 `output: 'export'`, `images: { unoptimized: true }`, `trailingSlash: true`. 빌드 산출물은 `out/`. 서버 전용 기능/런타임 리다이렉트 사용 금지.
- 디자인 토큰(값 그대로): 배경 `#FAFAF8`, 잉크 `#1A1A1A`, 서브 `#6B6B6B`, 약한 서브 `#9A9A96`, 경계 `#E6E6E2`, 표면 `#FFFFFF`, 보조표면 `#F4F4F0`, 포인트 `#2C5545`, 포인트약배경 `rgba(44,85,69,.1)`, on-point `#FFFFFF`. 상태색: 상승 `#2C7A5B`, 하락/불가 `#B4564B`, 유지 `#9A9A96`, 조건부 `#B4863C`. 다크: 배경 `#16171A`, 잉크 `#EDEDEA`, 포인트 `#7FC2A2`, on-point 어두운 잉크 `#16171A`.
- 타이포 스케일: 히어로 42, 화면 제목 24, 본문 15, 캡션 12. UI 텍스트는 항상 Pretendard, 견본 텍스트만 견본 폰트로 렌더.
- 포인트색은 액션에만. 라이선스 상태는 색 단독 금지 — 아이콘+텍스트 병행(WCAG AA).
- 보이스: 브랜드 층(로고/히어로/404/빈상태)은 존댓말 다정 담백, 정보 층은 건조한 사실만("안전/문제없음" 같은 보증 표현 금지). 유료 폰트 견본은 실제 서체가 아니면 "대체 견본"임을 반드시 명시(오정보 금지).
- 비동작 액션(검색/등록/필터 칩 등)은 `type="button"` + 상태는 `aria-pressed`로 표기하고 폼 제출/네비게이션을 하지 않는다.
- 95% 시각 판정(스펙 9장): 기준 브라우저 Chromium, 뷰포트 데스크톱 1280 / 모바일 390, DPR 1. Playwright가 각 라우트 스크린샷을 아티팩트로 남기고, 원본 참조와 육안 5% 이내로 대조한다. 폰트 안티에일리어싱 차이는 무시.
- 커밋 컨벤션: `<타입>: <설명>`(feat/fix/refactor/chore/test).

---

## 파일 구조 (이 계획 범위)

```
apps/web/
  next.config.ts            정적 출력 (수정)
  postcss.config.mjs        삭제 (Tailwind 제거)
  vitest.config.ts          단위 테스트 (신규)
  vitest.setup.ts           jest-dom (신규)
  playwright.config.ts      스모크 (신규)
  package.json              deps/scripts (수정)
  app/
    layout.tsx              루트: 폰트/테마/헤더/푸터 (수정)
    page.tsx / page.module.css       홈 (수정/신규)
    globals.css             리셋 + 토큰 + Pretendard (수정)
    fonts/page.tsx / fonts/page.module.css        목록 (신규)
    fonts/[slug]/page.tsx / fonts/[slug]/page.module.css   상세 (신규)
    trends/page.tsx / trends/page.module.css      트렌드 (신규)
    not-found.tsx / not-found.module.css          404 (신규)
  components/                각 *.tsx + *.module.css
    Header Footer Hero TierChip LicenseBadge Button FilterChip
    TrendRow TrendTable FontCard FontGrid PreviewInput Specimen AdSlot
  lib/  fonts.ts  data.ts
  data/  fonts.ts  trends.ts
  types/  font.ts
  styles/  tokens.css
  e2e/  smoke.spec.ts
```

---

## Task 1: 스캐폴드 재정비 (Tailwind 제거 + 토큰 + 정적 출력)

**Files:**
- Modify: `apps/web/package.json`
- Delete: `apps/web/postcss.config.mjs`
- Modify: `apps/web/next.config.ts`
- Create: `apps/web/styles/tokens.css`
- Modify: `apps/web/app/globals.css`

**Interfaces:**
- Produces: Tailwind 없는 빌드 가능 상태, CSS 변수 토큰(라이트/다크), Pretendard Variable self-host, 정적 출력 설정.

- [ ] **Step 1: Tailwind devDependencies 제거**

`apps/web/package.json`의 `devDependencies`에서 `@tailwindcss/postcss`, `tailwindcss` 두 줄 삭제. 나머지 유지.

- [ ] **Step 2: postcss 설정 삭제**

Run: `rm apps/web/postcss.config.mjs`

- [ ] **Step 3: 정적 출력 설정**

`apps/web/next.config.ts` 전체 교체:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
```

- [ ] **Step 4: 토큰 파일 작성**

`apps/web/styles/tokens.css`:

```css
:root {
  --bg: #FAFAF8; --ink: #1A1A1A; --sub: #6B6B6B; --sub-2: #9A9A96;
  --border: #E6E6E2; --surface: #FFFFFF; --surface-2: #F4F4F0;
  --point: #2C5545; --point-weak: rgba(44, 85, 69, .1); --on-point: #FFFFFF;
  --up: #2C7A5B; --down: #B4564B; --hold: #9A9A96; --warn: #B4863C;
  --radius-card: 12px; --radius-btn: 10px; --radius-pill: 20px;
  --pad-page: 40px;
}
:root[data-theme="dark"] {
  --bg: #16171A; --ink: #EDEDEA; --sub: #B9BCBD; --sub-2: #8A8E90;
  --border: #2A2C30; --surface: #1D1F22; --surface-2: #202226;
  --point: #7FC2A2; --point-weak: rgba(127, 194, 162, .14); --on-point: #16171A;
}
@media (max-width: 620px) { :root { --pad-page: 20px; } }
```

- [ ] **Step 5: globals.css 교체 (리셋 + 토큰 + Pretendard Variable)**

`apps/web/app/globals.css` 전체 교체. Pretendard는 variable CSS로 self-host(패키지에 `variable/pretendardvariable.css` 존재 확인됨):

```css
@import "pretendard/dist/web/variable/pretendardvariable.css";
@import "../styles/tokens.css";

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
html { -webkit-text-size-adjust: 100%; }
body {
  min-height: 100vh; display: flex; flex-direction: column;
  background: var(--bg); color: var(--ink);
  font-family: "Pretendard Variable", "Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 15px; line-height: 1.6; -webkit-font-smoothing: antialiased;
}
a { color: inherit; text-decoration: none; }
button { font-family: inherit; }
img, svg { max-width: 100%; display: block; }
```

- [ ] **Step 6: 설치 + 빌드 확인**

Run: `cd apps/web && pnpm install && pnpm build`
Expected: 성공. Tailwind 관련 에러 없음, `styles/tokens.css`와 Pretendard import 해석됨, `out/` 생성.

- [ ] **Step 7: Commit (lockfile 포함)**

```bash
git add apps/web/package.json apps/web/next.config.ts apps/web/styles/tokens.css apps/web/app/globals.css apps/web/pnpm-lock.yaml
git rm apps/web/postcss.config.mjs
git commit -m "chore(web): remove Tailwind, add CSS tokens + static export"
```

---

## Task 2: 타입 정의 (types/font.ts, FontKey 유니언)

**Files:**
- Create: `apps/web/types/font.ts`

**Interfaces:**
- Produces: `FontKey`(유니언), `Category`, `Tier`, `Commercial`, `TrendChange`, `Font`, `TrendItem`, `Collection`. `fontKey`는 오타를 컴파일 타임에 잡도록 유니언으로 제한.

- [ ] **Step 1: 타입 작성**

`apps/web/types/font.ts`:

```ts
export type FontKey =
  | "pretendard" | "blackHanSans" | "jua" | "doHyeon" | "gowunBatang"
  | "nanumMyeongjo" | "kirangHaerang" | "gaegu" | "songMyung";

export type Category = "고딕" | "명조" | "손글씨" | "장식";
export type Tier = "free" | "paid";
export type Commercial = "yes" | "conditional" | "no";
export type TrendChange = "up" | "down" | "hold" | "new";

export interface Font {
  slug: string;
  nameKo: string;
  nameEn: string;
  fontKey: FontKey;
  tier: Tier;
  category: Category;
  foundry: string;
  availableWeights: number[]; // 단일 굵기 폰트는 [400]
  moves: number;
  license: { commercial: Commercial; verifiedAt: string };
  officialUrl: string;
  aliases: string[];
  freeAlternatives?: string[]; // 실제 slug, 최대 3
}

export interface TrendItem {
  rank: number;
  change: TrendChange;
  changeAmount?: number;
  font: Pick<Font, "slug" | "nameKo" | "fontKey" | "tier">;
  moves: number;
}

export interface Collection {
  slug: string; title: string; intro: string;
  items: { fontSlug: string; comment: string }[];
}
```

- [ ] **Step 2: 타입 체크**

Run: `cd apps/web && pnpm exec tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 3: Commit**

```bash
git add apps/web/types/font.ts
git commit -m "feat(web): font domain types with FontKey union"
```

---

## Task 3: 목업 폰트 데이터 (data/fonts.ts, 10종)

**Files:**
- Create: `apps/web/data/fonts.ts`

**Interfaces:**
- Consumes: `Font`, `FontKey` from `types/font.ts`.
- Produces: `fonts: Font[]` (10종: 무료 9 + 유료 1). TOP10 표를 채우기에 충분. `fontKey`는 Task 5 매핑 키와 일치.

- [ ] **Step 1: 데이터 작성**

`apps/web/data/fonts.ts`:

```ts
import type { Font } from "@/types/font";

export const fonts: Font[] = [
  { slug: "pretendard", nameKo: "프리텐다드", nameEn: "Pretendard", fontKey: "pretendard",
    tier: "free", category: "고딕", foundry: "길형진", availableWeights: [400, 500, 700, 800],
    moves: 5120, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://github.com/orioncactus/pretendard", aliases: ["프리텐다드", "pretendard", "프리텐더드"] },
  { slug: "black-han-sans", nameKo: "검은고딕", nameEn: "Black Han Sans", fontKey: "blackHanSans",
    tier: "free", category: "고딕", foundry: "장수영-Zess", availableWeights: [400],
    moves: 3120, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Black+Han+Sans", aliases: ["검은고딕", "블랙한산스", "black han"] },
  { slug: "jua", nameKo: "배민 주아", nameEn: "Jua", fontKey: "jua",
    tier: "free", category: "장식", foundry: "우아한형제들", availableWeights: [400],
    moves: 2870, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Jua", aliases: ["주아", "배민주아", "jua"] },
  { slug: "do-hyeon", nameKo: "배민 도현", nameEn: "Do Hyeon", fontKey: "doHyeon",
    tier: "free", category: "고딕", foundry: "우아한형제들", availableWeights: [400],
    moves: 2450, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Do+Hyeon", aliases: ["도현", "배민도현", "do hyeon"] },
  { slug: "gowun-batang", nameKo: "고운바탕", nameEn: "Gowun Batang", fontKey: "gowunBatang",
    tier: "free", category: "명조", foundry: "고운글꼴", availableWeights: [400, 700],
    moves: 1980, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Gowun+Batang", aliases: ["고운바탕", "gowun batang"] },
  { slug: "nanum-myeongjo", nameKo: "나눔명조", nameEn: "Nanum Myeongjo", fontKey: "nanumMyeongjo",
    tier: "free", category: "명조", foundry: "네이버", availableWeights: [400, 700, 800],
    moves: 1740, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Nanum+Myeongjo", aliases: ["나눔명조", "nanum myeongjo"] },
  { slug: "kirang-haerang", nameKo: "기랑해랑", nameEn: "Kirang Haerang", fontKey: "kirangHaerang",
    tier: "free", category: "손글씨", foundry: "우아한형제들", availableWeights: [400],
    moves: 980, license: { commercial: "conditional", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Kirang+Haerang", aliases: ["기랑해랑", "kirang"] },
  { slug: "gaegu", nameKo: "개구", nameEn: "Gaegu", fontKey: "gaegu",
    tier: "free", category: "손글씨", foundry: "이영희", availableWeights: [300, 400, 700],
    moves: 860, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Gaegu", aliases: ["개구", "개구체", "gaegu"] },
  { slug: "song-myung", nameKo: "송명", nameEn: "Song Myung", fontKey: "songMyung",
    tier: "free", category: "명조", foundry: "숨은참조", availableWeights: [400],
    moves: 720, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Song+Myung", aliases: ["송명", "송명체", "song myung"] },
  { slug: "sandoll-gothic-neo", nameKo: "산돌 고딕 Neo", nameEn: "Sandoll Gothic Neo", fontKey: "blackHanSans",
    tier: "paid", category: "고딕", foundry: "산돌", availableWeights: [100, 200, 300, 400, 500, 600, 700, 800, 900],
    moves: 4210, license: { commercial: "no", verifiedAt: "2026-07-12" },
    officialUrl: "https://www.sandoll.co.kr/", aliases: ["산돌고딕", "sandoll gothic"],
    freeAlternatives: ["pretendard", "do-hyeon", "black-han-sans"] },
];
```

주의: 유료 폰트(`sandoll-gothic-neo`)는 실제 웹폰트가 없어 견본을 대체 서체(`blackHanSans`)로 표시한다 — 상세 화면에서 "대체 견본"임을 명시한다(Task 11). `freeAlternatives`는 실제 slug를 가리킨다.

- [ ] **Step 2: 타입 체크**

Run: `cd apps/web && pnpm exec tsc --noEmit`
Expected: 에러 없음(모든 fontKey가 FontKey 유니언에 속함).

- [ ] **Step 3: Commit**

```bash
git add apps/web/data/fonts.ts
git commit -m "feat(web): mock font data (10 fonts)"
```

---

## Task 4: 조회/무결성 헬퍼 + Vitest

**Files:**
- Create: `apps/web/lib/data.ts`, `apps/web/vitest.config.ts`, `apps/web/vitest.setup.ts`
- Modify: `apps/web/package.json`
- Test: `apps/web/lib/data.test.ts`

**Interfaces:**
- Consumes: `fonts`, `Font`, `FontKey`.
- Produces: `getFontBySlug(slug): Font | undefined`, `getAllSlugs(): string[]`, `resolveFreeAlternatives(font): Font[]`(무료만, 최대 3), `assertDataIntegrity(validKeys: FontKey[]): void`.

- [ ] **Step 1: 테스트 도구 추가**

`apps/web/package.json`의 `devDependencies`에 추가: `"vitest": "^2"`, `"@vitejs/plugin-react": "^4"`, `"@testing-library/react": "^16"`, `"@testing-library/jest-dom": "^6"`, `"jsdom": "^25"`. `scripts`에 추가: `"test": "vitest run"`, `"test:watch": "vitest"`.

Run: `cd apps/web && pnpm install`

- [ ] **Step 2: Vitest 설정**

`apps/web/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./", import.meta.url)) } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./vitest.setup.ts"] },
});
```

`apps/web/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 3: Write the failing test**

`apps/web/lib/data.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives, assertDataIntegrity } from "@/lib/data";
import type { FontKey } from "@/types/font";

const KEYS: FontKey[] = ["pretendard", "blackHanSans", "jua", "doHyeon", "gowunBatang", "nanumMyeongjo", "kirangHaerang", "gaegu", "songMyung"];

describe("data helpers", () => {
  it("finds a font by slug", () => {
    expect(getFontBySlug("pretendard")?.nameKo).toBe("프리텐다드");
    expect(getFontBySlug("nope")).toBeUndefined();
  });
  it("has at least 10 fonts for TOP 10", () => {
    expect(getAllSlugs().length).toBeGreaterThanOrEqual(10);
  });
  it("resolves free alternatives to real free fonts (max 3)", () => {
    const paid = getFontBySlug("sandoll-gothic-neo")!;
    const alts = resolveFreeAlternatives(paid);
    expect(alts.length).toBeLessThanOrEqual(3);
    expect(alts.every((f) => f.tier === "free")).toBe(true);
    expect(alts.map((f) => f.slug)).toContain("pretendard");
  });
  it("passes integrity check", () => {
    expect(() => assertDataIntegrity(KEYS)).not.toThrow();
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run lib/data.test.ts`
Expected: FAIL (`lib/data` 없음).

- [ ] **Step 5: Write implementation**

`apps/web/lib/data.ts`:

```ts
import { fonts } from "@/data/fonts";
import type { Font, FontKey } from "@/types/font";

export function getFontBySlug(slug: string): Font | undefined {
  return fonts.find((f) => f.slug === slug);
}

export function getAllSlugs(): string[] {
  return fonts.map((f) => f.slug);
}

export function resolveFreeAlternatives(font: Font): Font[] {
  return (font.freeAlternatives ?? [])
    .map((slug) => getFontBySlug(slug))
    .filter((f): f is Font => Boolean(f) && f!.tier === "free")
    .slice(0, 3);
}

export function assertDataIntegrity(validKeys: FontKey[]): void {
  const keySet = new Set<string>(validKeys);
  const slugs = new Set<string>();
  for (const f of fonts) {
    if (slugs.has(f.slug)) throw new Error(`중복 slug: ${f.slug}`);
    slugs.add(f.slug);
    if (!keySet.has(f.fontKey)) throw new Error(`미매핑 fontKey: ${f.slug} -> ${f.fontKey}`);
  }
  for (const f of fonts) {
    const alts = f.freeAlternatives ?? [];
    if (alts.length > 3) throw new Error(`freeAlternatives 3개 초과: ${f.slug}`);
    for (const alt of alts) {
      if (alt === f.slug) throw new Error(`freeAlternatives 자기참조: ${f.slug}`);
      const target = getFontBySlug(alt);
      if (!target) throw new Error(`freeAlternatives 참조 오류: ${f.slug} -> ${alt}`);
      if (target.tier !== "free") throw new Error(`freeAlternatives가 유료: ${f.slug} -> ${alt}`);
    }
  }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run lib/data.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit (lockfile 포함)**

```bash
git add apps/web/lib/data.ts apps/web/lib/data.test.ts apps/web/vitest.config.ts apps/web/vitest.setup.ts apps/web/package.json apps/web/pnpm-lock.yaml
git commit -m "feat(web): data helpers + integrity check with vitest"
```

---

## Task 5: 폰트 등록 + fontKey 매핑 (lib/fonts.ts)

**Files:**
- Create: `apps/web/lib/fonts.ts`

**Interfaces:**
- Consumes: `FontKey`.
- Produces: `fontClassNames: string`(루트 html 클래스), `fontKeyToVar: Record<FontKey, string>`. 견본 컴포넌트는 `fontKeyToVar[font.fontKey]`로 `fontFamily` 적용.

- [ ] **Step 1: 폰트 등록**

`apps/web/lib/fonts.ts`. 견본 폰트는 CWV 보호를 위해 `subsets: ["latin"]` + `preload: false`(한글 글리프는 런타임 swap 로드) + `display: "swap"`. 단일 굵기 폰트는 `weight` 명시. 데이터에서 실제 쓰이는 8개만 등록(미사용 폰트 등록 금지).

```ts
import {
  Black_Han_Sans, Jua, Do_Hyeon, Gowun_Batang, Nanum_Myeongjo,
  Kirang_Haerang, Gaegu, Song_Myung,
} from "next/font/google";
import type { FontKey } from "@/types/font";

const base = { subsets: ["latin"] as const, display: "swap" as const, preload: false };

const blackHanSans = Black_Han_Sans({ ...base, weight: "400", variable: "--font-black-han-sans" });
const jua = Jua({ ...base, weight: "400", variable: "--font-jua" });
const doHyeon = Do_Hyeon({ ...base, weight: "400", variable: "--font-do-hyeon" });
const gowunBatang = Gowun_Batang({ ...base, weight: ["400", "700"], variable: "--font-gowun-batang" });
const nanumMyeongjo = Nanum_Myeongjo({ ...base, weight: ["400", "700", "800"], variable: "--font-nanum-myeongjo" });
const kirangHaerang = Kirang_Haerang({ ...base, weight: "400", variable: "--font-kirang-haerang" });
const gaegu = Gaegu({ ...base, weight: ["300", "400", "700"], variable: "--font-gaegu" });
const songMyung = Song_Myung({ ...base, weight: "400", variable: "--font-song-myung" });

export const fontClassNames = [
  blackHanSans.variable, jua.variable, doHyeon.variable, gowunBatang.variable,
  nanumMyeongjo.variable, kirangHaerang.variable, gaegu.variable, songMyung.variable,
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
```

- [ ] **Step 2: 빌드로 폰트 다운로드 확인**

Run: `cd apps/web && pnpm build`
Expected: 성공(빌드 시 Google Fonts self-host). `Record<FontKey, ...>`라 키 누락 시 타입 에러로 사전 차단.

- [ ] **Step 3: Commit**

```bash
git add apps/web/lib/fonts.ts
git commit -m "feat(web): register sample google fonts + fontKey mapping"
```

---

## Task 6: 원자 컴포넌트 — TierChip, LicenseBadge

**Files:**
- Create: `apps/web/components/TierChip.tsx` (+ .module.css)
- Create: `apps/web/components/LicenseBadge.tsx` (+ .module.css)
- Test: `apps/web/components/LicenseBadge.test.tsx`

**Interfaces:**
- Consumes: `Tier`, `Commercial`.
- Produces: `<TierChip tier />`(free=무료 포인트약배경 / paid=유료 보조표면), `<LicenseBadge commercial />`(yes=가능/conditional=조건부/no=불가, 아이콘+텍스트).

주의(테스트 범위): TierChip은 2상태 단순 표시라 단위 테스트를 만들지 않는다(Playwright로 시각 검증). LicenseBadge는 3분기 매핑 로직이라 단위 테스트를 만든다.

- [ ] **Step 1: TierChip 작성**

`apps/web/components/TierChip.module.css`:

```css
.chip { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 5px; font-size: 10.5px; font-weight: 600; }
.free { background: var(--point-weak); color: var(--point); }
.paid { background: var(--surface-2); color: var(--sub); }
```

`apps/web/components/TierChip.tsx`:

```tsx
import type { Tier } from "@/types/font";
import styles from "./TierChip.module.css";

export function TierChip({ tier }: { tier: Tier }) {
  return (
    <span className={`${styles.chip} ${tier === "free" ? styles.free : styles.paid}`}>
      {tier === "free" ? "무료" : "유료"}
    </span>
  );
}
```

- [ ] **Step 2: LicenseBadge 실패 테스트**

`apps/web/components/LicenseBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { LicenseBadge } from "./LicenseBadge";

describe("LicenseBadge", () => {
  it("shows 가능 for yes", () => { render(<LicenseBadge commercial="yes" />); expect(screen.getByText("가능")).toBeInTheDocument(); });
  it("shows 조건부 for conditional", () => { render(<LicenseBadge commercial="conditional" />); expect(screen.getByText("조건부")).toBeInTheDocument(); });
  it("shows 불가 for no", () => { render(<LicenseBadge commercial="no" />); expect(screen.getByText("불가")).toBeInTheDocument(); });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run components/LicenseBadge.test.tsx`
Expected: FAIL.

- [ ] **Step 4: LicenseBadge 작성**

`apps/web/components/LicenseBadge.module.css`:

```css
.badge { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; }
.icon { width: 18px; height: 18px; border-radius: 5px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; }
.yes { color: var(--point); } .yes .icon { background: var(--point-weak); }
.conditional { color: var(--warn); } .conditional .icon { background: rgba(196, 150, 60, .16); }
.no { color: var(--down); } .no .icon { background: rgba(180, 86, 75, .14); }
```

`apps/web/components/LicenseBadge.tsx`:

```tsx
import type { Commercial } from "@/types/font";
import styles from "./LicenseBadge.module.css";

const MAP: Record<Commercial, { cls: "yes" | "conditional" | "no"; icon: string; label: string }> = {
  yes: { cls: "yes", icon: "✓", label: "가능" },
  conditional: { cls: "conditional", icon: "!", label: "조건부" },
  no: { cls: "no", icon: "✕", label: "불가" },
};

export function LicenseBadge({ commercial }: { commercial: Commercial }) {
  const m = MAP[commercial];
  return (
    <span className={`${styles.badge} ${styles[m.cls]}`}>
      <span className={styles.icon} aria-hidden="true">{m.icon}</span>
      <span>{m.label}</span>
    </span>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run components/LicenseBadge.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/TierChip.tsx apps/web/components/TierChip.module.css apps/web/components/LicenseBadge.tsx apps/web/components/LicenseBadge.module.css apps/web/components/LicenseBadge.test.tsx
git commit -m "feat(web): TierChip + LicenseBadge (3-state branch)"
```

---

## Task 7: 원자 컴포넌트 — Button, FilterChip

**Files:**
- Create: `apps/web/components/Button.tsx` (+ .module.css)
- Create: `apps/web/components/FilterChip.tsx` (+ .module.css)

**Interfaces:**
- Produces: `<Button variant href? children>` — href면 `<Link>`, 아니면 `<button type="button">`. `<FilterChip active? children>` — 비동작 시각 칩(`type="button"` + `aria-pressed`).

- [ ] **Step 1: Button 작성**

`apps/web/components/Button.module.css`:

```css
.btn { display: inline-flex; align-items: center; justify-content: center; padding: 10px 18px; border-radius: var(--radius-btn); font-size: 12.5px; font-weight: 600; border: 1px solid transparent; cursor: pointer; }
.primary { background: var(--point); color: var(--on-point); }
.secondary { background: transparent; color: var(--point); border-color: var(--point); }
```

`apps/web/components/Button.tsx`:

```tsx
import Link from "next/link";
import styles from "./Button.module.css";

type Props = { variant?: "primary" | "secondary"; href?: string; children: React.ReactNode };

export function Button({ variant = "primary", href, children }: Props) {
  const cls = `${styles.btn} ${styles[variant]}`;
  if (href) return <Link className={cls} href={href}>{children}</Link>;
  return <button type="button" className={cls}>{children}</button>;
}
```

- [ ] **Step 2: FilterChip 작성**

`apps/web/components/FilterChip.module.css`:

```css
.chip { padding: 7px 13px; border-radius: var(--radius-pill); font-size: 12px; font-weight: 500; border: 1px solid var(--border); background: transparent; color: var(--sub); cursor: pointer; }
.active { border-color: var(--point); color: var(--point); }
```

`apps/web/components/FilterChip.tsx`:

```tsx
import styles from "./FilterChip.module.css";

export function FilterChip({ active = false, children }: { active?: boolean; children: React.ReactNode }) {
  return (
    <button type="button" aria-pressed={active} className={`${styles.chip} ${active ? styles.active : ""}`}>
      {children}
    </button>
  );
}
```

- [ ] **Step 3: 타입 체크**

Run: `cd apps/web && pnpm exec tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 4: Commit**

```bash
git add apps/web/components/Button.tsx apps/web/components/Button.module.css apps/web/components/FilterChip.tsx apps/web/components/FilterChip.module.css
git commit -m "feat(web): Button + FilterChip atoms"
```

---

## Task 8: 레이아웃 — Header, Footer, 루트 layout, 테마 스크립트

**Files:**
- Create: `apps/web/components/Header.tsx` (+ .module.css), `apps/web/components/Footer.tsx` (+ .module.css)
- Modify: `apps/web/app/layout.tsx`

**Interfaces:**
- Consumes: `fontClassNames`.
- Produces: 전역 헤더(로고 A만 포인트 + nav + 검색버튼)/푸터, `<html lang="ko" data-theme>` 루트 + FOUC 방지 인라인 스크립트(dark/light만 허용).
- 디자인 근거: 원본 `FontAgit 화면 세트.dc.html` 10a(라인 61-70) + 홈 1d(라인 748-833) 헤더.

- [ ] **Step 1: Header 작성 (모바일 반응형 포함)**

`apps/web/components/Header.module.css`:

```css
.header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px var(--pad-page); border-bottom: 1px solid var(--border); background: var(--bg); position: sticky; top: 0; z-index: 10; }
.brand { display: flex; align-items: center; gap: 12px; min-width: 0; }
.wordmark { font-size: 22px; font-weight: 800; letter-spacing: -.03em; color: var(--ink); }
.wordmark .a { color: var(--point); }
.ko { font-size: 13px; font-weight: 500; color: var(--sub); }
.nav { display: flex; gap: 22px; }
.nav a { font-size: 14px; font-weight: 500; color: var(--sub); }
.nav a:hover { color: var(--ink); }
.actions { display: flex; gap: 10px; align-items: center; }
.iconBtn { width: 36px; height: 36px; border-radius: 8px; border: 1px solid var(--border); background: transparent; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; color: var(--sub); }
@media (max-width: 620px) {
  .ko { display: none; }
  .nav { gap: 14px; }
  .nav a { font-size: 13px; }
}
```

`apps/web/components/Header.tsx`:

```tsx
import Link from "next/link";
import styles from "./Header.module.css";

export function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <Link href="/" className={styles.wordmark} aria-label="FontAgit 홈">
          Font<span className={styles.a}>A</span>git
        </Link>
        <span className={styles.ko}>폰트 아지트</span>
      </div>
      <nav className={styles.nav}>
        <Link href="/fonts">폰트</Link>
        <Link href="/trends">트렌드</Link>
        <Link href="/collections">컬렉션</Link>
        <Link href="/submit">등록</Link>
      </nav>
      <div className={styles.actions}>
        <button type="button" className={styles.iconBtn} aria-label="검색">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>
        </button>
      </div>
    </header>
  );
}
```

주의: nav의 `/collections`, `/submit`는 이 계획 범위 밖(Phase 3)이라 아직 페이지가 없어 404로 간다 — 허용(후속 화면). 스모크 테스트는 이 두 링크의 목적지를 검증하지 않는다.

- [ ] **Step 2: Footer 작성**

`apps/web/components/Footer.module.css`:

```css
.footer { margin-top: auto; padding: 28px var(--pad-page); background: var(--surface-2); border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
.tagline { font-size: 13px; color: var(--sub); }
.links { display: flex; gap: 18px; }
.links a { font-size: 12px; color: var(--sub); }
```

`apps/web/components/Footer.tsx`:

```tsx
import Link from "next/link";
import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <span className={styles.tagline}>당신의 폰트 아지트 </span>
      <div className={styles.links}>
        <Link href="/fonts">폰트</Link>
        <Link href="/trends">트렌드</Link>
      </div>
    </footer>
  );
}
```

- [ ] **Step 3: 루트 layout 교체 (테마 값 검증 포함)**

`apps/web/app/layout.tsx` 전체 교체:

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { fontClassNames } from "@/lib/fonts";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

export const metadata: Metadata = {
  title: "FontAgit 폰트 아지트",
  description: "무료-유료-국내외 폰트를 검색-비교하는 폰트 아지트",
};

const themeScript = `(function(){try{var t=localStorage.getItem('theme');if(t!=='dark'&&t!=='light'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={fontClassNames} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <Header />
        {children}
        <Footer />
      </body>
    </html>
  );
}
```

- [ ] **Step 4: 빌드 + 타입 체크**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build`
Expected: 성공.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/Header.tsx apps/web/components/Header.module.css apps/web/components/Footer.tsx apps/web/components/Footer.module.css apps/web/app/layout.tsx
git commit -m "feat(web): root layout with header, footer, theme script"
```

---

## Task 9: 홈 화면 (1d)

**Files:**
- Create: `apps/web/components/Hero.tsx` (+ .module.css), `apps/web/components/TrendRow.tsx` (+ .module.css), `apps/web/components/TrendTable.tsx` (+ .module.css), `apps/web/components/AdSlot.tsx` (+ .module.css)
- Create: `apps/web/data/trends.ts`
- Modify: `apps/web/app/page.tsx`; Create: `apps/web/app/page.module.css`

**Interfaces:**
- Consumes: `fonts`, `fontKeyToVar`, `TierChip`, `Button`, `FilterChip`.
- Produces: `weeklyTrends: TrendItem[]`(10행), `<TrendRow item />`, `<TrendTable title items />`, `<Hero />`, `<AdSlot />`. 홈 = Hero + 이번주 TOP10 + 광고 슬롯.
- 디자인 근거: 홈 1d 라인 748-833.

- [ ] **Step 1: 트렌드 데이터 (10행)**

`apps/web/data/trends.ts`:

```ts
import type { TrendItem, TrendChange } from "@/types/font";
import { fonts } from "@/data/fonts";

function row(rank: number, slug: string, change: TrendChange, changeAmount?: number): TrendItem {
  const f = fonts.find((x) => x.slug === slug)!;
  return { rank, change, changeAmount, moves: f.moves, font: { slug: f.slug, nameKo: f.nameKo, fontKey: f.fontKey, tier: f.tier } };
}

export const weeklyTrends: TrendItem[] = [
  row(1, "pretendard", "up", 2), row(2, "black-han-sans", "hold"),
  row(3, "jua", "up", 1), row(4, "do-hyeon", "down", 1),
  row(5, "gowun-batang", "new"), row(6, "nanum-myeongjo", "hold"),
  row(7, "sandoll-gothic-neo", "up", 3), row(8, "kirang-haerang", "down", 2),
  row(9, "gaegu", "new"), row(10, "song-myung", "hold"),
];

export const monthlyTrends: TrendItem[] = [
  row(1, "black-han-sans", "hold"), row(2, "pretendard", "up", 3),
  row(3, "jua", "down", 1), row(4, "nanum-myeongjo", "hold"),
  row(5, "gowun-batang", "up", 2), row(6, "do-hyeon", "down", 2),
  row(7, "gaegu", "new"), row(8, "sandoll-gothic-neo", "hold"),
  row(9, "kirang-haerang", "up", 1), row(10, "song-myung", "new"),
];
```

- [ ] **Step 2: TrendRow / TrendTable / AdSlot**

`apps/web/components/TrendRow.module.css`:

```css
.row { display: flex; align-items: center; gap: 14px; padding: 12px 0; border-bottom: 1px solid var(--border); }
.rank { width: 22px; font-size: 15px; font-weight: 700; color: var(--point); }
.change { width: 44px; font-size: 12px; font-weight: 500; }
.up { color: var(--up); } .down { color: var(--down); } .hold { color: var(--hold); }
.new { color: var(--point); font-weight: 700; font-size: 10px; }
.name { flex: 1; font-size: 22px; color: var(--ink); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.moves { font-size: 12px; color: var(--sub); white-space: nowrap; }
```

`apps/web/components/TrendRow.tsx`:

```tsx
import Link from "next/link";
import type { TrendItem } from "@/types/font";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./TrendRow.module.css";

const LABEL: Record<TrendItem["change"], (n?: number) => string> = {
  up: (n) => `▲ ${n ?? ""}`.trim(),
  down: (n) => `▼ ${n ?? ""}`.trim(),
  hold: () => "—",
  new: () => "NEW",
};

export function TrendRow({ item }: { item: TrendItem }) {
  return (
    <Link href={`/fonts/${item.font.slug}`} className={styles.row}>
      <span className={styles.rank}>{item.rank}</span>
      <span className={`${styles.change} ${styles[item.change]}`}>{LABEL[item.change](item.changeAmount)}</span>
      <span className={styles.name} style={{ fontFamily: fontKeyToVar[item.font.fontKey] }}>{item.font.nameKo}</span>
      <span className={styles.moves}>이동 {item.moves.toLocaleString()}회</span>
      <TierChip tier={item.font.tier} />
    </Link>
  );
}
```

`apps/web/components/TrendTable.module.css`:

```css
.title { font-size: 24px; font-weight: 800; color: var(--ink); margin: 0 0 16px; }
.wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 0 44px; }
@media (max-width: 720px) { .wrap { grid-template-columns: 1fr; } }
```

`apps/web/components/TrendTable.tsx`:

```tsx
import type { TrendItem } from "@/types/font";
import { TrendRow } from "./TrendRow";
import styles from "./TrendTable.module.css";

export function TrendTable({ title, items }: { title: string; items: TrendItem[] }) {
  return (
    <section>
      <h2 className={styles.title}>{title}</h2>
      <div className={styles.wrap}>{items.map((it) => <TrendRow key={it.rank} item={it} />)}</div>
    </section>
  );
}
```

`apps/web/components/AdSlot.module.css`:

```css
.slot { height: 90px; border: 1px dashed var(--border); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: var(--sub-2); font-size: 12px; background: var(--surface-2); }
```

`apps/web/components/AdSlot.tsx`:

```tsx
import styles from "./AdSlot.module.css";
export function AdSlot() { return <div className={styles.slot} aria-hidden="true">광고</div>; }
```

- [ ] **Step 3: Hero**

`apps/web/components/Hero.module.css`:

```css
.hero { padding: 56px var(--pad-page); text-align: center; }
.h1 { font-size: 42px; font-weight: 800; letter-spacing: -.03em; color: var(--ink); margin: 0 0 12px; }
.sub { font-size: 15px; color: var(--sub); margin: 0 0 24px; }
.searchbox { display: flex; gap: 8px; max-width: 560px; margin: 0 auto 18px; }
.input { flex: 1; height: 56px; padding: 0 18px; border: 1px solid var(--border); border-radius: 12px; font-size: 15px; background: var(--surface); color: var(--ink); }
.chips { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
@media (max-width: 620px) { .h1 { font-size: 32px; } }
```

`apps/web/components/Hero.tsx`:

```tsx
import { Button } from "./Button";
import { FilterChip } from "./FilterChip";
import styles from "./Hero.module.css";

export function Hero() {
  return (
    <section className={styles.hero}>
      <h1 className={styles.h1}>폰트 덕후들의 아지트</h1>
      <p className={styles.sub}>무료-유료-국내외 폰트를 한 곳에서 찾고 비교하세요.</p>
      <div className={styles.searchbox}>
        <input className={styles.input} type="search" placeholder="폰트 이름-분위기로 검색" aria-label="폰트 검색" />
        <Button variant="primary">검색</Button>
      </div>
      <div className={styles.chips}>
        <FilterChip active>전체</FilterChip>
        <FilterChip>고딕</FilterChip>
        <FilterChip>명조</FilterChip>
        <FilterChip>손글씨</FilterChip>
        <FilterChip>장식</FilterChip>
      </div>
    </section>
  );
}
```

- [ ] **Step 4: 홈 페이지 (CSS Modules)**

`apps/web/app/page.module.css`:

```css
.main { max-width: 1180px; margin: 0 auto; width: 100%; }
.body { padding: 0 var(--pad-page) 56px; display: flex; flex-direction: column; gap: 40px; }
```

`apps/web/app/page.tsx` 전체 교체:

```tsx
import { Hero } from "@/components/Hero";
import { TrendTable } from "@/components/TrendTable";
import { AdSlot } from "@/components/AdSlot";
import { weeklyTrends } from "@/data/trends";
import styles from "./page.module.css";

export default function Home() {
  return (
    <main className={styles.main}>
      <Hero />
      <div className={styles.body}>
        <TrendTable title="이번 주 TOP 10" items={weeklyTrends} />
        <AdSlot />
      </div>
    </main>
  );
}
```

- [ ] **Step 5: 빌드 확인**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build`
Expected: 성공. `out/index.html` 생성.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/Hero.* apps/web/components/TrendRow.* apps/web/components/TrendTable.* apps/web/components/AdSlot.* apps/web/data/trends.ts apps/web/app/page.tsx apps/web/app/page.module.css
git commit -m "feat(web): home screen (hero + weekly top10 + ad slot)"
```

---

## Task 10: 폰트 카드 + 목록 화면 (1f)

**Files:**
- Create: `apps/web/components/FontCard.tsx` (+ .module.css), `apps/web/components/FontGrid.tsx` (+ .module.css)
- Create: `apps/web/app/fonts/page.tsx`, `apps/web/app/fonts/page.module.css`

**Interfaces:**
- Consumes: `fonts`, `fontKeyToVar`, `TierChip`, `LicenseBadge`, `FilterChip`.
- Produces: `<FontCard font />`, `<FontGrid fonts />`, 목록 페이지(필터 바 + 카드 그리드).
- 디자인 근거: 폰트 목록 1f 라인 897-930.

- [ ] **Step 1: FontCard**

`apps/web/components/FontCard.module.css`:

```css
.card { display: flex; flex-direction: column; gap: 10px; padding: 20px; border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); }
.specimen { font-size: 34px; color: var(--ink); line-height: 1.2; min-height: 44px; }
.name { font-size: 15px; font-weight: 700; color: var(--ink); }
.meta { font-size: 12px; color: var(--sub); }
.foot { display: flex; align-items: center; gap: 10px; margin-top: 2px; }
```

`apps/web/components/FontCard.tsx`:

```tsx
import Link from "next/link";
import type { Font } from "@/types/font";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import { LicenseBadge } from "./LicenseBadge";
import styles from "./FontCard.module.css";

export function FontCard({ font }: { font: Font }) {
  return (
    <Link href={`/fonts/${font.slug}`} className={styles.card}>
      <div className={styles.specimen} style={{ fontFamily: fontKeyToVar[font.fontKey] }}>다람쥐 헌 쳇바퀴에 타고파</div>
      <div className={styles.name}>{font.nameKo}</div>
      <div className={styles.meta}>{font.foundry} - {font.availableWeights.length}가지 굵기 - 이동 {font.moves.toLocaleString()}회</div>
      <div className={styles.foot}>
        <TierChip tier={font.tier} />
        <LicenseBadge commercial={font.license.commercial} />
      </div>
    </Link>
  );
}
```

- [ ] **Step 2: FontGrid**

`apps/web/components/FontGrid.module.css`:

```css
.grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 960px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 620px) { .grid { grid-template-columns: 1fr; } }
```

`apps/web/components/FontGrid.tsx`:

```tsx
import type { Font } from "@/types/font";
import { FontCard } from "./FontCard";
import styles from "./FontGrid.module.css";

export function FontGrid({ fonts }: { fonts: Font[] }) {
  return <div className={styles.grid}>{fonts.map((f) => <FontCard key={f.slug} font={f} />)}</div>;
}
```

- [ ] **Step 3: 목록 페이지**

`apps/web/app/fonts/page.module.css`:

```css
.main { max-width: 1180px; margin: 0 auto; width: 100%; padding: var(--pad-page); }
.h1 { font-size: 24px; font-weight: 800; margin: 0 0 20px; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; }
```

`apps/web/app/fonts/page.tsx`:

```tsx
import { fonts } from "@/data/fonts";
import { FontGrid } from "@/components/FontGrid";
import { FilterChip } from "@/components/FilterChip";
import styles from "./page.module.css";

export default function FontsPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.h1}>폰트</h1>
      <div className={styles.filters}>
        <FilterChip active>전체</FilterChip>
        <FilterChip>무료</FilterChip>
        <FilterChip>유료</FilterChip>
        <FilterChip>고딕</FilterChip>
        <FilterChip>명조</FilterChip>
        <FilterChip>손글씨</FilterChip>
      </div>
      <FontGrid fonts={fonts} />
    </main>
  );
}
```

- [ ] **Step 4: 빌드 확인**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build`
Expected: 성공. `out/fonts/index.html` 생성.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/FontCard.* apps/web/components/FontGrid.* apps/web/app/fonts/page.tsx apps/web/app/fonts/page.module.css
git commit -m "feat(web): font list screen (filter bar + card grid)"
```

---

## Task 11: 미리보기 입력 + 상세 화면 (1g 무료 / 6a 유료)

**Files:**
- Create: `apps/web/components/PreviewInput.tsx` (+ .module.css), `apps/web/components/Specimen.tsx` (+ .module.css)
- Create: `apps/web/app/fonts/[slug]/page.tsx`, `apps/web/app/fonts/[slug]/page.module.css`

**Interfaces:**
- Consumes: `getFontBySlug`, `getAllSlugs`, `resolveFreeAlternatives`, `fontKeyToVar`, `TierChip`, `LicenseBadge`, `Button`, `FontCard`.
- Produces: 상세 페이지. 무료는 견본+미리보기+굵기+라이선스+공식 이동. 유료는 "대체 견본" 명시 + 구매 이동 + 무료 대안 3개. `generateStaticParams` + `dynamicParams=false` + 없는 slug는 `notFound()`.
- `<PreviewInput fontFamily />`(client, 라이브 반영), `<Specimen fontFamily weights substitute? />`(굵기는 실제 로드된 것만).
- 디자인 근거: 무료 상세 1g 라인 931-975, 유료 상세 6a 라인 282-326.

- [ ] **Step 1: PreviewInput (client)**

`apps/web/components/PreviewInput.module.css`:

```css
.wrap { display: flex; flex-direction: column; gap: 12px; }
.sample { font-size: 40px; line-height: 1.3; color: var(--ink); min-height: 52px; word-break: break-word; }
.input { height: 48px; padding: 0 16px; border: 1px solid var(--border); border-radius: 10px; font-size: 15px; background: var(--surface); color: var(--ink); }
@media (max-width: 620px) { .sample { font-size: 30px; } }
```

`apps/web/components/PreviewInput.tsx`:

```tsx
"use client";
import { useState } from "react";
import styles from "./PreviewInput.module.css";

export function PreviewInput({ fontFamily }: { fontFamily: string }) {
  const [text, setText] = useState("입력해 보세요");
  return (
    <div className={styles.wrap}>
      <div className={styles.sample} style={{ fontFamily }}>{text || " "}</div>
      <input className={styles.input} value={text} onChange={(e) => setText(e.target.value)} placeholder="미리볼 문장을 입력하세요" aria-label="미리보기 입력" />
    </div>
  );
}
```

- [ ] **Step 2: Specimen (실제 굵기만, 대체 견본 라벨)**

`apps/web/components/Specimen.module.css`:

```css
.wrap { display: flex; flex-direction: column; gap: 14px; border: 1px solid var(--border); border-radius: var(--radius-card); padding: 24px; background: var(--surface); }
.line { color: var(--ink); line-height: 1.3; }
.cap { font-size: 11px; color: var(--sub-2); }
.note { font-size: 12px; color: var(--warn); }
```

`apps/web/components/Specimen.tsx`:

```tsx
import styles from "./Specimen.module.css";

export function Specimen({ fontFamily, weights, substitute = false }: { fontFamily: string; weights: number[]; substitute?: boolean }) {
  const sizes = [40, 28, 18];
  return (
    <div className={styles.wrap} style={{ fontFamily }}>
      {substitute && <div className={styles.note}>실제 유료 서체가 아닌 대체 견본입니다.</div>}
      {sizes.map((s, i) => (
        <div key={s}>
          <span className={styles.line} style={{ fontSize: s, fontWeight: weights[Math.min(i, weights.length - 1)] }}>
            다람쥐 헌 쳇바퀴에 타고파 ABCabc 12345
          </span>
        </div>
      ))}
      <div className={styles.cap}>지원 굵기: {weights.join(", ")}</div>
    </div>
  );
}
```

- [ ] **Step 3: 상세 페이지 (tier 분기, 정적 생성, 대체 견본)**

`apps/web/app/fonts/[slug]/page.module.css`:

```css
.main { max-width: 900px; margin: 0 auto; width: 100%; padding: var(--pad-page); display: flex; flex-direction: column; gap: 28px; }
.head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.h1 { font-size: 24px; font-weight: 800; margin: 0; }
.meta { font-size: 12px; color: var(--sub); }
.altTitle { font-size: 18px; font-weight: 700; margin: 8px 0 14px; }
.altGrid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 720px) { .altGrid { grid-template-columns: 1fr; } }
```

`apps/web/app/fonts/[slug]/page.tsx`:

```tsx
import { notFound } from "next/navigation";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives } from "@/lib/data";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "@/components/TierChip";
import { LicenseBadge } from "@/components/LicenseBadge";
import { Button } from "@/components/Button";
import { PreviewInput } from "@/components/PreviewInput";
import { Specimen } from "@/components/Specimen";
import { FontCard } from "@/components/FontCard";
import styles from "./page.module.css";

export const dynamicParams = false;
export function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export default async function FontDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const font = getFontBySlug(slug);
  if (!font) notFound();
  const family = fontKeyToVar[font.fontKey];
  const isPaid = font.tier === "paid";
  // 유료는 대체 서체(단일 굵기)로만 렌더 -> 실제 로드 굵기 [400]만 사용
  const specimenWeights = isPaid ? [400] : font.availableWeights;

  return (
    <main className={styles.main}>
      <header className={styles.head}>
        <h1 className={styles.h1}>{font.nameKo}</h1>
        <TierChip tier={font.tier} />
        <LicenseBadge commercial={font.license.commercial} />
      </header>
      <div className={styles.meta}>{font.foundry} - {font.availableWeights.length}가지 굵기 - 이동 {font.moves.toLocaleString()}회 - 확인일 {font.license.verifiedAt}</div>

      <PreviewInput fontFamily={family} />
      <Specimen fontFamily={family} weights={specimenWeights} substitute={isPaid} />

      {isPaid ? (
        <>
          <Button variant="primary" href={font.officialUrl}>구매 페이지로 이동</Button>
          <section>
            <h2 className={styles.altTitle}>비슷한 무료 대안</h2>
            <div className={styles.altGrid}>
              {resolveFreeAlternatives(font).map((alt) => <FontCard key={alt.slug} font={alt} />)}
            </div>
          </section>
        </>
      ) : (
        <Button variant="primary" href={font.officialUrl}>공식 페이지에서 내려받기</Button>
      )}
    </main>
  );
}
```

- [ ] **Step 4: 빌드 확인 (정적 생성 + tier 분기)**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm build`
Expected: 성공. `out/fonts/pretendard/index.html`(무료, 대체 견본 라벨 없음)과 `out/fonts/sandoll-gothic-neo/index.html`(유료, "대체 견본" 문구 + 무료 대안 3개) 생성.

- [ ] **Step 5: Commit**

```bash
git add -- 'apps/web/components/PreviewInput.tsx' 'apps/web/components/PreviewInput.module.css' 'apps/web/components/Specimen.tsx' 'apps/web/components/Specimen.module.css' 'apps/web/app/fonts/[slug]/page.tsx' 'apps/web/app/fonts/[slug]/page.module.css'
git commit -m "feat(web): font detail (free/paid branch, preview, free alternatives)"
```

주의: `[slug]` 경로는 zsh에서 glob되므로 `git add`에 반드시 작은따옴표를 쓴다.

---

## Task 12: 트렌드 화면 (1h) + 404

**Files:**
- Create: `apps/web/app/trends/page.tsx`, `apps/web/app/trends/page.module.css`
- Create: `apps/web/app/not-found.tsx`, `apps/web/app/not-found.module.css`

**Interfaces:**
- Consumes: `TrendTable`, `weeklyTrends`, `monthlyTrends`, `Button`.
- Produces: `/trends`(주간/월간 두 표를 각각 제목으로 구분해 표시 — 비동작 필터칩 없음), 404(아지트지기 보이스).
- 디자인 근거: 트렌드 1h 라인 976-999, 시스템 1i 라인 1000-1050.

주의(모순 해소): 이전 안의 "주간 active 칩 + 두 표 동시 표시"는 자기모순이라 제거한다. 이 계획에서는 두 표를 각각 명확한 제목으로 나란히 보인다(클라이언트 탭 토글은 Phase 3에서 도입).

- [ ] **Step 1: 트렌드 페이지**

`apps/web/app/trends/page.module.css`:

```css
.main { max-width: 1180px; margin: 0 auto; width: 100%; padding: var(--pad-page); display: flex; flex-direction: column; gap: 32px; }
.h1 { font-size: 24px; font-weight: 800; margin: 0; }
```

`apps/web/app/trends/page.tsx`:

```tsx
import { TrendTable } from "@/components/TrendTable";
import { weeklyTrends, monthlyTrends } from "@/data/trends";
import styles from "./page.module.css";

export default function TrendsPage() {
  return (
    <main className={styles.main}>
      <h1 className={styles.h1}>트렌드</h1>
      <TrendTable title="이번 주 TOP 10" items={weeklyTrends} />
      <TrendTable title="이번 달 TOP 10" items={monthlyTrends} />
    </main>
  );
}
```

- [ ] **Step 2: 404 페이지**

`apps/web/app/not-found.module.css`:

```css
.main { max-width: 560px; margin: 0 auto; width: 100%; padding: 80px var(--pad-page); text-align: center; display: flex; flex-direction: column; gap: 16px; align-items: center; }
.code { font-size: 42px; font-weight: 800; color: var(--ink); }
.msg { font-size: 15px; color: var(--sub); margin: 0; }
```

`apps/web/app/not-found.tsx`:

```tsx
import { Button } from "@/components/Button";
import styles from "./not-found.module.css";

export default function NotFound() {
  return (
    <main className={styles.main}>
      <div className={styles.code}>404</div>
      <p className={styles.msg}>길을 잘못 드셨어요. 아지트 입구로 모실게요.</p>
      <Button variant="primary" href="/">홈으로</Button>
    </main>
  );
}
```

- [ ] **Step 3: 빌드 + 전체 단위 테스트**

Run: `cd apps/web && pnpm exec tsc --noEmit && pnpm test && pnpm build`
Expected: 타입 OK, 단위 테스트 전부 PASS, 빌드 성공, `out/trends/index.html`과 `out/404.html` 생성.

- [ ] **Step 4: Commit**

```bash
git add apps/web/app/trends/page.tsx apps/web/app/trends/page.module.css apps/web/app/not-found.tsx apps/web/app/not-found.module.css
git commit -m "feat(web): trends screen + 404 page"
```

---

## Task 13: Playwright 스모크 + 95% 검증 세팅

**Files:**
- Create: `apps/web/playwright.config.ts`, `apps/web/e2e/smoke.spec.ts`
- Modify: `apps/web/package.json`

**Interfaces:**
- Produces: 정적 산출물(`out/`)을 서빙해 각 라우트를 데스크톱(1280)/모바일(390) Chromium으로 로드, 핵심 텍스트 + 콘솔 에러 0 검증, 스크린샷 아티팩트 저장(원본 대조용).

- [ ] **Step 1: Playwright 추가**

`apps/web/package.json`의 `devDependencies`에 `"@playwright/test": "^1"` 추가, `scripts`에 `"e2e": "playwright test"` 추가.

Run: `cd apps/web && pnpm install && pnpm exec playwright install chromium`

- [ ] **Step 2: Playwright 설정 (out/ 정적 서빙)**

`apps/web/playwright.config.ts`. 정적 export 결과를 서빙해 실서비스와 동일 조건으로 검증:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  webServer: {
    command: "pnpm exec serve out -l 4310 --no-clipboard",
    port: 4310,
    reuseExistingServer: true,
  },
  use: { baseURL: "http://localhost:4310", screenshot: "on", deviceScaleFactor: 1 },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 900 } } },
    { name: "mobile", use: { ...devices["iPhone 12"], viewport: { width: 390, height: 844 } } },
  ],
});
```

주의: `serve` 미설치 시 `pnpm add -D serve`로 추가하거나 `command`를 `npx --yes serve out -l 4310`로 바꾼다. 사전 조건: 실행 전 `pnpm build`로 `out/`이 있어야 한다.

- [ ] **Step 3: 스모크 스펙**

`apps/web/e2e/smoke.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

const routes = [
  { path: "/", text: "폰트 덕후들의 아지트" },
  { path: "/fonts/", text: "폰트" },
  { path: "/fonts/pretendard/", text: "프리텐다드" },
  { path: "/fonts/sandoll-gothic-neo/", text: "대체 견본" },
  { path: "/trends/", text: "이번 주 TOP 10" },
];

for (const r of routes) {
  test(`loads ${r.path} without console errors`, async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    await page.goto(r.path, { waitUntil: "networkidle" });
    await expect(page.getByText(r.text).first()).toBeVisible();
    expect(errors, `console errors on ${r.path}: ${errors.join(" | ")}`).toEqual([]);
  });
}

test("preview input updates specimen live", async ({ page }) => {
  await page.goto("/fonts/pretendard/", { waitUntil: "networkidle" });
  await page.getByLabel("미리보기 입력").fill("가나다 테스트");
  await expect(page.getByText("가나다 테스트").first()).toBeVisible();
});
```

- [ ] **Step 4: 빌드 후 스모크 실행**

Run: `cd apps/web && pnpm build && pnpm exec playwright test`
Expected: 데스크톱/모바일 프로젝트 각 라우트 PASS, 콘솔 에러 0, 미리보기 라이브 반영 통과. 스크린샷은 `test-results/`에 저장 — 원본 1d/1f/1g/6a/1h와 95% 육안 대조(뷰포트 1280/390, DPR 1). 유료 페이지에 "대체 견본" 문구 확인.

- [ ] **Step 5: Commit (lockfile 포함)**

```bash
git add apps/web/playwright.config.ts apps/web/e2e/smoke.spec.ts apps/web/package.json apps/web/pnpm-lock.yaml
git commit -m "test(web): playwright smoke across core routes (desktop + mobile)"
```

---

## 후속 계획 (범위 밖 — Phase 3-4)

별도 계획서: 타입 캔버스(3a), 비교(5a), 컬렉션 목록/상세(8a, nav `/collections` 목적지), 등록(8b, nav `/submit`), 빈 상태, 모바일 정밀화(safe-area/키보드/탭바), 다크모드 토글 UI + 트렌드 주간/월간 클라이언트 탭(9b), 런칭자산(파비콘/OG 사전생성, 7). OG는 export 제약상 전 slug 빌드 시 사전생성 + `ImageResponse`에 한글 폰트 바이트 직접 로드(불안정 시 `public/og/` PNG 폴백).

---

## Self-Review

**Spec coverage:** 토큰/폰트/타입/데이터/헬퍼(Task 1-5), 원자 컴포넌트(6-7), 레이아웃(8), 홈 1d(9), 목록 1f(10), 상세 1g/6a(11), 트렌드 1h + 404(12), 검증 세팅(13). 정적 export/generateStaticParams/dynamicParams/notFound(1, 11). 폰트 로딩 위치(preload:false, 5). 다크 --on-point(1, 7). 무결성(4). CSS Modules 전면 적용(모든 페이지). 범위 밖은 후속 계획 명시. OK

**Placeholder scan:** 코드 스텝 모두 실제 코드. 화면 마크업은 원본 디자인 라인 범위를 SSOT로 지정. 남은 TODO 없음.

**Type consistency:** `FontKey` 유니언이 `Font.fontKey`/`fontKeyToVar: Record<FontKey>`/data/trends에 일관 적용(오타는 컴파일 차단). `getFontBySlug`/`getAllSlugs`/`resolveFreeAlternatives`/`assertDataIntegrity(validKeys)` 시그니처가 정의처(Task 4)와 소비처 일치. `TrendItem.font`=`slug/nameKo/fontKey/tier` 통일. 상세 async `params: Promise<{slug}>` Next 16 준수. `Specimen`은 `substitute` prop 추가, 유료는 `[400]`만 렌더(가짜 굵기 방지). `[slug]` git add 따옴표.

**Codex 리뷰 반영:** Task1+2 병합(빌드 순서), lockfile 커밋, [slug] 따옴표, Playwright 실체+95% 기준, TOP10 10행, 인라인 스타일 제거(CSS Modules), 모바일 반응형(pad-page 변수 + 미디어쿼리), 트렌드 필터 모순 제거, FontKey 유니언, 무결성 강화, 유료 견본 정직성, Pretendard Variable 경로, 미사용 Noto 제거, 테마 값 검증, TierChip 단위테스트 제외 반영 완료.
