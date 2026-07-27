# 폰트 상세 굵기별 견본 + 이탤릭 (#107) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 폰트 상세 화면에 확인된 굵기x이탤릭 조합별 실제 견본 섹션을 추가하고, 미확인 정보는 추정 없이 표시한다.

**Architecture:** 순수 변환 계층(weightLabels.ts: variants 정규화-이탤릭 판정-weights 정규화)을 먼저 만들고, 데이터 매퍼가 이를 사용해 화면 모델에 `confirmedWeights`/`variants`를 노출한다. 상세 페이지는 서버 컴포넌트로 유지하고, 신규 클라이언트 래퍼 `DetailSpecimenPanel`이 문장 상태-스타일시트 1회 로드-`document.fonts` 실로드 검증을 담당하며 표시 전용 `WeightSpecimenSection`에 조합별 상태를 내려준다.

**Tech Stack:** Next.js SSG(output: export), React 클라이언트 컴포넌트, vitest, CSS Modules, Google Fonts CSS2 API.

**스펙:** `docs/superpowers/specs/2026-07-27-font-detail-weights-italic-design.md` (Codex 리뷰 반영본)

## Global Constraints

- `app/fonts/[slug]/page.tsx`는 서버 컴포넌트 유지(generateStaticParams/generateMetadata 불변). 클라이언트 로직은 전부 래퍼로.
- Tier B/C는 외부 네트워크 요청을 하나도 추가하지 않는다.
- 견본 행 CSS에 `font-synthesis: none` 필수(합성 굵기-이탤릭 차단).
- 견본 행의 SSoT는 정규화된 variants 조합. `confirmedWeights`는 개수-헤더 나열 전용.
- 라벨 표기: 숫자 먼저 `400 Regular`. 이름 매핑 없는 값은 숫자만.
- `Font`의 신규 필드는 optional(`confirmedWeights?`, `variants?`)로 추가 — 기존 테스트 픽스처 회귀 방지.
- 테스트는 핵심 변환 3영역만(신규 weightLabels.test.ts + 기존 fontPreview.test.ts 확장). UI 스냅샷 테스트 금지.
- 문구(정확히 이 문자열 사용): 로드 실패 행 `견본을 불러오지 못했습니다`, Tier B/C `이 폰트는 웹 견본을 제공하지 않습니다`, 미확인 `굵기 정보 미확인`, 하단 안내 `폰트가 지원하지 않는 글자는 대체 글꼴로 표시될 수 있습니다.`
- 각 태스크 종료 시 커밋. 커밋 형식 `feat|fix|docs|test: ...`.
- 실행 위치: `apps/web` (명령은 저장소 루트에서 `pnpm --filter web <cmd>`).

---

### Task 1: weightLabels.ts — 정규화-판정 순수 함수 (TDD)

**Files:**
- Create: `apps/web/lib/weightLabels.ts`
- Test: `apps/web/lib/weightLabels.test.ts`

**Interfaces:**
- Consumes: `SourceTier` 타입(`@/types/font`)
- Produces (후속 태스크가 그대로 사용):
  - `WEIGHT_LABELS: Record<number, string>`
  - `formatWeightLabel(weight: number): string` — `"400 Regular"`, 매핑 없으면 `"350"`
  - `interface VariantCombination { weight: number; style: "normal" | "italic" }`
  - `normalizeVariants(variants: string[]): VariantCombination[]`
  - `type ItalicSupport = "supported" | "unsupported" | "unknown"`
  - `resolveItalicSupport(font: { sourceTier?: SourceTier; variants?: string[] }): { status: ItalicSupport; italicCombos: VariantCombination[] }`
  - `normalizeWeights(weights: number[]): number[] | null`

- [ ] **Step 1: 실패하는 테스트 작성** — `apps/web/lib/weightLabels.test.ts`

