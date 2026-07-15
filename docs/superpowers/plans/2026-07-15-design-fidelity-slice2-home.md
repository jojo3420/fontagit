# 디자인 정합 Slice 2 (홈 1d 2단) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 홈 화면을 디자인 1d(딥그린)와 90% 일치시킨다 — 1단 → 2단(왼쪽 히어로 + 오른쪽 이번 주 인기 TOP 10).

**Architecture:** 홈 페이지를 2단 그리드로 재구성. Hero를 2단 왼쪽 패널로 문구/칩/정렬 정합. 오른쪽에 신규 `WeeklyRankPanel`(패널 헤더 + 힌트 + 전체 링크 + 순위 리스트)을 두되 순위 항목은 기존 `TrendRow`를 재사용. 데이터는 기존 `weeklyTrends`(10항목) 사용, 신규 데이터 없음. 시각 일치는 스크린샷 병렬 비교(배점 90)로 판정.

**Tech Stack:** Next.js 16(App Router) / React 19 / TypeScript / CSS Modules / Pretendard / Vitest + Testing Library / Playwright(캡처).

## Global Constraints

- 색/토큰 재설계 금지. `styles/tokens.css` 기존 변수만 사용(`--point` #2C5545, `--point-weak`, `--border`, `--surface`, `--sub` 등).
- TypeScript strict. 주석 한국어. `console.*` 금지. 인라인 스타일은 견본 fontFamily만 예외(TrendRow의 `style={{ fontFamily }}`는 기존 허용 패턴).
- 90% 판정 배점: 모듈 존재 40 / 레이아웃-정렬 30 / 간격-타이포-모서리 20 / 텍스트 라벨 10. 합격 90.
- 상단 네비 6개 유지(수용한 차이, 헤더 채점 제외 규칙 동일).
- 디자인 1d 확정 라벨(정확히):
  - H1: `당신의 폰트 아지트`
  - 부제: `설치 없이, 웹에서. 좋은 폰트를 골라두고 지금 뜨는 흐름까지 챙겨드려요.`
  - 검색 placeholder: `폰트 이름을 검색하세요 (예: 프리텐다드)`
  - 카테고리 칩(순서): `한글`(active) / `고딕` / `명조` / `손글씨` / `무료` / `유료`
  - 우측 패널 헤더: `이번 주 인기 TOP 10`, 힌트: `이동 클릭 기준 - 매주 갱신`(가운뎃점은 `{String.fromCharCode(183)}`), 전체 링크: `전체 →`(→ 리터럴 허용, /trends로 이동)
- 테스트: 단일 `npx vitest run <path>`, 전체 `npm run test`. 작업 디렉터리 `apps/web`.
- 커밋 위생: 각 태스크에서 **명시 파일만** `git add`. `git add .`/`-A`/`commit -a` 금지. 미추적 파일(docs/**, .superpowers/**) 커밋 금지.
- 컨벤셔널 커밋.

---

## 파일 구조 (생성/수정)

- Modify: `apps/web/components/Hero.tsx` + `Hero.module.css` — 문구/칩/좌측정렬 정합.
- Modify: `apps/web/components/Hero.test.tsx`(없으면 생성) — H1/칩/placeholder 단언.
- Create: `apps/web/components/WeeklyRankPanel.tsx` + `.module.css` + `.test.tsx` — 우측 TOP 10 패널.
- Modify: `apps/web/app/page.tsx` — 2단 조립(Hero + WeeklyRankPanel), AdSlot은 2단 아래로.
- Modify: `apps/web/app/page.module.css` — 2단 그리드.
- 재사용(수정 없음): `components/TrendRow.tsx`, `data/trends.ts`(weeklyTrends), `components/FilterChip.tsx`.

---

## Task 2.1: Hero 디자인 1d 정합

**Files:**
- Modify: `apps/web/components/Hero.tsx`, `apps/web/components/Hero.module.css`
- Create: `apps/web/components/Hero.test.tsx`

**Interfaces:**
- `Hero()` (props 없음). 좌측 정렬 히어로 패널. 검색 입력 + 카테고리 칩.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/components/Hero.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Hero } from "@/components/Hero";

describe("Hero", () => {
  it("디자인 1d 문구를 렌더한다", () => {
    render(<Hero />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("당신의 폰트 아지트");
    expect(screen.getByPlaceholderText("폰트 이름을 검색하세요 (예: 프리텐다드)")).toBeInTheDocument();
  });
  it("카테고리 칩을 순서대로 렌더한다", () => {
    render(<Hero />);
    for (const label of ["한글", "고딕", "명조", "손글씨", "무료", "유료"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run components/Hero.test.tsx`
Expected: FAIL — 현재 H1은 "폰트 덕후들의 아지트", 칩 라벨 불일치.

- [ ] **Step 3: `Hero.tsx` 교체**

`apps/web/components/Hero.tsx` 전체를 아래로 교체:

```tsx
import { FilterChip } from "./FilterChip";
import styles from "./Hero.module.css";

const CHIPS = ["한글", "고딕", "명조", "손글씨", "무료", "유료"] as const;

/** 홈 히어로(디자인 1d 좌측 패널). 검색 입력 + 카테고리 칩 */
export function Hero() {
  return (
    <section className={styles.hero}>
      <h1 className={styles.h1}>당신의 폰트 아지트</h1>
      <p className={styles.sub}>
        설치 없이, 웹에서. 좋은 폰트를 골라두고 지금 뜨는 흐름까지 챙겨드려요.
      </p>
      <input
        className={styles.input}
        type="search"
        placeholder="폰트 이름을 검색하세요 (예: 프리텐다드)"
        aria-label="폰트 검색"
      />
      <div className={styles.chips}>
        {CHIPS.map((label, i) => (
          <FilterChip key={label} active={i === 0}>{label}</FilterChip>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: `Hero.module.css` 교체 (좌측 정렬 2단용)**

`apps/web/components/Hero.module.css` 전체를 아래로 교체:

```css
.hero { display: flex; flex-direction: column; gap: 16px; }
.h1 { font-size: 30px; font-weight: 800; letter-spacing: -.03em; color: var(--ink); margin: 0; }
.sub { font-size: 14px; line-height: 1.6; color: var(--sub); margin: 0; }
.input { height: 48px; padding: 0 16px; border: 1px solid var(--border); border-radius: var(--radius-btn); font-size: 15px; background: var(--surface); color: var(--ink); }
.input:focus { outline: none; border-color: var(--point); }
.chips { display: flex; gap: 8px; flex-wrap: wrap; }
@media (max-width: 900px) { .h1 { font-size: 26px; } }
```

- [ ] **Step 5: 통과 확인**

Run: `npx vitest run components/Hero.test.tsx`
Expected: PASS.

- [ ] **Step 6: 커밋**

```bash
cd apps/web
git add components/Hero.tsx components/Hero.module.css components/Hero.test.tsx
git commit -m "feat(home): Hero 디자인 1d 정합(문구/칩/좌측정렬)"
```

---

## Task 2.2: WeeklyRankPanel 컴포넌트 (우측 TOP 10)

**Files:**
- Create: `apps/web/components/WeeklyRankPanel.tsx`, `apps/web/components/WeeklyRankPanel.module.css`, `apps/web/components/WeeklyRankPanel.test.tsx`

**Interfaces:**
- Consumes: `TrendItem`(@/types/font), `TrendRow`(@/components/TrendRow).
- Produces: `WeeklyRankPanel({ items }: { items: TrendItem[] })`. 헤더 `이번 주 인기 TOP 10` + 힌트 `이동 클릭 기준 {가운뎃점} 매주 갱신` + `전체 →`(href `/trends`) + `items`를 `TrendRow`로 렌더.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/components/WeeklyRankPanel.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { weeklyTrends } from "@/data/trends";

describe("WeeklyRankPanel", () => {
  it("패널 헤더/힌트/전체 링크를 렌더한다", () => {
    render(<WeeklyRankPanel items={weeklyTrends} />);
    expect(screen.getByText("이번 주 인기 TOP 10")).toBeInTheDocument();
    expect(screen.getByText(/이동 클릭 기준/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /전체/ })).toHaveAttribute("href", "/trends");
  });
  it("전달된 순위 항목 수만큼 렌더한다", () => {
    render(<WeeklyRankPanel items={weeklyTrends} />);
    expect(screen.getAllByText(/이동 .*회/).length).toBe(weeklyTrends.length);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run components/WeeklyRankPanel.test.tsx`
Expected: FAIL — import 실패.

- [ ] **Step 3: 구현**

Create `apps/web/components/WeeklyRankPanel.tsx`:

```tsx
import Link from "next/link";
import type { TrendItem } from "@/types/font";
import { TrendRow } from "./TrendRow";
import styles from "./WeeklyRankPanel.module.css";

/** 홈 우측 "이번 주 인기 TOP 10" 패널. 순위 항목은 TrendRow 재사용 */
export function WeeklyRankPanel({ items }: { items: TrendItem[] }) {
  return (
    <aside className={styles.panel}>
      <div className={styles.head}>
        <div>
          <h2 className={styles.title}>이번 주 인기 TOP 10</h2>
          <p className={styles.hint}>이동 클릭 기준 {String.fromCharCode(183)} 매주 갱신</p>
        </div>
        <Link href="/trends" className={styles.all}>전체 →</Link>
      </div>
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.rank}>
            <TrendRow item={item} />
          </li>
        ))}
      </ul>
    </aside>
  );
}
```

Create `apps/web/components/WeeklyRankPanel.module.css`:

```css
.panel { background: rgba(44, 85, 69, .045); border: 1px solid rgba(44, 85, 69, .12); border-radius: var(--radius-card); padding: 20px; }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
.title { font-size: 15px; font-weight: 800; color: var(--ink); margin: 0; }
.hint { font-size: 11px; color: var(--sub); margin: 4px 0 0; }
.all { font-size: 12px; font-weight: 600; color: var(--point); white-space: nowrap; }
.list { list-style: none; padding: 0; margin: 0; }
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run components/WeeklyRankPanel.test.tsx`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
cd apps/web
git add components/WeeklyRankPanel.tsx components/WeeklyRankPanel.module.css components/WeeklyRankPanel.test.tsx
git commit -m "feat(home): WeeklyRankPanel 인기 TOP 10 패널"
```

---

## Task 2.3: 홈 2단 조립

**Files:**
- Modify: `apps/web/app/page.tsx`, `apps/web/app/page.module.css`
- Create: `apps/web/app/page.test.tsx`

**Interfaces:**
- Consumes: `Hero`, `WeeklyRankPanel`, `AdSlot`, `weeklyTrends`.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/app/page.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Home from "@/app/page";

describe("홈 페이지", () => {
  it("히어로와 인기 TOP 10 패널을 함께 렌더한다", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("당신의 폰트 아지트");
    expect(screen.getByText("이번 주 인기 TOP 10")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run "app/page.test.tsx"`
Expected: FAIL — 현재 홈에 "이번 주 인기 TOP 10" 패널 없음(TrendTable "이번 주 인기 폰트").

- [ ] **Step 3: `page.tsx` 교체**

`apps/web/app/page.tsx` 전체를 아래로 교체:

```tsx
import { Hero } from "@/components/Hero";
import { WeeklyRankPanel } from "@/components/WeeklyRankPanel";
import { AdSlot } from "@/components/AdSlot";
import { weeklyTrends } from "@/data/trends";
import styles from "./page.module.css";

export default function Home() {
  return (
    <main className={styles.main}>
      <div className={styles.grid}>
        <Hero />
        <WeeklyRankPanel items={weeklyTrends} />
      </div>
      <section className={styles.adSection}>
        <div className={styles.container}>
          <AdSlot />
        </div>
      </section>
    </main>
  );
}
```

- [ ] **Step 4: `page.module.css` 교체 (2단 그리드)**

`apps/web/app/page.module.css` 전체를 아래로 교체:

```css
.main { width: 100%; }
.grid { max-width: 1180px; margin: 0 auto; width: 100%; padding: var(--pad-page); display: grid; grid-template-columns: minmax(0, 1fr) 420px; gap: 48px; align-items: start; }
.container { max-width: 1180px; margin: 0 auto; }
.adSection { padding: 24px var(--pad-page); }
@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; gap: 28px; }
}
```

- [ ] **Step 5: 통과 확인 + 전체 검증**

Run: `npx vitest run "app/page.test.tsx"`
Expected: PASS.
Run: `npm run test`
Expected: 전체 PASS.
Run: `npm run build`
Expected: SSG 빌드 성공.

- [ ] **Step 6: 커밋**

```bash
cd apps/web
git add "app/page.tsx" "app/page.module.css" "app/page.test.tsx"
git commit -m "feat(home): 홈 2단 레이아웃 조립(Hero + 인기 TOP 10)"
```

---

## Task 2.4: 홈 시각 정합 검증 (데스크톱/모바일/다크)

디자인 1d 프레임과 실제 `/` 를 병렬 캡처해 Global Constraints 배점으로 채점, 90 이상까지 CSS 조정.

**Files:**
- Modify(필요 시): `apps/web/components/Hero.module.css`, `apps/web/components/WeeklyRankPanel.module.css`, `apps/web/components/TrendRow.module.css`, `apps/web/app/page.module.css`

- [ ] **Step 1: 실제 렌더 캡처** — dev 서버(`localhost:3000`)에서 `/` 를 데스크톱(1280) / 모바일(390) / 다크(data-theme=dark) 캡처. `docs/review/screens/home-*.png`.

- [ ] **Step 2: 디자인 1d 프레임 캡처** — 디자인 HTML에서 1d(딥그린 홈) 프레임을 같은 뷰포트로 캡처.

- [ ] **Step 3: 배점 채점** — 모듈40/레이아웃30/간격-타이포20/텍스트10. 90 미만 항목 diff 리스트.
  - **특히 확인/결정**: 우측 TOP 10이 단일 세로 리스트인지 2×5 그리드인지 디자인과 대조해 결정. 2×5면 `WeeklyRankPanel.module.css`의 `.list`를 `display:grid; grid-template-columns:1fr 1fr; gap:...`로. 히어로-패널 좌우 폭 비율, 검색 입력 옆 버튼 유무, 칩 active 스타일도 대조.

- [ ] **Step 4: 90 미만 항목 CSS 조정 후 재캡처** — 토큰 변수 범위 내 조정. 6종(데/모/다) 90 이상까지 반복.

- [ ] **Step 5: 캡처 저장 + 커밋(CSS 변경 시)**

```bash
cd apps/web
git add components/Hero.module.css components/WeeklyRankPanel.module.css components/TrendRow.module.css app/page.module.css
git commit -m "fix(home): 시각 정합 미세 조정(배점 90 달성)"
```
변경 없으면 커밋 생략.

---

## Self-Review (계획 작성자 점검)

- **스펙 커버리지**: 스펙 슬라이스 2(홈 2단, 히어로+검색+칩 / 인기 TOP 10)→Task 2.1~2.3, 시각검증→2.4. 커버.
- **결정 유보(의도)**: 우측 TOP 10의 1열 vs 2×5 그리드는 두 목업 판독이 엇갈려 2.4 Step 3에서 프레임 대조로 확정(스크린샷 비교 방식에 부합).
- **AdSlot**: 디자인 1d에 없음 → 2단 아래로 이동해 폴드 채점 영향 최소화. 삭제하지 않음(기능 보존).
- **타입 일관성**: `WeeklyRankPanel({items: TrendItem[]})` ↔ `weeklyTrends: TrendItem[]` ↔ `TrendRow({item: TrendItem})` 일치. `FilterChip active` prop 기존 시그니처 사용.
- **플레이스홀더**: 없음(모든 스텝 실제 코드/명령/기대 출력).

---

## 다음 계획 (범위 밖)

슬라이스 3~8(목록/트렌드/비교/캔버스/컬렉션/등록)은 각 착수 시 별도 계획. 스펙 섹션 5 참조.
