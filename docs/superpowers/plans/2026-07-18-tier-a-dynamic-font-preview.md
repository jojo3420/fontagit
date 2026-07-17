# Tier A Dynamic Font Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/fonts` 목록과 폰트 상세에서 Google Tier A 폰트를 각 서체로 렌더링하고, 로딩 전·실패 시에는 Pretendard 폴백을 유지한다.

**Architecture:** DB의 `source_tier`를 웹 도메인까지 전달하고, 순수 정책 함수가 self-host 폰트·Google Tier A·그 외 폰트를 구분한다. Google Tier A 중 기존 `fontKey`가 없는 폰트만 CSS2 stylesheet를 뷰포트 진입 시 한 번 로드하며, 카드와 상세 견본은 같은 지연 로딩 컴포넌트를 사용한다.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, Google Fonts CSS2 API, Vitest, Testing Library, Playwright

## Global Constraints

- Google Fonts CSS2 URL은 `https://fonts.googleapis.com/css2?family=<encoded>&display=swap` 형식만 사용한다.
- `source_tier='A'`이면서 `fontKey=null`인 폰트만 외부 stylesheet를 요청한다.
- Tier B/C와 출처 미상 폰트는 Google에 요청하지 않고 Pretendard 폴백을 유지한다.
- 같은 stylesheet URL은 문서에 한 번만 삽입한다.
- 화면에서 200px 이내로 접근한 견본만 로드한다. `IntersectionObserver` 미지원 환경은 즉시 로드한다.
- DB 마이그레이션과 외부 패키지 추가는 하지 않는다.
- 테스트는 핵심 정책의 해피 패스 1개와 치명적 예외 2개, 총 3개 이하로 제한한다.

---

### Task 1: 폰트 출처와 미리보기 정책

**Files:**
- Modify: `apps/web/lib/db/types.ts`
- Modify: `apps/web/types/font.ts`
- Modify: `apps/web/lib/db/mappers.ts`
- Create: `apps/web/lib/fontPreview.ts`
- Create: `apps/web/lib/fontPreview.test.ts`

**Interfaces:**
- Consumes: DB `fonts.source_tier`, 기존 `familyOf(fontKey)`
- Produces: `SourceTier`, `Font.sourceTier`, `resolveFontPreview(font)`

- [ ] **Step 1: 핵심 정책의 실패 테스트 작성**

```ts
import { describe, expect, it } from "vitest";
import { resolveFontPreview } from "@/lib/fontPreview";

describe("resolveFontPreview", () => {
  it("미매핑 Tier A 폰트를 Google CSS2 URL과 실제 family로 연결한다", () => {
    expect(resolveFontPreview({
      fontKey: null,
      nameEn: "Orbitron",
      sourceTier: "A",
    })).toEqual({
      fontFamily: '"Orbitron", "Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl: "https://fonts.googleapis.com/css2?family=Orbitron&display=swap",
    });
  });

  it("이미 self-host된 폰트는 외부 stylesheet를 요청하지 않는다", () => {
    expect(resolveFontPreview({
      fontKey: "jua",
      nameEn: "Jua",
      sourceTier: "A",
    }).stylesheetUrl).toBeNull();
  });

  it("Tier B 폰트를 Google에 잘못 요청하지 않는다", () => {
    expect(resolveFontPreview({
      fontKey: null,
      nameEn: "경기천년제목",
      sourceTier: "B",
    })).toEqual({
      fontFamily: '"Pretendard Variable", "Pretendard", sans-serif',
      stylesheetUrl: null,
    });
  });
});
```

- [ ] **Step 2: RED 확인**

Run: `cd apps/web && pnpm test -- lib/fontPreview.test.ts`

Expected: FAIL — `@/lib/fontPreview`가 아직 존재하지 않는다.

- [ ] **Step 3: DB 출처를 웹 도메인까지 전달**

`apps/web/types/font.ts`:

```ts
export type SourceTier = "A" | "B" | "C";

export interface Font {
  // 기존 필드 유지
  sourceTier?: SourceTier;
}
```

`apps/web/lib/db/types.ts`의 `FontRow`:

```ts
import type { SourceTier } from "@/types/font";

source_tier?: SourceTier;
```

