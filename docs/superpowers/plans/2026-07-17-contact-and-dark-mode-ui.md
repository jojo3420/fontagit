# 문의 페이지 및 다크모드 UI 개선 구현 계획

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** 문의 페이지의 깨진 이메일 표시를 개선하고, 애드블록 안내와 Playground 글자 지원 검사에 라이트·다크모드를 올바르게 적용한다.

**Architecture:** 기존 React 구조와 전역 테마 변수는 유지한다. 문의 페이지는 작은 재사용 이메일 링크를 페이지 내부에 정의한다. 다크모드 문제는 존재하지 않는 CSS 변수를 FontAgit 공통 변수로 교체하고, 애드블록만 화면 우측 하단 고정 알림으로 배치한다.

**Tech Stack:** Next.js 16, React 19, TypeScript, CSS Modules, pnpm

---

## 사전 원칙

- 단순 UI 변경이므로 새 단위 테스트는 작성하지 않는다.
- 현재 작업공간에 사용자 변경이 있으므로 격리된 Git worktree에서 작업한다.
- 대상 파일 외 변경은 커밋하지 않는다.
- 구현 전 `improve-ui` 절차로 가장 작은 UI 규칙을 불러와 적용한다.

### Task 1: 격리 작업공간 준비

**Files:**
- No source changes

**Step 1: 현재 작업공간 형태 확인**

Run:

```bash
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
git status --short --branch
```

**Step 2: `.worktrees` 사용 가능 여부와 ignore 확인**

Run:

```bash
ls -d .worktrees worktrees 2>/dev/null
git check-ignore -q .worktrees
```

Expected: `.worktrees`가 없더라도 ignore 규칙이 확인된다. 확인되지 않으면 사용자 작업과 섞이지 않는 외부 임시 경로를 사용한다.

**Step 3: 새 브랜치와 worktree 생성**

Run:

```bash
git worktree add .worktrees/contact-dark-ui -b fix/contact-dark-ui
```

**Step 4: 의존성과 기준 상태 확인**

Run in worktree:

```bash
pnpm install --frozen-lockfile
pnpm --filter web lint
pnpm --filter web test
```

Expected: 기존 린트와 테스트 통과. 기존 실패가 있으면 구현 전에 중단하고 원인을 보고한다.

### Task 2: UI 규칙 선택

**Files:**
- No source changes

**Step 1: UI 도구 시작**

Run:

```bash
npx ui-skills start
npx ui-skills categories
```

**Step 2: 현재 작업에 맞는 최소 스킬 검색**

Run:

```bash
npx ui-skills list --category visual
```

목록에 따라 다크모드·접근성·반응형 수정에 맞는 스킬 하나만 선택하고 `npx ui-skills get <skill>`로 불러온다. 출력된 MUST/SHOULD/NEVER를 아래 구현에 반영한다.

### Task 3: 문의 이메일 카드 구현

**Files:**
- Modify: `apps/web/app/contact/page.tsx`
- Modify: `apps/web/app/contact/page.module.css`

**Step 1: 페이지 내부 이메일 링크 컴포넌트 추가**

`page.tsx`에 서버 컴포넌트로 동작하는 작은 표현 컴포넌트를 추가한다.

```tsx
function EmailLink({ subject }: { subject: string }) {
  const href = `mailto:contact@fontagit.com?subject=${encodeURIComponent(subject)}`;

  return (
    <a className={styles.emailLink} href={href}>
      <svg aria-hidden="true" ...>...</svg>
      <span>contact@fontagit.com</span>
    </a>
  );
}
```

**Step 2: 세 TODO와 이모지를 링크로 교체**

- 일반 문의: `[일반 문의] FontAgit`
- 저작권 신고: `[저작권 신고] FontAgit`
- 피드백: `[피드백] FontAgit`

세 영역에 `EmailLink`를 넣고 기존 `📧`와 TODO 주석을 제거한다.

**Step 3: 카드와 링크 스타일 추가**

- 문의 영역: `--surface`, `--border`, `--ink`, `--sub` 사용
- 이메일 링크: 전체 클릭 가능, `--surface-2` 배경, `--point` 아이콘·초점 사용
- `:focus-visible`로 키보드 초점 표시
- 모바일에서 링크 너비 100%, 주소는 `overflow-wrap: anywhere`
- 존재하지 않는 `--bg-secondary` 사용 제거

**Step 4: 정적 검사**

Run:

```bash
rg -n "TODO|📧|contact@fontagit.com|mailto:" apps/web/app/contact
pnpm --filter web exec eslint app/contact/page.tsx
```

Expected: TODO와 이모지는 0건, 이메일 주소와 `mailto:`는 구현부에서 확인된다.

