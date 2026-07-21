# /fonts 용도별 섹션 계층화 + 타입 캔버스 통합 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/fonts`를 용도 5섹션으로 계층화하고 상단 타입 캔버스로 모든 폰트 견본을 실시간 미리보기해, 서체 입문자의 선택을 안내한다.

**Architecture:** 폰트 배정은 하이브리드(런타임 순수 함수 `sectionOf` 자동 매핑 + 정적 큐레이션 오버레이). `/fonts` 서버 페이지가 `searchParams`로 개요/평면 모드를 분기하고, 개요 모드는 클라이언트 `SectionedFontsView`가 캔버스 문구 상태를 소유해 `useDeferredValue`로 하위 카드에 전파한다. 기존 `LazyFontPreview` 지연 로딩과 무한스크롤을 그대로 재사용한다.

**Tech Stack:** Next.js(App Router, apps/web — 아래 Global Constraints의 경고 참고), React 18, TypeScript(strict), vitest + @testing-library/react.

## Global Constraints

- **수정된 Next.js**: `apps/web/AGENTS.md`가 "이건 당신이 아는 Next.js가 아니다 — 코드 작성 전 `node_modules/next/dist/docs/`의 관련 문서를 읽어라"라고 경고한다. 특히 서버 컴포넌트의 `searchParams`가 Promise일 수 있으니 Task 4 착수 전 반드시 확인한다.
- **작업 디렉터리**: 모든 경로는 `apps/web/` 기준. 테스트/명령은 `apps/web/`에서 실행한다.
- **테스트 명령**: 단일 파일 `npx vitest run <상대경로>`, 전체 `npm test`(= `vitest run`). 컴포넌트 테스트는 `@testing-library/react`.
- **코딩 규칙**: TypeScript 타입 100%, 한국어 docstring, `console.log` 금지, 하드코딩 금지(섹션 값은 `SECTIONS`/`SectionSlug` 상수 사용), 불변 패턴.
- **카테고리 값 고정**: `Category = "고딕" | "명조" | "손글씨" | "장식"` 4종뿐(`types/font.ts:5`). 그 외 문자열은 없다.
- **`availableWeights`**: `number[]`, 매퍼가 빈 배열 시 `[400]` 기본값 보장(`lib/db/mappers.ts:65`) — 빈 배열 방어 코드 불필요.
- **커밋 규칙**: `<타입>: <설명>` (feat/fix/refactor/docs/test). 브랜치 `feat/60-fonts-section-canvas`(이미 생성됨).

---

## Slice 1 — 섹션 자동 매핑 + 개요 렌더 (에픽 1단계)

### Task 1: 섹션 정의 + 자동 매핑 라이브러리

**Files:**
- Create: `apps/web/lib/sections.ts`
- Test: `apps/web/lib/sections.test.ts`

**Interfaces:**
- Consumes: `Font`, `Category` (`@/types/font`)
- Produces:
  - `type SectionSlug = "body" | "headline" | "brand" | "handwriting" | "decorative"`
  - `interface SectionDef { slug: SectionSlug; label: string; guide: string; order: number }`
  - `const SECTIONS: SectionDef[]`
  - `function sectionOf(font: Pick<Font, "category" | "availableWeights">): SectionSlug`
  - `function groupFontsBySection(fonts: Font[]): Record<SectionSlug, Font[]>`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/lib/sections.test.ts`

```tsx
import { describe, it, expect } from "vitest";
import { sectionOf, groupFontsBySection, SECTIONS } from "./sections";
import type { Font } from "@/types/font";

function makeFont(over: Partial<Font>): Font {
  return {
    slug: "s", nameKo: "이름", nameEn: "name", fontKey: null, tier: "free",
    category: "고딕", foundry: "f", availableWeights: [400], moves: 0,
    license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
    officialUrl: "", aliases: [], subsets: ["korean"], ...over,
  } as Font;
}

describe("sectionOf", () => {
  it("손글씨 → handwriting", () => {
    expect(sectionOf(makeFont({ category: "손글씨" }))).toBe("handwriting");
  });
  it("장식 → decorative", () => {
    expect(sectionOf(makeFont({ category: "장식" }))).toBe("decorative");
  });
  it("명조 → brand", () => {
    expect(sectionOf(makeFont({ category: "명조" }))).toBe("brand");
  });
  it("고딕 + 본문 굵기 포함 → body", () => {
    expect(sectionOf(makeFont({ category: "고딕", availableWeights: [400, 700] }))).toBe("body");
  });
  it("고딕 + 굵은 굵기만(700+) → headline", () => {
    expect(sectionOf(makeFont({ category: "고딕", availableWeights: [700, 900] }))).toBe("headline");
  });
});

describe("groupFontsBySection", () => {
  it("섹션별로 분배하고 빈 섹션은 빈 배열", () => {
    const groups = groupFontsBySection([
      makeFont({ slug: "a", category: "명조" }),
      makeFont({ slug: "b", category: "손글씨" }),
    ]);
    expect(groups.brand.map((f) => f.slug)).toEqual(["a"]);
    expect(groups.handwriting.map((f) => f.slug)).toEqual(["b"]);
    expect(groups.body).toEqual([]);
  });
});

