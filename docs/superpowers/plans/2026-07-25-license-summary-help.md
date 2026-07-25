# License Summary Help Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 라이선스 요약의 각 항목에 마우스, 키보드, 모바일로 확인 가능한 짧은 도움말을 추가한다.

**Architecture:** `LicenseSummaryCard`의 행 데이터에 도움말 키와 문구를 함께 두고, 네이티브 버튼과 `aria-describedby`로 설명을 연결한다. 표시 동작은 CSS `:hover`와 `:focus`로 처리해 클라이언트 상태와 새 의존성을 만들지 않는다.

**Tech Stack:** React 19, Next.js 16, CSS Modules, Vitest, Testing Library

## Global Constraints

- 도움말은 허용 여부를 단정하지 않고 항목의 뜻만 설명한다.
- 마우스 hover, 키보드 focus, 모바일 tap에서 모두 표시한다.
- 아이콘 전용 버튼에는 접근 가능한 이름을 제공한다.
- 기존 라이선스 값 계산과 데이터 모델은 바꾸지 않는다.
- 새 UI 라이브러리를 추가하지 않는다.

---

### Task 1: 접근 가능한 라이선스 도움말

**Files:**
- Modify: `apps/web/components/LicenseSummaryCard.test.tsx`
- Modify: `apps/web/components/LicenseSummaryCard.tsx`
- Modify: `apps/web/components/LicenseSummaryCard.module.css`

**Interfaces:**
- Consumes: 기존 `Font`, `LicenseState`, 라이선스 라벨·상태 변환 함수
- Produces: 각 라이선스 행의 `help` 문구와 `helpKey`, 접근 가능한 도움말 버튼·툴팁

- [ ] **Step 1: 실패하는 컴포넌트 테스트 작성**

`LicenseSummaryCard.test.tsx`의 verified 폰트 테스트에 다음 동작 검증을 추가한다.

```tsx
const commercialHelp = screen.getByRole("button", { name: "상업적 사용 설명" });
const descriptionId = commercialHelp.getAttribute("aria-describedby");
expect(descriptionId).toBeTruthy();
expect(document.getElementById(descriptionId!)).toHaveTextContent(
  "광고·상품·웹사이트·영상 등 상업 활동의 결과물에 폰트를 사용할 수 있는지 뜻해요.",
);

expect(screen.getByRole("button", { name: "폰트 판매 설명" })).toHaveAttribute(
  "aria-describedby",
);
```

- [ ] **Step 2: 테스트가 기능 부재로 실패하는지 확인**

Run: `pnpm --filter web test -- components/LicenseSummaryCard.test.tsx`

Expected: `상업적 사용 설명` 버튼을 찾지 못해 실패

- [ ] **Step 3: 최소 구현 작성**

`LicenseSummaryCard.tsx`에 확정 문구를 추가하고 행 타입을 다음 형태로 확장한다.

```tsx
type LicenseHelpKey =
  | "commercial"
  | "modify"
  | "redistribute"
  | "embedding"
  | "font-sale"
  | "attribution"
  | "webfont";

type LicenseRow = {
  label: string;
  value: string;
  state: LicenseState;
  helpKey: LicenseHelpKey;
  help: string;
};
```

각 행의 레이블 영역은 네이티브 버튼과 툴팁을 포함하게 한다.

```tsx
<span className={styles.labelHelp}>
  <span className={styles.rowLabel}>{r.label}</span>
  <button
    type="button"
    className={styles.helpTrigger}
    aria-label={`${r.label} 설명`}
    aria-describedby={helpId}
  >
    i
  </button>
  <span id={helpId} role="tooltip" className={styles.tooltip}>
    {r.help}
  </span>
</span>
```

`helpId`는 `font.slug`와 `helpKey`로 만든다. CSS는 기본 상태에서 툴팁을 숨기고 `.labelHelp:hover` 또는 `.helpTrigger:focus`일 때 표시한다. `:focus-visible`에는 눈에 보이는 외곽선을 제공한다.

- [ ] **Step 4: 컴포넌트 테스트 통과 확인**

Run: `pnpm --filter web test -- components/LicenseSummaryCard.test.tsx`

Expected: 4 tests passed

- [ ] **Step 5: 전체 웹 검증**

Run: `pnpm --filter web test`

Expected: 모든 테스트 통과

Run: `pnpm --filter web lint`

Expected: 오류 0개

Run: `pnpm --filter web build`

Expected: 종료 코드 0

### Task 2: 실제 상호작용 검증

**Files:**
- Modify: 없음

**Interfaces:**
- Consumes: 로컬 상세 페이지의 라이선스 요약 카드
- Produces: hover, focus, 모바일 tap 동작의 브라우저 검증 결과

- [ ] **Step 1: 로컬 웹 서버 실행**

Run: `pnpm --filter web dev`

Expected: 로컬 주소가 출력되고 서버가 요청을 받음

- [ ] **Step 2: 데스크톱 마우스와 키보드 검증**

상세 페이지에서 `상업적 사용` 레이블에 마우스를 올려 설명이 보이는지 확인한다. Tab 키로 `상업적 사용 설명` 버튼에 초점을 옮겨 같은 설명과 초점 표시가 보이는지 확인한다.

- [ ] **Step 3: 모바일 크기 터치 검증**

브라우저 화면을 모바일 크기로 바꾸고 정보 버튼을 눌러 설명이 카드 밖으로 잘리지 않고 표시되는지 확인한다.

- [ ] **Step 4: 변경 범위 확인**

Run: `git diff --check`

Expected: 출력 없음, 종료 코드 0

Run: `git status --short`

Expected: 설계·계획 문서와 `LicenseSummaryCard` 관련 파일만 변경
