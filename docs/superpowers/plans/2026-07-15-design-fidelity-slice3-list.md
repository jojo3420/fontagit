# 디자인 정합 Slice 3 (폰트 목록 1f) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox(`- [ ]`).

**Goal:** /fonts 목록 화면을 디자인 1f와 90% 일치 — 상단 가로 칩 → 왼쪽 필터 사이드바(220px) + (개수/정렬 툴바 + 카드 그리드).

**Architecture:** /fonts를 2단(필터 사이드바 + 본문)으로 재구성. 신규 `FontFilters`(분류/가격/용도 섹션, 시각 매칭). FontCard를 디자인 1f 미니멀 카드(견본 pangram + 폰트명 + 티어 배지)로 단순화(meta/LicenseBadge 제거 — FontCard는 /fonts 전용). 툴바(개수 + 인기순/최신순)는 page에 인라인. 데이터/모델 변경 없음. 시각 일치는 스크린샷 비교(배점 90).

**Tech Stack:** Next.js 16 / React 19 / TypeScript / CSS Modules / Vitest + Testing Library / Playwright.

## Global Constraints

- 색/토큰 재설계 금지, `styles/tokens.css` 기존 변수만.
- TypeScript strict, 주석 한국어, `console.*` 금지. 인라인 스타일은 견본 fontFamily만 예외.
- 90% 배점: 모듈40/레이아웃30/간격-타이포20/텍스트10, 합격 90.
- 네비 6개 유지(수용한 차이).
- 필터 사이드바는 **시각(visual) 매칭**(비기능) — 현재 칩도 비기능이고 "용도"는 데이터 모델에 없음. 필터링 로직은 이 슬라이스 범위 아님.
- 디자인 1f 확정 라벨:
  - 필터 섹션: `분류`(체크박스: 고딕/명조/손글씨/디스플레이), `가격`(체크박스: 무료/유료), `용도`(칩: 본문/제목/로고)
  - 툴바: 개수 `폰트 {N}종`(N=fonts.length), 정렬 버튼 `인기순`(active)/`최신순`
  - 카드: 견본 텍스트 `다람쥐 헌 / 쳇바퀴`(2줄), 폰트명, 무료/유료 배지
- 테스트: 단일 `npx vitest run <path>`, 전체 `npm run test`. 작업 디렉터리 `apps/web`.
- 커밋 위생: 명시 파일만 `git add`. `git add .`/`-A`/`commit -a` 금지. 미추적(docs/**, .superpowers/**) 커밋 금지. 컨벤셔널 커밋.

---

## 파일 구조

- Create: `apps/web/components/FontFilters.tsx` + `.module.css` + `.test.tsx`
- Modify: `apps/web/components/FontCard.tsx` + `FontCard.module.css`; Create/Update: `apps/web/components/FontCard.test.tsx`
- Modify: `apps/web/components/FontGrid.module.css`(간격 14px)
- Modify: `apps/web/app/fonts/page.tsx` + `page.module.css`; Create: `apps/web/app/fonts/page.test.tsx`
- 재사용: `FilterChip`(용도 칩), `TierChip`, `data/fonts.ts`.

---

## Task 3.1: FontFilters 사이드바 컴포넌트

**Files:** Create `apps/web/components/FontFilters.tsx`, `FontFilters.module.css`, `FontFilters.test.tsx`

**Interfaces:** `FontFilters()` (props 없음). 시각 필터 사이드바.

- [ ] **Step 1: 실패 테스트**

Create `apps/web/components/FontFilters.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontFilters } from "@/components/FontFilters";

describe("FontFilters", () => {
  it("필터 섹션 제목을 렌더한다", () => {
    render(<FontFilters />);
    expect(screen.getByText("분류")).toBeInTheDocument();
    expect(screen.getByText("가격")).toBeInTheDocument();
    expect(screen.getByText("용도")).toBeInTheDocument();
  });
  it("분류/가격 옵션 라벨을 렌더한다", () => {
    render(<FontFilters />);
    for (const label of ["고딕", "명조", "손글씨", "디스플레이", "무료", "유료"]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
  });
});
```

- [ ] **Step 2: 실패 확인** — Run `npx vitest run components/FontFilters.test.tsx` → FAIL(import 실패).

- [ ] **Step 3: 구현**

Create `apps/web/components/FontFilters.tsx`:

```tsx
import { FilterChip } from "./FilterChip";
import styles from "./FontFilters.module.css";

const CATEGORIES = ["고딕", "명조", "손글씨", "디스플레이"] as const;
const PRICES = ["무료", "유료"] as const;
const USES = ["본문", "제목", "로고"] as const;

/** 폰트 목록 좌측 필터 사이드바(디자인 1f). 현재는 시각 매칭(비기능) */
export function FontFilters() {
  return (
    <aside className={styles.sidebar}>
      <section className={styles.section}>
        <h2 className={styles.title}>분류</h2>
        {CATEGORIES.map((c) => (
          <label key={c} className={styles.check}>
            <input type="checkbox" name="category" value={c} /> {c}
          </label>
        ))}
      </section>
      <section className={styles.section}>
        <h2 className={styles.title}>가격</h2>
        {PRICES.map((p) => (
          <label key={p} className={styles.check}>
            <input type="checkbox" name="price" value={p} /> {p}
          </label>
        ))}
      </section>
      <section className={styles.section}>
        <h2 className={styles.title}>용도</h2>
        <div className={styles.chips}>
          {USES.map((u) => (
            <FilterChip key={u}>{u}</FilterChip>
          ))}
        </div>
      </section>
    </aside>
  );
}
```

Create `apps/web/components/FontFilters.module.css`:

```css
.sidebar { display: flex; flex-direction: column; gap: 24px; }
.section { display: flex; flex-direction: column; gap: 10px; }
.title { font-size: 12px; font-weight: 700; color: var(--ink); margin: 0 0 2px; }
.check { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--sub); cursor: pointer; }
.chips { display: flex; gap: 8px; flex-wrap: wrap; }
```

- [ ] **Step 4: 통과 확인** — Run `npx vitest run components/FontFilters.test.tsx` → PASS(2).

- [ ] **Step 5: 커밋**

```bash
cd apps/web
git add components/FontFilters.tsx components/FontFilters.module.css components/FontFilters.test.tsx
git commit -m "feat(list): FontFilters 필터 사이드바(분류/가격/용도)"
```

---

## Task 3.2: FontCard 디자인 1f 미니멀 정합

**Files:** Modify `apps/web/components/FontCard.tsx`, `FontCard.module.css`; Create/Update `apps/web/components/FontCard.test.tsx`

**Interfaces:** `FontCard({ font }: { font: Font })`. 견본(pangram) + 폰트명 + 티어 배지. (meta/LicenseBadge 제거)

- [ ] **Step 1: 실패 테스트 작성/갱신**

Create(또는 기존이 있으면 전체 교체) `apps/web/components/FontCard.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FontCard } from "@/components/FontCard";
import { getFontBySlug } from "@/lib/data";