`apps/web/lib/db/mappers.ts`의 반환값:

```ts
sourceTier: row.source_tier,
```

`sourceTier`는 기존 정적 샘플과 테스트 객체의 대량 수정을 피하기 위해 선택 필드로 둔다. 값이 없으면 외부 요청 금지로 처리한다.

- [ ] **Step 4: 최소 정책 구현**

`apps/web/lib/fontPreview.ts`:

```ts
import type { Font } from "@/types/font";
import { familyOf } from "@/lib/fonts";

const FALLBACK_FAMILY = '"Pretendard Variable", "Pretendard", sans-serif';

type PreviewFont = Pick<Font, "fontKey" | "nameEn" | "sourceTier">;

export interface FontPreviewResolution {
  fontFamily: string;
  stylesheetUrl: string | null;
}

export function resolveFontPreview(font: PreviewFont): FontPreviewResolution {
  if (font.fontKey) {
    return { fontFamily: familyOf(font.fontKey), stylesheetUrl: null };
  }

  const family = font.nameEn.trim();
  if (font.sourceTier !== "A" || !family) {
    return { fontFamily: FALLBACK_FAMILY, stylesheetUrl: null };
  }

  const query = new URLSearchParams({ family, display: "swap" });
  return {
    fontFamily: `${JSON.stringify(family)}, ${FALLBACK_FAMILY}`,
    stylesheetUrl: `https://fonts.googleapis.com/css2?${query.toString()}`,
  };
}
```

- [ ] **Step 5: GREEN 확인**

Run: `cd apps/web && pnpm test -- lib/fontPreview.test.ts __tests__/mappers.test.ts`

Expected: 2개 테스트 파일 전체 PASS.

---

### Task 2: 뷰포트 기반 stylesheet 로더와 화면 연결

**Files:**
- Create: `apps/web/components/LazyFontPreview.tsx`
- Modify: `apps/web/components/FontCard.tsx`
- Modify: `apps/web/components/SpecimenBox.tsx`
- Modify: `apps/web/app/fonts/[slug]/page.tsx`

**Interfaces:**
- Consumes: `resolveFontPreview(font)`
- Produces: `LazyFontPreview({ font, className, children })`

- [ ] **Step 1: 지연 로더 구현**

```tsx
"use client";

import { useEffect, useMemo, useRef } from "react";
import type { Font } from "@/types/font";
import { resolveFontPreview } from "@/lib/fontPreview";

function ensureStylesheet(url: string) {
  const exists = Array.from(
    document.querySelectorAll<HTMLLinkElement>('link[data-fontagit-webfont="true"]')
  ).some((link) => link.href === url);
  if (exists) return;

  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = url;
  link.dataset.fontagitWebfont = "true";
  document.head.appendChild(link);
}

