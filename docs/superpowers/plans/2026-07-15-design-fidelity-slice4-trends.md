# 디자인 정합 Slice 4 (트렌드 1h) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox(`- [ ]`).

**Goal:** /trends 화면을 디자인 1h와 90% 일치 — H1 "이번 주 인기 폰트" + 설명 + 주간/월간 탭 + 단일 주간 순위 카드 리스트(10행).

**Architecture:** 현재 /trends는 `TrendTable`(주간/월간 2표 스택). 디자인 1h는 **단일 주간 리스트**(카드형 행) + 상단 H1/설명/탭. `page.tsx`를 재작성: 상단 헤드(H1 26px + 설명 + FilterChip 주간/월간) + `weeklyTrends` 카드 리스트. 신규 `TrendRankRow`(트렌드 전용 카드형 행: 순위/변동/폰트명/클릭수(이동)/티어배지). 홈 사이드바 `TrendRow`는 **불변**(WeeklyRankPanel 배점 96 검증됨). 사용처 없는 `TrendTable` 제거. 데이터/모델 변경 없음.

**Tech Stack:** Next.js 16 / React 19 / TypeScript / CSS Modules / Vitest + Testing Library / Playwright.

## Global Constraints

- 색/토큰 재설계 금지, `styles/tokens.css` 기존 변수만.
- TypeScript strict, 주석 한국어, `console.*` 금지. 인라인 스타일은 견본 fontFamily만 예외.
- 90% 배점: 모듈40/레이아웃30/간격-타이포20/텍스트10, 합격 90.
- 네비 6개 유지(수용한 차이).
- 월간 탭은 **시각(visual) 매칭**(비기능) — 디자인 1h는 주간 단일 리스트만 렌더. `monthlyTrends` 데이터는 보존(삭제 금지), 탭 전환 로직은 이 슬라이스 범위 아님.
- 광고 플레이스홀더(목업 하단 dashed 박스)는 **수용한 차이**로 제외(수익화 기능, 정합 범위 밖).
- 디자인 1h 확정 라벨/구조:
  - H1: `이번 주 인기 폰트`
  - 설명: `이동 클릭 기준 인기 순위입니다 (다운로드 순위 아님).`
  - 탭: `주간`(active) / `월간`(inactive) — FilterChip 재사용
  - 카드 행: 순위(point 22px) + 변동(▲/▼/—/NEW) + 폰트명(실제 서체 26px) + 클릭수(숫자 + "이동" 라벨) + 무료/유료 배지(TierChip)
