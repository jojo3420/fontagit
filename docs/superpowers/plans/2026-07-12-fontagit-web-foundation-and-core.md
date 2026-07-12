# FontAgit 웹 토대 + 핵심 화면 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 `apps/web` 스캐폴드를 스펙 토대(CSS 변수 토큰 + CSS Modules + self-host 폰트)로 재정비하고, 핵심 4화면(홈/목록/상세/트렌드)을 디자인 95% 재현으로 구현한다.

**Architecture:** Next.js 16 App Router를 정적 출력(`output: 'export'`)으로 서빙한다. 스타일은 `styles/tokens.css`의 CSS 변수 + 컴포넌트별 CSS Modules. 콘텐츠는 `data/`의 타입 지정 목업. 폰트는 Pretendard(npm 패키지, 로컬 self-host) + 견본 한글 폰트(next/font/google)로 self-host. 로직 있는 부분만 Vitest 단위 테스트, 화면은 build + Playwright 스모크로 검증.

**Tech Stack:** Next.js 16.2.10, React 19.2.4, TypeScript 5, CSS Modules, Vitest + React Testing Library, Playwright, pretendard(npm), next/font/google.

## Global Constraints

- 결과물 위치: `apps/web`. 패키지명은 반드시 `web`(기존 `pnpm --filter web`, 루트 `web:dev`/`web:build` 스크립트와 정합). 기존 스캐폴드를 수정하며, 이 세션 결정(CSS Modules)이 Tailwind보다 우선한다 — Tailwind는 제거한다.
- 원본 디자인(시각 SSOT): `docs/design/fontagit-v2/project/FontAgit 화면 세트.dc.html`. 화면 마크업은 이 파일의 해당 섹션을 번역해 재현한다(그대로 렌더하지 말고 소스를 읽어 픽셀 값을 옮긴다).
- 스펙: `docs/superpowers/specs/2026-07-12-fontagit-web-screens-design.md`. 토큰/컴포넌트/데이터/검증 기준의 SSOT.
- Next.js 16 주의(AGENTS.md): dynamic route의 `params`는 async다 — `params: Promise<{ slug: string }>` + `const { slug } = await params`. 코드 전 `apps/web/node_modules/next/dist/docs/`의 해당 가이드 확인.
- 정적 출력: `next.config.ts`에 `output: 'export'`, `images: { unoptimized: true }`, `trailingSlash: true`. 빌드 산출물은 `out/`. 서버 전용 기능/런타임 리다이렉트 사용 금지.
- 디자인 토큰(값 그대로): 배경 `#FAFAF8`, 잉크 `#1A1A1A`, 서브 `#6B6B6B`, 약한 서브 `#9A9A96`, 경계 `#E6E6E2`, 표면 `#FFFFFF`, 보조표면 `#F4F4F0`, 포인트 `#2C5545`, 포인트약배경 `rgba(44,85,69,.1)`, on-point `#FFFFFF`. 상태색: 상승 `#2C7A5B`, 하락/불가 `#B4564B`, 유지 `#9A9A96`, 조건부 `#B4863C`. 다크: 배경 `#16171A`, 잉크 `#EDEDEA`, 포인트 `#7FC2A2`, on-point 어두운 잉크 `#16171A`.
- 타이포 스케일: 히어로 42, 화면 제목 24, 본문 15, 캡션 12. UI 텍스트는 항상 Pretendard, 견본 텍스트만 견본 폰트로 렌더.
- 포인트색은 액션에만. 라이선스 상태는 색 단독 금지 — 아이콘+텍스트 병행(WCAG AA).
- 보이스: 브랜드 층(로고/히어로/404/빈상태)은 존댓말 다정 담백, 정보 층은 건조한 사실만("안전/문제없음" 같은 보증 표현 금지).
- 비동작 액션(검색/등록/필터 칩 등)은 `type="button"`으로 폼 제출/네비게이션을 막는다.
- 커밋 컨벤션: `<타입>: <설명>`(feat/fix/refactor/docs/test/chore). 각 태스크 끝에 커밋.

---

## 파일 구조 (이 계획 범위)

```
apps/web/
  next.config.ts            정적 출력 설정 (수정)
  postcss.config.mjs        삭제 (Tailwind 제거)
  vitest.config.ts          단위 테스트 설정 (신규)
  vitest.setup.ts           jest-dom 등록 (신규)
  package.json              deps/scripts 정리 (수정)
  app/
    layout.tsx              루트 레이아웃: 폰트/테마/헤더/푸터 (수정)
    page.tsx                홈 (수정)
    globals.css             리셋 + 토큰 import (수정)
    fonts/page.tsx          목록 (신규)
    fonts/[slug]/page.tsx   상세 무료/유료 (신규)
    trends/page.tsx         트렌드 (신규)
    not-found.tsx           404 (신규)
  components/
    Header.tsx (+ .module.css)
    Footer.tsx (+ .module.css)
    Hero.tsx (+ .module.css)
    TierChip.tsx (+ .module.css)
    LicenseBadge.tsx (+ .module.css)
    Button.tsx (+ .module.css)
    FilterChip.tsx (+ .module.css)
    TrendRow.tsx (+ .module.css)
    TrendTable.tsx (+ .module.css)
    FontCard.tsx (+ .module.css)
    FontGrid.tsx (+ .module.css)
    PreviewInput.tsx (+ .module.css)
    Specimen.tsx (+ .module.css)
    AdSlot.tsx (+ .module.css)
  lib/
    fonts.ts                next/font 등록 + fontKey 매핑
    data.ts                 slug 조회/무결성 헬퍼
  data/
    fonts.ts                목업 폰트
    trends.ts               목업 트렌드
  types/
    font.ts                 Font/TrendItem/Collection 타입
  styles/
    tokens.css              CSS 변수 토큰
```

---

## Task 1: 스캐폴드 재정비 (Tailwind 제거 + 정적 출력 설정)

**Files:**
- Modify: `apps/web/package.json`
- Delete: `apps/web/postcss.config.mjs`
- Modify: `apps/web/next.config.ts`
- Modify: `apps/web/app/globals.css`

**Interfaces:**
- Produces: Tailwind 없는 빌드 가능 상태, 정적 출력 설정.

