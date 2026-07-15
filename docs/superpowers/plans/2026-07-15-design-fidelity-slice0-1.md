# 디자인 정합 Slice 0+1 (공통 크롬 + 데이터 모델 + 폰트 상세) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 폰트 상세 화면(무료 1g / 유료 6a)을 디자인 목업과 90% 일치시키고, 이를 뒷받침할 라이선스 데이터 모델과 공통 크롬을 정합한다.

**Architecture:** 라이선스 요약 카드용 필드를 `Font` 타입에 추가하고 10개 폰트 데이터를 채운다. 순수 매핑/파생 로직(`lib/license.ts`)은 단위 테스트로 검증한다. 폰트 상세 페이지를 1단에서 2단(본문 + sticky 사이드바)으로 재구성하고, 신규 프레젠테이션 컴포넌트(Breadcrumb / SpecimenBox / LicenseSummaryCard / AlternativesCard)를 조립한다. 시각 일치는 스크린샷 병렬 비교(배점 90)로 판정한다.

**Tech Stack:** Next.js 16(App Router, SSG) / React 19 / TypeScript / CSS Modules / Pretendard / Vitest + Testing Library / Playwright(캡처).

## Global Constraints

- 색/토큰 재설계 금지. `styles/tokens.css`의 기존 CSS 변수만 사용(`--point` #2C5545, `--border` #E6E6E2, `--surface`, `--surface-2`, `--radius-card` 12px 등).
- TypeScript strict. Docstring/주석 한국어. `console.*` 금지. 하드코딩 대신 매핑 상수/유니온 타입.
- 90% 판정 배점: 모듈 존재 40 / 레이아웃-정렬 30 / 간격-타이포-모서리 20 / 텍스트 라벨 10. 합격선 90.
- 상단 네비 6개 유지(폰트/트렌드/캔버스/비교/컬렉션/등록). 헤더 채점은 네비 항목 수/라벨 제외.
- 대표 slug: 무료 상세 `nanum-myeongjo`, 유료 상세 `sandoll-gothic-neo`.
- 테스트 명령: 단일 `npx vitest run <path>`, 전체 `npm run test`. 작업 디렉터리 `apps/web`.
- 커밋: 컨벤셔널(`feat:`, `fix:`, `refactor:`, `test:`, `docs:`).

---

## 파일 구조 (생성/수정)

- Modify: `apps/web/types/font.ts` — `License`에 `type/webfont/redistribution`, `Font`에 `priceFrom?` 추가.
- Create: `apps/web/lib/license.ts` — enum→한국어 라벨 + 상태 + 판매처 호스트 파생(순수 함수).
- Create: `apps/web/lib/license.test.ts` — license.ts 단위 테스트.
- Modify: `apps/web/lib/data.ts` — `checkIntegrity`에 라이선스 필수 필드 검증 추가.
- Modify: `apps/web/lib/data.test.ts` — 라이선스 검증 테스트 추가.
- Modify: `apps/web/data/fonts.ts` — 10개 폰트에 신규 라이선스 필드 채움(sandoll `commercial` 보정 포함).
- Create: `apps/web/components/Breadcrumb.tsx` + `.module.css` + `Breadcrumb.test.tsx`.
- Create: `apps/web/components/SpecimenBox.tsx` + `.module.css` + `SpecimenBox.test.tsx`.
- Create: `apps/web/components/LicenseSummaryCard.tsx` + `.module.css` + `LicenseSummaryCard.test.tsx`.
- Create: `apps/web/components/AlternativesCard.tsx` + `.module.css` + `AlternativesCard.test.tsx`.
- Modify: `apps/web/app/fonts/[slug]/page.tsx` — 2단 레이아웃으로 재구성.
- Modify: `apps/web/app/fonts/[slug]/page.module.css` — 2단/반응형/다크 스타일.
- Create: `apps/web/app/fonts/[slug]/page.test.tsx` — 무료/유료 변형 모듈 존재 통합 테스트.

---

## Task 0.1: 라이선스 데이터 모델 + 파생 로직

**Files:**
- Modify: `apps/web/types/font.ts`
- Create: `apps/web/lib/license.ts`, `apps/web/lib/license.test.ts`
- Modify: `apps/web/lib/data.ts`, `apps/web/lib/data.test.ts`
- Modify: `apps/web/data/fonts.ts`

**Interfaces:**
- Produces:
  - `License` = `{ commercial: Commercial; verifiedAt: string; type: string; webfont: LicenseWebfont; redistribution: LicenseRedistribution }`
  - `type LicenseWebfont = "included" | "separate" | "no"`
  - `type LicenseRedistribution = "yes" | "no"`
  - `Font.priceFrom?: number`
  - `commercialLabel(c: Commercial): string`, `webfontLabel(w: LicenseWebfont): string`, `redistributionLabel(r: LicenseRedistribution): string`
  - `type LicenseState = "ok" | "cond" | "no"`
  - `commercialState(c)`, `webfontState(w)`, `redistributionState(r)` → `LicenseState`
  - `deriveSellerHost(url: string): string | null`

- [ ] **Step 1: 타입 확장 — 실패 테스트 먼저 (license.ts 미존재로 실패 유도)**

Create `apps/web/lib/license.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import {
  commercialLabel, webfontLabel, redistributionLabel,
  commercialState, webfontState, redistributionState,
  deriveSellerHost,
} from "@/lib/license";

describe("license 라벨 매핑", () => {
  it("상업적 사용 라벨", () => {
    expect(commercialLabel("yes")).toBe("가능");
    expect(commercialLabel("conditional")).toBe("구매 시");
    expect(commercialLabel("no")).toBe("불가");
  });
  it("웹폰트 라벨", () => {
    expect(webfontLabel("included")).toBe("포함");
    expect(webfontLabel("separate")).toBe("별도 구매");
    expect(webfontLabel("no")).toBe("불가");
  });
  it("재배포 라벨", () => {
    expect(redistributionLabel("yes")).toBe("가능");
    expect(redistributionLabel("no")).toBe("불가");
  });
});

describe("license 상태 매핑", () => {
  it("상태값", () => {
    expect(commercialState("yes")).toBe("ok");
    expect(commercialState("conditional")).toBe("cond");
    expect(commercialState("no")).toBe("no");
    expect(webfontState("included")).toBe("ok");
    expect(webfontState("separate")).toBe("cond");
    expect(webfontState("no")).toBe("no");
    expect(redistributionState("yes")).toBe("ok");
    expect(redistributionState("no")).toBe("no");
  });
});

describe("deriveSellerHost", () => {
  it("www. 제거 후 호스트만", () => {
    expect(deriveSellerHost("https://www.sandoll.co.kr/")).toBe("sandoll.co.kr");
    expect(deriveSellerHost("https://fonts.google.com/specimen/Nanum+Myeongjo")).toBe("fonts.google.com");
  });
  it("빈/잘못된 값은 null", () => {
    expect(deriveSellerHost("")).toBeNull();
    expect(deriveSellerHost("not a url")).toBeNull();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `npx vitest run lib/license.test.ts`
Expected: FAIL — "Failed to resolve import @/lib/license".

- [ ] **Step 3: `types/font.ts` 확장**

`License` 인터페이스와 신규 유니온을 추가하고 `Font`에 `priceFrom?`를 추가한다. 기존 `Commercial` 타입은 유지.

```typescript
export type LicenseWebfont = "included" | "separate" | "no";
export type LicenseRedistribution = "yes" | "no";

export interface License {
  commercial: Commercial;
  verifiedAt: string;
  type: string; // 예: "상용 라이선스", "SIL OFL"
  webfont: LicenseWebfont;
  redistribution: LicenseRedistribution;
}
```

그리고 `Font` 인터페이스에서 `license: { commercial: Commercial; verifiedAt: string }`를 `license: License`로 교체하고, `aliases: string[];` 아래에 다음을 추가한다:

```typescript
  priceFrom?: number; // 유료 폰트 시작가(원). 무료는 미설정
```

- [ ] **Step 4: `lib/license.ts` 구현**

```typescript
import type {
  Commercial, LicenseWebfont, LicenseRedistribution,
} from "@/types/font";

/** 라이선스 아이콘 상태: ok(가능) / cond(조건부) / no(불가) */
export type LicenseState = "ok" | "cond" | "no";

/** 상업적 사용 한국어 라벨 */
export function commercialLabel(c: Commercial): string {
  return { yes: "가능", conditional: "구매 시", no: "불가" }[c];
}

/** 웹폰트 한국어 라벨 */
export function webfontLabel(w: LicenseWebfont): string {
  return { included: "포함", separate: "별도 구매", no: "불가" }[w];
}

/** 재배포 한국어 라벨 */
export function redistributionLabel(r: LicenseRedistribution): string {
  return { yes: "가능", no: "불가" }[r];
}

export function commercialState(c: Commercial): LicenseState {
  return { yes: "ok", conditional: "cond", no: "no" }[c] as LicenseState;
}

export function webfontState(w: LicenseWebfont): LicenseState {
  return { included: "ok", separate: "cond", no: "no" }[w] as LicenseState;
}

export function redistributionState(r: LicenseRedistribution): LicenseState {
  return { yes: "ok", no: "no" }[r] as LicenseState;
}

/** officialUrl에서 판매처 호스트만 파생. www. 제거. 실패 시 null */
export function deriveSellerHost(url: string): string | null {
  try {
    const host = new URL(url).hostname;
    return host.replace(/^www\./, "") || null;
  } catch {
    return null;
  }
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `npx vitest run lib/license.test.ts`
Expected: PASS (전체 통과).

- [ ] **Step 6: `data/fonts.ts` — 10개 폰트에 신규 필드 채움**

각 폰트의 `license` 객체에 `type/webfont/redistribution`를 추가한다. 무료 폰트는 아래 무료 프리셋을 적용한다(commercial은 기존 값 유지, 대부분 `"yes"`):

```typescript
// 무료(OFL/무료 라이선스) 폰트 공통값 — 각 폰트 license에 병합
license: { commercial: "yes", verifiedAt: "2026-07-12", type: "SIL OFL", webfont: "included", redistribution: "yes" }
```

유료 `sandoll-gothic-neo`는 디자인 6a와 일치하도록 다음으로 교체(`commercial`을 `"no"`→`"conditional"`로 보정, `priceFrom` 추가):

```typescript
{ slug: "sandoll-gothic-neo", nameKo: "산돌 고딕 Neo", nameEn: "Sandoll Gothic Neo", fontKey: "blackHanSans",
  tier: "paid", category: "고딕", foundry: "산돌", availableWeights: [100, 200, 300, 400, 500, 600, 700, 800, 900],
  moves: 4210,
  license: { commercial: "conditional", verifiedAt: "2026-07-12", type: "상용 라이선스", webfont: "separate", redistribution: "no" },
  officialUrl: "https://www.sandoll.co.kr/", aliases: ["산돌고딕", "sandoll gothic"],
  priceFrom: 99000,
  freeAlternatives: ["pretendard", "do-hyeon", "black-han-sans"] }
```

무료 폰트별 `verifiedAt`/`type`이 기존과 다르면 기존 `verifiedAt`은 유지하고 `type`만 실제 값으로. 예: `nanum-myeongjo`는 `type: "SIL OFL"`, `webfont: "included"`, `redistribution: "yes"`, `commercial: "yes"` 유지. 나머지 8개 무료 폰트도 동일 프리셋 적용(단, 라이선스가 명백히 다른 폰트는 실제 값 사용; 불명확하면 위 무료 프리셋).

- [ ] **Step 7: `lib/data.ts` — checkIntegrity에 라이선스 검증 추가**

`checkIntegrity` 함수의 첫 번째 for 루프(폰트 순회) 안, `fontKey` 검증 다음 줄에 라이선스 필수 필드 검증을 추가한다:

```typescript
    const lic = f.license;
    if (!lic.type || lic.type.trim() === "") throw new Error(`license.type 누락: ${f.slug}`);
    if (!["included", "separate", "no"].includes(lic.webfont)) throw new Error(`license.webfont 오류: ${f.slug} -> ${lic.webfont}`);
    if (!["yes", "no"].includes(lic.redistribution)) throw new Error(`license.redistribution 오류: ${f.slug} -> ${lic.redistribution}`);
    if (f.tier === "paid" && f.priceFrom !== undefined && f.priceFrom <= 0) throw new Error(`priceFrom 양수 아님: ${f.slug}`);
```

- [ ] **Step 8: `lib/data.test.ts` — 라이선스 검증 테스트 추가**

`describe("data helpers", ...)` 블록 안(마지막 `it` 다음)에 추가:

```typescript
  it("모든 폰트에 라이선스 필드가 채워져 있다", () => {
    for (const slug of getAllSlugs()) {
      const f = getFontBySlug(slug)!;
      expect(f.license.type.length).toBeGreaterThan(0);
      expect(["included", "separate", "no"]).toContain(f.license.webfont);
      expect(["yes", "no"]).toContain(f.license.redistribution);
    }
  });
  it("유료 폰트 sandoll-gothic-neo는 구매 시/별도 구매/불가 + 가격", () => {
    const p = getFontBySlug("sandoll-gothic-neo")!;
    expect(p.license.commercial).toBe("conditional");
    expect(p.license.webfont).toBe("separate");
    expect(p.license.redistribution).toBe("no");
    expect(p.priceFrom).toBe(99000);
  });
```

- [ ] **Step 9: 전체 테스트 + 빌드 통과 확인**

Run: `npx vitest run lib/license.test.ts lib/data.test.ts`
Expected: PASS.
Run: `npm run build`
Expected: 빌드 성공(assertDataIntegrity가 신규 검증 포함해 통과).

- [ ] **Step 10: 커밋**

```bash
cd apps/web
git add types/font.ts lib/license.ts lib/license.test.ts lib/data.ts lib/data.test.ts data/fonts.ts
git commit -m "feat(fonts): 라이선스 데이터 모델 확장 + 파생 로직(라벨/상태/판매처 호스트)"
```

---

## Task 0.2: 공통 크롬(Header/Footer) 디자인 대조

Header는 이미 그린 A 워드마크/서브타이틀/6개 네비/테마-검색을 갖춰 디자인 톤에 근접. 이 태스크는 시각 대조 후 필요한 미세 조정만 한다(과잉 변경 금지).

**Files:**
- Modify(필요 시): `apps/web/components/Header.module.css`, `apps/web/components/Footer.tsx`(+css)

- [ ] **Step 1: 개발 서버 기동 후 헤더/푸터 캡처**

Run: `cd apps/web && npm run dev` (백그라운드). 브라우저로 `http://localhost:3000/` 헤더/푸터를 데스크톱-모바일-다크 3종 캡처.

- [ ] **Step 2: 디자인 프레임 캡처**

디자인 HTML(`localhost:63342`의 화면 세트)에서 헤더/푸터 영역을 같은 뷰포트로 캡처.

- [ ] **Step 3: Global Constraints 배점으로 채점**

로고 형태-위치, 헤더 높이, 좌우 패딩, 우측 액션 정렬/간격만 채점(네비 항목 수/라벨 제외). 90 미만인 항목만 기록.

- [ ] **Step 4: 90 미만 항목만 CSS 조정**

간격/높이/폰트 크기 등 토큰 변수 범위에서 조정. 구조 변경 금지. 90 이상이면 변경 없이 통과 처리.

- [ ] **Step 5: 재캡처로 90 이상 확인 후 커밋(변경 있을 때만)**

```bash
cd apps/web
git add components/Header.module.css components/Footer.tsx components/Footer.module.css
git commit -m "fix(chrome): 헤더/푸터 간격-정렬 디자인 톤 정합"
```
변경이 없으면 커밋 생략하고 다음 태스크로.

---

## Task 1.1: Breadcrumb 컴포넌트

**Files:**
- Create: `apps/web/components/Breadcrumb.tsx`, `apps/web/components/Breadcrumb.module.css`, `apps/web/components/Breadcrumb.test.tsx`

**Interfaces:**
- Produces: `Breadcrumb({ items }: { items: BreadcrumbItem[] })`, `type BreadcrumbItem = { label: string; href?: string }`. 마지막 항목은 현재 위치(링크 없음). 구분자 `›`.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/components/Breadcrumb.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Breadcrumb } from "@/components/Breadcrumb";

describe("Breadcrumb", () => {
  it("항목 라벨을 모두 렌더한다", () => {
    render(<Breadcrumb items={[{ label: "폰트", href: "/fonts" }, { label: "명조" }, { label: "나눔명조" }]} />);
    expect(screen.getByText("폰트")).toBeInTheDocument();
    expect(screen.getByText("명조")).toBeInTheDocument();
    expect(screen.getByText("나눔명조")).toBeInTheDocument();
  });
  it("href 있는 항목만 링크로 렌더한다", () => {
    render(<Breadcrumb items={[{ label: "폰트", href: "/fonts" }, { label: "나눔명조" }]} />);
    expect(screen.getByRole("link", { name: "폰트" })).toHaveAttribute("href", "/fonts");
    expect(screen.queryByRole("link", { name: "나눔명조" })).toBeNull();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run components/Breadcrumb.test.tsx`
Expected: FAIL — import 실패.

- [ ] **Step 3: 구현**

Create `apps/web/components/Breadcrumb.tsx`:

```tsx
import Link from "next/link";
import styles from "./Breadcrumb.module.css";

/** 브레드크럼 항목. 마지막 항목은 href 없이 현재 위치로 표시 */
export type BreadcrumbItem = { label: string; href?: string };

/** 상단 경로 표시. 구분자는 › */
export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className={styles.wrap} aria-label="경로">
      {items.map((item, i) => (
        <span key={i} className={styles.item}>
          {item.href ? (
            <Link href={item.href} className={styles.link}>{item.label}</Link>
          ) : (
            <span className={styles.current}>{item.label}</span>
          )}
          {i < items.length - 1 && <span className={styles.sep} aria-hidden>›</span>}
        </span>
      ))}
    </nav>
  );
}
```

Create `apps/web/components/Breadcrumb.module.css`:

```css
.wrap { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: 13px; color: var(--sub); }
.item { display: inline-flex; align-items: center; gap: 6px; }
.link { color: var(--sub); }
.link:hover { color: var(--ink); }
.current { color: var(--sub); }
.sep { color: var(--sub-2); }
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run components/Breadcrumb.test.tsx`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
cd apps/web
git add components/Breadcrumb.tsx components/Breadcrumb.module.css components/Breadcrumb.test.tsx
git commit -m "feat(detail): Breadcrumb 컴포넌트"
```

---

## Task 1.2: SpecimenBox 컴포넌트 (견본 박스 + 무료 편집 입력)

**Files:**
- Create: `apps/web/components/SpecimenBox.tsx`, `apps/web/components/SpecimenBox.module.css`, `apps/web/components/SpecimenBox.test.tsx`

**Interfaces:**
- Produces: `SpecimenBox({ fontFamily, editable, initialText?, caption? }: { fontFamily: string; editable: boolean; initialText?: string; caption?: string })`. 클라이언트 컴포넌트. `editable`이면 입력창이 대형 견본을 실시간 갱신. `caption`은 견본 아래 회색 주석(유료 대체 견본 안내).
- 기본 견본 문구: `"다람쥐 헌 쳇바퀴에 타고파"`.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/components/SpecimenBox.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SpecimenBox } from "@/components/SpecimenBox";

describe("SpecimenBox", () => {
  it("기본 견본 문구를 렌더한다", () => {
    render(<SpecimenBox fontFamily="var(--font-x)" editable={false} />);
    expect(screen.getByText("다람쥐 헌 쳇바퀴에 타고파")).toBeInTheDocument();
  });
  it("editable이면 입력이 견본을 갱신한다", () => {
    render(<SpecimenBox fontFamily="var(--font-x)" editable initialText="가나다" />);
    const input = screen.getByLabelText("미리보기 입력");
    fireEvent.change(input, { target: { value: "라마바" } });
    expect(screen.getByText("라마바")).toBeInTheDocument();
  });
  it("editable=false이면 입력이 없다", () => {
    render(<SpecimenBox fontFamily="var(--font-x)" editable={false} />);
    expect(screen.queryByLabelText("미리보기 입력")).toBeNull();
  });
  it("caption을 렌더한다", () => {
    render(<SpecimenBox fontFamily="var(--font-x)" editable={false} caption="대체 견본입니다" />);
    expect(screen.getByText("대체 견본입니다")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run components/SpecimenBox.test.tsx`
Expected: FAIL — import 실패.

- [ ] **Step 3: 구현**

Create `apps/web/components/SpecimenBox.tsx`:

```tsx
"use client";
import { useState } from "react";
import styles from "./SpecimenBox.module.css";

const DEFAULT_TEXT = "다람쥐 헌 쳇바퀴에 타고파";

/**
 * 견본 박스. 대형 견본 텍스트를 fontFamily로 렌더한다.
 * editable=true면 하단 입력이 견본을 실시간 갱신(무료 폰트).
 * caption이 있으면 견본 아래 회색 주석 표시(유료 대체 견본 안내).
 */
export function SpecimenBox({
  fontFamily,
  editable,
  initialText,
  caption,
}: {
  fontFamily: string;
  editable: boolean;
  initialText?: string;
  caption?: string;
}) {
  const [text, setText] = useState(initialText ?? DEFAULT_TEXT);
  return (
    <div className={styles.box}>
      <div className={styles.sample} style={{ fontFamily }}>{text || " "}</div>
      {caption && <p className={styles.caption}>{caption}</p>}
      {editable && (
        <input
          className={styles.input}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="미리볼 문장을 입력하세요"
          aria-label="미리보기 입력"
        />
      )}
    </div>
  );
}
```

Create `apps/web/components/SpecimenBox.module.css`:

```css
.box { border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); padding: 40px 34px; display: flex; flex-direction: column; gap: 18px; }
.sample { font-size: 56px; font-weight: 700; line-height: 1.25; color: var(--ink); word-break: keep-all; }
.caption { font-size: 12.5px; color: var(--sub); margin: 0; }
.input { height: 46px; border: 1px solid var(--border); border-radius: var(--radius-btn); background: var(--bg); padding: 0 14px; font-size: 15px; color: var(--ink); }
.input:focus { outline: none; border-color: var(--point); }
@media (max-width: 620px) { .sample { font-size: 34px; } .box { padding: 24px 18px; } }
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run components/SpecimenBox.test.tsx`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
cd apps/web
git add components/SpecimenBox.tsx components/SpecimenBox.module.css components/SpecimenBox.test.tsx
git commit -m "feat(detail): SpecimenBox 견본 박스(편집형/대체 견본 캡션)"
```

---

## Task 1.3: LicenseSummaryCard 컴포넌트

**Files:**
- Create: `apps/web/components/LicenseSummaryCard.tsx`, `apps/web/components/LicenseSummaryCard.module.css`, `apps/web/components/LicenseSummaryCard.test.tsx`

**Interfaces:**
- Consumes: `license.ts`의 라벨/상태 함수, `deriveSellerHost`.
- Produces: `LicenseSummaryCard({ font }: { font: Font })`. 폰트 하나를 받아 라이선스 요약 카드 전체(제목/서브/3행/안내/CTA/판매처)를 렌더한다.
- CTA: 유료면 `구매하러 가기` + `₩{priceFrom.toLocaleString()}~`(priceFrom 없으면 가격 생략, 문구 `구매 페이지로 이동`), 무료면 `공식 페이지에서 내려받기`.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/components/LicenseSummaryCard.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LicenseSummaryCard } from "@/components/LicenseSummaryCard";
import { getFontBySlug } from "@/lib/data";

describe("LicenseSummaryCard", () => {
  it("유료 폰트: 3개 라이선스 행 + 가격 CTA + 판매처", () => {
    const paid = getFontBySlug("sandoll-gothic-neo")!;
    render(<LicenseSummaryCard font={paid} />);
    expect(screen.getByText("라이선스 요약")).toBeInTheDocument();
    expect(screen.getByText("상업적 사용")).toBeInTheDocument();
    expect(screen.getByText("구매 시")).toBeInTheDocument();
    expect(screen.getByText("웹폰트")).toBeInTheDocument();
    expect(screen.getByText("별도 구매")).toBeInTheDocument();
    expect(screen.getByText("재배포")).toBeInTheDocument();
    expect(screen.getByText(/구매하러 가기/)).toBeInTheDocument();
    expect(screen.getByText(/₩99,000~/)).toBeInTheDocument();
    expect(screen.getByText(/sandoll\.co\.kr/)).toBeInTheDocument();
  });
  it("무료 폰트: 내려받기 CTA", () => {
    const free = getFontBySlug("nanum-myeongjo")!;
    render(<LicenseSummaryCard font={free} />);
    expect(screen.getByText("공식 페이지에서 내려받기")).toBeInTheDocument();
    expect(screen.getAllByText("가능").length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run components/LicenseSummaryCard.test.tsx`
Expected: FAIL — import 실패.

- [ ] **Step 3: 구현**

Create `apps/web/components/LicenseSummaryCard.tsx`:

```tsx
import type { Font } from "@/types/font";
import {
  commercialLabel, webfontLabel, redistributionLabel,
  commercialState, webfontState, redistributionState,
  deriveSellerHost, type LicenseState,
} from "@/lib/license";
import styles from "./LicenseSummaryCard.module.css";

const STATE_ICON: Record<LicenseState, string> = { ok: "✓", cond: "!", no: "✕" };

/** 라이선스 요약 사이드바 카드. 폰트 하나의 라이선스/구매 정보를 렌더 */
export function LicenseSummaryCard({ font }: { font: Font }) {
  const isPaid = font.tier === "paid";
  const host = deriveSellerHost(font.officialUrl);
  const rows: { label: string; value: string; state: LicenseState }[] = [
    { label: "상업적 사용", value: commercialLabel(font.license.commercial), state: commercialState(font.license.commercial) },
    { label: "웹폰트", value: webfontLabel(font.license.webfont), state: webfontState(font.license.webfont) },
    { label: "재배포", value: redistributionLabel(font.license.redistribution), state: redistributionState(font.license.redistribution) },
  ];
  const notice = isPaid
    ? "조건은 판매처 정책에 따릅니다. 구매 전 라이선스 범위를 확인하세요."
    : "무료 라이선스라도 사용 전 조건을 확인하세요.";
  const ctaLabel = isPaid ? "구매하러 가기" : "공식 페이지에서 내려받기";
  const price = isPaid && font.priceFrom ? `₩${font.priceFrom.toLocaleString()}~` : null;

  return (
    <aside className={styles.card}>
      <h2 className={styles.title}>라이선스 요약</h2>
      <p className={styles.sub}>{font.license.type} {String.fromCharCode(183)} 확인일 {font.license.verifiedAt}</p>
      <ul className={styles.rows}>
        {rows.map((r) => (
          <li key={r.label} className={styles.row}>
            <span className={`${styles.icon} ${styles[r.state]}`} aria-hidden>{STATE_ICON[r.state]}</span>
            <span className={styles.rowLabel}>{r.label}</span>
            <span className={`${styles.rowValue} ${styles[r.state]}`}>{r.value}</span>
          </li>
        ))}
      </ul>
      <p className={styles.notice}>{notice}</p>
      <a className={styles.cta} href={font.officialUrl} target="_blank" rel="noreferrer">
        <span>{ctaLabel}</span>
        {price && <span className={styles.price}>{price}</span>}
      </a>
      {host && <p className={styles.seller}>이동 → {host}</p>}
    </aside>
  );
}
```

Create `apps/web/components/LicenseSummaryCard.module.css`:

```css
.card { border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); padding: 24px; display: flex; flex-direction: column; gap: 12px; }
.title { font-size: 15px; font-weight: 700; color: var(--ink); margin: 0; }
.sub { font-size: 11.5px; color: var(--sub); margin: 0 0 4px; }
.rows { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.row { display: flex; align-items: center; gap: 10px; font-size: 13.5px; }
.icon { width: 20px; height: 20px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; }
.rowLabel { color: var(--ink); }
.rowValue { margin-left: auto; font-weight: 600; }
.ok { color: var(--point); }
.cond { color: var(--warn); }
.no { color: var(--down); }
.icon.ok { background: var(--point-weak); }
.icon.cond { background: rgba(180, 134, 60, .14); }
.icon.no { background: rgba(180, 86, 75, .12); }
.notice { font-size: 12px; color: var(--sub); background: var(--surface-2); border-radius: 8px; padding: 12px 14px; margin: 4px 0; }
.cta { display: flex; align-items: center; justify-content: space-between; gap: 8px; background: var(--point); color: var(--on-point); border-radius: var(--radius-btn); padding: 14px 18px; font-size: 14px; font-weight: 600; }
.price { font-weight: 700; }
.seller { text-align: center; font-size: 11.5px; color: var(--sub); margin: 0; }
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run components/LicenseSummaryCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
cd apps/web
git add components/LicenseSummaryCard.tsx components/LicenseSummaryCard.module.css components/LicenseSummaryCard.test.tsx
git commit -m "feat(detail): LicenseSummaryCard 라이선스 요약 카드"
```

---

## Task 1.4: AlternativesCard 컴포넌트

**Files:**
- Create: `apps/web/components/AlternativesCard.tsx`, `apps/web/components/AlternativesCard.module.css`, `apps/web/components/AlternativesCard.test.tsx`

**Interfaces:**
- Consumes: `fontKeyToVar`(lib/fonts), `Font` 타입.
- Produces: `AlternativesCard({ category, items }: { category: string; items: Font[] })`. items가 비어 있으면 `null` 반환(렌더 안 함). 제목은 `비슷한 무료 대안 {items.length}개`, 서브는 `분위기가 가까운 무료 {category}입니다`.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/components/AlternativesCard.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AlternativesCard } from "@/components/AlternativesCard";
import { getFontBySlug, resolveFreeAlternatives } from "@/lib/data";

describe("AlternativesCard", () => {
  it("대안 개수를 제목에 반영한다", () => {
    const paid = getFontBySlug("sandoll-gothic-neo")!;
    const alts = resolveFreeAlternatives(paid);
    render(<AlternativesCard category="고딕" items={alts} />);
    expect(screen.getByText(`비슷한 무료 대안 ${alts.length}개`)).toBeInTheDocument();
    expect(screen.getByText("분위기가 가까운 무료 고딕입니다")).toBeInTheDocument();
    expect(screen.getAllByText("무료").length).toBe(alts.length);
  });
  it("items가 비면 렌더하지 않는다", () => {
    const { container } = render(<AlternativesCard category="명조" items={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run components/AlternativesCard.test.tsx`
Expected: FAIL — import 실패.

- [ ] **Step 3: 구현**

Create `apps/web/components/AlternativesCard.tsx`:

```tsx
import Link from "next/link";
import type { Font } from "@/types/font";
import { fontKeyToVar } from "@/lib/fonts";
import styles from "./AlternativesCard.module.css";

/** 유료 폰트의 비슷한 무료 대안 카드. items가 비면 렌더하지 않음 */
export function AlternativesCard({ category, items }: { category: string; items: Font[] }) {
  if (items.length === 0) return null;
  return (
    <aside className={styles.card}>
      <h2 className={styles.title}>비슷한 무료 대안 {items.length}개</h2>
      <p className={styles.sub}>분위기가 가까운 무료 {category}입니다</p>
      <ul className={styles.list}>
        {items.map((f) => (
          <li key={f.slug} className={styles.item}>
            <Link href={`/fonts/${f.slug}`} className={styles.name} style={{ fontFamily: fontKeyToVar[f.fontKey] }}>
              {f.nameKo}
            </Link>
            <span className={styles.badge}>무료</span>
          </li>
        ))}
      </ul>
    </aside>
  );
}
```

Create `apps/web/components/AlternativesCard.module.css`:

```css
.card { border: 1px solid var(--border); border-radius: var(--radius-card); background: var(--surface); padding: 24px; display: flex; flex-direction: column; gap: 6px; }
.title { font-size: 15px; font-weight: 700; color: var(--ink); margin: 0; }
.sub { font-size: 12px; color: var(--sub); margin: 0 0 10px; }
.list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.item { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 12px 0; border-top: 1px solid var(--border); }
.item:first-child { border-top: none; }
.name { font-size: 20px; font-weight: 600; color: var(--ink); }
.badge { font-size: 11px; font-weight: 600; color: var(--sub); background: var(--surface-2); border-radius: var(--radius-pill); padding: 3px 10px; }
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run components/AlternativesCard.test.tsx`
Expected: PASS.

- [ ] **Step 5: 커밋**

```bash
cd apps/web
git add components/AlternativesCard.tsx components/AlternativesCard.module.css components/AlternativesCard.test.tsx
git commit -m "feat(detail): AlternativesCard 무료 대안 카드(개수 반영/0개 숨김)"
```

---

## Task 1.5: 폰트 상세 페이지 2단 재구성

**Files:**
- Modify: `apps/web/app/fonts/[slug]/page.tsx`
- Modify: `apps/web/app/fonts/[slug]/page.module.css`
- Create: `apps/web/app/fonts/[slug]/page.test.tsx`

**Interfaces:**
- Consumes: Breadcrumb, SpecimenBox, LicenseSummaryCard, AlternativesCard, TierChip, `getFontBySlug`, `getAllSlugs`, `resolveFreeAlternatives`, `fontKeyToVar`.

- [ ] **Step 1: 통합 실패 테스트 작성**

Create `apps/web/app/fonts/[slug]/page.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import FontDetail from "@/app/fonts/[slug]/page";

async function renderDetail(slug: string) {
  const ui = await FontDetail({ params: Promise.resolve({ slug }) });
  render(ui);
}

describe("폰트 상세 페이지", () => {
  it("무료 폰트: 브레드크럼/제목/견본/라이선스 카드, 대안 카드는 없음", async () => {
    await renderDetail("nanum-myeongjo");
    expect(screen.getByText("나눔명조")).toBeInTheDocument();
    expect(screen.getByText("라이선스 요약")).toBeInTheDocument();
    expect(screen.getByText("공식 페이지에서 내려받기")).toBeInTheDocument();
    expect(screen.getByLabelText("미리보기 입력")).toBeInTheDocument();
    expect(screen.queryByText(/비슷한 무료 대안/)).toBeNull();
  });
  it("유료 폰트: 대체 견본 캡션 + 대안 카드 + 구매 CTA, 입력 없음", async () => {
    await renderDetail("sandoll-gothic-neo");
    expect(screen.getByText("산돌 고딕 Neo")).toBeInTheDocument();
    expect(screen.getByText(/구매하러 가기/)).toBeInTheDocument();
    expect(screen.getByText(/비슷한 무료 대안/)).toBeInTheDocument();
    expect(screen.queryByLabelText("미리보기 입력")).toBeNull();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run "app/fonts/[slug]/page.test.tsx"`
Expected: FAIL — 현재 페이지에 "라이선스 요약"/"비슷한 무료 대안 N개" 모듈 없음.

- [ ] **Step 3: `page.tsx` 재구성**

`apps/web/app/fonts/[slug]/page.tsx` 전체를 아래로 교체한다:

```tsx
import { notFound } from "next/navigation";
import { getFontBySlug, getAllSlugs, resolveFreeAlternatives } from "@/lib/data";
import { fontKeyToVar } from "@/lib/fonts";
import { Breadcrumb } from "@/components/Breadcrumb";
import { SpecimenBox } from "@/components/SpecimenBox";
import { LicenseSummaryCard } from "@/components/LicenseSummaryCard";
import { AlternativesCard } from "@/components/AlternativesCard";
import { TierChip } from "@/components/TierChip";
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
  const alternatives = isPaid ? resolveFreeAlternatives(font) : [];
  const caption = isPaid
    ? "견본은 유사 서체로 대체 표시 — 실제 서체는 공식 페이지에서 확인하세요."
    : undefined;

  return (
    <main className={styles.wrap}>
      <Breadcrumb
        items={[
          { label: "폰트", href: "/fonts" },
          { label: font.category, href: `/fonts?category=${encodeURIComponent(font.category)}` },
          { label: font.nameKo },
        ]}
      />
      <div className={styles.grid}>
        <div className={styles.main}>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>{font.nameKo}</h1>
            <TierChip tier={font.tier} />
          </div>
          <p className={styles.meta}>
            {font.foundry} {String.fromCharCode(183)} {font.availableWeights.length}가지 굵기 {String.fromCharCode(183)} 이동 {font.moves.toLocaleString()}회
          </p>
          <SpecimenBox fontFamily={family} editable={!isPaid} caption={caption} />
        </div>
        <div className={styles.side}>
          <LicenseSummaryCard font={font} />
          <AlternativesCard category={font.category} items={alternatives} />
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 4: `page.module.css` 2단 레이아웃으로 교체**

`apps/web/app/fonts/[slug]/page.module.css` 전체를 아래로 교체한다:

```css
.wrap { max-width: 1180px; margin: 0 auto; width: 100%; padding: var(--pad-page); display: flex; flex-direction: column; gap: 22px; }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 360px; gap: 40px; align-items: start; }
.main { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.titleRow { display: flex; align-items: center; gap: 12px; }
.title { font-size: 42px; font-weight: 800; letter-spacing: -0.02em; color: var(--ink); margin: 0; }
.meta { font-size: 13.5px; color: var(--sub); margin: 0 0 8px; }
.side { display: flex; flex-direction: column; gap: 18px; position: sticky; top: 88px; }
@media (max-width: 900px) {
  .grid { grid-template-columns: 1fr; gap: 24px; }
  .side { position: static; }
  .title { font-size: 32px; }
}
```

- [ ] **Step 5: 통과 확인**

Run: `npx vitest run "app/fonts/[slug]/page.test.tsx"`
Expected: PASS (무료/유료 두 케이스).

- [ ] **Step 6: 전체 테스트 + 빌드**

Run: `npm run test`
Expected: PASS(기존 포함 전체).
Run: `npm run build`
Expected: 빌드 성공.

- [ ] **Step 7: 커밋**

```bash
cd apps/web
git add "app/fonts/[slug]/page.tsx" "app/fonts/[slug]/page.module.css" "app/fonts/[slug]/page.test.tsx"
git commit -m "feat(detail): 폰트 상세 2단 레이아웃 + 라이선스/대안 사이드바 조립"
```

---

## Task 1.6: 시각 정합 검증 루프 (무료/유료, 데스크톱-모바일-다크)

디자인 프레임 1g/6a와 실제 렌더를 병렬 캡처해 Global Constraints 배점으로 채점하고 90 이상까지 CSS를 조정한다.

**Files:**
- Modify(필요 시): `apps/web/components/*.module.css`, `apps/web/app/fonts/[slug]/page.module.css`

- [ ] **Step 1: 개발 서버 기동**

Run: `cd apps/web && npm run dev` (백그라운드, 3000).

- [ ] **Step 2: 실제 렌더 캡처**

`/e2e` 스킬 또는 Playwright로 아래를 캡처(뷰포트별):
- 무료: `http://localhost:3000/fonts/nanum-myeongjo` — 1280px, 375px, 1280px+다크(`data-theme="dark"`).
- 유료: `http://localhost:3000/fonts/sandoll-gothic-neo` — 동일 3종.

- [ ] **Step 3: 디자인 프레임 캡처**

디자인 HTML(`localhost:63342`)에서 1g(무료)-6a(유료) 프레임을 같은 뷰포트로 캡처.

- [ ] **Step 4: 배점 채점**

각 화면을 모듈 존재 40 / 레이아웃 30 / 간격-타이포 20 / 텍스트 10으로 채점. 90 미만 항목을 diff 리스트로 기록.

- [ ] **Step 5: 90 미만 항목 CSS 조정 후 재캡처**

토큰 변수 범위에서 간격/크기/모서리 조정. 구조/모듈은 이미 확정이므로 미세 조정 위주. 6종(무료-유료 × 데/모/다) 모두 90 이상 될 때까지 반복.

- [ ] **Step 6: 최종 캡처 저장 + 커밋**

캡처를 `docs/review/`에 저장(예: `slice1-free-desktop.png` 등). CSS 변경이 있으면:

```bash
cd apps/web
git add app/fonts/[slug]/page.module.css components/SpecimenBox.module.css components/LicenseSummaryCard.module.css components/AlternativesCard.module.css components/Breadcrumb.module.css
git commit -m "fix(detail): 시각 정합 미세 조정(배점 90 달성)"
```

---

## Self-Review (계획 작성자 점검)

- **스펙 커버리지**: 섹션 3(데이터 모델)→Task 0.1, 섹션 3.1(예외 정책)→Task 0.1(host 파생/무료 대안 0개 숨김은 1.4/1.3에서 구현)/priceFrom 없는 유료→1.3 CTA 분기, 섹션 4(상세 모듈)→1.1~1.5, 섹션 4.1(props)→각 컴포넌트 태스크, 섹션 4.2(모바일)→1.5 CSS + SpecimenBox 반응형, 섹션 2.2(배점)→1.6, 섹션 6(크롬)→0.2, 섹션 7(Header 예외)→0.2. 커버 확인.
- **미커버 주의**: 모바일 "미리보기 입력 하단 고정(fixed bottom)"은 SpecimenBox 반응형에서 일반 흐름으로만 처리(고정 미구현). 디자인 4b의 하단 고정은 배점상 레이아웃 세부라 1.6에서 필요 시 추가. → 1.6 Step 5에서 판정 후 결정(현재 계획은 sticky 사이드바 해제까지만 명시).
- **타입 일관성**: `LicenseState`(license.ts) ↔ LicenseSummaryCard `styles[r.state]` 일치. `deriveSellerHost` 반환 `string|null` ↔ 카드 `host &&` 처리 일치. `resolveFreeAlternatives`→`Font[]` ↔ AlternativesCard `items: Font[]` 일치.
- **플레이스홀더**: 없음(모든 스텝에 실제 코드/명령/기대 출력 포함).

---

## 다음 계획 (이 계획 범위 밖)

슬라이스 2~8(홈/목록/트렌드/비교/캔버스/컬렉션/등록)은 각 착수 시 본 계획과 동일 형식의 별도 계획으로 상세화한다. 스펙 섹션 5 참조.