```ts
import { describe, expect, it } from "vitest";
import {
  formatWeightLabel,
  normalizeVariants,
  normalizeWeights,
  resolveItalicSupport,
} from "./weightLabels";

describe("normalizeVariants", () => {
  it("Google Fonts 4형태를 정규화하고 불가값은 무시한다", () => {
    expect(
      normalizeVariants(["regular", "italic", "700", "700italic", "wat", ""])
    ).toEqual([
      { weight: 400, style: "normal" },
      { weight: 400, style: "italic" },
      { weight: 700, style: "normal" },
      { weight: 700, style: "italic" },
    ]);
    // 중복 제거 + weight 오름차순, 같은 weight는 normal 우선
    expect(normalizeVariants(["700", "300", "700", "300italic"])).toEqual([
      { weight: 300, style: "normal" },
      { weight: 300, style: "italic" },
      { weight: 700, style: "normal" },
    ]);
  });
});

describe("resolveItalicSupport", () => {
  it("italic 조합 존재는 supported, Tier A variants 보유-italic 없음은 unsupported, 그 외 unknown", () => {
    expect(
      resolveItalicSupport({ sourceTier: "A", variants: ["regular", "italic"] })
    ).toEqual({
      status: "supported",
      italicCombos: [{ weight: 400, style: "italic" }],
    });
    expect(
      resolveItalicSupport({ sourceTier: "A", variants: ["regular", "700"] }).status
    ).toBe("unsupported");
    expect(resolveItalicSupport({ sourceTier: "A", variants: [] }).status).toBe("unknown");
    expect(
      resolveItalicSupport({ sourceTier: "B", variants: undefined }).status
    ).toBe("unknown");
  });
});

describe("normalizeWeights", () => {
  it("비정상값-중복 제거, 정렬, 빈 결과는 null", () => {
    expect(normalizeWeights([700, 400, 400, 0, 1001, Number.NaN])).toEqual([400, 700]);
    expect(normalizeWeights([])).toBeNull();
    expect(normalizeWeights([0])).toBeNull();
  });
});

describe("formatWeightLabel", () => {
  it("이름 매핑이 있으면 숫자+이름, 없으면 숫자만", () => {
    expect(formatWeightLabel(400)).toBe("400 Regular");
    expect(formatWeightLabel(350)).toBe("350");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `pnpm --filter web test -- lib/weightLabels.test.ts`
Expected: FAIL — `Cannot find module './weightLabels'` 또는 함수 미정의

- [ ] **Step 3: 구현** — `apps/web/lib/weightLabels.ts`

```ts
import type { SourceTier } from "@/types/font";

/** CSS font-weight 표준 이름. 매핑 없는 값은 숫자만 표기한다. */
export const WEIGHT_LABELS: Record<number, string> = {
  100: "Thin",
  200: "ExtraLight",
  300: "Light",
  400: "Regular",
  500: "Medium",
  600: "SemiBold",
  700: "Bold",
  800: "ExtraBold",
  900: "Black",
};

export function formatWeightLabel(weight: number): string {
  const name = WEIGHT_LABELS[weight];
  return name ? `${weight} ${name}` : String(weight);
}

export interface VariantCombination {
  weight: number;
  style: "normal" | "italic";
}

const VARIANT_PATTERN = /^(\d+)?(italic)?$/;

/**
 * Google Fonts variants(regular/italic/700/700italic)를 조합으로 정규화한다.
 * 해석 불가능한 값은 무시하고, 중복 제거 후 weight 오름차순(normal 우선) 정렬.
 */
export function normalizeVariants(variants: string[]): VariantCombination[] {
  const seen = new Set<string>();
  const combos: VariantCombination[] = [];
  for (const raw of variants) {
    const value = raw.trim().toLowerCase();
    if (!value) continue;
    const match = VARIANT_PATTERN.exec(value === "regular" ? "400" : value);
    if (!match || (!match[1] && !match[2])) continue;
    const weight = match[1] ? Number(match[1]) : 400;
    if (!Number.isInteger(weight) || weight < 1 || weight > 1000) continue;
    const style: VariantCombination["style"] = match[2] ? "italic" : "normal";
    const key = `${weight}-${style}`;
    if (seen.has(key)) continue;
    seen.add(key);
    combos.push({ weight, style });
  }
  return combos.sort(
    (a, b) => a.weight - b.weight || (a.style === b.style ? 0 : a.style === "normal" ? -1 : 1)
  );
}

export type ItalicSupport = "supported" | "unsupported" | "unknown";

/**
 * 이탤릭 지원 판정. variants가 SSoT이며 Tier A + variants 보유 상태에서만
 * "미지원"을 단정한다(그 외 데이터 부족은 unknown).
 */