### Task 4: 애드블록 안내를 반응형 알림으로 변경

**Files:**
- Modify: `apps/web/components/AdBlock/AdBlockBanner.module.css`
- Modify only if needed: `apps/web/components/AdBlock/AdBlockBanner.tsx`

**Step 1: 배너 배치 수정**

`.banner`를 다음 원칙으로 바꾼다.

```css
.banner {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 50;
  width: min(420px, calc(100vw - 48px));
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--sub);
}
```

본문 흐름용 `margin`은 제거하고 그림자와 둥근 모서리를 적용한다.

**Step 2: 닫기 버튼 상태 수정**

- 기본 글자: `--sub`
- hover 배경: `--surface-2`
- hover 글자: `--ink`
- `:focus-visible` 테두리: `--point`
- `transition: all` 대신 실제로 변하는 속성만 지정

**Step 3: 모바일 위치 적용**

620px 이하에서 좌우 16px, 모바일 하단 메뉴와 안전 영역을 고려한 `bottom` 값을 사용한다.

**Step 4: 잘못된 변수 제거 확인**

Run:

```bash
rg -n "surface-secondary|border-secondary|text-secondary|surface-hover|text-primary|focus-ring" apps/web/components/AdBlock
```

Expected: 0건.

### Task 5: Playground 글자 지원 검사 다크모드 적용

**Files:**
- Modify: `apps/web/components/GlyphCheckerSection.module.css`
- Modify: `apps/web/components/GlyphChecker.module.css`

**Step 1: 기본 영역의 색상 변수 교체**

- 페이지 영역: `--surface`
- 내부 카드·입력·버튼: `--surface-2` 또는 `--surface`
- 테두리: `--border`
- 주요 글자: `--ink`
- 보조 글자: `--sub`, `--sub-2`
- 강조·초점: `--point`, `--point-weak`

**Step 2: 상태 색상 정의**

기존 전역 변수에 없는 성공·경고·오류 색은 CSS Module 안에서 라이트·다크모드에 모두 읽히는 값으로 명시한다. 경고 카드의 글자와 배경 대비를 함께 조정하고 현재 기호와 문구는 유지한다.

**Step 3: 상호작용 상태 정리**

- 선택창, 입력창, 버튼의 hover·focus-visible 상태를 공통 변수로 통일한다.
- disabled 상태도 다크모드에서 읽을 수 있게 한다.
- `transition: all`을 실제 변하는 속성으로 제한한다.

**Step 4: 잘못된 변수 제거 확인**

Run:

```bash
rg -n -- "--color-" apps/web/components/GlyphChecker.module.css apps/web/components/GlyphCheckerSection.module.css
```

Expected: 0건.

### Task 6: 브라우저와 품질 검증

**Files:**
- No new test files

**Step 1: 개발 서버 실행**

Run:

```bash
pnpm --filter web dev
```

**Step 2: 브라우저 직접 확인**

- `/contact`: 세 이메일 카드, 제목별 `mailto:`, 모바일 줄바꿈, 키보드 초점
- `/trends`: 라이트·다크 배너 색상, 우측 하단 위치, 닫기 버튼
- `/playground`: 글자 지원 검사 전체 영역, 선택창, 경고 카드의 라이트·다크 색상
- 모바일 폭: 배너가 하단 메뉴와 콘텐츠를 가리지 않는지 확인

**Step 3: 전체 정적 검증**

Run:

```bash
pnpm --filter web lint
pnpm --filter web test
pnpm --filter web build
git diff --check
git status --short
```

Expected: 모든 명령 통과, 대상 UI 파일과 계획·설계 문서 외 변경 없음.

### Task 7: 변경 검토와 커밋

**Files:**
- Review all changed target files

**Step 1: 변경 범위 확인**

Run:

```bash
git diff --stat
git diff -- apps/web/app/contact/page.tsx apps/web/app/contact/page.module.css apps/web/components/AdBlock/AdBlockBanner.module.css apps/web/components/GlyphCheckerSection.module.css apps/web/components/GlyphChecker.module.css
```

**Step 2: 대상 파일만 커밋**

Run:

```bash
git add apps/web/app/contact/page.tsx apps/web/app/contact/page.module.css apps/web/components/AdBlock/AdBlockBanner.module.css apps/web/components/GlyphCheckerSection.module.css apps/web/components/GlyphChecker.module.css
git commit -m "fix: 문의 및 다크모드 UI 개선"
```

**Step 3: 푸시 전 최종 상태 보고**

검증 결과와 실제 변경 파일을 보고하고, 연결할 PR 브랜치가 확인된 뒤 해당 브랜치에 안전하게 반영한다.