- 미들닷 필요 시 `{String.fromCharCode(183)}` verbatim(이 슬라이스엔 미사용 예상).
- 테스트: 단일 `npx vitest run <path>`, 전체 `npm run test`. 작업 디렉터리 `apps/web`.
- 커밋 위생: 명시 파일만 `git add`. `git add .`/`-A`/`commit -a` 금지. 미추적(docs/**, .superpowers/**) 커밋 금지. 컨벤셔널 커밋.

---

## 파일 구조

- Create: `apps/web/components/TrendRankRow.tsx` + `.module.css` + `.test.tsx`
- Rewrite: `apps/web/app/trends/page.tsx` + `page.module.css`; Create: `apps/web/app/trends/page.test.tsx`
- Remove: `apps/web/components/TrendTable.tsx` + `TrendTable.module.css` (사용처: trends/page.tsx 뿐, 재작성으로 소멸)
- 불변(건드리지 말 것): `components/TrendRow.tsx`/`.module.css`(홈 전용), `WeeklyRankPanel`, `FilterChip`, `TierChip`, `data/trends.ts`, `styles/tokens.css`
- 재사용: `FilterChip`(탭), `TierChip`(배지), `fontKeyToVar`(견본), `weeklyTrends`(데이터).

---

## Task 4.1: TrendRankRow 트렌드 전용 카드 행

**Files:** Create `apps/web/components/TrendRankRow.tsx`, `TrendRankRow.module.css`, `TrendRankRow.test.tsx`

**Interfaces:** `TrendRankRow({ item }: { item: TrendItem })`. 카드형 순위 행(순위/변동/폰트명/클릭수/티어배지). 홈 `TrendRow`와 별개 컴포넌트.

- [ ] **Step 1: 실패 테스트**

Create `apps/web/components/TrendRankRow.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendRankRow } from "@/components/TrendRankRow";
import { weeklyTrends } from "@/data/trends";

describe("TrendRankRow", () => {
  it("순위/폰트명/클릭수/티어배지/상세링크를 렌더한다", () => {
    const item = weeklyTrends[0]; // 1위 프리텐다드(무료)
    render(<TrendRankRow item={item} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText(item.font.nameKo)).toBeInTheDocument();
    expect(screen.getByText(item.moves.toLocaleString())).toBeInTheDocument();
    expect(screen.getByText("이동")).toBeInTheDocument();
    expect(screen.getByText("무료")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", `/fonts/${item.font.slug}`);
  });
  it("변동 라벨을 렌더한다(up이면 ▲)", () => {
    const item = weeklyTrends[0]; // change up 2
    render(<TrendRankRow item={item} />);
    expect(screen.getByText(/▲/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인** — Run `npx vitest run components/TrendRankRow.test.tsx` → FAIL(import 실패).

- [ ] **Step 3: 구현**

Create `apps/web/components/TrendRankRow.tsx` (아래 코드 verbatim, 로직/CSS 임의 변경 금지):

```tsx
import Link from "next/link";
import type { TrendItem } from "@/types/font";
import { fontKeyToVar } from "@/lib/fonts";
import { TierChip } from "./TierChip";
import styles from "./TrendRankRow.module.css";

const LABEL: Record<TrendItem["change"], (n?: number) => string> = {
  up: (n) => `▲ ${n ?? ""}`.trim(),
  down: (n) => `▼ ${n ?? ""}`.trim(),
  hold: () => "—",
  new: () => "NEW",
};

/** 트렌드 페이지 전용 카드형 순위 행(디자인 1h). 홈 사이드바 TrendRow와 별개 */
export function TrendRankRow({ item }: { item: TrendItem }) {
  return (
    <Link href={`/fonts/${item.font.slug}`} className={styles.row}>
      <span className={styles.rank}>{item.rank}</span>
      <span className={`${styles.change} ${styles[item.change]}`}>
        {LABEL[item.change](item.changeAmount)}
      </span>
      <span
        className={styles.name}
        style={{ fontFamily: fontKeyToVar[item.font.fontKey] }}
      >
        {item.font.nameKo}
      </span>
      <span className={styles.clicks}>
        <b className={styles.num}>{item.moves.toLocaleString()}</b>
        <em className={styles.label}>이동</em>
      </span>
      <TierChip tier={item.font.tier} />
    </Link>
  );
}
```

Create `apps/web/components/TrendRankRow.module.css` (아래 verbatim):

```css
.row { display: flex; align-items: center; gap: 18px; padding: 16px 18px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-card); text-decoration: none; color: inherit; }
.rank { width: 26px; font-size: 22px; font-weight: 800; color: var(--point); }
.change { width: 34px; font-size: 12px; font-weight: 500; }
.up { color: var(--up); } .down { color: var(--down); } .hold { color: var(--hold); }
.new { color: var(--point); font-weight: 700; font-size: 10px; }
.name { flex: 1; font-size: 26px; line-height: 1.2; color: var(--ink); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.clicks { display: flex; flex-direction: column; align-items: flex-end; line-height: 1.2; white-space: nowrap; }
.num { font-size: 14px; font-weight: 700; color: var(--ink); }
.label { font-size: 10.5px; font-style: normal; color: var(--sub); }
```

- [ ] **Step 4: 통과 확인** — Run `npx vitest run components/TrendRankRow.test.tsx` → PASS(2).

- [ ] **Step 5: 커밋**

```bash
cd apps/web
git add components/TrendRankRow.tsx components/TrendRankRow.module.css components/TrendRankRow.test.tsx
git commit -m "feat(trends): TrendRankRow 트렌드 전용 카드형 순위 행(디자인 1h)"
```

---

## Task 4.2: /trends 재조립 (헤드 + 탭 + 단일 리스트) + TrendTable 제거

**Files:** Rewrite `apps/web/app/trends/page.tsx`, `page.module.css`; Create `apps/web/app/trends/page.test.tsx`; Remove `apps/web/components/TrendTable.tsx`, `TrendTable.module.css`

- [ ] **Step 1: 실패 테스트**

Create `apps/web/app/trends/page.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import TrendsPage from "@/app/trends/page";
import { weeklyTrends } from "@/data/trends";

describe("트렌드 페이지", () => {
  it("H1/설명/주간-월간 탭을 렌더한다", () => {
    render(<TrendsPage />);
    expect(screen.getByRole("heading", { name: "이번 주 인기 폰트" })).toBeInTheDocument();
    expect(screen.getByText(/이동 클릭 기준 인기 순위입니다/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "주간" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "월간" })).toBeInTheDocument();
  });
  it("주간 순위 전체(10행)를 렌더한다", () => {
    render(<TrendsPage />);
    const links = screen.getAllByRole("link");
    // 순위 카드 링크 = weeklyTrends 길이
    expect(links.length).toBe(weeklyTrends.length);
  });
});
```

- [ ] **Step 2: 실패 확인** — Run `npx vitest run "app/trends/page.test.tsx"` → FAIL(현재 H1 "트렌드").

- [ ] **Step 3: `page.tsx` 교체**

`apps/web/app/trends/page.tsx` 전체를 아래로 교체 (verbatim):

```tsx
import { weeklyTrends } from "@/data/trends";
import { FilterChip } from "@/components/FilterChip";
import { TrendRankRow } from "@/components/TrendRankRow";
import styles from "./page.module.css";