export function resolveItalicSupport(font: {
  sourceTier?: SourceTier;
  variants?: string[];
}): { status: ItalicSupport; italicCombos: VariantCombination[] } {
  const combos = normalizeVariants(font.variants ?? []);
  const italicCombos = combos.filter((c) => c.style === "italic");
  if (italicCombos.length > 0) return { status: "supported", italicCombos };
  if (font.sourceTier === "A" && combos.length > 0) {
    return { status: "unsupported", italicCombos: [] };
  }
  return { status: "unknown", italicCombos: [] };
}

/** DB weights를 표시용으로 정규화한다. 유효값이 없으면 null(미확인). */
export function normalizeWeights(weights: number[]): number[] | null {
  const cleaned = [
    ...new Set(
      weights.filter((w) => Number.isInteger(w) && w >= 1 && w <= 1000)
    ),
  ].sort((a, b) => a - b);
  return cleaned.length > 0 ? cleaned : null;
}
```

- [ ] **Step 4: 통과 확인**

Run: `pnpm --filter web test -- lib/weightLabels.test.ts`
Expected: PASS (4 tests)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/weightLabels.ts apps/web/lib/weightLabels.test.ts
git commit -m "feat: variants 정규화-이탤릭 판정-weights 정규화 유틸 (#107)"
```

---

### Task 2: 화면 모델 필드 노출 (FontRow.variants + Font.confirmedWeights/variants + 매퍼)

**Files:**
- Modify: `apps/web/lib/db/types.ts` (FontRow, weights 필드 근처 11행)
- Modify: `apps/web/types/font.ts` (Font 인터페이스, availableWeights 근처)
- Modify: `apps/web/lib/db/mappers.ts` (availableWeights 매핑 행 근처, 약 65행)

**Interfaces:**
- Consumes: Task 1 `normalizeWeights(weights: number[]): number[] | null`
- Produces: `Font.confirmedWeights?: number[] | null`, `Font.variants?: string[]` — 이후 모든 태스크가 이 두 필드를 읽는다. DB `fonts.variants`는 `text[] not null default '{}'`(0001 마이그레이션)이므로 row에서 항상 배열이다.

- [ ] **Step 1: FontRow에 variants 추가** — `apps/web/lib/db/types.ts`의 `weights: number[];` 바로 아래에:

```ts
  variants: string[];
```

- [ ] **Step 2: Font 타입 확장** — `apps/web/types/font.ts`의 `availableWeights: number[];` 아래에:

```ts
  /** 확인된 굵기(정규화, 표시 전용). null 또는 미설정 = 미확인. */
  confirmedWeights?: number[] | null;
  /** Google Fonts variants 원본(예: ["regular","italic","700"]). 빈 배열 = 미확인. */
  variants?: string[];
```

- [ ] **Step 3: 매퍼 반영** — `apps/web/lib/db/mappers.ts` 상단 import에 `import { normalizeWeights } from "@/lib/weightLabels";` 추가 후, `availableWeights: row.weights.length > 0 ? row.weights : [400],` 바로 아래에:

```ts
    confirmedWeights: normalizeWeights(row.weights),
    variants: row.variants,
```

- [ ] **Step 4: 전체 테스트-린트 그린 확인** (기존 픽스처 회귀 없음 검증)

Run: `pnpm --filter web test && pnpm --filter web lint`
Expected: PASS (신규 필드가 optional이라 기존 Font 픽스처 그린 유지)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/db/types.ts apps/web/types/font.ts apps/web/lib/db/mappers.ts
git commit -m "feat: Font 모델에 confirmedWeights-variants 노출 (#107)"
```

---

### Task 3: resolveDetailFontPreview — 상세 전용 로더 URL (TDD)

**Files:**
- Modify: `apps/web/lib/fontPreview.ts`
- Test: `apps/web/lib/fontPreview.test.ts` (기존 파일 확장)

**Interfaces:**
- Consumes: Task 1 `normalizeVariants`, `VariantCombination`; 기존 `FALLBACK_FAMILY`, `familyOf`
- Produces:
  - `interface DetailFontPreviewResolution { fontFamily: string; stylesheetUrl: string | null; combos: VariantCombination[] }`
  - `resolveDetailFontPreview(font: Pick<Font, "fontKey" | "nameEn" | "sourceTier" | "variants">): DetailFontPreviewResolution`
  - 규칙: Tier A + nameEn + 조합 1개 이상일 때만 `ital,wght` axis URL 생성. fontKey(로컬 폰트)는 시트 없이 로컬 패밀리 + 조합 반환. 그 외 `stylesheetUrl: null, combos: []`.

- [ ] **Step 1: 실패하는 테스트 추가** — `apps/web/lib/fontPreview.test.ts` 하단에:

```ts
import { resolveDetailFontPreview } from "./fontPreview";