- [ ] **Step 1: Tailwind devDependencies 제거**

`apps/web/package.json`의 `devDependencies`에서 `@tailwindcss/postcss`, `tailwindcss` 두 줄을 삭제한다. 나머지(next, react, react-dom, pretendard, eslint, typescript, @types/*)는 유지.

- [ ] **Step 2: postcss 설정 삭제**

Run: `rm apps/web/postcss.config.mjs`

- [ ] **Step 3: 정적 출력 설정 작성**

`apps/web/next.config.ts` 전체를 교체:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
```

- [ ] **Step 4: globals.css를 리셋 + 토큰 import로 교체**

`apps/web/app/globals.css` 전체를 교체(Tailwind import 제거). Pretendard는 npm 패키지 CSS로 self-host 유지:

```css
@import "pretendard/dist/web/static/pretendard.css";
@import "../styles/tokens.css";

*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
html { -webkit-text-size-adjust: 100%; }
body {
  background: var(--bg);
  color: var(--ink);
  font-family: "Pretendard Variable", "Pretendard", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 15px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; text-decoration: none; }
button { font-family: inherit; }
img, svg { max-width: 100%; display: block; }
```

- [ ] **Step 5: 의존성 재설치 + 빌드로 Tailwind 제거 확인**

Run: `cd apps/web && pnpm install && pnpm build`
Expected: 빌드 성공. `styles/tokens.css` 미존재로 실패하면 Task 2 먼저 진행 후 재빌드(순서상 Task 2와 함께 커밋 가능). Tailwind 관련 에러가 없어야 한다.

- [ ] **Step 6: Commit**

```bash
git add apps/web/package.json apps/web/next.config.ts apps/web/app/globals.css
git rm apps/web/postcss.config.mjs
git commit -m "chore(web): remove Tailwind, set static export + CSS tokens base"
```

---

## Task 2: 디자인 토큰 (tokens.css)

**Files:**
- Create: `apps/web/styles/tokens.css`

**Interfaces:**
- Produces: 전역 CSS 변수(라이트/다크). 모든 컴포넌트가 `var(--*)`로 참조.

- [ ] **Step 1: 토큰 파일 작성**

`apps/web/styles/tokens.css`:

```css
:root {
  --bg: #FAFAF8;
  --ink: #1A1A1A;
  --sub: #6B6B6B;
  --sub-2: #9A9A96;
  --border: #E6E6E2;
  --surface: #FFFFFF;
  --surface-2: #F4F4F0;
  --point: #2C5545;
  --point-weak: rgba(44, 85, 69, .1);
  --on-point: #FFFFFF;
  --up: #2C7A5B;
  --down: #B4564B;
  --hold: #9A9A96;
  --warn: #B4863C;
  --radius-card: 12px;
  --radius-btn: 10px;
  --radius-pill: 20px;
}

:root[data-theme="dark"] {
  --bg: #16171A;
  --ink: #EDEDEA;
  --sub: #B9BCBD;
  --sub-2: #8A8E90;
  --border: #2A2C30;
  --surface: #1D1F22;
  --surface-2: #202226;
  --point: #7FC2A2;
  --point-weak: rgba(127, 194, 162, .14);
  --on-point: #16171A;
}
```

- [ ] **Step 2: 빌드로 import 확인**

Run: `cd apps/web && pnpm build`
Expected: 성공(globals.css의 `@import "../styles/tokens.css"` 해석됨).

- [ ] **Step 3: Commit**

```bash
git add apps/web/styles/tokens.css
git commit -m "feat(web): add design tokens (light/dark CSS variables)"
```

---

## Task 3: 타입 정의 (types/font.ts)

**Files:**
- Create: `apps/web/types/font.ts`

**Interfaces:**
- Produces: `Category`, `Tier`, `Commercial`, `TrendChange`, `Font`, `TrendItem`, `Collection` — 이후 모든 데이터/컴포넌트가 소비.

- [ ] **Step 1: 타입 작성**

`apps/web/types/font.ts`:

```ts
export type Category = "고딕" | "명조" | "손글씨" | "장식";
export type Tier = "free" | "paid";
export type Commercial = "yes" | "conditional" | "no";
export type TrendChange = "up" | "down" | "hold" | "new";

export interface Font {
  slug: string;
  nameKo: string;
  nameEn: string;
  fontKey: string;            // lib/fonts.ts 매핑 키 (화면 전용)
  tier: Tier;
  category: Category;
  foundry: string;
  availableWeights: number[]; // 단일 굵기 폰트는 [400]
  moves: number;              // 이동수(목업)
  license: { commercial: Commercial; verifiedAt: string };
  officialUrl: string;
  aliases: string[];
  freeAlternatives?: string[]; // 유료 상세의 무료 대안 slug (최대 3)
}

export interface TrendItem {
  rank: number;
  change: TrendChange;
  changeAmount?: number;
  font: Pick<Font, "slug" | "nameKo" | "fontKey" | "tier">;
  moves: number;
}

export interface Collection {
  slug: string;
  title: string;
  intro: string;
  items: { fontSlug: string; comment: string }[];
}
```

- [ ] **Step 2: 타입 체크**

Run: `cd apps/web && pnpm exec tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 3: Commit**

```bash
git add apps/web/types/font.ts
git commit -m "feat(web): add font domain types"
```

---

## Task 4: 목업 폰트 데이터 (data/fonts.ts)

**Files:**
- Create: `apps/web/data/fonts.ts`

**Interfaces:**
- Consumes: `Font` from `types/font.ts`.
- Produces: `fonts: Font[]` (named export). 이후 조회/그리드/상세가 소비.

- [ ] **Step 1: 데이터 작성 (디자인 등장 폰트로)**

`apps/web/data/fonts.ts` (fontKey는 Task 6의 매핑 키와 일치해야 함):

```ts
import type { Font } from "@/types/font";

export const fonts: Font[] = [
  {
    slug: "pretendard", nameKo: "프리텐다드", nameEn: "Pretendard", fontKey: "pretendard",
    tier: "free", category: "고딕", foundry: "길형진", availableWeights: [400, 500, 700, 800],
    moves: 5120, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://github.com/orioncactus/pretendard", aliases: ["프리텐다드", "pretendard", "프리텐더드"],
  },
  {
    slug: "black-han-sans", nameKo: "검은고딕", nameEn: "Black Han Sans", fontKey: "blackHanSans",
    tier: "free", category: "고딕", foundry: "장수영-Zess", availableWeights: [400],
    moves: 3120, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Black+Han+Sans", aliases: ["검은고딕", "블랙한산스", "black han"],
  },
  {
    slug: "jua", nameKo: "배민 주아", nameEn: "Jua", fontKey: "jua",
    tier: "free", category: "장식", foundry: "우아한형제들", availableWeights: [400],
    moves: 2870, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Jua", aliases: ["주아", "배민주아", "jua"],
  },
  {
    slug: "do-hyeon", nameKo: "배민 도현", nameEn: "Do Hyeon", fontKey: "doHyeon",
    tier: "free", category: "고딕", foundry: "우아한형제들", availableWeights: [400],
    moves: 2450, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Do+Hyeon", aliases: ["도현", "배민도현", "do hyeon"],
  },
  {
    slug: "gowun-batang", nameKo: "고운바탕", nameEn: "Gowun Batang", fontKey: "gowunBatang",
    tier: "free", category: "명조", foundry: "고운글꼴", availableWeights: [400, 700],
    moves: 1980, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Gowun+Batang", aliases: ["고운바탕", "gowun batang"],
  },
  {
    slug: "nanum-myeongjo", nameKo: "나눔명조", nameEn: "Nanum Myeongjo", fontKey: "nanumMyeongjo",
    tier: "free", category: "명조", foundry: "네이버", availableWeights: [400, 700, 800],
    moves: 1740, license: { commercial: "yes", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Nanum+Myeongjo", aliases: ["나눔명조", "nanum myeongjo"],
  },
  {
    slug: "kirang-haerang", nameKo: "기랑해랑", nameEn: "Kirang Haerang", fontKey: "kirangHaerang",
    tier: "free", category: "손글씨", foundry: "우아한형제들", availableWeights: [400],
    moves: 980, license: { commercial: "conditional", verifiedAt: "2026-07-12" },
    officialUrl: "https://fonts.google.com/specimen/Kirang+Haerang", aliases: ["기랑해랑", "kirang"],
  },
  {
    slug: "sandoll-gothic-neo", nameKo: "산돌 고딕 Neo", nameEn: "Sandoll Gothic Neo", fontKey: "blackHanSans",
    tier: "paid", category: "고딕", foundry: "산돌", availableWeights: [100, 200, 300, 400, 500, 600, 700, 800, 900],
    moves: 4210, license: { commercial: "no", verifiedAt: "2026-07-12" },
    officialUrl: "https://www.sandoll.co.kr/", aliases: ["산돌고딕", "sandoll gothic"],
    freeAlternatives: ["pretendard", "do-hyeon", "black-han-sans"],
  },
];
```

주의: 유료 폰트(`sandoll-gothic-neo`)는 실제 웹폰트가 없으므로 견본은 대체 fontKey(`blackHanSans`)로 렌더한다(디자인도 유료 견본을 대체 서체로 표시). `freeAlternatives`는 실제 `slug`를 가리킨다.

- [ ] **Step 2: 타입 체크**

Run: `cd apps/web && pnpm exec tsc --noEmit`
Expected: 에러 없음.

- [ ] **Step 3: Commit**

```bash
git add apps/web/data/fonts.ts
git commit -m "feat(web): add mock font data"
```

---

## Task 5: 조회/무결성 헬퍼 + 테스트 (lib/data.ts)

**Files:**
- Create: `apps/web/lib/data.ts`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/vitest.setup.ts`
- Modify: `apps/web/package.json` (test deps + scripts)
- Test: `apps/web/lib/data.test.ts`

**Interfaces:**
- Consumes: `fonts` from `data/fonts.ts`.
- Produces: `getFontBySlug(slug: string): Font | undefined`, `getAllSlugs(): string[]`, `resolveFreeAlternatives(font: Font): Font[]`, `assertDataIntegrity(): void`.

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

describe("data helpers", () => {
  it("finds a font by slug", () => {
    expect(getFontBySlug("pretendard")?.nameKo).toBe("프리텐다드");
    expect(getFontBySlug("nope")).toBeUndefined();
  });
  it("returns all slugs", () => {
    expect(getAllSlugs()).toContain("black-han-sans");
  });
  it("resolves free alternatives to real fonts (max 3)", () => {
    const paid = getFontBySlug("sandoll-gothic-neo")!;
    const alts = resolveFreeAlternatives(paid);
    expect(alts.length).toBeLessThanOrEqual(3);
    expect(alts.every((f) => f.tier === "free")).toBe(true);
    expect(alts.map((f) => f.slug)).toContain("pretendard");
  });
  it("passes integrity check (all referenced slugs exist)", () => {
    expect(() => assertDataIntegrity()).not.toThrow();
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run lib/data.test.ts`
Expected: FAIL (`lib/data` 모듈 없음).

- [ ] **Step 5: Write minimal implementation**

`apps/web/lib/data.ts`:

```ts
import { fonts } from "@/data/fonts";
import type { Font } from "@/types/font";

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

export function assertDataIntegrity(): void {
  const slugs = new Set(getAllSlugs());
  for (const f of fonts) {
    for (const alt of f.freeAlternatives ?? []) {
      if (!slugs.has(alt)) throw new Error(`freeAlternatives 참조 오류: ${f.slug} -> ${alt}`);
    }
  }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run lib/data.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add apps/web/lib/data.ts apps/web/lib/data.test.ts apps/web/vitest.config.ts apps/web/vitest.setup.ts apps/web/package.json
git commit -m "feat(web): data helpers + integrity check with vitest"
```

---

## Task 6: 폰트 등록 + fontKey 매핑 (lib/fonts.ts)

**Files:**
- Create: `apps/web/lib/fonts.ts`

**Interfaces:**
- Produces: `fontClassNames: string` (루트 html에 붙일 변수 클래스), `fontKeyToVar: Record<string, string>` (fontKey를 CSS 변수명으로 매핑). 견본 컴포넌트는 `fontKeyToVar[font.fontKey]`로 `fontFamily: var(--font-xxx)` 적용.

- [ ] **Step 1: 폰트 등록 작성**

`apps/web/lib/fonts.ts`. 견본 폰트는 CWV 보호를 위해 `preload: false` + `display: "swap"`. 단일 굵기 폰트는 `weight` 명시.

```ts
import {
  Black_Han_Sans, Jua, Do_Hyeon, Gowun_Batang, Nanum_Myeongjo,
  Kirang_Haerang, Noto_Sans_KR,
} from "next/font/google";

const common = { subsets: ["latin"] as const, display: "swap" as const, preload: false };

const blackHanSans = Black_Han_Sans({ ...common, weight: "400", variable: "--font-black-han-sans" });
const jua = Jua({ ...common, weight: "400", variable: "--font-jua" });
const doHyeon = Do_Hyeon({ ...common, weight: "400", variable: "--font-do-hyeon" });
const gowunBatang = Gowun_Batang({ ...common, weight: ["400", "700"], variable: "--font-gowun-batang" });
const nanumMyeongjo = Nanum_Myeongjo({ ...common, weight: ["400", "700", "800"], variable: "--font-nanum-myeongjo" });
const kirangHaerang = Kirang_Haerang({ ...common, weight: "400", variable: "--font-kirang-haerang" });
const notoSansKr = Noto_Sans_KR({ ...common, variable: "--font-noto-sans-kr" });

export const fontClassNames = [
  blackHanSans.variable, jua.variable, doHyeon.variable, gowunBatang.variable,
  nanumMyeongjo.variable, kirangHaerang.variable, notoSansKr.variable,
].join(" ");

export const fontKeyToVar: Record<string, string> = {
  pretendard: '"Pretendard Variable", "Pretendard", sans-serif',
  blackHanSans: "var(--font-black-han-sans)",
  jua: "var(--font-jua)",
  doHyeon: "var(--font-do-hyeon)",
  gowunBatang: "var(--font-gowun-batang)",
  nanumMyeongjo: "var(--font-nanum-myeongjo)",
  kirangHaerang: "var(--font-kirang-haerang)",
  notoSansKr: "var(--font-noto-sans-kr)",
};
```

주의: Next 빌드가 `subsets` 관련 에러(korean subset 요구)를 내면 해당 폰트 호출에 `subsets: ["korean"]`을 추가한다(node_modules/next/dist/docs/01-app/03-api-reference/02-components/font.md 참조).

- [ ] **Step 2: 빌드로 폰트 다운로드 확인**

Run: `cd apps/web && pnpm build`
Expected: 성공(빌드 시 Google Fonts 다운로드 self-host). 실패 시 위 subsets 주의 적용.

- [ ] **Step 3: Commit**

```bash
git add apps/web/lib/fonts.ts
git commit -m "feat(web): register sample google fonts + fontKey mapping"
```

---

## Task 7: 원자 컴포넌트 — TierChip

**Files:**
- Create: `apps/web/components/TierChip.tsx`, `apps/web/components/TierChip.module.css`
- Test: `apps/web/components/TierChip.test.tsx`

**Interfaces:**
- Consumes: `Tier` from `types/font.ts`.
- Produces: `<TierChip tier={tier} />` — `free`는 "무료"(포인트 약배경/포인트 텍스트), `paid`는 "유료"(보조표면/서브 텍스트).

- [ ] **Step 1: Write the failing test**

`apps/web/components/TierChip.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TierChip } from "./TierChip";

describe("TierChip", () => {
  it("renders 무료 for free", () => {
    render(<TierChip tier="free" />);
    expect(screen.getByText("무료")).toBeInTheDocument();
  });
  it("renders 유료 for paid", () => {
    render(<TierChip tier="paid" />);
    expect(screen.getByText("유료")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run components/TierChip.test.tsx`
Expected: FAIL (모듈 없음).

- [ ] **Step 3: Write implementation**

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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run components/TierChip.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/TierChip.tsx apps/web/components/TierChip.module.css apps/web/components/TierChip.test.tsx
git commit -m "feat(web): TierChip component"
```

---

## Task 8: 원자 컴포넌트 — LicenseBadge (분기 로직)

**Files:**
- Create: `apps/web/components/LicenseBadge.tsx`, `apps/web/components/LicenseBadge.module.css`
- Test: `apps/web/components/LicenseBadge.test.tsx`

**Interfaces:**
- Consumes: `Commercial` from `types/font.ts`.
- Produces: `<LicenseBadge commercial={c} />` — `yes`는 체크+"가능"(포인트), `conditional`은 느낌표+"조건부"(warn), `no`는 엑스+"불가"(down). 색 단독 금지, 항상 텍스트 병행.

- [ ] **Step 1: Write the failing test**

`apps/web/components/LicenseBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { LicenseBadge } from "./LicenseBadge";

describe("LicenseBadge", () => {
  it("shows 가능 for yes", () => {
    render(<LicenseBadge commercial="yes" />);
    expect(screen.getByText("가능")).toBeInTheDocument();
  });
  it("shows 조건부 for conditional", () => {
    render(<LicenseBadge commercial="conditional" />);
    expect(screen.getByText("조건부")).toBeInTheDocument();
  });
  it("shows 불가 for no", () => {
    render(<LicenseBadge commercial="no" />);
    expect(screen.getByText("불가")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run components/LicenseBadge.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write implementation**

`apps/web/components/LicenseBadge.module.css`:

```css
.badge { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 500; }
.icon { width: 18px; height: 18px; border-radius: 5px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 800; }
.yes { color: var(--point); }
.yes .icon { background: var(--point-weak); }
.conditional { color: var(--warn); }
.conditional .icon { background: rgba(196, 150, 60, .16); }
.no { color: var(--down); }
.no .icon { background: rgba(180, 86, 75, .14); }
```

`apps/web/components/LicenseBadge.tsx`:

```tsx
import type { Commercial } from "@/types/font";
import styles from "./LicenseBadge.module.css";

const MAP: Record<Commercial, { cls: string; icon: string; label: string }> = {
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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run components/LicenseBadge.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/LicenseBadge.tsx apps/web/components/LicenseBadge.module.css apps/web/components/LicenseBadge.test.tsx
git commit -m "feat(web): LicenseBadge with 3-state branch"
```

---

## Task 9: 원자 컴포넌트 — Button, FilterChip

**Files:**
- Create: `apps/web/components/Button.tsx`, `apps/web/components/Button.module.css`
- Create: `apps/web/components/FilterChip.tsx`, `apps/web/components/FilterChip.module.css`

**Interfaces:**
- Produces: `<Button variant="primary"|"secondary" href?={string} ...>` — href 있으면 `<a>`(next/link), 없으면 `<button type="button">`(비동작 액션 안전). `<FilterChip active={boolean}>{label}</FilterChip>` — 시각 상태만.

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

type Props = {
  variant?: "primary" | "secondary";
  href?: string;
  children: React.ReactNode;
};

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
  return <button type="button" className={`${styles.chip} ${active ? styles.active : ""}`}>{children}</button>;
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

## Task 10: 레이아웃 — Header, Footer, 루트 layout, 테마 스크립트

**Files:**
- Create: `apps/web/components/Header.tsx`, `apps/web/components/Header.module.css`
- Create: `apps/web/components/Footer.tsx`, `apps/web/components/Footer.module.css`
- Modify: `apps/web/app/layout.tsx`

**Interfaces:**
- Consumes: `fontClassNames` from `lib/fonts.ts`.
- Produces: 전역 헤더(로고+nav+검색버튼)/푸터, `<html lang="ko" data-theme>` 루트, FOUC 방지 인라인 스크립트.
- 디자인 근거: 헤더/로고는 원본 `FontAgit 화면 세트.dc.html`의 10a(라인 61-70)와 홈 1d(라인 748-833) 헤더 참조.

- [ ] **Step 1: Header 작성 (로고 A만 포인트, nav, 검색버튼)**

`apps/web/components/Header.module.css`:

```css
.header { display: flex; align-items: center; justify-content: space-between; padding: 16px 40px; border-bottom: 1px solid var(--border); background: var(--bg); position: sticky; top: 0; z-index: 10; }
.brand { display: flex; align-items: center; gap: 12px; }
.wordmark { font-size: 22px; font-weight: 800; letter-spacing: -.03em; color: var(--ink); }
.wordmark .a { color: var(--point); }
.ko { font-size: 13px; font-weight: 500; color: var(--sub); }
.nav { display: flex; gap: 22px; }
.nav a { font-size: 14px; font-weight: 500; color: var(--sub); }
.nav a:hover { color: var(--ink); }
.actions { display: flex; gap: 10px; align-items: center; }
.iconBtn { width: 36px; height: 36px; border-radius: 8px; border: 1px solid var(--border); background: transparent; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; color: var(--sub); }
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

주의: nav의 `/collections`, `/submit`는 이 계획 범위 밖(Phase 3)으로 아직 페이지가 없다. Phase 3 전까지는 링크가 404로 간다 — 허용(집계상 후속 화면). 필요 시 Phase 3에서 페이지 추가.

- [ ] **Step 2: Footer 작성 (브랜드 층 보이스)**

`apps/web/components/Footer.module.css`:

```css
.footer { margin-top: auto; padding: 28px 40px; background: var(--surface-2); border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }
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
      <span className={styles.tagline}>당신의 폰트 아지트. 오늘도 좋은 서체 찾으시길.</span>
      <div className={styles.links}>
        <Link href="/fonts">폰트</Link>
        <Link href="/trends">트렌드</Link>
      </div>
    </footer>
  );
}
```

- [ ] **Step 3: 루트 layout 교체 (폰트/테마/헤더/푸터 + FOUC 스크립트)**

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

const themeScript = `(function(){try{var t=localStorage.getItem('theme');if(!t){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`;

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

주의: body는 globals.css에서 `min-height` flex column을 위해 아래 CSS를 globals.css에 추가한다 — `body { min-height: 100vh; display: flex; flex-direction: column; }` (Task 1의 body 규칙에 병합).

- [ ] **Step 4: globals.css body에 flex column 추가**

`apps/web/app/globals.css`의 `body { ... }` 규칙에 `min-height: 100vh; display: flex; flex-direction: column;`를 추가한다.

- [ ] **Step 5: 빌드 + 스모크**

Run: `cd apps/web && pnpm build`
Expected: 성공. 그다음 Run: `cd apps/web && pnpm dev` 후 Playwright(e2e-runner 또는 playwright MCP)로 `http://localhost:3000` 로드 — 헤더 로고 "FontAgit"(A 포인트색), nav 4개, 푸터 태그라인 렌더, 콘솔 에러 0 확인. 스크린샷 저장.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/Header.tsx apps/web/components/Header.module.css apps/web/components/Footer.tsx apps/web/components/Footer.module.css apps/web/app/layout.tsx apps/web/app/globals.css
git commit -m "feat(web): root layout with header, footer, theme script"
```

---

## Task 11: 홈 화면 (1d)

**Files:**
- Create: `apps/web/components/Hero.tsx` (+ .module.css)
- Create: `apps/web/components/TrendRow.tsx` (+ .module.css), `apps/web/components/TrendTable.tsx` (+ .module.css)
- Create: `apps/web/components/AdSlot.tsx` (+ .module.css)
- Create: `apps/web/data/trends.ts`
- Modify: `apps/web/app/page.tsx`

**Interfaces:**
- Consumes: `fonts` (data), `fontKeyToVar` (lib/fonts), `TierChip`, `Button`, `FilterChip`.
- Produces: 홈 페이지 = Hero(검색+필터칩) + 이번주 TOP10(TrendTable) + 광고 슬롯.
- 디자인 근거: 원본 `FontAgit 화면 세트.dc.html` 홈 1d, 라인 748-833(헤더 아래 히어로, TOP10 2열 그리드, 카드 순위/변동/이름[견본 폰트]/이동수/무료배지, 광고 슬롯). 값(폰트 크기, 간격, 색)은 소스에서 옮긴다.

- [ ] **Step 1: 목업 트렌드 데이터**

`apps/web/data/trends.ts`:

```ts
import type { TrendItem } from "@/types/font";
import { fonts } from "@/data/fonts";

function pick(slug: string): TrendItem["font"] {
  const f = fonts.find((x) => x.slug === slug)!;
  return { slug: f.slug, nameKo: f.nameKo, fontKey: f.fontKey, tier: f.tier };
}

export const weeklyTrends: TrendItem[] = [
  { rank: 1, change: "up", changeAmount: 2, font: pick("pretendard"), moves: 5120 },
  { rank: 2, change: "hold", font: pick("black-han-sans"), moves: 3120 },
  { rank: 3, change: "up", changeAmount: 1, font: pick("jua"), moves: 2870 },
  { rank: 4, change: "down", changeAmount: 1, font: pick("do-hyeon"), moves: 2450 },
  { rank: 5, change: "new", font: pick("gowun-batang"), moves: 1980 },
  { rank: 6, change: "hold", font: pick("nanum-myeongjo"), moves: 1740 },
];
```

- [ ] **Step 2: TrendRow + TrendTable + AdSlot 작성**

`apps/web/components/TrendRow.module.css`:

```css
.row { display: flex; align-items: center; gap: 14px; padding: 12px 0; border-bottom: 1px solid var(--border); }
.rank { width: 22px; font-size: 15px; font-weight: 700; color: var(--point); }
.change { width: 44px; font-size: 12px; font-weight: 500; }
.up { color: var(--up); }
.down { color: var(--down); }
.hold { color: var(--hold); }
.new { color: var(--point); font-weight: 700; font-size: 10px; }
.name { flex: 1; font-size: 22px; color: var(--ink); }
.moves { font-size: 12px; color: var(--sub); }
```

`apps/web/components/TrendRow.tsx`:

```tsx
import Link from "next/link";
import type { TrendItem } from "@/types/font";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./TrendRow.module.css";

const CHANGE: Record<TrendItem["change"], (n?: number) => string> = {
  up: (n) => `▲ ${n ?? ""}`.trim(),
  down: (n) => `▼ ${n ?? ""}`.trim(),
  hold: () => "—",
  new: () => "NEW",
};

export function TrendRow({ item }: { item: TrendItem }) {
  return (
    <Link href={`/fonts/${item.font.slug}`} className={styles.row}>
      <span className={styles.rank}>{item.rank}</span>
      <span className={`${styles.change} ${styles[item.change]}`}>{CHANGE[item.change](item.changeAmount)}</span>
      <span className={styles.name} style={{ fontFamily: fontKeyToVar[item.font.fontKey] }}>{item.font.nameKo}</span>
      <span className={styles.moves}>이동 {item.moves.toLocaleString()}회</span>
      <TierChip tier={item.font.tier} />
    </Link>
  );
}
```

`apps/web/components/TrendTable.module.css`:

```css
.wrap { display: grid; grid-template-columns: 1fr 1fr; gap: 0 44px; }
@media (max-width: 720px) { .wrap { grid-template-columns: 1fr; } }
.title { font-size: 24px; font-weight: 800; color: var(--ink); margin: 0 0 16px; }
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
      <div className={styles.wrap}>
        {items.map((it) => <TrendRow key={it.rank} item={it} />)}
      </div>
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
export function AdSlot() {
  return <div className={styles.slot} aria-hidden="true">광고</div>;
}
```

- [ ] **Step 3: Hero 작성**

`apps/web/components/Hero.module.css`:

```css
.hero { padding: 56px 40px; text-align: center; }
.h1 { font-size: 42px; font-weight: 800; letter-spacing: -.03em; color: var(--ink); margin: 0 0 12px; }
.sub { font-size: 15px; color: var(--sub); margin: 0 0 24px; }
.searchbox { display: flex; gap: 8px; max-width: 560px; margin: 0 auto 18px; }
.input { flex: 1; height: 56px; padding: 0 18px; border: 1px solid var(--border); border-radius: 12px; font-size: 15px; background: var(--surface); color: var(--ink); }
.chips { display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
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

- [ ] **Step 4: 홈 페이지 조립**

`apps/web/app/page.tsx` 전체 교체:

```tsx
import { Hero } from "@/components/Hero";
import { TrendTable } from "@/components/TrendTable";
import { AdSlot } from "@/components/AdSlot";
import { weeklyTrends } from "@/data/trends";

export default function Home() {
  return (
    <main style={{ maxWidth: 1180, margin: "0 auto", width: "100%" }}>
      <Hero />
      <div style={{ padding: "0 40px 56px", display: "flex", flexDirection: "column", gap: 40 }}>
        <TrendTable title="이번 주 TOP 10" items={weeklyTrends} />
        <AdSlot />
      </div>
    </main>
  );
}
```

- [ ] **Step 5: 빌드 + 스모크 검증**

Run: `cd apps/web && pnpm build`
Expected: 성공. dev 서버 + Playwright로 `/` 로드 — 히어로 제목, 검색박스, 필터칩 5개, TOP10 행(폰트명이 각 견본 폰트로 렌더), 광고 슬롯, 콘솔 에러 0. 데스크톱(1280)/모바일(390) 스크린샷 저장 후 원본 1d와 대조.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/Hero.* apps/web/components/TrendRow.* apps/web/components/TrendTable.* apps/web/components/AdSlot.* apps/web/data/trends.ts apps/web/app/page.tsx
git commit -m "feat(web): home screen (hero + weekly top10 + ad slot)"
```

---

## Task 12: 폰트 카드 + 목록 화면 (1f)

**Files:**
- Create: `apps/web/components/FontCard.tsx` (+ .module.css), `apps/web/components/FontGrid.tsx` (+ .module.css)
- Create: `apps/web/app/fonts/page.tsx`

**Interfaces:**
- Consumes: `fonts`, `fontKeyToVar`, `TierChip`, `LicenseBadge`, `FilterChip`.
- Produces: `<FontCard font={Font} />`, 목록 페이지 = 필터 바(FilterChip, 시각만) + 카드 그리드.
- 디자인 근거: 원본 폰트 목록 1f, 라인 897-930(필터 + 카드 그리드; 카드는 견본 글자/이름/메타/무료배지/라이선스).

- [ ] **Step 1: FontCard 작성**

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
      <div className={styles.specimen} style={{ fontFamily: fontKeyToVar[font.fontKey] }}>
        다람쥐 헌 쳇바퀴에 타고파
      </div>
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

- [ ] **Step 2: FontGrid 작성**

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
  return (
    <div className={styles.grid}>
      {fonts.map((f) => <FontCard key={f.slug} font={f} />)}
    </div>
  );
}
```

- [ ] **Step 3: 목록 페이지 작성**

`apps/web/app/fonts/page.tsx`:

```tsx
import { fonts } from "@/data/fonts";
import { FontGrid } from "@/components/FontGrid";
import { FilterChip } from "@/components/FilterChip";

export default function FontsPage() {
  return (
    <main style={{ maxWidth: 1180, margin: "0 auto", width: "100%", padding: "40px" }}>
      <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 20px" }}>폰트</h1>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 24 }}>
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

- [ ] **Step 4: 빌드 + 스모크 검증**

Run: `cd apps/web && pnpm build`
Expected: 성공. Playwright로 `/fonts/` 로드 — 필터칩, 카드 그리드(각 카드 견본 글자가 해당 폰트로 렌더, 무료/유료 배지, 라이선스 배지). 데스크톱/모바일 스크린샷 원본 1f 대조.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/FontCard.* apps/web/components/FontGrid.* apps/web/app/fonts/page.tsx
git commit -m "feat(web): font list screen (filter bar + card grid)"
```

---

## Task 13: 미리보기 입력 + 상세 화면 (1g 무료 / 6a 유료)

**Files:**
- Create: `apps/web/components/PreviewInput.tsx` (+ .module.css), `apps/web/components/Specimen.tsx` (+ .module.css)
- Create: `apps/web/app/fonts/[slug]/page.tsx`

**Interfaces:**
- Consumes: `getFontBySlug`, `getAllSlugs`, `resolveFreeAlternatives`, `fontKeyToVar`, `TierChip`, `LicenseBadge`, `Button`, `FontCard`.
- Produces: 상세 페이지. 무료(tier=free)는 견본+미리보기+굵기+라이선스+공식 이동. 유료(tier=paid)는 구매 이동 + "비슷한 무료 대안 3개"(FontCard) 모듈 추가. `generateStaticParams`로 전 slug 사전 생성, `dynamicParams=false`, 없는 slug는 `notFound()`.
- 디자인 근거: 무료 상세 1g 라인 931-975, 유료 상세 6a 라인 282-326(무료 대안 모듈).

- [ ] **Step 1: PreviewInput 작성 (핵심 인터랙션, client component)**

`apps/web/components/PreviewInput.module.css`:

```css
.wrap { display: flex; flex-direction: column; gap: 12px; }
.sample { font-size: 40px; line-height: 1.3; color: var(--ink); min-height: 52px; word-break: break-word; }
.input { height: 48px; padding: 0 16px; border: 1px solid var(--border); border-radius: 10px; font-size: 15px; background: var(--surface); color: var(--ink); }
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
      <div className={styles.sample} style={{ fontFamily }}>{text || " "}</div>
      <input
        className={styles.input}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="미리볼 문장을 입력하세요"
        aria-label="미리보기 입력"
      />
    </div>
  );
}
```

- [ ] **Step 2: Specimen 작성 (굵기별/크기별 견본)**

`apps/web/components/Specimen.module.css`:

```css
.wrap { display: flex; flex-direction: column; gap: 14px; border: 1px solid var(--border); border-radius: var(--radius-card); padding: 24px; background: var(--surface); }
.line { color: var(--ink); line-height: 1.3; }
.cap { font-size: 11px; color: var(--sub-2); }
```

`apps/web/components/Specimen.tsx`:

```tsx
import styles from "./Specimen.module.css";

export function Specimen({ fontFamily, weights }: { fontFamily: string; weights: number[] }) {
  const sizes = [40, 28, 18];
  return (
    <div className={styles.wrap} style={{ fontFamily }}>
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

- [ ] **Step 3: 상세 페이지 (tier 분기 + 정적 생성)**

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

export const dynamicParams = false;
export function generateStaticParams() {
  return getAllSlugs().map((slug) => ({ slug }));
}

export default async function FontDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const font = getFontBySlug(slug);
  if (!font) notFound();
  const family = fontKeyToVar[font.fontKey];

  return (
    <main style={{ maxWidth: 900, margin: "0 auto", width: "100%", padding: "40px", display: "flex", flexDirection: "column", gap: 28 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: 0 }}>{font.nameKo}</h1>
        <TierChip tier={font.tier} />
        <LicenseBadge commercial={font.license.commercial} />
      </header>
      <div style={{ fontSize: 12, color: "var(--sub)" }}>
        {font.foundry} - {font.availableWeights.length}가지 굵기 - 이동 {font.moves.toLocaleString()}회 - 확인일 {font.license.verifiedAt}
      </div>

      <PreviewInput fontFamily={family} />
      <Specimen fontFamily={family} weights={font.availableWeights} />

      {font.tier === "paid" ? (
        <>
          <Button variant="primary" href={font.officialUrl}>구매 페이지로 이동</Button>
          <section>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: "8px 0 14px" }}>비슷한 무료 대안</h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
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

- [ ] **Step 4: 빌드 검증 (정적 생성 + tier 분기)**

Run: `cd apps/web && pnpm build`
Expected: 성공. `out/fonts/pretendard/index.html`(무료)과 `out/fonts/sandoll-gothic-neo/index.html`(유료) 생성 확인. 유료 페이지에 "비슷한 무료 대안" 3개 카드 포함, 무료 페이지엔 없음.

- [ ] **Step 5: 스모크 (미리보기 인터랙션)**

dev 서버 + Playwright로 `/fonts/pretendard/` 로드 — 미리보기 입력에 텍스트 타이핑 시 상단 견본 문장이 즉시 바뀌는지 확인. `/fonts/sandoll-gothic-neo/`에서 무료 대안 3카드 확인. 스크린샷 원본 1g/6a 대조.

- [ ] **Step 6: Commit**

```bash
git add apps/web/components/PreviewInput.* apps/web/components/Specimen.* apps/web/app/fonts/[slug]/page.tsx
git commit -m "feat(web): font detail (free/paid branch, preview, free alternatives)"
```

---

## Task 14: 트렌드 화면 (1h) + 404

**Files:**
- Create: `apps/web/app/trends/page.tsx`
- Create: `apps/web/app/not-found.tsx`
- Modify: `apps/web/data/trends.ts` (monthly 추가)

**Interfaces:**
- Consumes: `TrendTable`, `weeklyTrends`, `monthlyTrends`, `FilterChip`.
- Produces: `/trends` 페이지(주간/월간 필터칩 + TrendTable), 404 페이지(아지트지기 보이스).
- 디자인 근거: 트렌드 1h 라인 976-999(TOP10 확장, 주간/월간), 시스템 1i 라인 1000-1050(404 카피).

- [ ] **Step 1: 월간 트렌드 데이터 추가**

`apps/web/data/trends.ts`에 아래 export 추가:

```ts
export const monthlyTrends: TrendItem[] = [
  { rank: 1, change: "hold", font: pick("black-han-sans"), moves: 12400 },
  { rank: 2, change: "up", changeAmount: 3, font: pick("pretendard"), moves: 11800 },
  { rank: 3, change: "down", changeAmount: 1, font: pick("jua"), moves: 9200 },
  { rank: 4, change: "hold", font: pick("nanum-myeongjo"), moves: 7100 },
  { rank: 5, change: "up", changeAmount: 2, font: pick("gowun-batang"), moves: 6500 },
  { rank: 6, change: "new", font: pick("kirang-haerang"), moves: 4300 },
];
```

- [ ] **Step 2: 트렌드 페이지 작성**

`apps/web/app/trends/page.tsx`:

```tsx
import { TrendTable } from "@/components/TrendTable";
import { FilterChip } from "@/components/FilterChip";
import { weeklyTrends, monthlyTrends } from "@/data/trends";

export default function TrendsPage() {
  return (
    <main style={{ maxWidth: 1180, margin: "0 auto", width: "100%", padding: "40px", display: "flex", flexDirection: "column", gap: 32 }}>
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 800, margin: "0 0 16px" }}>트렌드</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <FilterChip active>주간</FilterChip>
          <FilterChip>월간</FilterChip>
        </div>
      </div>
      <TrendTable title="이번 주 TOP 10" items={weeklyTrends} />
      <TrendTable title="이번 달 TOP 10" items={monthlyTrends} />
    </main>
  );
}
```

- [ ] **Step 3: 404 페이지 작성 (브랜드 보이스)**

`apps/web/app/not-found.tsx`:

```tsx
import { Button } from "@/components/Button";

export default function NotFound() {
  return (
    <main style={{ maxWidth: 560, margin: "0 auto", width: "100%", padding: "80px 40px", textAlign: "center", display: "flex", flexDirection: "column", gap: 16, alignItems: "center" }}>
      <div style={{ fontSize: 42, fontWeight: 800, color: "var(--ink)" }}>404</div>
      <p style={{ fontSize: 15, color: "var(--sub)", margin: 0 }}>길을 잘못 드셨어요. 아지트 입구로 모실게요.</p>
      <Button variant="primary" href="/">홈으로</Button>
    </main>
  );
}
```

- [ ] **Step 4: 빌드 + 스모크**

Run: `cd apps/web && pnpm build`
Expected: 성공. Playwright로 `/trends/` (주간/월간 두 표), 없는 URL(예 `/fonts/none/`는 dynamicParams=false로 빌드에서 제외되므로 존재하지 않는 정적 경로 접근 시 404) 및 임의 경로 404 카피 확인. 스크린샷 대조.

- [ ] **Step 5: 전체 테스트 + 빌드 최종 확인**

Run: `cd apps/web && pnpm test && pnpm build`
Expected: 단위 테스트 전부 PASS, 빌드 성공, `out/` 생성.

- [ ] **Step 6: Commit**

```bash
git add apps/web/app/trends/page.tsx apps/web/app/not-found.tsx apps/web/data/trends.ts
git commit -m "feat(web): trends screen + 404 page"
```

---

## 후속 계획 (이 계획 범위 밖 — Phase 3-4)

별도 계획서로 이어간다: 타입 캔버스(3a), 비교(5a), 컬렉션 목록/상세(8a), 등록(8b), 빈 상태, 모바일 반응형 정밀화(4a/4b/4c, safe-area/키보드/탭바), 다크모드 토글 UI(9b), 런칭자산(파비콘/OG 사전생성, 7). OG는 `output: 'export'` 제약상 전 slug 빌드 시 사전생성 + `ImageResponse`에 한글 폰트 바이트 직접 로드(불안정 시 `public/og/` PNG 폴백).

---

## Self-Review

**Spec coverage (이 계획 범위):**
- 토큰/폰트/타입/데이터/조회헬퍼: Task 1-6. OK
- 원자 컴포넌트(TierChip/LicenseBadge/Button/FilterChip): Task 7-9. OK
- 레이아웃/헤더/푸터/테마 스크립트: Task 10. OK
- 홈 1d: Task 11. 목록 1f: Task 12. 상세 1g/6a(tier 분기+무료 대안+정적 생성): Task 13. 트렌드 1h + 404 1i(일부): Task 14. OK
- 정적 export/generateStaticParams/dynamicParams=false/notFound: Task 1, 13. OK
- 폰트 로딩 위치(루트=UI폰트, 견본=preload:false): Task 6, 10. OK
- 다크 --on-point: Task 2, 9. OK
- 데이터 무결성 검사: Task 5. OK
- 범위 밖(캔버스/비교/컬렉션/등록/빈상태/모바일 정밀/다크토글/런칭자산): 후속 계획으로 명시. OK

**Placeholder scan:** 코드 스텝은 모두 실제 코드 포함. 화면 마크업은 원본 디자인 파일의 정확한 라인 범위를 SSOT로 지정(모호 지시 아님). 남은 TODO 없음.

**Type consistency:** `Font.fontKey`/`fontKeyToVar` 키 일치, `getFontBySlug`/`getAllSlugs`/`resolveFreeAlternatives`/`assertDataIntegrity` 시그니처가 Task 5 정의와 소비처 일치, `TrendItem.font`는 `slug/nameKo/fontKey/tier`로 통일, 상세의 async `params: Promise<{slug}>` Next 16 규칙 준수.