describe("SECTIONS", () => {
  it("5개 섹션이 order 순으로 정의됨", () => {
    expect(SECTIONS.map((s) => s.slug)).toEqual(["body", "headline", "brand", "handwriting", "decorative"]);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run lib/sections.test.ts`
Expected: FAIL — "Failed to resolve import ./sections" 또는 "sectionOf is not a function"

- [ ] **Step 3: 구현 작성** — `apps/web/lib/sections.ts`

```ts
import type { Font } from "@/types/font";

/** /fonts 용도 섹션 slug */
export type SectionSlug = "body" | "headline" | "brand" | "handwriting" | "decorative";

export interface SectionDef {
  slug: SectionSlug;
  label: string;
  guide: string;
  order: number;
}

export const SECTIONS: SectionDef[] = [
  { slug: "body", label: "본문-긴 글", guide: "오래 읽어도 편안한 서체", order: 1 },
  { slug: "headline", label: "제목-강조", guide: "시선을 잡는 굵고 큰 서체", order: 2 },
  { slug: "brand", label: "브랜드-감성", guide: "분위기를 만드는 명조-세리프", order: 3 },
  { slug: "handwriting", label: "손글씨-캐주얼", guide: "친근하고 개성 있는 손글씨", order: 4 },
  { slug: "decorative", label: "개성-장식", guide: "포스터-이벤트용 튀는 서체", order: 5 },
];

const HEADLINE_MIN_WEIGHT = 700;

/** 폰트를 대표 용도 섹션 하나로 매핑(자동 매핑). 큐레이션은 별도 오버레이. */
export function sectionOf(font: Pick<Font, "category" | "availableWeights">): SectionSlug {
  switch (font.category) {
    case "손글씨":
      return "handwriting";
    case "장식":
      return "decorative";
    case "명조":
      return "brand";
    case "고딕":
      // 본문 굵기(700 미만)가 하나도 없으면 제목용으로 본다
      return font.availableWeights.every((w) => w >= HEADLINE_MIN_WEIGHT) ? "headline" : "body";
    default:
      return "body";
  }
}

export function groupFontsBySection(fonts: Font[]): Record<SectionSlug, Font[]> {
  const groups: Record<SectionSlug, Font[]> = {
    body: [], headline: [], brand: [], handwriting: [], decorative: [],
  };
  for (const font of fonts) {
    groups[sectionOf(font)].push(font);
  }
  return groups;
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run lib/sections.test.ts`
Expected: PASS (전체 통과)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/sections.ts apps/web/lib/sections.test.ts
git commit -m "feat: 폰트 용도 섹션 자동 매핑(sectionOf/groupFontsBySection) (#60)"
```

---

### Task 2: 단일 섹션 카드 컴포넌트 FontSection

**Files:**
- Create: `apps/web/components/FontSection.tsx`, `apps/web/components/FontSection.module.css`
- Test: `apps/web/components/FontSection.test.tsx`

**Interfaces:**
- Consumes: `SectionDef` (`@/lib/sections`), `Font` (`@/types/font`), `FontGrid` (`./FontGrid`)
- Produces: `function FontSection(props: { section: SectionDef; fonts: Font[]; totalCount: number }): JSX.Element` — 상위 N개는 호출자가 이미 잘라서 넘긴다. `totalCount`는 섹션 전체 개수(더보기 표시용).

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/components/FontSection.test.tsx`

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontSection } from "./FontSection";
import type { Font } from "@/types/font";
import type { SectionDef } from "@/lib/sections";

const section: SectionDef = { slug: "body", label: "본문-긴 글", guide: "가이드", order: 1 };
const font = { slug: "a", nameKo: "가폰트", nameEn: "a", fontKey: null, tier: "free",
  category: "고딕", foundry: "f", availableWeights: [400], moves: 0,
  license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
  officialUrl: "", aliases: [], subsets: ["korean"] } as Font;

describe("FontSection", () => {
  it("라벨-가이드-카드-더보기 링크를 렌더한다", () => {
    render(<FontSection section={section} fonts={[font]} totalCount={20} />);
    expect(screen.getByText("본문-긴 글")).toBeInTheDocument();
    expect(screen.getByText("가이드")).toBeInTheDocument();
    expect(screen.getByText("가폰트")).toBeInTheDocument();
    const more = screen.getByRole("link", { name: /더보기/ });
    expect(more).toHaveAttribute("href", "/fonts?section=body");
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run components/FontSection.test.tsx`
Expected: FAIL — "Failed to resolve import ./FontSection"

- [ ] **Step 3: 구현 작성** — `apps/web/components/FontSection.tsx`

```tsx
import Link from "next/link";
import type { Font } from "@/types/font";
import type { SectionDef } from "@/lib/sections";
import { FontGrid } from "./FontGrid";
import styles from "./FontSection.module.css";

/** /fonts 개요의 용도 섹션 한 덩어리: 헤더 + 대표 카드 + 더보기 */
export function FontSection({
  section,
  fonts,
  totalCount,
}: {
  section: SectionDef;
  fonts: Font[];
  totalCount: number;
}) {
  return (
    <section className={styles.section}>
      <header className={styles.header}>
        <h2 className={styles.label}>{section.label}</h2>
        <p className={styles.guide}>{section.guide}</p>
      </header>
      <FontGrid fonts={fonts} />
      <Link href={`/fonts?section=${section.slug}`} className={styles.more}>
        더보기 ({totalCount}종)
      </Link>
    </section>
  );
}
```

`apps/web/components/FontSection.module.css`:

```css
.section { margin-bottom: 2.5rem; }
.header { margin-bottom: 1rem; }
.label { font-size: 1.25rem; font-weight: 700; }
.guide { color: var(--muted, #666); font-size: 0.9rem; margin-top: 0.25rem; }
.more { display: inline-block; margin-top: 1rem; font-size: 0.9rem; text-decoration: underline; }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run components/FontSection.test.tsx`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/FontSection.tsx apps/web/components/FontSection.module.css apps/web/components/FontSection.test.tsx
git commit -m "feat: 용도 섹션 카드 컴포넌트 FontSection (#60)"
```

---

### Task 3: 섹션 개요 컴포넌트 SectionOverview

**Files:**
- Create: `apps/web/components/SectionOverview.tsx`, `apps/web/components/SectionOverview.module.css`
- Test: `apps/web/components/SectionOverview.test.tsx`

**Interfaces:**
- Consumes: `SECTIONS`, `groupFontsBySection` (`@/lib/sections`), `FontSection` (`./FontSection`), `Font`
- Produces: `function SectionOverview(props: { fonts: Font[]; topN?: number }): JSX.Element` — 내부에서 그룹핑, 각 섹션 상위 `topN`(기본 12)개만 카드로, 빈 섹션은 렌더 생략, 상단 "전체 폰트 보기" 링크.

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/components/SectionOverview.test.tsx`

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SectionOverview } from "./SectionOverview";
import type { Font } from "@/types/font";

function f(slug: string, category: Font["category"], weights = [400]): Font {
  return { slug, nameKo: slug, nameEn: slug, fontKey: null, tier: "free", category,
    foundry: "f", availableWeights: weights, moves: 0,
    license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
    officialUrl: "", aliases: [], subsets: ["korean"] } as Font;
}

describe("SectionOverview", () => {
  it("데이터 있는 섹션만 렌더하고 전체 보기 링크를 제공한다", () => {
    render(<SectionOverview fonts={[f("m", "명조"), f("h", "손글씨")]} />);
    expect(screen.getByText("브랜드-감성")).toBeInTheDocument();
    expect(screen.getByText("손글씨-캐주얼")).toBeInTheDocument();
    expect(screen.queryByText("본문-긴 글")).not.toBeInTheDocument(); // 빈 섹션 숨김
    expect(screen.getByRole("link", { name: /전체 폰트 보기/ })).toHaveAttribute("href", "/fonts?section=all");
  });

  it("섹션당 topN개만 카드로 노출한다", () => {
    const many = Array.from({ length: 20 }, (_, i) => f(`b${i}`, "명조"));
    render(<SectionOverview fonts={many} topN={12} />);
    // FontCard는 nameKo를 렌더 → 12개만
    expect(screen.getAllByText(/^b\d+$/).length).toBe(12);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run components/SectionOverview.test.tsx`
Expected: FAIL — "Failed to resolve import ./SectionOverview"

- [ ] **Step 3: 구현 작성** — `apps/web/components/SectionOverview.tsx`

```tsx
import Link from "next/link";
import type { Font } from "@/types/font";
import { SECTIONS, groupFontsBySection } from "@/lib/sections";
import { FontSection } from "./FontSection";
import styles from "./SectionOverview.module.css";

const DEFAULT_TOP_N = 12;

/** /fonts 개요: 용도 섹션별로 대표 폰트를 계층 렌더한다 */
export function SectionOverview({ fonts, topN = DEFAULT_TOP_N }: { fonts: Font[]; topN?: number }) {
  const groups = groupFontsBySection(fonts);

  return (
    <div className={styles.overview}>
      <div className={styles.top}>
        <Link href="/fonts?section=all" className={styles.viewAll}>
          전체 폰트 보기
        </Link>
      </div>
      {SECTIONS.map((section) => {
        const all = groups[section.slug];
        if (all.length === 0) return null;
        return (
          <FontSection
            key={section.slug}
            section={section}
            fonts={all.slice(0, topN)}
            totalCount={all.length}
          />
        );
      })}
    </div>
  );
}
```

`apps/web/components/SectionOverview.module.css`:

```css
.overview { width: 100%; }
.top { display: flex; justify-content: flex-end; margin-bottom: 1rem; }
.viewAll { font-size: 0.9rem; text-decoration: underline; }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run components/SectionOverview.test.tsx`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/SectionOverview.tsx apps/web/components/SectionOverview.module.css apps/web/components/SectionOverview.test.tsx
git commit -m "feat: 섹션 개요 컴포넌트 SectionOverview (#60)"
```

---

### Task 4: /fonts 라우팅 분기 + 섹션 필터

**Files:**
- Modify: `apps/web/app/fonts/page.tsx` (전체 교체)
- Modify: `apps/web/components/ClientFontsList.tsx:21-31` (섹션 필터 추가)
- Test: `apps/web/app/fonts/page.test.tsx` (갱신), `apps/web/components/ClientFontsList.test.tsx` (신규)

**Interfaces:**
- Consumes: `getAllFonts` (`@/lib/data`), `SectionOverview`, `ClientFontFilters`, `ClientFontsList`, `sectionOf` (`@/lib/sections`)
- Produces: `/fonts`가 `section`/필터 파라미터 없으면 개요, 있으면 평면 목록. `ClientFontsList`는 `?section=<slug>`면 `sectionOf`로 선필터.

- [ ] **Step 1: searchParams API 확인 (AGENTS.md 준수)**

Run: `ls apps/web/node_modules/next/dist/docs/ && grep -rl "searchParams" apps/web/node_modules/next/dist/docs/ | head`
Expected: 서버 컴포넌트 `searchParams`가 Promise인지 동기 객체인지 확인. 아래 구현은 Promise 가정(`await searchParams`) — 문서와 다르면 그에 맞춰 `await` 유무만 조정한다.

- [ ] **Step 2: 실패 테스트 작성** — `apps/web/components/ClientFontsList.test.tsx`

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ClientFontsList } from "./ClientFontsList";
import type { Font } from "@/types/font";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams("section=handwriting"),
}));

function f(slug: string, category: Font["category"]): Font {
  return { slug, nameKo: slug, nameEn: slug, fontKey: null, tier: "free", category,
    foundry: "f", availableWeights: [400], moves: 0,
    license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
    officialUrl: "", aliases: [], subsets: ["korean"] } as Font;
}

describe("ClientFontsList 섹션 선필터", () => {
  it("?section=handwriting이면 손글씨 폰트만 남긴다", () => {
    render(<ClientFontsList fonts={[f("hand", "손글씨"), f("body", "고딕")]} />);
    expect(screen.getByText("hand")).toBeInTheDocument();
    expect(screen.queryByText("body")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `npx vitest run components/ClientFontsList.test.tsx`
Expected: FAIL — 두 폰트 모두 렌더되어 `body`도 존재(선필터 미구현)

- [ ] **Step 4: ClientFontsList 섹션 선필터 구현** — `apps/web/components/ClientFontsList.tsx`

`import { sectionOf } from "@/lib/sections";`를 상단 import에 추가하고, 29행 `const filtered = filterFonts(...)` 앞에 섹션 선필터를 넣는다:

```tsx
  const sectionParam = searchParams.get("section");
  const base =
    sectionParam && sectionParam !== "all"
      ? fonts.filter((font) => sectionOf(font) === sectionParam)
      : fonts;

  const filtered = filterFonts(base, categories, tiers, sourceTiers);
```

(기존 `const filtered = filterFonts(fonts, ...)`의 첫 인자를 `base`로 교체)

- [ ] **Step 5: 섹션 필터 테스트 통과 확인**

Run: `npx vitest run components/ClientFontsList.test.tsx`
Expected: PASS

- [ ] **Step 6: page.test.tsx 갱신(개요/평면 분기)** — `apps/web/app/fonts/page.test.tsx`

기존 테스트는 항상 평면 목록을 가정한다. 개요 모드가 기본이 되므로, 개요 렌더를 확인하도록 갱신한다. 아래 테스트를 추가/교체한다:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import FontsPage from "./page";
import type { Font } from "@/types/font";

function f(slug: string, category: Font["category"]): Font {
  return { slug, nameKo: slug, nameEn: slug, fontKey: null, tier: "free", category,
    foundry: "f", availableWeights: [400], moves: 0,
    license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
    officialUrl: "", aliases: [], subsets: ["korean"] } as Font;
}

vi.mock("@/lib/data", () => ({ getAllFonts: vi.fn(async () => [f("m", "명조")]) }));

describe("폰트 목록 페이지", () => {
  it("section 파라미터 없으면 개요(전체 폰트 보기)를 렌더한다", async () => {
    const ui = await FontsPage({ searchParams: Promise.resolve({}) });
    render(ui);
    expect(screen.getByRole("link", { name: /전체 폰트 보기/ })).toBeInTheDocument();
  });
  it("section=all이면 평면 목록(정렬 툴바)을 렌더한다", async () => {
    const ui = await FontsPage({ searchParams: Promise.resolve({ section: "all" }) });
    render(ui);
    expect(screen.getByText(/폰트 \d+종/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: page.tsx 개편 구현** — `apps/web/app/fonts/page.tsx` (전체 교체)

```tsx
import type { Metadata } from "next";
import { Suspense } from "react";
import { getAllFonts } from "@/lib/data";
import { ClientFontFilters } from "@/components/ClientFontFilters";
import { ClientFontsList } from "@/components/ClientFontsList";
import { SectionOverview } from "@/components/SectionOverview";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "폰트 찾기 - FontAgit",
  alternates: { canonical: "/fonts/" },
};

type SearchParams = Record<string, string | string[] | undefined>;

/** section/필터 파라미터가 없으면 개요, 있으면 평면 목록 모드 */
function isOverviewMode(params: SearchParams): boolean {
  return !params.section && !params.category && !params.tier && !params.source;
}

export default async function FontsPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const fonts = await getAllFonts();

  if (isOverviewMode(params)) {
    return (
      <main className={styles.main}>
        <SectionOverview fonts={fonts} />
      </main>
    );
  }

  return (
    <main className={styles.main}>
      <Suspense fallback={<div />}>
        <ClientFontFilters fonts={fonts} />
      </Suspense>
      <Suspense fallback={<div />}>
        <ClientFontsList fonts={fonts} />
      </Suspense>
    </main>
  );
}
```

- [ ] **Step 8: 관련 테스트 전체 통과 확인**

Run: `npx vitest run app/fonts/page.test.tsx components/ClientFontsList.test.tsx`
Expected: PASS

- [ ] **Step 9: 커밋**

```bash
git add apps/web/app/fonts/page.tsx apps/web/app/fonts/page.test.tsx apps/web/components/ClientFontsList.tsx apps/web/components/ClientFontsList.test.tsx
git commit -m "feat: /fonts 개요/평면 모드 분기 + 섹션 선필터 (#60)"
```

---

## Slice 2 — 타입 캔버스 실시간 동기화 (에픽 3단계)

### Task 5: FontCard previewText prop

**Files:**
- Modify: `apps/web/components/FontCard.tsx:9-13`
- Test: `apps/web/components/FontCard.test.tsx` (확장)

**Interfaces:**
- Consumes: `getSpecimenText` (`@/lib/specimen`), `LazyFontPreview`
- Produces: `function FontCard(props: { font: Font; previewText?: string })` — `previewText`가 있으면 그 문구를, 없으면 기존 팬그램을 `LazyFontPreview` 안에 렌더(지연 로딩 경로 유지).

- [ ] **Step 1: 실패 테스트 작성(FontCard.test.tsx에 추가)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontCard } from "./FontCard";
import type { Font } from "@/types/font";

const font = { slug: "a", nameKo: "가폰트", nameEn: "a", fontKey: null, tier: "free",
  category: "고딕", foundry: "f", availableWeights: [400], moves: 0,
  license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
  officialUrl: "", aliases: [], subsets: ["korean"] } as Font;

describe("FontCard previewText", () => {
  it("previewText가 있으면 견본으로 그 문구를 렌더한다", () => {
    render(<FontCard font={font} previewText="아지트" />);
    expect(screen.getByText("아지트")).toBeInTheDocument();
  });
  it("previewText가 없으면 기존 팬그램 렌더(하위 호환)", () => {
    render(<FontCard font={font} />);
    expect(screen.getByText(/다람쥐/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run components/FontCard.test.tsx`
Expected: FAIL — previewText 미지원으로 "아지트" 없음

- [ ] **Step 3: 구현 수정** — `apps/web/components/FontCard.tsx`

함수 시그니처와 본문을 아래로 교체(9~19행):

```tsx
export function FontCard({ font, previewText }: { font: Font; previewText?: string }) {
  const custom = previewText?.trim();
  const words = (custom || getSpecimenText(font, false)).split(" ");
  const line1 = words.slice(0, 2).join(" ");
  const line2 = words.slice(2, 4).join(" ");

  return (
    <Link href={`/fonts/${font.slug}`} className={styles.card}>
      <LazyFontPreview font={font} className={styles.specimen}>
        {custom ? custom : (<>{line1}<br />{line2}</>)}
      </LazyFontPreview>
```

(나머지 foot 블록은 그대로. `custom`이 있으면 줄바꿈 없이 통문구를, 없으면 기존 2줄 분할을 렌더)

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run components/FontCard.test.tsx`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/FontCard.tsx apps/web/components/FontCard.test.tsx
git commit -m "feat: FontCard previewText로 커스텀 견본 문구 지원 (#60)"
```

---

### Task 6: previewText 전파 (FontGrid → FontSection → SectionOverview)

**Files:**
- Modify: `apps/web/components/FontGrid.tsx:5-16`, `apps/web/components/FontSection.tsx`, `apps/web/components/SectionOverview.tsx`
- Test: `apps/web/components/FontGrid.test.tsx` (신규)

**Interfaces:**
- Produces: `FontGrid({ fonts, previewText? })`, `FontSection({ section, fonts, totalCount, previewText? })`, `SectionOverview({ fonts, topN?, previewText? })` — 모두 `previewText`를 하위로 그대로 내려보냄.

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/components/FontGrid.test.tsx`

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontGrid } from "./FontGrid";
import type { Font } from "@/types/font";

const font = { slug: "a", nameKo: "가폰트", nameEn: "a", fontKey: null, tier: "free",
  category: "고딕", foundry: "f", availableWeights: [400], moves: 0,
  license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
  officialUrl: "", aliases: [], subsets: ["korean"] } as Font;

describe("FontGrid previewText 전파", () => {
  it("previewText를 카드 견본으로 내려보낸다", () => {
    render(<FontGrid fonts={[font]} previewText="테스트문구" />);
    expect(screen.getByText("테스트문구")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run components/FontGrid.test.tsx`
Expected: FAIL — previewText 미전파

- [ ] **Step 3: FontGrid 수정** — `apps/web/components/FontGrid.tsx`

```tsx
import type { Font } from "@/types/font";
import { FontCard } from "./FontCard";
import styles from "./FontGrid.module.css";

interface FontGridProps {
  fonts: Font[];
  previewText?: string;
}

export function FontGrid({ fonts, previewText }: FontGridProps) {
  return (
    <div className={styles.grid}>
      {fonts.map((font) => (
        <FontCard key={font.slug} font={font} previewText={previewText} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: FontSection 수정** — `apps/web/components/FontSection.tsx`

props에 `previewText?: string`를 추가하고 `<FontGrid fonts={fonts} previewText={previewText} />`로 전달한다:

```tsx
export function FontSection({
  section,
  fonts,
  totalCount,
  previewText,
}: {
  section: SectionDef;
  fonts: Font[];
  totalCount: number;
  previewText?: string;
}) {
  return (
    <section className={styles.section}>
      <header className={styles.header}>
        <h2 className={styles.label}>{section.label}</h2>
        <p className={styles.guide}>{section.guide}</p>
      </header>
      <FontGrid fonts={fonts} previewText={previewText} />
      <Link href={`/fonts?section=${section.slug}`} className={styles.more}>
        더보기 ({totalCount}종)
      </Link>
    </section>
  );
}
```

- [ ] **Step 5: SectionOverview 수정** — `apps/web/components/SectionOverview.tsx`

props에 `previewText?: string`를 추가하고 `FontSection`에 전달한다:

```tsx
export function SectionOverview({
  fonts,
  topN = DEFAULT_TOP_N,
  previewText,
}: {
  fonts: Font[];
  topN?: number;
  previewText?: string;
}) {
  const groups = groupFontsBySection(fonts);
  return (
    <div className={styles.overview}>
      <div className={styles.top}>
        <Link href="/fonts?section=all" className={styles.viewAll}>전체 폰트 보기</Link>
      </div>
      {SECTIONS.map((section) => {
        const all = groups[section.slug];
        if (all.length === 0) return null;
        return (
          <FontSection
            key={section.slug}
            section={section}
            fonts={all.slice(0, topN)}
            totalCount={all.length}
            previewText={previewText}
          />
        );
      })}
    </div>
  );
}
```

- [ ] **Step 6: 관련 테스트 통과 확인**

Run: `npx vitest run components/FontGrid.test.tsx components/FontSection.test.tsx components/SectionOverview.test.tsx`
Expected: PASS

- [ ] **Step 7: 커밋**

```bash
git add apps/web/components/FontGrid.tsx apps/web/components/FontGrid.test.tsx apps/web/components/FontSection.tsx apps/web/components/SectionOverview.tsx
git commit -m "feat: previewText를 그리드/섹션/개요로 전파 (#60)"
```

---

### Task 7: 타입 캔버스 입력 바 TypeCanvasBar

**Files:**
- Create: `apps/web/components/TypeCanvasBar.tsx`, `apps/web/components/TypeCanvasBar.module.css`
- Test: `apps/web/components/TypeCanvasBar.test.tsx`

**Interfaces:**
- Produces: `function TypeCanvasBar(props: { value: string; onChange: (v: string) => void; placeholder?: string }): JSX.Element` — 제어 컴포넌트(상태는 부모 소유). 입력창 + 초기화 버튼, 스티키 스타일.

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/components/TypeCanvasBar.test.tsx`

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TypeCanvasBar } from "./TypeCanvasBar";

describe("TypeCanvasBar", () => {
  it("입력하면 onChange가 호출된다", async () => {
    const onChange = vi.fn();
    render(<TypeCanvasBar value="" onChange={onChange} />);
    await userEvent.type(screen.getByRole("textbox"), "가");
    expect(onChange).toHaveBeenCalledWith("가");
  });
  it("초기화 버튼은 빈 문자열로 onChange를 호출한다", async () => {
    const onChange = vi.fn();
    render(<TypeCanvasBar value="아지트" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /초기화/ }));
    expect(onChange).toHaveBeenCalledWith("");
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run components/TypeCanvasBar.test.tsx`
Expected: FAIL — "Failed to resolve import ./TypeCanvasBar"

- [ ] **Step 3: 구현 작성** — `apps/web/components/TypeCanvasBar.tsx`

```tsx
"use client";

import styles from "./TypeCanvasBar.module.css";

/** 상단 스티키 타입 캔버스: 문구를 입력하면 모든 폰트 견본에 반영된다 */
export function TypeCanvasBar({
  value,
  onChange,
  placeholder = "미리볼 문구를 입력하세요",
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <div className={styles.bar}>
      <input
        type="text"
        className={styles.input}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        aria-label="미리보기 문구"
      />
      <button type="button" className={styles.reset} onClick={() => onChange("")}>
        초기화
      </button>
    </div>
  );
}
```

`apps/web/components/TypeCanvasBar.module.css`:

```css
.bar { position: sticky; top: 0; z-index: 20; display: flex; gap: 0.5rem;
  padding: 0.75rem 1rem; background: var(--bg, #fff); border-bottom: 1px solid var(--border, #eee); }
.input { flex: 1; padding: 0.5rem 0.75rem; border: 1px solid var(--border, #ddd); border-radius: 6px; }
.reset { padding: 0.5rem 0.9rem; border: 1px solid var(--border, #ddd); border-radius: 6px; background: transparent; cursor: pointer; }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `npx vitest run components/TypeCanvasBar.test.tsx`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/TypeCanvasBar.tsx apps/web/components/TypeCanvasBar.module.css apps/web/components/TypeCanvasBar.test.tsx
git commit -m "feat: 타입 캔버스 입력 바 TypeCanvasBar (#60)"
```

---

### Task 8: SectionedFontsView (캔버스 상태 소유 + useDeferredValue)

**Files:**
- Create: `apps/web/components/SectionedFontsView.tsx`
- Modify: `apps/web/app/fonts/page.tsx` (개요 모드가 SectionedFontsView 렌더)
- Test: `apps/web/components/SectionedFontsView.test.tsx`

**Interfaces:**
- Consumes: `TypeCanvasBar`, `SectionOverview`, `Font`
- Produces: `function SectionedFontsView(props: { fonts: Font[] }): JSX.Element` — `useState(text)` 소유, `useDeferredValue(text)`를 `SectionOverview.previewText`로 전달, 상단에 `TypeCanvasBar`.

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/components/SectionedFontsView.test.tsx`

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SectionedFontsView } from "./SectionedFontsView";
import type { Font } from "@/types/font";

function f(slug: string, category: Font["category"]): Font {
  return { slug, nameKo: slug, nameEn: slug, fontKey: null, tier: "free", category,
    foundry: "f", availableWeights: [400], moves: 0,
    license: { commercial: "yes", verifiedAt: "", type: "", webfont: "included", redistribution: "yes" },
    officialUrl: "", aliases: [], subsets: ["korean"] } as Font;
}

describe("SectionedFontsView", () => {
  it("캔버스에 입력하면 폰트 카드 견본이 그 문구로 바뀐다", async () => {
    render(<SectionedFontsView fonts={[f("m", "명조")]} />);
    await userEvent.type(screen.getByRole("textbox"), "아지트");
    expect(await screen.findByText("아지트")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run components/SectionedFontsView.test.tsx`
Expected: FAIL — "Failed to resolve import ./SectionedFontsView"

- [ ] **Step 3: 구현 작성** — `apps/web/components/SectionedFontsView.tsx`

```tsx
"use client";

import { useState, useDeferredValue } from "react";
import type { Font } from "@/types/font";
import { TypeCanvasBar } from "./TypeCanvasBar";
import { SectionOverview } from "./SectionOverview";

/** /fonts 개요 모드 루트: 캔버스 문구를 소유해 모든 섹션 카드에 실시간 반영 */
export function SectionedFontsView({ fonts }: { fonts: Font[] }) {
  const [text, setText] = useState("");
  // 매 키 입력마다 대량 카드가 동기 리렌더되어 버벅이는 것을 막는다
  const deferredText = useDeferredValue(text);

  return (
    <>
      <TypeCanvasBar value={text} onChange={setText} />
      <SectionOverview fonts={fonts} previewText={deferredText} />
    </>
  );
}
```

- [ ] **Step 4: page.tsx 개요 모드 연결** — `apps/web/app/fonts/page.tsx`

`import { SectionOverview }`를 `import { SectionedFontsView } from "@/components/SectionedFontsView";`로 교체하고, 개요 분기를 아래로 바꾼다:

```tsx
  if (isOverviewMode(params)) {
    return (
      <main className={styles.main}>
        <SectionedFontsView fonts={fonts} />
      </main>
    );
  }
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `npx vitest run components/SectionedFontsView.test.tsx app/fonts/page.test.tsx`
Expected: PASS (page 테스트의 "전체 폰트 보기" 링크는 SectionedFontsView 내부 SectionOverview가 여전히 렌더하므로 통과)

- [ ] **Step 6: 커밋**

```bash
git add apps/web/components/SectionedFontsView.tsx apps/web/components/SectionedFontsView.test.tsx apps/web/app/fonts/page.tsx
git commit -m "feat: 타입 캔버스 실시간 동기화 SectionedFontsView(useDeferredValue) (#60)"
```

---

## Slice 3 — 큐레이션 오버레이 (에디터 추천, C안)

### Task 9: 큐레이션 데이터 + 유효성 테스트

**Files:**
- Create: `apps/web/data/sectionCuration.ts`
- Test: `apps/web/data/sectionCuration.test.ts`

**Interfaces:**
- Produces: `const SECTION_CURATION: Record<SectionSlug, string[]>` — 섹션별 에디터 추천 폰트 slug(상단 고정). 빈 배열 허용(추천 없음).

- [ ] **Step 1: 후보 slug 목록 확보(큐레이션 근거)**

Run: `grep -oE '"slug": *"[^"]+"' apps/web/data/fonts.ts | head -40` (정적 예시) 또는 dev DB 조회로 실제 slug 확보.
목적: 존재하는 slug만 추천에 넣기 위해 실제 값을 확인한다. 확인된 유명 폰트(예: `pretendard`, `nanum-myeongjo` 등 실제 slug)만 사용.

- [ ] **Step 2: 실패 테스트 작성** — `apps/web/data/sectionCuration.test.ts`

```ts
import { describe, it, expect } from "vitest";
import { SECTION_CURATION } from "./sectionCuration";
import { SECTIONS } from "@/lib/sections";

describe("SECTION_CURATION", () => {
  it("모든 섹션 slug를 key로 가진다", () => {
    for (const s of SECTIONS) {
      expect(SECTION_CURATION[s.slug]).toBeDefined();
      expect(Array.isArray(SECTION_CURATION[s.slug])).toBe(true);
    }
  });
  it("추천 slug에 중복이 없다", () => {
    const all = Object.values(SECTION_CURATION).flat();
    expect(new Set(all).size).toBe(all.length);
  });
});
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `npx vitest run data/sectionCuration.test.ts`
Expected: FAIL — "Failed to resolve import ./sectionCuration"

- [ ] **Step 4: 구현 작성(빈 베이스라인)** — `apps/web/data/sectionCuration.ts`

```ts
import type { SectionSlug } from "@/lib/sections";

/** 섹션별 에디터 추천 폰트 slug(LLM 큐레이션 + 사람 스팟 검수). Step 5에서 실제 slug로 채운다. */
export const SECTION_CURATION: Record<SectionSlug, string[]> = {
  body: [],
  headline: [],
  brand: [],
  handwriting: [],
  decorative: [],
};
```

- [ ] **Step 5: 실제 slug로 큐레이션 채우기**

Step 1에서 확인한 실제 slug 중 각 섹션에 확실히 맞는 유명 폰트를 3~6개씩 배열에 채운다. 예: `body`에 본문용 고딕 slug, `brand`에 대표 명조 slug. 무명 폰트는 넣지 않는다(스팟 검수 불가 시 제외). 배열 값은 반드시 Step 1에서 확인된 실존 slug여야 한다.

- [ ] **Step 6: 실존성 통합 테스트 추가(getAllFonts 대비)** — `apps/web/data/sectionCuration.test.ts`에 추가

```ts
import { getAllFonts } from "@/lib/data";

it("추천 slug는 실제 폰트에 존재한다", async () => {
  const slugs = new Set((await getAllFonts()).map((f) => f.slug));
  for (const slug of Object.values(SECTION_CURATION).flat()) {
    expect(slugs.has(slug)).toBe(true);
  }
});
```

(주의: 이 테스트는 DB 접근이 필요하다. dev env가 노출된 셸에서 실행하거나, DB 계층을 mock 한다 — memory의 웹 테스트 env 주의사항 참고.)

- [ ] **Step 7: 테스트 통과 확인**

Run: `npx vitest run data/sectionCuration.test.ts`
Expected: PASS

- [ ] **Step 8: 커밋**

```bash
git add apps/web/data/sectionCuration.ts apps/web/data/sectionCuration.test.ts
git commit -m "feat: 섹션 에디터 추천 큐레이션 데이터 + 실존성 검증 (#60)"
```

---

### Task 10: 에디터 추천을 섹션 상단에 고정 노출

**Files:**
- Modify: `apps/web/components/SectionOverview.tsx`, `apps/web/components/FontSection.tsx`
- Test: `apps/web/components/SectionOverview.test.tsx` (추천 반영 케이스 추가)

**Interfaces:**
- Produces: `FontSection`에 `recommended?: Font[]` prop 추가 — 있으면 상단에 별도 강조 그리드로, 이후 나머지 대표 카드. `SectionOverview`가 `SECTION_CURATION`으로 추천 폰트를 앞으로 정렬해 전달.

- [ ] **Step 1: 실패 테스트 작성(SectionOverview.test.tsx에 추가)**

```tsx
import { SECTION_CURATION } from "@/data/sectionCuration";
// (테스트 내에서 큐레이션을 직접 넣기 어려우면, 정렬 결과로 추천이 앞에 오는지 확인)

it("추천 폰트를 섹션 앞쪽에 우선 배치한다", () => {
  // brand 섹션 추천에 'pick'이 있다고 가정한 정렬 함수 단위 검증으로 대체 가능
  // 여기서는 orderByCuration 유틸을 검증한다
});
```

실제로는 정렬 로직을 순수 함수로 분리해 단위 테스트한다. `apps/web/lib/sections.ts`에 유틸 추가:

```ts
/** 추천 slug를 앞으로 정렬(안정 정렬) */
export function orderByCuration(fonts: Font[], recommendedSlugs: string[]): Font[] {
  const rank = new Map(recommendedSlugs.map((s, i) => [s, i]));
  return [...fonts].sort((a, b) => {
    const ra = rank.has(a.slug) ? rank.get(a.slug)! : Number.MAX_SAFE_INTEGER;
    const rb = rank.has(b.slug) ? rank.get(b.slug)! : Number.MAX_SAFE_INTEGER;
    return ra - rb;
  });
}
```

`apps/web/lib/sections.test.ts`에 테스트 추가:

```tsx
import { orderByCuration } from "./sections";

describe("orderByCuration", () => {
  it("추천 slug를 앞으로, 나머지는 원래 순서 유지", () => {
    const fonts = [makeFont({ slug: "a" }), makeFont({ slug: "b" }), makeFont({ slug: "c" })];
    expect(orderByCuration(fonts, ["c"]).map((f) => f.slug)).toEqual(["c", "a", "b"]);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run lib/sections.test.ts`
Expected: FAIL — orderByCuration 미정의

- [ ] **Step 3: orderByCuration 구현** — 위 코드를 `apps/web/lib/sections.ts`에 추가.

- [ ] **Step 4: SectionOverview에서 추천 우선 정렬 적용** — `apps/web/components/SectionOverview.tsx`

`import { SECTION_CURATION } from "@/data/sectionCuration";`와 `orderByCuration`를 import하고, 섹션 렌더 시 정렬한다:

```tsx
      {SECTIONS.map((section) => {
        const all = orderByCuration(groups[section.slug], SECTION_CURATION[section.slug]);
        if (all.length === 0) return null;
        return (
          <FontSection key={section.slug} section={section}
            fonts={all.slice(0, topN)} totalCount={all.length} previewText={previewText} />
        );
      })}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `npx vitest run lib/sections.test.ts components/SectionOverview.test.tsx`
Expected: PASS

- [ ] **Step 6: 커밋**

```bash
git add apps/web/lib/sections.ts apps/web/lib/sections.test.ts apps/web/components/SectionOverview.tsx
git commit -m "feat: 에디터 추천 폰트를 섹션 앞쪽에 우선 노출 (#60)"
```

---

## Slice 4 — 마감/회귀

### Task 11: 전체 보기 흐름 + 회귀 검증

**Files:**
- Test: 전체 스위트
- Verify: lint, build

**Interfaces:** 신규 없음. 기존 흐름(`?section=all`, `?section=<slug>`, 개요) 회귀 확인.

- [ ] **Step 1: 전체 테스트 실행**

Run: `cd apps/web && npm test`
Expected: PASS (신규 + 기존 전부)

- [ ] **Step 2: 린트**

Run: `cd apps/web && npm run lint`
Expected: 에러 0 (경고는 기존 수준 유지)

- [ ] **Step 3: 프로덕션 빌드(SSG 확인)**

Run: `cd apps/web && npm run build`
Expected: 빌드 성공. `/fonts`가 정상 생성되고 `searchParams` 사용으로 인한 렌더 오류 없음. (동적 렌더로 전환되면 로그 확인 후 허용 여부 판단)

- [ ] **Step 4: 수동 확인 체크리스트(문서화)**

`docs/superpowers/plans/`에 별도 파일 불필요. 아래를 육안 확인(dev 서버 `npm run dev`):
- `/fonts` → 용도 섹션 개요 + 상단 캔버스
- 캔버스에 문구 입력 → 모든 섹션 카드 견본이 실시간 변경(버벅임 없음)
- 섹션 "더보기" → `/fonts?section=<slug>` 해당 용도 폰트만
- "전체 폰트 보기" → `/fonts?section=all` 평면 목록 + 필터

- [ ] **Step 5: 최종 커밋(문서 동기화)**

```bash
git add -A
git commit -m "docs: #60 섹션 계층화+캔버스 구현 완료 회귀 확인"
```

---

## Self-Review (작성자 점검 결과)

- **스펙 커버리지**: 결정 1(용도 섹션 중심)=Task 3, 결정 2(5분류)=Task 1, 결정 3(하이브리드 배정)=Task 1(자동)+Task 9/10(큐레이션), 결정 4(스티키 캔버스)=Task 7/8, 결정 5(더보기 필터뷰)=Task 4, 결정 6(컬렉션 유지)=변경 없음(회귀 Task 11), 결정 7(전체 보기)=Task 3/11. 성능(useDeferredValue)=Task 8, LazyFontPreview 통합=Task 5, top N 렌더=Task 3. 누락 없음.
- **플레이스홀더**: 모든 코드 스텝에 실제 코드 포함. Task 9 큐레이션 값만 실데이터 의존이라 Step 1/5에서 "실존 slug 확인 후 채움"으로 절차화(검증 테스트로 보증) — TBD 아님.
- **타입 일관성**: `SectionSlug`/`SECTIONS`/`sectionOf`/`groupFontsBySection`/`orderByCuration`/`SECTION_CURATION`/`previewText` 시그니처가 전 태스크에서 일치. `FontCard`/`FontGrid`/`FontSection`/`SectionOverview`의 `previewText?: string` 옵셔널로 하위 호환.
- **리스크**: Task 4의 `searchParams` API는 수정된 Next.js라 Step 1에서 문서 확인 필수. Task 9의 DB 접근 테스트는 env 노출 셸 또는 mock 필요.