describe("FontCard", () => {
  it("폰트명/티어배지/상세링크를 렌더한다", () => {
    const font = getFontBySlug("nanum-myeongjo")!;
    render(<FontCard font={font} />);
    expect(screen.getByText("나눔명조")).toBeInTheDocument();
    expect(screen.getByText("무료")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/fonts/nanum-myeongjo");
  });
  it("견본 pangram을 렌더한다", () => {
    const font = getFontBySlug("nanum-myeongjo")!;
    render(<FontCard font={font} />);
    expect(screen.getByText(/다람쥐 헌/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인** — Run `npx vitest run components/FontCard.test.tsx` → FAIL(현재 견본 "한글", pangram 없음). 기존 테스트가 meta/license를 단언했다면 그 부분은 이 교체 파일로 대체됨.

- [ ] **Step 3: `FontCard.tsx` 교체**

`apps/web/components/FontCard.tsx` 전체를 아래로 교체:

```tsx
import Link from "next/link";
import type { Font } from "@/types/font";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./FontCard.module.css";

/** 폰트 목록 카드(디자인 1f). 견본 + 폰트명 + 티어 배지 */
export function FontCard({ font }: { font: Font }) {
  return (
    <Link href={`/fonts/${font.slug}`} className={styles.card}>
      <div className={styles.specimen} style={{ fontFamily: fontKeyToVar[font.fontKey] }}>
        다람쥐 헌<br />쳇바퀴
      </div>
      <div className={styles.foot}>
        <h3 className={styles.name}>{font.nameKo}</h3>
        <TierChip tier={font.tier} />
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: `FontCard.module.css` 교체**

`apps/web/components/FontCard.module.css` 전체를 아래로 교체:

```css
.card { display: flex; flex-direction: column; gap: 14px; padding: 20px; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; text-decoration: none; color: inherit; }
.specimen { font-size: 30px; line-height: 1.25; color: var(--ink); word-break: keep-all; }
.foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.name { margin: 0; font-size: 13.5px; font-weight: 600; color: var(--ink); }
```

- [ ] **Step 5: 통과 확인** — Run `npx vitest run components/FontCard.test.tsx` → PASS(2).

- [ ] **Step 6: 커밋**

```bash
cd apps/web
git add components/FontCard.tsx components/FontCard.module.css components/FontCard.test.tsx
git commit -m "refactor(list): FontCard 디자인 1f 미니멀 정합(견본+이름+배지)"
```

---

## Task 3.3: /fonts 2단 조립 (사이드바 + 툴바 + 그리드)

**Files:** Modify `apps/web/app/fonts/page.tsx`, `page.module.css`, `components/FontGrid.module.css`; Create `apps/web/app/fonts/page.test.tsx`

- [ ] **Step 1: 실패 테스트**

Create `apps/web/app/fonts/page.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FontsPage from "@/app/fonts/page";
import { fonts } from "@/data/fonts";

describe("폰트 목록 페이지", () => {
  it("필터 섹션과 개수/정렬 툴바를 렌더한다", () => {
    render(<FontsPage />);
    expect(screen.getByText("분류")).toBeInTheDocument();
    expect(screen.getByText(`폰트 ${fonts.length}종`)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "인기순" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인** — Run `npx vitest run "app/fonts/page.test.tsx"` → FAIL(현재 "분류" 없음).

- [ ] **Step 3: `page.tsx` 교체**

`apps/web/app/fonts/page.tsx` 전체를 아래로 교체:

```tsx
import { fonts } from "@/data/fonts";
import { FontFilters } from "@/components/FontFilters";
import { FontGrid } from "@/components/FontGrid";
import styles from "./page.module.css";

export default function FontsPage() {
  return (
    <main className={styles.main}>
      <FontFilters />
      <div className={styles.body}>
        <div className={styles.toolbar}>
          <span className={styles.count}>폰트 {fonts.length}종</span>
          <div className={styles.sorts}>
            <button type="button" className={`${styles.sort} ${styles.active}`}>인기순</button>
            <button type="button" className={styles.sort}>최신순</button>
          </div>
        </div>
        <FontGrid fonts={fonts} />
      </div>
    </main>
  );
}
```

- [ ] **Step 4: `page.module.css` 교체 (2단)**

`apps/web/app/fonts/page.module.css` 전체를 아래로 교체:

```css
.main { max-width: 1180px; margin: 0 auto; width: 100%; padding: var(--pad-page); display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 40px; align-items: start; }
.body { display: flex; flex-direction: column; gap: 18px; min-width: 0; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.count { font-size: 13px; color: var(--sub); }
.sorts { display: flex; gap: 8px; }
.sort { padding: 6px 12px; border-radius: var(--radius-pill); border: 1px solid var(--border); background: transparent; color: var(--sub); font-size: 12px; cursor: pointer; }
.sort.active { border-color: var(--point); color: var(--point); }
@media (max-width: 720px) {
  .main { grid-template-columns: 1fr; gap: 24px; }
}
```

- [ ] **Step 5: `FontGrid.module.css` 간격 14px**

`apps/web/components/FontGrid.module.css`의 `.grid`의 `gap: 16px;`를 `gap: 14px;`로 변경(나머지 유지).

- [ ] **Step 6: 통과 + 전체 검증**

Run: `npx vitest run "app/fonts/page.test.tsx"` → PASS.
Run: `npm run test` → 전체 PASS.
Run: `npm run build` → SSG 성공.

- [ ] **Step 7: 커밋**

```bash
cd apps/web
git add "app/fonts/page.tsx" "app/fonts/page.module.css" components/FontGrid.module.css "app/fonts/page.test.tsx"
git commit -m "feat(list): /fonts 2단 조립(필터 사이드바 + 개수/정렬 툴바 + 그리드)"
```

---

## Task 3.4: 목록 시각 정합 검증

디자인 1f 프레임과 `/fonts`를 병렬 캡처, 배점 90 이상까지 CSS 조정.

**Files:** Modify(필요 시) `apps/web/components/FontFilters.module.css`, `FontCard.module.css`, `app/fonts/page.module.css`

- [ ] **Step 1: 실제 렌더 캡처** — `localhost:3000/fonts/`를 데스크톱(1280)/모바일(390)/다크 캡처. `docs/review/screens/list-*.png`.
- [ ] **Step 2: 디자인 1f 프레임 캡처** — 같은 뷰포트.
- [ ] **Step 3: 배점 채점** — 사이드바 폭/섹션, 카드 견본 크기/2줄, 그리드 열수/간격, 툴바 개수/정렬 위치. 90 미만 diff 기록.
- [ ] **Step 4: 90 미만 CSS 조정 후 재캡처** — 토큰 변수 범위. 3종 90 이상까지.
- [ ] **Step 5: 캡처 저장 + 커밋(CSS 변경 시)**

```bash
cd apps/web
git add components/FontFilters.module.css components/FontCard.module.css app/fonts/page.module.css
git commit -m "fix(list): 시각 정합 미세 조정(배점 90 달성)"
```
변경 없으면 생략.

---

## Self-Review

- **스펙 커버리지**: 스펙 슬라이스 3(목록: 필터 사이드바 + 카드 그리드)→Task 3.1~3.3, 시각검증→3.4. 커버.
- **의도적 결정**: 필터 사이드바 시각-only(용도 필터는 데이터 없음, 현재 칩도 비기능). 필터링 로직은 범위 밖(향후). FontCard 미니멀화(디자인 1f 카드는 meta/license 미표시) — FontCard는 /fonts 전용이라 안전.
- **라벨 주의**: 분류 "디스플레이"는 디자인 라벨(데이터 Category는 "장식") — 시각 매칭이라 무방.
- **타입 일관성**: FontCard `{font: Font}`, FontGrid `{fonts: Font[]}` 유지. FilterChip active prop 기존 시그니처.
- **플레이스홀더**: 없음.

---

## 다음 계획 (범위 밖)

슬라이스 4~8(트렌드/비교/캔버스/컬렉션/등록)은 각 착수 시 별도 계획. 스펙 섹션 5.