export function LazyFontPreview({
  font,
  className,
  children,
}: {
  font: Pick<Font, "fontKey" | "nameEn" | "sourceTier">;
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const preview = useMemo(
    () => resolveFontPreview(font),
    [font.fontKey, font.nameEn, font.sourceTier]
  );

  useEffect(() => {
    if (!preview.stylesheetUrl || !ref.current) return;

    const load = () => ensureStylesheet(preview.stylesheetUrl!);
    if (!("IntersectionObserver" in window)) {
      load();
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          load();
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [preview.stylesheetUrl]);

  return (
    <div ref={ref} className={className} style={{ fontFamily: preview.fontFamily }}>
      {children}
    </div>
  );
}
```

- [ ] **Step 2: 목록 카드 연결**

`FontCard.tsx`에서 `familyOf` 직접 호출을 제거하고 견본 `div`를 다음으로 교체한다.

```tsx
<LazyFontPreview font={font} className={styles.specimen}>
  {line1}<br />
  {line2}
</LazyFontPreview>
```

기존 문구 계산은 한 번만 실행해 `line1`, `line2`로 나눈다.

- [ ] **Step 3: 상세 견본 연결**

`SpecimenBox`에서 `fontFamily` prop을 제거하고 sample `div`를 다음으로 교체한다.

```tsx
<LazyFontPreview font={font} className={styles.sample}>
  {text || " "}
</LazyFontPreview>
```

`apps/web/app/fonts/[slug]/page.tsx`에서는 `familyOf` import와 `family` 지역 변수를 제거하고 다음처럼 호출한다.

```tsx
<SpecimenBox font={font} editable={!isPaid} caption={caption} />
```

기존 `SpecimenBox` 테스트는 `fontFamily` prop만 제거한다. 이는 단순 UI 전달 테스트를 추가하는 것이 아니라 기존 테스트를 새 인터페이스에 맞추는 작업이다.

- [ ] **Step 4: 관련 테스트와 타입 검사**

Run: `cd apps/web && pnpm test -- lib/fontPreview.test.ts components/FontCard.test.tsx components/SpecimenBox.test.tsx __tests__/mappers.test.ts`

Expected: 지정한 테스트 전체 PASS.

Run: `cd apps/web && pnpm exec tsc --noEmit`

Expected: 이번 변경에서 발생한 새 타입 오류 0건. 현재 기준선에는 `mappers.test.ts`의 누락 fixture, `WeeklyRankPanel.test.tsx`의 잘못된 `FontKey`, `filters.test.ts`의 optional `subsets` 오류가 이미 있으므로 결과를 수정 전 기준선과 대조한다. 이 별도 오류를 이번 버그 수정에 섞어 고치지 않는다.

---

### Task 3: 실제 증상과 전체 회귀 검증

**Files:**
- Modify only if verification exposes a defect in Task 1-2 files.

**Interfaces:**
- Consumes: 실행 중인 `http://127.0.0.1:3000/fonts/`
- Produces: Orbitron의 계산된 `font-family`와 Google stylesheet 요청 증거

- [ ] **Step 1: 전체 정적 검증**

Run: `cd apps/web && pnpm test`

Expected: 실패 0건.

Run: `cd apps/web && pnpm lint`

Expected: ESLint 오류 0건.

Run: `cd apps/web && pnpm build`

Expected: Next.js 정적 빌드 exit 0.

- [ ] **Step 2: 브라우저 원증상 검증**

Playwright로 `/fonts/`를 열고 Orbitron 카드가 뷰포트에 들어온 뒤 다음을 확인한다.

```ts
expect(getComputedStyle(orbitronSpecimen).fontFamily).toContain("Orbitron");
expect(document.querySelectorAll(
  'link[data-fontagit-webfont="true"][href*="family=Orbitron"]'
)).toHaveLength(1);
expect(Array.from(document.fonts).some(
  (face) => face.family === "Orbitron" && face.status === "loaded"
)).toBe(true);
```

계산된 CSS 이름만 확인하면 실제 폰트 파일이 없어도 통과하므로, `document.fonts.load('400 48px "Orbitron"', 'The quick brown fox')` 완료 후 `FontFaceSet`의 loaded 상태까지 확인한다.

또한 Tier B인 `경기천년제목`에는 Google stylesheet 링크가 생기지 않아야 한다. 별도 브라우저 컨텍스트에서는 `fonts.googleapis.com`과 `fonts.gstatic.com` 요청을 차단하고, Orbitron 견본이 계속 보이며 Pretendard 기준 견본과 폭이 같은지 확인해 네트워크 실패 폴백을 검증한다.

- [ ] **Step 3: 변경 범위 검토와 커밋**

Run: `git diff --check`

Expected: 공백 오류 0건.

스테이징은 아래 파일만 명시적으로 수행한다.

```bash
git add \
  docs/superpowers/plans/2026-07-18-tier-a-dynamic-font-preview.md \
  docs/review/2026-07-18-tier-a-font-preview-red-team.md \
  apps/web/types/font.ts \
  apps/web/lib/db/types.ts \
  apps/web/lib/db/mappers.ts \
  apps/web/lib/fontPreview.ts \
  apps/web/lib/fontPreview.test.ts \
  apps/web/components/LazyFontPreview.tsx \
  apps/web/components/FontCard.tsx \
  apps/web/components/SpecimenBox.tsx \
  apps/web/components/SpecimenBox.test.tsx \
  'apps/web/app/fonts/[slug]/page.tsx'
```

Commit: `fix: Tier A 폰트 실제 견본 렌더링`

기존 검색 색인 문서와 `docs/review/`의 다른 미커밋 파일은 포함하지 않는다.