export default function TrendsPage() {
  return (
    <main className={styles.main}>
      <div className={styles.head}>
        <h1 className={styles.h1}>이번 주 인기 폰트</h1>
        <p className={styles.lead}>이동 클릭 기준 인기 순위입니다 (다운로드 순위 아님).</p>
        <div className={styles.filters}>
          <FilterChip active>주간</FilterChip>
          <FilterChip>월간</FilterChip>
        </div>
      </div>
      <ul className={styles.list}>
        {weeklyTrends.map((item) => (
          <li key={item.rank}>
            <TrendRankRow item={item} />
          </li>
        ))}
      </ul>
    </main>
  );
}
```

- [ ] **Step 4: `page.module.css` 교체**

`apps/web/app/trends/page.module.css` 전체를 아래로 교체 (verbatim):

```css
.main { max-width: 760px; margin: 0 auto; width: 100%; padding: var(--pad-page); display: flex; flex-direction: column; gap: 22px; }
.head { display: flex; flex-direction: column; }
.h1 { font-size: 26px; font-weight: 800; line-height: 1.3; color: var(--ink); margin: 0; }
.lead { font-size: 13px; color: var(--sub); margin: 4px 0 0; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 20px; }
.list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
```

- [ ] **Step 5: TrendTable 제거** — page.tsx가 더 이상 import하지 않음을 확인 후 파일 삭제:

```bash
cd apps/web
git rm components/TrendTable.tsx components/TrendTable.module.css
```

- [ ] **Step 6: 통과 + 전체 검증**

Run: `npx vitest run "app/trends/page.test.tsx"` → PASS.
Run: `npm run test` → 전체 PASS(TrendTable 참조 잔존 없음 확인).
Run: `npm run build` → SSG 성공.

- [ ] **Step 7: 커밋**

```bash
cd apps/web
git add "app/trends/page.tsx" "app/trends/page.module.css" "app/trends/page.test.tsx"
git commit -m "feat(trends): /trends 단일 주간 리스트 재조립(헤드+탭) + TrendTable 제거"
```

(git rm은 이미 스테이징됨 — 위 add와 함께 한 커밋으로 처리)

---

## Task 4.3: 트렌드 시각 정합 검증

디자인 1h 프레임과 `/trends`를 병렬 캡처, 배점 90 이상까지 CSS 조정.

**Files:** Modify(필요 시) `apps/web/components/TrendRankRow.module.css`, `app/trends/page.module.css`

- [ ] **Step 1: 실제 렌더 캡처** — `localhost:3000/trends`를 데스크톱(1280)/모바일(390)/다크 캡처. `docs/review/screens/trends-*.png`.
- [ ] **Step 2: 디자인 1h 프레임 캡처** — 같은 뷰포트.
- [ ] **Step 3: 배점 채점** — H1/설명/탭 존재, 카드 행 순위-변동-폰트명-클릭수-배지, 행 카드 스타일(테두리/radius/padding), 리스트 간격. 90 미만 diff 기록.
- [ ] **Step 4: 90 미만 CSS 조정 후 재캡처** — 토큰 변수 범위. 3종 90 이상까지. (클릭수 라벨 위치, 컨테이너 폭 760px 적정성 확인)
- [ ] **Step 5: 캡처 저장 + 커밋(CSS 변경 시)**

```bash
cd apps/web
git add components/TrendRankRow.module.css app/trends/page.module.css
git commit -m "fix(trends): 시각 정합 미세 조정(배점 90 달성)"
```
변경 없으면 생략.

---

## Self-Review

- **스펙 커버리지**: 스펙 슬라이스 4(트렌드 1h: TOP 10 확장 주간/월간 정합)→Task 4.1~4.2, 시각검증→4.3. 커버.
- **의도적 결정**: (a) 단일 주간 리스트(디자인 1h가 단일). 월간 탭 시각-only, monthlyTrends 데이터 보존. (b) TrendRankRow 신규(홈 TrendRow 불변, 사이드바 vs 페이지 스타일 상이). (c) 광고 플레이스홀더 제외(수익화 범위 밖, 수용한 차이). (d) 10행 렌더(디자인 5행은 프레임 높이 제약, 실제는 전체 순위).
- **불변 보장**: TrendRow.module.css/WeeklyRankPanel 미수정 → 홈 배점 96 유지. FilterChip/TierChip 시그니처 재사용.
- **배지 톤**: TierChip 재사용(무료=surface-2/sub). 디자인 목업 무료 배지(point-weak)와 미세 톤차 → 시각검증 4.3에서 90 판정. 배점 90 미달 시에만 조정.
- **제거 안전성**: TrendTable 사용처 = trends/page.tsx 뿐(grep 검증 완료), 재작성으로 소멸.
- **플레이스홀더**: 없음.

---

## 다음 계획 (범위 밖)

슬라이스 5~8(비교/캔버스/컬렉션/등록)은 각 착수 시 별도 계획. 스펙 섹션 5.