describe("resolveDetailFontPreview", () => {
  it("Tier A는 정규화 조합으로 ital,wght URL을 만든다(튜플 오름차순)", () => {
    const result = resolveDetailFontPreview({
      fontKey: null,
      nameEn: "Noto Sans KR",
      sourceTier: "A",
      variants: ["700italic", "regular", "700", "italic"],
    });
    expect(result.combos).toHaveLength(4);
    expect(result.stylesheetUrl).toBe(
      "https://fonts.googleapis.com/css2?family=Noto+Sans+KR%3Aital%2Cwght%400%2C400%3B0%2C700%3B1%2C400%3B1%2C700&display=swap"
    );
  });

  it("Tier B-C와 조합 없음은 외부 요청을 만들지 않는다", () => {
    expect(
      resolveDetailFontPreview({
        fontKey: null,
        nameEn: "어떤체",
        sourceTier: "B",
        variants: ["regular"],
      })
    ).toEqual({ fontFamily: expect.any(String), stylesheetUrl: null, combos: [] });
    expect(
      resolveDetailFontPreview({
        fontKey: null,
        nameEn: "Some Font",
        sourceTier: "A",
        variants: [],
      }).stylesheetUrl
    ).toBeNull();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `pnpm --filter web test -- lib/fontPreview.test.ts`
Expected: FAIL — `resolveDetailFontPreview` 미정의

- [ ] **Step 3: 구현** — `apps/web/lib/fontPreview.ts` 하단에 추가:

```ts
import {
  normalizeVariants,
  type VariantCombination,
} from "@/lib/weightLabels";

export interface DetailFontPreviewResolution {
  fontFamily: string;
  stylesheetUrl: string | null;
  combos: VariantCombination[];
}

/**
 * 상세 화면 전용: 확인된 굵기x이탤릭 조합 전체를 담은 시트 URL을 만든다.
 * Tier B/C는 외부 요청을 만들지 않는다(조합도 비움 — 견본 미제공 정책).
 */
export function resolveDetailFontPreview(
  font: Pick<Font, "fontKey" | "nameEn" | "sourceTier" | "variants">
): DetailFontPreviewResolution {
  const family = font.nameEn.trim();
  if (font.sourceTier !== "A") {
    return { fontFamily: FALLBACK_FAMILY, stylesheetUrl: null, combos: [] };
  }
  const combos = normalizeVariants(font.variants ?? []);
  if (font.fontKey) {
    return { fontFamily: familyOf(font.fontKey), stylesheetUrl: null, combos };
  }
  if (!family || combos.length === 0) {
    return { fontFamily: FALLBACK_FAMILY, stylesheetUrl: null, combos: [] };
  }
  const tuples = [...combos]
    .sort((a, b) => (a.style === b.style ? a.weight - b.weight : a.style === "normal" ? -1 : 1))
    .map((c) => `${c.style === "italic" ? 1 : 0},${c.weight}`);
  const query = new URLSearchParams({
    family: `${family}:ital,wght@${tuples.join(";")}`,
    display: "swap",
  });
  return {
    fontFamily: `${JSON.stringify(family)}, ${FALLBACK_FAMILY}`,
    stylesheetUrl: `https://fonts.googleapis.com/css2?${query.toString()}`,
    combos,
  };
}
```

- [ ] **Step 4: 통과 확인** (기존 resolveFontPreview 테스트 포함 전체 그린)

Run: `pnpm --filter web test -- lib/fontPreview.test.ts`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/fontPreview.ts apps/web/lib/fontPreview.test.ts
git commit -m "feat: 상세 전용 ital,wght 시트 로더 resolveDetailFontPreview (#107)"
```

---

### Task 4: SpecimenBox controlled 모드 + 시트 위임

**Files:**
- Modify: `apps/web/components/SpecimenBox.tsx`

**Interfaces:**
- Produces: 선택적 props `text?: string; onTextChange?: (text: string) => void; stylesheetManaged?: boolean`. 미지정 시 기존 단독 동작 100% 유지(하위 호환). `stylesheetManaged`가 true면 LazyFontPreview 대신 부모가 로드한 시트를 신뢰하고 fontFamily만 적용(중복 시트 요청 방지).
- Consumes: 기존 `resolveFontPreview`(fontFamily 문자열용)

- [ ] **Step 1: 구현** — `apps/web/components/SpecimenBox.tsx` 전체를 다음으로 교체:

```tsx
"use client";
import { useState } from "react";
import type { Font } from "@/types/font";
import { getDefaultSpecimenText } from "@/lib/specimen";
import { resolveFontPreview } from "@/lib/fontPreview";
import { LazyFontPreview } from "./LazyFontPreview";
import styles from "./SpecimenBox.module.css";

/**
 * 견본 박스. 대형 견본 텍스트를 fontFamily로 렌더한다.
 * editable=true면 하단 입력이 견본을 실시간 갱신(무료 폰트).
 * caption이 있으면 견본 아래 회색 주석 표시(유료 대체 견본 안내).
 * text/onTextChange를 주면 controlled로 동작(상세 화면 문장 공유).
 * stylesheetManaged=true면 시트 로드는 부모 책임(중복 요청 방지).
 */
export function SpecimenBox({
  font,
  editable,
  initialText,
  caption,
  text: controlledText,
  onTextChange,
  stylesheetManaged = false,
}: {
  font: Font;
  editable: boolean;
  initialText?: string;
  caption?: string;
  text?: string;
  onTextChange?: (text: string) => void;
  stylesheetManaged?: boolean;
}) {
  const [innerText, setInnerText] = useState(
    initialText ?? getDefaultSpecimenText(font)
  );
  const isControlled = controlledText !== undefined;
  const text = isControlled ? controlledText : innerText;
  const setText = (next: string) => {
    if (!isControlled) setInnerText(next);
    onTextChange?.(next);
  };
  return (
    <div className={styles.box}>
      {stylesheetManaged ? (
        <div
          className={styles.sample}
          style={{ fontFamily: resolveFontPreview(font).fontFamily }}
        >
          {text || " "}
        </div>
      ) : (
        <LazyFontPreview font={font} className={styles.sample}>
          {text || " "}
        </LazyFontPreview>
      )}
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

- [ ] **Step 2: 기존 테스트로 하위 호환 검증**

Run: `pnpm --filter web test -- components/SpecimenBox.test.tsx`
Expected: PASS (기존 테스트 무수정 그린)

- [ ] **Step 3: 커밋**

```bash
git add apps/web/components/SpecimenBox.tsx
git commit -m "feat: SpecimenBox controlled 모드-시트 위임 옵션 (#107)"
```

---

### Task 5: WeightSpecimenSection — 표시 전용 섹션

**Files:**
- Create: `apps/web/components/WeightSpecimenSection.tsx`
- Create: `apps/web/components/WeightSpecimenSection.module.css`

**Interfaces:**
- Consumes: Task 1 `formatWeightLabel`, `resolveItalicSupport`, `VariantCombination`
- Produces: 표시 전용 컴포넌트(자체 네트워크-부수효과 없음). Props:

```ts
export type ComboLoadStatus = "loading" | "loaded" | "failed";
export function comboKey(combo: VariantCombination): string; // `${weight}-${style}`
interface Props {
  font: Font;
  text: string;                       // 공유 미리보기 문장
  combos: VariantCombination[];       // 견본 행 SSoT (빈 배열 = 견본 미제공)
  statuses: Record<string, ComboLoadStatus>; // comboKey → 상태
  fontFamily: string;                 // 부모가 해석한 family
}
```

- [ ] **Step 1: 스타일 작성** — `apps/web/components/WeightSpecimenSection.module.css`

```css
.section {
  margin-top: 24px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 12px;
  padding: 20px;
}
.header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.title {
  font-size: 15px;
  font-weight: 600;
}
.weightList {
  font-size: 13px;
  color: var(--muted, #6b7280);
}
.badge {
  font-size: 12px;
  border-radius: 999px;
  padding: 2px 10px;
  background: var(--chip-bg, #f3f4f6);
  color: var(--muted, #6b7280);
}
.row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 0;
  border-top: 1px solid var(--border, #f3f4f6);
}
.rowLabel {
  font-size: 12px;
  color: var(--muted, #6b7280);
}
.rowSample {
  font-size: 24px;
  line-height: 1.5;
  overflow-wrap: anywhere;
  font-synthesis: none;
}
.rowFallback {
  font-size: 13px;
  color: var(--muted, #9ca3af);
}
.skeleton {
  height: 36px;
  border-radius: 6px;
  background: var(--chip-bg, #f3f4f6);
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  50% { opacity: 0.5; }
}
.notice {
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted, #9ca3af);
}
```

- [ ] **Step 2: 컴포넌트 구현** — `apps/web/components/WeightSpecimenSection.tsx`

```tsx
"use client";
import type { Font } from "@/types/font";
import {
  formatWeightLabel,
  resolveItalicSupport,
  type VariantCombination,
} from "@/lib/weightLabels";
import styles from "./WeightSpecimenSection.module.css";

export type ComboLoadStatus = "loading" | "loaded" | "failed";

export function comboKey(combo: VariantCombination): string {
  return `${combo.weight}-${combo.style}`;
}

const ITALIC_BADGE: Record<string, string> = {
  supported: "이탤릭 지원",
  unsupported: "이탤릭 미지원",
  unknown: "이탤릭 정보 미확인",
};

function rowLabel(combo: VariantCombination): string {
  const base = formatWeightLabel(combo.weight);
  return combo.style === "italic" ? `${base} Italic` : base;
}

/**
 * 지원 굵기 섹션(표시 전용). 견본 행은 combos(정규화 variants) 기준으로만
 * 그린다 — confirmedWeights로 행을 만들지 않는다(합성 견본 방지).
 */
export function WeightSpecimenSection({
  font,
  text,
  combos,
  statuses,
  fontFamily,
}: {
  font: Font;
  text: string;
  combos: VariantCombination[];
  statuses: Record<string, ComboLoadStatus>;
  fontFamily: string;
}) {
  const confirmed = font.confirmedWeights ?? null;
  const italic = resolveItalicSupport(font);
  const hasRows = combos.length > 0;

  return (
    <section className={styles.section} aria-label="지원 굵기">
      <div className={styles.header}>
        <h2 className={styles.title}>지원 굵기</h2>
        <span className={styles.badge}>{ITALIC_BADGE[italic.status]}</span>
      </div>
      <p className={styles.weightList}>
        {confirmed
          ? confirmed.map(formatWeightLabel).join(" - ")
          : "굵기 정보 미확인"}
      </p>
      {hasRows ? (
        <>
          {combos.map((combo) => {
            const status = statuses[comboKey(combo)] ?? "loading";
            return (
              <div key={comboKey(combo)} className={styles.row}>
                <span className={styles.rowLabel}>{rowLabel(combo)}</span>
                {status === "loading" && <div className={styles.skeleton} />}
                {status === "loaded" && (
                  <div
                    className={styles.rowSample}
                    style={{
                      fontFamily,
                      fontWeight: combo.weight,
                      fontStyle: combo.style,
                    }}
                  >
                    {text || " "}
                  </div>
                )}
                {status === "failed" && (
                  <span className={styles.rowFallback}>
                    견본을 불러오지 못했습니다
                  </span>
                )}
              </div>
            );
          })}
          <p className={styles.notice}>
            폰트가 지원하지 않는 글자는 대체 글꼴로 표시될 수 있습니다.
          </p>
        </>
      ) : (
        <p className={styles.rowFallback}>
          이 폰트는 웹 견본을 제공하지 않습니다
          {font.officialUrl ? (
            <>
              {" - "}
              <a href={font.officialUrl} target="_blank" rel="noopener noreferrer">
                공식 배포 페이지에서 확인
              </a>
            </>
          ) : null}
        </p>
      )}
    </section>
  );
}
```

- [ ] **Step 3: 린트 확인**

Run: `pnpm --filter web lint`
Expected: PASS

- [ ] **Step 4: 커밋**

```bash
git add apps/web/components/WeightSpecimenSection.tsx apps/web/components/WeightSpecimenSection.module.css
git commit -m "feat: 지원 굵기 섹션 표시 컴포넌트 (#107)"
```

---

### Task 6: DetailSpecimenPanel — 문장 상태 + 시트 1회 로드 + 실로드 검증

**Files:**
- Create: `apps/web/components/DetailSpecimenPanel.tsx`

**Interfaces:**
- Consumes: Task 3 `resolveDetailFontPreview`, Task 4 SpecimenBox controlled props, Task 5 `WeightSpecimenSection`/`ComboLoadStatus`/`comboKey`
- Produces: `DetailSpecimenPanel({ font, editable, caption })` — 상세 페이지가 SpecimenBox 자리에 그대로 배치하는 유일한 클라이언트 진입점.

- [ ] **Step 1: 구현** — `apps/web/components/DetailSpecimenPanel.tsx`

```tsx
"use client";
import { useEffect, useMemo, useState } from "react";
import type { Font } from "@/types/font";
import { getDefaultSpecimenText } from "@/lib/specimen";
import { resolveDetailFontPreview } from "@/lib/fontPreview";
import { SpecimenBox } from "./SpecimenBox";
import {
  WeightSpecimenSection,
  comboKey,
  type ComboLoadStatus,
} from "./WeightSpecimenSection";

const LOAD_TIMEOUT_MS = 5000;
/** 판정 일관성을 위한 고정 검사 문자열(사용자 입력과 무관). */
const PROBE_TEXT = "다람쥐 한글Aa1";

function ensureStylesheet(url: string): Promise<void> {
  const existing = Array.from(
    document.querySelectorAll<HTMLLinkElement>(
      'link[data-fontagit-webfont="true"]'
    )
  ).find((link) => link.href === url);
  if (existing) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = url;
    link.dataset.fontagitWebfont = "true";
    link.onload = () => resolve();
    link.onerror = () => reject(new Error("stylesheet load failed"));
    document.head.appendChild(link);
  });
}

/** 요청 조합과 로드된 FontFace의 weight/style이 실제로 일치하는지 대조한다. */
function fontActuallyLoaded(
  family: string,
  weight: number,
  style: "normal" | "italic"
): boolean {
  return Array.from(document.fonts).some(
    (face) =>
      face.family.replace(/^["']|["']$/g, "") === family &&
      face.style === style &&
      (face.weight === String(weight) ||
        face.weight.split(" ").includes(String(weight))) &&
      face.status === "loaded"
  );
}

/**
 * 상세 화면 클라이언트 래퍼: 미리보기 문장 상태를 소유하고,
 * 전체 조합 시트를 1회 로드한 뒤 조합별 실로드를 검증해 섹션에 내려준다.
 */
export function DetailSpecimenPanel({
  font,
  editable,
  caption,
}: {
  font: Font;
  editable: boolean;
  caption?: string;
}) {
  const [text, setText] = useState(getDefaultSpecimenText(font));
  const detail = useMemo(() => resolveDetailFontPreview(font), [font]);
  const [statuses, setStatuses] = useState<Record<string, ComboLoadStatus>>({});

  useEffect(() => {
    if (detail.combos.length === 0) return;
    let cancelled = false;
    const familyName = font.nameEn.trim();
    const markAll = (status: ComboLoadStatus) => {
      if (cancelled) return;
      setStatuses(
        Object.fromEntries(detail.combos.map((c) => [comboKey(c), status]))
      );
    };
    markAll("loading");

    const verify = async () => {
      for (const combo of detail.combos) {
        const spec = `${combo.style} ${combo.weight} 16px ${JSON.stringify(familyName)}`;
        let ok = false;
        try {
          await document.fonts.load(spec, PROBE_TEXT);
          ok = fontActuallyLoaded(familyName, combo.weight, combo.style);
        } catch {
          ok = false;
        }
        if (cancelled) return;
        setStatuses((prev) => ({
          ...prev,
          [comboKey(combo)]: ok ? "loaded" : "failed",
        }));
      }
    };

    const timeout = window.setTimeout(() => {
      if (cancelled) return;
      setStatuses((prev) =>
        Object.fromEntries(
          detail.combos.map((c) => [
            comboKey(c),
            prev[comboKey(c)] === "loaded" ? "loaded" : "failed",
          ])
        )
      );
    }, LOAD_TIMEOUT_MS);

    const start = detail.stylesheetUrl
      ? ensureStylesheet(detail.stylesheetUrl)
      : Promise.resolve();
    start.then(verify).catch(() => markAll("failed"));

    return () => {
      cancelled = true;
      window.clearTimeout(timeout);
    };
  }, [detail, font.nameEn]);

  return (
    <>
      <SpecimenBox
        font={font}
        editable={editable}
        caption={caption}
        text={text}
        onTextChange={setText}
        stylesheetManaged={detail.stylesheetUrl !== null}
      />
      <WeightSpecimenSection
        font={font}
        text={text}
        combos={detail.combos}
        statuses={statuses}
        fontFamily={detail.fontFamily}
      />
    </>
  );
}
```

- [ ] **Step 2: 린트-타입 확인**

Run: `pnpm --filter web lint && pnpm --filter web test`
Expected: PASS (신규 컴포넌트는 테스트 없음 — 게이트만)

- [ ] **Step 3: 커밋**

```bash
git add apps/web/components/DetailSpecimenPanel.tsx
git commit -m "feat: 상세 견본 패널 - 시트 1회 로드와 조합별 실로드 검증 (#107)"
```

---

### Task 7: 상세 페이지 통합 + Meta 문구

**Files:**
- Modify: `apps/web/app/fonts/[slug]/page.tsx` (PublishedFontDetail, 약 103~131행)

**Interfaces:**
- Consumes: Task 6 `DetailSpecimenPanel`
- Produces: 사용자 가시 변경 — Meta의 `N가지 굵기`가 confirmedWeights 기준으로 바뀌고 SpecimenBox 자리가 패널로 교체된다. 페이지는 서버 컴포넌트 유지.

- [ ] **Step 1: import 교체** — `SpecimenBox` import를 제거하고:

```tsx
import { DetailSpecimenPanel } from "@/components/DetailSpecimenPanel";
```

- [ ] **Step 2: Meta 문구 수정** — `<p className={styles.meta}>` 내부의 `{font.availableWeights.length}가지 굵기` 부분을 다음으로 교체:

```tsx
{font.confirmedWeights ? `${font.confirmedWeights.length}가지 굵기` : "굵기 정보 미확인"}
```

- [ ] **Step 3: 패널 배치** — `<SpecimenBox font={font} editable={!isPaid} caption={caption} />` 를 다음으로 교체:

```tsx
<DetailSpecimenPanel font={font} editable={!isPaid} caption={caption} />
```

(HoldFontDetail 등 다른 상태 화면의 SpecimenBox 사용처가 있으면 그대로 둔다 — 하위 호환 모드로 동작.)

- [ ] **Step 4: 전체 게이트 실행**

Run: `pnpm --filter web test && pnpm --filter web lint && pnpm --filter web build`
Expected: 테스트-린트 PASS, SSG 2,500+ 페이지 빌드 성공

- [ ] **Step 5: 커밋**

```bash
git add "apps/web/app/fonts/[slug]/page.tsx"
git commit -m "feat: 상세 화면에 지원 굵기 섹션 통합 (#107)"
```

---

### Task 8: 수동 확인 (스펙 9장 완료 조건)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 로컬 구동** — `pnpm --filter web dev` 후 브라우저에서:
  - Tier A 다굵기(예: `/fonts/noto-sans-kr`): 조합별 견본 행, 이탤릭 있으면 이탤릭 행
  - Tier A 이탤릭 미지원: "이탤릭 미지원" 배지 + 이탤릭 행 없음
  - Tier B(예: `/fonts/고도체`): "이 폰트는 웹 견본을 제공하지 않습니다" + 공식 링크
  - 굵기 미확인 폰트: "굵기 정보 미확인"
  - 개발자도구 네트워크 오프라인: 로드 실패 안내, 합성 견본 미노출
  - 모바일 뷰포트(375px): 세로 스택, 가로 스크롤 없음
  - 문장 입력 변경 시 대형 견본과 굵기 행이 동시 갱신
- [ ] **Step 2: 결과를 PR 본문에 기록** (확인 항목 체크리스트)

---

## Self-Review 결과

- 스펙 커버리지: 절 2 확정 4건(Task 5, 7), 절 3 데이터(Task 1, 2), 절 4 섹션-래퍼-로더 통합(Task 4, 5, 6), 절 5 로딩-검증(Task 3, 6), 절 6 상태-Meta(Task 5, 6, 7), 절 7 테스트(Task 1, 3), 절 9 수동 확인(Task 8) — 갭 없음
- 플레이스홀더: 없음(모든 코드 스텝에 실제 코드 포함)
- 타입 일관성: `VariantCombination`/`comboKey`/`ComboLoadStatus`/`resolveDetailFontPreview` 시그니처가 태스크 간 동일함을 교차 확인
