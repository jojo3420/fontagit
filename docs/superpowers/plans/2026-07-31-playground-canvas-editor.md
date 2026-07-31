# 플레이그라운드 캔버스 편집기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 폰트를 설치하지 않고 무료 서체 여러 개를 조합해 레이아웃을 실험하고 PNG로 내려받는 `/playground` 편집기를 만든다.

**Architecture:** 정적 내보내기(`output: "export"`) 구조라 서버 라우트가 없다. 서버 컴포넌트가 빌드 시점에 폰트 목록을 읽어 클라이언트 편집기에 props로 내려주고, 편집 상태의 단일 원본은 Fabric 캔버스 객체 트리다. React는 상태를 복제하지 않고 Fabric 이벤트를 구독해 패널 표시만 갱신한다. 계산 로직(폰트 로딩 정책, 되돌리기 스택, 정렬-스냅, 배율)은 전부 `lib/playground/` 아래 순수 함수로 빼서 Fabric 없이 테스트한다.

**Tech Stack:** Next.js 16.2.10 (App Router, static export), React 19.2.4, Fabric.js 7.4.0(신규), TypeScript, vitest 2 + jsdom + Testing Library, Playwright.

**설계 문서:** `docs/superpowers/specs/2026-07-30-playground-canvas-editor-design.md`
**리뷰 반영:** `docs/review/review-result-dual-20260730-205443.md` (Must 9 + Should 7)

## Global Constraints

- Fabric API를 쓰기 전 반드시 context7 MCP로 조회한다. 라이브러리 ID는 `/websites/fabricjs`. 조회 결과에 없는 메서드는 구현하지 말고 보고한다. 학습 데이터의 v5/v6 예제를 그대로 쓰면 안 된다.
- 이 계획에 이미 검증해 넣은 Fabric API(추가 조회 불필요): `new Canvas(el, options)`, `canvas.dispose(): Promise<boolean>`, `canvas.toDataURL({format, multiplier})`, `canvas.toObject(propertiesToInclude?)`, `canvas.loadFromJSON(json): Promise<Canvas>`, `canvas.requestRenderAll()`, `canvas.getActiveObjects(): FabricObject[]`, 이벤트 `selection:created` / `selection:updated` / `selection:cleared`, `text.initDimensions()`, `FabricObject.customProperties = string[]`.
- 폰트 식별자는 `slug` 하나로 통일한다. 캔버스 객체, 계측 파라미터, CTA 링크, 스냅샷 복원 키 모두 `slug`를 쓴다.
- self-host 폰트의 캔버스 패밀리는 반드시 `canvasFamilyOf(fontKey)`(`lib/fonts.ts:106`)를 쓴다. `familyOf()`는 CSS 변수(`var(--font-jua)`)를 반환하며 캔버스가 해석하지 못한다.
- 편집기 컴포넌트가 300줄을 넘으면 로직을 훅이나 `lib/playground/` 유틸로 추출한다.
- 스타일은 기존 관례대로 CSS Module(`*.module.css`)을 쓴다. 반응형 기준 폭은 900px.
- 모든 사용자 문구는 한국어. 로그는 `console.log` 금지.
- 테스트 실행은 `apps/web`에서 `pnpm test`(vitest run), 개별 파일은 `pnpm exec vitest run <경로>`.
- 커밋 형식: `<타입>: <설명> (#69)`.

---

## 파일 구조

### 신규 (순수 로직, Fabric 비의존)

| 파일 | 책임 |
|---|---|
| `lib/playground/types.ts` | 편집기 공용 타입(`PlaygroundFont`, `Box`, `CanvasSize` 등) |
| `lib/playground/fontCatalog.ts` | `Font[]`를 편집기용 `PlaygroundFont[]`로 변환, 렌더 불가 폰트 제외 |
| `lib/playground/textPresets.ts` | 제목/부제/본문 프리셋 값, 굵기 대체 규칙 |
| `lib/playground/fontLoader.ts` | 스타일시트 주입, 로딩 대기, 세대 토큰, 타임아웃 |
| `lib/playground/historyStack.ts` | 되돌리기/다시하기 스택과 복원 잠금 |
| `lib/playground/geometry.ts` | 정렬, 간격 균등, 스냅 판정, 프리셋 재배치, 내보내기 배율 |
| `lib/playground/canvasPresets.ts` | 캔버스 프리셋 정의와 자유 크기 검증 |
| `lib/analytics/events.ts` | GA4 커스텀 이벤트 전송 헬퍼(현재 코드베이스에 없음, 신규) |

### 신규 (UI)

| 파일 | 책임 |
|---|---|
| `app/playground/page.tsx` | 서버 컴포넌트. 폰트 목록을 읽어 편집기에 전달, 메타데이터 |
| `components/playground/PlaygroundEditor.tsx` | 편집기 조립, 화면 폭에 따른 배치 전환 |
| `components/playground/CanvasStage.tsx` | Fabric 캔버스 생성-정리, 줌-화면맞춤, 스냅 안내선 렌더 |
| `components/playground/EditorToolbar.tsx` | 텍스트 프리셋-도형 추가, 정렬, 되돌리기, 프리셋-줌 |
| `components/playground/FontPanel.tsx` | 사용 중 폰트, 검색, 분류 칩, 폰트 목록 |
| `components/playground/PropertiesPanel.tsx` | 선택 객체 속성 편집 |
| `components/playground/ExportMenu.tsx` | PNG 내보내기, 라이선스 고지 |
| `components/playground/useCanvasController.ts` | Fabric 인스턴스 수명, 이벤트 구독, 명령 API |
| `components/playground/useEditorShortcuts.ts` | 단축키 바인딩과 입력 컨텍스트 판별 |
| 각 컴포넌트별 `*.module.css` | 스타일 |

### 수정

| 파일 | 변경 |
|---|---|
| `components/Header.tsx` | 내비게이션에 플레이그라운드 링크 추가 |
| `app/fonts/[slug]/page.tsx` | 웹 렌더 가능 폰트에만 "이 폰트로 만들어보기" 버튼 |
| `e2e/smoke.spec.ts` | 라우트 목록에 `/playground` 추가 |
| `package.json` | fabric 의존성 추가 |

---

## Task 1: 편집기 폰트 카탈로그

**Files:**
- Create: `apps/web/lib/playground/types.ts`
- Create: `apps/web/lib/playground/fontCatalog.ts`
- Test: `apps/web/lib/playground/fontCatalog.test.ts`

**Interfaces:**
- Consumes: `resolveFontPreview(font)` from `@/lib/fontPreview` returns `{ fontFamily: string; stylesheetUrl: string | null }`. `canvasFamilyOf(fontKey: FontKey | null): string | null` from `@/lib/fonts`. `Font` type from `@/types/font`.
- Produces: `PlaygroundFont` 타입, `isPlayableFont(font): boolean`, `buildFontCatalog(fonts: Font[]): PlaygroundFont[]`.

- [ ] **Step 1: 타입 파일 작성**

`apps/web/lib/playground/types.ts`:

```ts
import type { Category } from "@/types/font";

export interface PlaygroundFont {
  slug: string;
  nameKo: string;
  nameEn: string;
  category: Category;
  availableWeights: number[];
  /** 캔버스에 그대로 넣을 수 있는 CSS font-family 값 (CSS 변수 금지) */
  canvasFamily: string;
  /** Google Fonts CSS2 주소. self-host 폰트는 null */
  stylesheetUrl: string | null;
  detailPath: string;
}

export interface CanvasSize {
  width: number;
  height: number;
}

export interface Box {
  id: string;
  left: number;
  top: number;
  width: number;
  height: number;
}
```

- [ ] **Step 2: 실패하는 테스트 작성**

`apps/web/lib/playground/fontCatalog.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildFontCatalog, isPlayableFont } from "./fontCatalog";
import type { Font } from "@/types/font";

function makeFont(overrides: Partial<Font>): Font {
  return {
    slug: "sample",
    nameKo: "샘플",
    nameEn: "Sample",
    fontKey: null,
    sourceTier: "A",
    tier: "free",
    category: "고딕",
    foundry: "테스트",
    availableWeights: [400, 700],
    moves: 0,
    license: {
      commercial: "yes",
      verifiedAt: "2026-07-30",
      type: "OFL",
      webfont: "included",
      redistribution: "yes",
    },
    officialUrl: "https://example.test",
    aliases: [],
    subsets: ["korean"],
    ...overrides,
  } as Font;
}

describe("isPlayableFont", () => {
  it("self-host 폰트는 렌더 가능하다", () => {
    expect(isPlayableFont(makeFont({ fontKey: "jua", sourceTier: "B" }))).toBe(true);
  });

  it("Tier A 폰트는 렌더 가능하다", () => {
    expect(isPlayableFont(makeFont({ sourceTier: "A" }))).toBe(true);
  });

  it("fontKey 없는 Tier B 폰트는 렌더 불가다", () => {
    expect(isPlayableFont(makeFont({ sourceTier: "B" }))).toBe(false);
  });
});

describe("buildFontCatalog", () => {
  it("렌더 불가 폰트를 제외한다", () => {
    const catalog = buildFontCatalog([
      makeFont({ slug: "a", sourceTier: "A" }),
      makeFont({ slug: "b", sourceTier: "B" }),
    ]);
    expect(catalog.map((f) => f.slug)).toEqual(["a"]);
  });

  it("self-host 폰트는 CSS 변수가 아닌 실제 폰트명을 쓴다", () => {
    const [entry] = buildFontCatalog([makeFont({ slug: "jua", fontKey: "jua" })]);
    expect(entry.canvasFamily).not.toContain("var(");
    expect(entry.stylesheetUrl).toBeNull();
  });

  it("Tier A 폰트는 스타일시트 주소를 갖는다", () => {
    const [entry] = buildFontCatalog([makeFont({ slug: "gothic", nameEn: "Noto Sans KR" })]);
    expect(entry.stylesheetUrl).toContain("fonts.googleapis.com");
    expect(entry.detailPath).toBe("/fonts/gothic");
  });

  it("굵기 목록이 비면 400을 채운다", () => {
    const [entry] = buildFontCatalog([makeFont({ availableWeights: [] })]);
    expect(entry.availableWeights).toEqual([400]);
  });
});
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/fontCatalog.test.ts`
Expected: FAIL — `Failed to resolve import "./fontCatalog"`

- [ ] **Step 4: 구현**

`apps/web/lib/playground/fontCatalog.ts`:

```ts
import type { Font } from "@/types/font";
import { canvasFamilyOf } from "@/lib/fonts";
import { resolveFontPreview } from "@/lib/fontPreview";
import type { PlaygroundFont } from "./types";

const FALLBACK_FAMILY = '"Pretendard Variable", "Pretendard", sans-serif';

export function isPlayableFont(font: Pick<Font, "fontKey" | "sourceTier">): boolean {
  return Boolean(font.fontKey) || font.sourceTier === "A";
}

export function buildFontCatalog(fonts: Font[]): PlaygroundFont[] {
  return fonts.filter(isPlayableFont).map((font) => {
    const preview = resolveFontPreview(font);
    const selfHostFamily = canvasFamilyOf(font.fontKey);
    const weights = font.availableWeights.length > 0 ? font.availableWeights : [400];

    return {
      slug: font.slug,
      nameKo: font.nameKo,
      nameEn: font.nameEn,
      category: font.category,
      availableWeights: [...weights].sort((a, b) => a - b),
      canvasFamily: selfHostFamily
        ? `${JSON.stringify(selfHostFamily)}, ${FALLBACK_FAMILY}`
        : preview.fontFamily,
      stylesheetUrl: preview.stylesheetUrl,
      detailPath: `/fonts/${font.slug}`,
    };
  });
}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/fontCatalog.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 6: 커밋**

```bash
git add apps/web/lib/playground/types.ts apps/web/lib/playground/fontCatalog.ts apps/web/lib/playground/fontCatalog.test.ts
git commit -m "feat: 플레이그라운드 폰트 카탈로그 변환 (#69)"
```

---

## Task 2: 텍스트 프리셋과 굵기 대체

**Files:**
- Create: `apps/web/lib/playground/textPresets.ts`
- Test: `apps/web/lib/playground/textPresets.test.ts`

**Interfaces:**
- Produces: `TextPresetName = "heading" | "subheading" | "body"`, `TEXT_PRESETS: Record<TextPresetName, TextPreset>`, `resolveWeight(requested: number, available: number[]): number`.

- [ ] **Step 1: 실패하는 테스트 작성**

`apps/web/lib/playground/textPresets.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { TEXT_PRESETS, resolveWeight } from "./textPresets";

describe("resolveWeight", () => {
  it("요청한 굵기가 있으면 그대로 쓴다", () => {
    expect(resolveWeight(700, [400, 700])).toBe(700);
  });

  it("없으면 가장 가까운 값을 쓴다", () => {
    expect(resolveWeight(700, [400, 500])).toBe(500);
  });

  it("거리가 같으면 굵은 쪽을 쓴다", () => {
    expect(resolveWeight(500, [400, 600])).toBe(600);
  });

  it("굵기가 하나뿐이면 그 값을 쓴다", () => {
    expect(resolveWeight(700, [400])).toBe(400);
  });

  it("목록이 비면 400을 쓴다", () => {
    expect(resolveWeight(700, [])).toBe(400);
  });
});

describe("TEXT_PRESETS", () => {
  it("제목-부제-본문 세 종을 제공한다", () => {
    expect(Object.keys(TEXT_PRESETS)).toEqual(["heading", "subheading", "body"]);
  });

  it("제목이 본문보다 크다", () => {
    expect(TEXT_PRESETS.heading.fontSize).toBeGreaterThan(TEXT_PRESETS.body.fontSize);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/textPresets.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`apps/web/lib/playground/textPresets.ts`:

```ts
export type TextPresetName = "heading" | "subheading" | "body";

export interface TextPreset {
  label: string;
  text: string;
  fontSize: number;
  fontWeight: number;
  lineHeight: number;
}

/** 1080x1080 캔버스 기준값. 다른 프리셋에서는 캔버스 배율에 비례해 조정한다. */
export const TEXT_PRESETS: Record<TextPresetName, TextPreset> = {
  heading: { label: "제목", text: "제목을 입력하세요", fontSize: 72, fontWeight: 700, lineHeight: 1.3 },
  subheading: { label: "부제", text: "부제를 입력하세요", fontSize: 40, fontWeight: 500, lineHeight: 1.4 },
  body: { label: "본문", text: "본문을 입력하세요", fontSize: 24, fontWeight: 400, lineHeight: 1.6 },
};

export function resolveWeight(requested: number, available: number[]): number {
  if (available.length === 0) return 400;
  if (available.includes(requested)) return requested;

  return available.reduce((best, weight) => {
    const bestDistance = Math.abs(best - requested);
    const distance = Math.abs(weight - requested);
    if (distance < bestDistance) return weight;
    if (distance === bestDistance) return Math.max(best, weight);
    return best;
  }, available[0]);
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/textPresets.test.ts`
Expected: PASS (7 tests)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/playground/textPresets.ts apps/web/lib/playground/textPresets.test.ts
git commit -m "feat: 텍스트 프리셋과 굵기 대체 규칙 (#69)"
```

---

## Task 3: 캔버스 프리셋과 자유 크기 검증

**Files:**
- Create: `apps/web/lib/playground/canvasPresets.ts`
- Test: `apps/web/lib/playground/canvasPresets.test.ts`

**Interfaces:**
- Consumes: `CanvasSize` from `./types`.
- Produces: `CANVAS_PRESETS: CanvasPreset[]`, `validateCustomSize(width: unknown, height: unknown): ValidationResult`.

- [ ] **Step 1: 실패하는 테스트 작성**

`apps/web/lib/playground/canvasPresets.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { CANVAS_PRESETS, validateCustomSize } from "./canvasPresets";

describe("CANVAS_PRESETS", () => {
  it("유튜브 썸네일, 정사각, 채널아트 세 종을 제공한다", () => {
    expect(CANVAS_PRESETS.map((p) => p.id)).toEqual(["youtube", "square", "channel"]);
    expect(CANVAS_PRESETS[0].size).toEqual({ width: 1280, height: 720 });
    expect(CANVAS_PRESETS[1].size).toEqual({ width: 1080, height: 1080 });
    expect(CANVAS_PRESETS[2].size).toEqual({ width: 2560, height: 1440 });
  });
});

describe("validateCustomSize", () => {
  it("정상 범위를 통과시킨다", () => {
    expect(validateCustomSize(800, 600)).toEqual({ ok: true, size: { width: 800, height: 600 } });
  });

  it("최소값 미만을 거부한다", () => {
    expect(validateCustomSize(199, 600)).toEqual({
      ok: false,
      message: "가로는 200에서 4096 사이로 입력해주세요",
    });
  });

  it("최대값 초과를 거부한다", () => {
    expect(validateCustomSize(800, 4097)).toEqual({
      ok: false,
      message: "세로는 200에서 4096 사이로 입력해주세요",
    });
  });

  it("소수와 문자를 거부한다", () => {
    expect(validateCustomSize(800.5, 600).ok).toBe(false);
    expect(validateCustomSize("팔백", 600).ok).toBe(false);
    expect(validateCustomSize("", 600).ok).toBe(false);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/canvasPresets.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`apps/web/lib/playground/canvasPresets.ts`:

```ts
import type { CanvasSize } from "./types";

export interface CanvasPreset {
  id: "youtube" | "square" | "channel";
  label: string;
  size: CanvasSize;
}

export const CANVAS_PRESETS: CanvasPreset[] = [
  { id: "youtube", label: "유튜브 썸네일", size: { width: 1280, height: 720 } },
  { id: "square", label: "정사각", size: { width: 1080, height: 1080 } },
  { id: "channel", label: "채널아트", size: { width: 2560, height: 1440 } },
];

export const DEFAULT_PRESET_ID = "square";
export const MIN_CANVAS_SIDE = 200;
export const MAX_CANVAS_SIDE = 4096;

export type ValidationResult =
  | { ok: true; size: CanvasSize }
  | { ok: false; message: string };

function isValidSide(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= MIN_CANVAS_SIDE &&
    value <= MAX_CANVAS_SIDE
  );
}

export function validateCustomSize(width: unknown, height: unknown): ValidationResult {
  if (!isValidSide(width)) {
    return { ok: false, message: `가로는 ${MIN_CANVAS_SIDE}에서 ${MAX_CANVAS_SIDE} 사이로 입력해주세요` };
  }
  if (!isValidSide(height)) {
    return { ok: false, message: `세로는 ${MIN_CANVAS_SIDE}에서 ${MAX_CANVAS_SIDE} 사이로 입력해주세요` };
  }
  return { ok: true, size: { width, height } };
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/canvasPresets.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/playground/canvasPresets.ts apps/web/lib/playground/canvasPresets.test.ts
git commit -m "feat: 캔버스 프리셋과 자유 크기 검증 (#69)"
```

---

## Task 4: 폰트 로딩 정책

**Files:**
- Create: `apps/web/lib/playground/fontLoader.ts`
- Test: `apps/web/lib/playground/fontLoader.test.ts`

**Interfaces:**
- Consumes: `PlaygroundFont` from `./types`.
- Produces: `createFontLoader(deps: FontLoaderDeps): FontLoader`, `FontLoadOutcome = "ready" | "failed" | "superseded"`.

설계 근거: 스타일시트는 같은 주소를 한 번만 주입하고, 실제 글자가 준비될 때까지 기다린 뒤 반영한다. 기다리지 않으면 글자 폭이 이전 폰트 기준으로 남아 배치가 틀어진다. 연속 클릭 시 늦게 도착한 응답이 최신 선택을 덮어쓰지 않도록 대상 객체별 세대 토큰을 둔다.

- [ ] **Step 1: 실패하는 테스트 작성**

`apps/web/lib/playground/fontLoader.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { createFontLoader } from "./fontLoader";
import type { PlaygroundFont } from "./types";

function makeFont(slug: string, stylesheetUrl: string | null = "https://fonts.googleapis.com/css2?family=Test"): PlaygroundFont {
  return {
    slug,
    nameKo: slug,
    nameEn: slug,
    category: "고딕",
    availableWeights: [400],
    canvasFamily: `"${slug}", sans-serif`,
    stylesheetUrl,
    detailPath: `/fonts/${slug}`,
  };
}

describe("createFontLoader", () => {
  it("self-host 폰트는 주입 없이 즉시 준비된다", async () => {
    const injectStylesheet = vi.fn();
    const loader = createFontLoader({
      injectStylesheet,
      loadFace: vi.fn(),
      timeoutMs: 5000,
    });

    const result = await loader.request(makeFont("jua", null), "obj-1");

    expect(result).toBe("ready");
    expect(injectStylesheet).not.toHaveBeenCalled();
  });

  it("같은 주소는 한 번만 주입한다", async () => {
    const injectStylesheet = vi.fn();
    const loader = createFontLoader({
      injectStylesheet,
      loadFace: vi.fn().mockResolvedValue(undefined),
      timeoutMs: 5000,
    });

    await loader.request(makeFont("a"), "obj-1");
    await loader.request(makeFont("a"), "obj-2");

    expect(injectStylesheet).toHaveBeenCalledTimes(1);
  });

  it("같은 객체에 새 요청이 오면 이전 요청은 폐기된다", async () => {
    let resolveFirst: () => void = () => {};
    const loadFace = vi
      .fn()
      .mockImplementationOnce(() => new Promise<void>((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce(undefined);

    const loader = createFontLoader({ injectStylesheet: vi.fn(), loadFace, timeoutMs: 5000 });

    const first = loader.request(makeFont("a"), "obj-1");
    const second = loader.request(makeFont("b"), "obj-1");
    resolveFirst();

    expect(await first).toBe("superseded");
    expect(await second).toBe("ready");
  });

  it("다른 객체 요청은 서로 폐기하지 않는다", async () => {
    const loader = createFontLoader({
      injectStylesheet: vi.fn(),
      loadFace: vi.fn().mockResolvedValue(undefined),
      timeoutMs: 5000,
    });

    const [a, b] = await Promise.all([
      loader.request(makeFont("a"), "obj-1"),
      loader.request(makeFont("b"), "obj-2"),
    ]);

    expect(a).toBe("ready");
    expect(b).toBe("ready");
  });

  it("로딩이 실패하면 failed를 돌려준다", async () => {
    const loader = createFontLoader({
      injectStylesheet: vi.fn(),
      loadFace: vi.fn().mockRejectedValue(new Error("network")),
      timeoutMs: 5000,
    });

    expect(await loader.request(makeFont("a"), "obj-1")).toBe("failed");
  });

  it("시간이 초과되면 failed를 돌려준다", async () => {
    vi.useFakeTimers();
    const loader = createFontLoader({
      injectStylesheet: vi.fn(),
      loadFace: vi.fn().mockImplementation(() => new Promise(() => {})),
      timeoutMs: 5000,
    });

    const pending = loader.request(makeFont("a"), "obj-1");
    await vi.advanceTimersByTimeAsync(5000);

    expect(await pending).toBe("failed");
    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/fontLoader.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`apps/web/lib/playground/fontLoader.ts`:

```ts
import type { PlaygroundFont } from "./types";

export type FontLoadOutcome = "ready" | "failed" | "superseded";

export interface FontLoaderDeps {
  injectStylesheet: (url: string) => void;
  loadFace: (spec: string) => Promise<unknown>;
  timeoutMs: number;
}

export interface FontLoader {
  request: (font: PlaygroundFont, targetId: string) => Promise<FontLoadOutcome>;
}

export function createFontLoader(deps: FontLoaderDeps): FontLoader {
  const injected = new Set<string>();
  const generations = new Map<string, number>();

  async function request(font: PlaygroundFont, targetId: string): Promise<FontLoadOutcome> {
    const generation = (generations.get(targetId) ?? 0) + 1;
    generations.set(targetId, generation);

    if (!font.stylesheetUrl) return "ready";

    if (!injected.has(font.stylesheetUrl)) {
      injected.add(font.stylesheetUrl);
      deps.injectStylesheet(font.stylesheetUrl);
    }

    const spec = `400 16px ${font.canvasFamily}`;
    const loaded = await withTimeout(deps.loadFace(spec), deps.timeoutMs);

    if (generations.get(targetId) !== generation) return "superseded";
    return loaded ? "ready" : "failed";
  }

  return { request };
}

async function withTimeout(promise: Promise<unknown>, timeoutMs: number): Promise<boolean> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<boolean>((resolve) => {
    timer = setTimeout(() => resolve(false), timeoutMs);
  });

  try {
    return await Promise.race([promise.then(() => true).catch(() => false), timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/fontLoader.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/playground/fontLoader.ts apps/web/lib/playground/fontLoader.test.ts
git commit -m "feat: 폰트 로딩 정책 (세대 토큰, 타임아웃) (#69)"
```

---

## Task 5: 되돌리기 스택

**Files:**
- Create: `apps/web/lib/playground/historyStack.ts`
- Test: `apps/web/lib/playground/historyStack.test.ts`

**Interfaces:**
- Produces: `createHistoryStack<T>(limit?: number): HistoryStack<T>` with `push(snapshot: T): void`, `undo(): T | null`, `redo(): T | null`, `canUndo(): boolean`, `canRedo(): boolean`, `beginRestore(): boolean`, `endRestore(): void`, `size(): number`.

설계 근거: 복원은 비동기라(Fabric `loadFromJSON`이 Promise 반환) 연타 시 캔버스와 스택이 어긋난다. `beginRestore()`가 false를 돌려주면 호출자는 그 요청을 버린다.

- [ ] **Step 1: 실패하는 테스트 작성**

`apps/web/lib/playground/historyStack.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { createHistoryStack } from "./historyStack";

describe("createHistoryStack", () => {
  it("최초 상태에서는 되돌릴 것이 없다", () => {
    const stack = createHistoryStack<string>();
    expect(stack.canUndo()).toBe(false);
    expect(stack.undo()).toBeNull();
  });

  it("직전 상태로 되돌린다", () => {
    const stack = createHistoryStack<string>();
    stack.push("A");
    stack.push("B");
    expect(stack.undo()).toBe("A");
  });

  it("되돌린 뒤 다시하기가 가능하다", () => {
    const stack = createHistoryStack<string>();
    stack.push("A");
    stack.push("B");
    stack.undo();
    expect(stack.redo()).toBe("B");
  });

  it("되돌린 뒤 새로 쌓으면 다시하기가 사라진다", () => {
    const stack = createHistoryStack<string>();
    stack.push("A");
    stack.push("B");
    stack.undo();
    stack.push("C");
    expect(stack.canRedo()).toBe(false);
  });

  it("깊이 상한을 넘으면 오래된 것부터 버린다", () => {
    const stack = createHistoryStack<string>(3);
    stack.push("A");
    stack.push("B");
    stack.push("C");
    stack.push("D");
    expect(stack.size()).toBe(3);
    expect(stack.undo()).toBe("C");
    expect(stack.undo()).toBe("B");
    expect(stack.undo()).toBeNull();
  });

  it("복원 중에는 다음 복원을 막는다", () => {
    const stack = createHistoryStack<string>();
    expect(stack.beginRestore()).toBe(true);
    expect(stack.beginRestore()).toBe(false);
    stack.endRestore();
    expect(stack.beginRestore()).toBe(true);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/historyStack.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`apps/web/lib/playground/historyStack.ts`:

```ts
export interface HistoryStack<T> {
  push: (snapshot: T) => void;
  undo: () => T | null;
  redo: () => T | null;
  canUndo: () => boolean;
  canRedo: () => boolean;
  beginRestore: () => boolean;
  endRestore: () => void;
  size: () => number;
}

export const DEFAULT_HISTORY_LIMIT = 30;

export function createHistoryStack<T>(limit: number = DEFAULT_HISTORY_LIMIT): HistoryStack<T> {
  const entries: T[] = [];
  let cursor = -1;
  let restoring = false;

  return {
    push(snapshot) {
      entries.splice(cursor + 1);
      entries.push(snapshot);
      if (entries.length > limit) entries.shift();
      cursor = entries.length - 1;
    },
    undo() {
      if (cursor <= 0) return null;
      cursor -= 1;
      return entries[cursor];
    },
    redo() {
      if (cursor >= entries.length - 1) return null;
      cursor += 1;
      return entries[cursor];
    },
    canUndo: () => cursor > 0,
    canRedo: () => cursor < entries.length - 1,
    beginRestore() {
      if (restoring) return false;
      restoring = true;
      return true;
    },
    endRestore() {
      restoring = false;
    },
    size: () => entries.length,
  };
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/historyStack.test.ts`
Expected: PASS (6 tests)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/playground/historyStack.ts apps/web/lib/playground/historyStack.test.ts
git commit -m "feat: 되돌리기 스택과 복원 잠금 (#69)"
```

---

## Task 6: 정렬, 스냅, 재배치, 내보내기 배율

**Files:**
- Create: `apps/web/lib/playground/geometry.ts`
- Test: `apps/web/lib/playground/geometry.test.ts`

**Interfaces:**
- Consumes: `Box`, `CanvasSize` from `./types`.
- Produces: `alignBoxes(boxes: Box[], mode: AlignMode, canvas: CanvasSize): Box[]`, `distributeBoxes(boxes: Box[], axis: "x" | "y"): Box[]`, `findSnap(moving: Box, others: Box[], canvas: CanvasSize, threshold?: number): SnapResult`, `rescaleBoxes(boxes: Box[], from: CanvasSize, to: CanvasSize): Box[]`, `exportMultiplier(canvas: CanvasSize, isMobile: boolean): number`.

설계 근거: 좌표(left/top)가 아니라 실제 경계 상자를 기준으로 맞춘다. 회전과 테두리가 있는 객체를 좌표로 맞추면 눈으로 볼 때 어긋난다. 프리셋 재배치는 객체 중심을 기준점으로 하고 가로세로 배율 중 작은 값을 크기에 적용한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`apps/web/lib/playground/geometry.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { alignBoxes, distributeBoxes, exportMultiplier, findSnap, rescaleBoxes } from "./geometry";
import type { Box } from "./types";

const canvas = { width: 1000, height: 1000 };

function box(id: string, left: number, top: number, width = 100, height = 50): Box {
  return { id, left, top, width, height };
}

describe("alignBoxes", () => {
  it("객체가 하나면 캔버스 기준으로 맞춘다", () => {
    const [result] = alignBoxes([box("a", 10, 10)], "center", canvas);
    expect(result.left).toBe(450);
  });

  it("여러 개면 선택 영역 기준으로 왼쪽을 맞춘다", () => {
    const result = alignBoxes([box("a", 100, 0), box("b", 300, 0)], "left", canvas);
    expect(result.map((b) => b.left)).toEqual([100, 100]);
  });

  it("아래 맞춤은 가장 아래 가장자리에 붙인다", () => {
    const result = alignBoxes([box("a", 0, 100), box("b", 0, 300)], "bottom", canvas);
    expect(result.map((b) => b.top)).toEqual([300, 300]);
  });
});

describe("distributeBoxes", () => {
  it("가로 간격을 균등하게 만든다", () => {
    const result = distributeBoxes(
      [box("a", 0, 0, 100), box("b", 150, 0, 100), box("c", 500, 0, 100)],
      "x"
    );
    expect(result.map((b) => b.left)).toEqual([0, 250, 500]);
  });

  it("객체가 셋 미만이면 그대로 둔다", () => {
    const boxes = [box("a", 0, 0), box("b", 200, 0)];
    expect(distributeBoxes(boxes, "x")).toEqual(boxes);
  });
});

describe("findSnap", () => {
  it("캔버스 중앙에 가까우면 흡착한다", () => {
    const result = findSnap(box("a", 448, 0, 100, 50), [], canvas);
    expect(result.dx).toBe(2);
    expect(result.guides).toContainEqual({ axis: "x", position: 500 });
  });

  it("다른 객체의 왼쪽 가장자리에 흡착한다", () => {
    const result = findSnap(box("a", 203, 400, 100, 50), [box("b", 200, 0, 100, 50)], canvas);
    expect(result.dx).toBe(-3);
  });

  it("임계 거리를 넘으면 흡착하지 않는다", () => {
    const result = findSnap(box("a", 420, 400, 100, 50), [box("b", 200, 0, 100, 50)], canvas);
    expect(result.dx).toBe(0);
    expect(result.guides).toEqual([]);
  });
});

describe("rescaleBoxes", () => {
  it("중심을 기준으로 비례 재배치한다", () => {
    const [result] = rescaleBoxes([box("a", 450, 450, 100, 100)], canvas, { width: 500, height: 500 });
    expect(result.width).toBe(50);
    expect(result.left).toBe(225);
  });

  it("비율이 다르면 작은 배율을 쓴다", () => {
    const [result] = rescaleBoxes([box("a", 0, 0, 100, 100)], canvas, { width: 2000, height: 1000 });
    expect(result.width).toBe(100);
  });
});

describe("exportMultiplier", () => {
  it("여유가 있으면 2배를 쓴다", () => {
    expect(exportMultiplier({ width: 1080, height: 1080 }, false)).toBe(2);
  });

  it("상한을 넘으면 축소한다", () => {
    expect(exportMultiplier({ width: 4096, height: 4096 }, false)).toBe(1);
  });

  it("모바일은 항상 1배 이하다", () => {
    expect(exportMultiplier({ width: 1080, height: 1080 }, true)).toBe(1);
  });

  it("모바일에서 상한을 넘으면 1보다 작아진다", () => {
    expect(exportMultiplier({ width: 2560, height: 1440 }, true)).toBeLessThan(1);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/geometry.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`apps/web/lib/playground/geometry.ts`:

```ts
import type { Box, CanvasSize } from "./types";

export type AlignMode = "left" | "center" | "right" | "top" | "middle" | "bottom";

export interface Guide {
  axis: "x" | "y";
  position: number;
}

export interface SnapResult {
  dx: number;
  dy: number;
  guides: Guide[];
}

export const SNAP_THRESHOLD = 6;
export const DESKTOP_PIXEL_CAP = 16_000_000;
export const MOBILE_PIXEL_CAP = 4_000_000;

export function alignBoxes(boxes: Box[], mode: AlignMode, canvas: CanvasSize): Box[] {
  if (boxes.length === 0) return boxes;

  const bounds =
    boxes.length === 1
      ? { left: 0, top: 0, right: canvas.width, bottom: canvas.height }
      : {
          left: Math.min(...boxes.map((b) => b.left)),
          top: Math.min(...boxes.map((b) => b.top)),
          right: Math.max(...boxes.map((b) => b.left + b.width)),
          bottom: Math.max(...boxes.map((b) => b.top + b.height)),
        };

  return boxes.map((b) => {
    switch (mode) {
      case "left":
        return { ...b, left: bounds.left };
      case "center":
        return { ...b, left: (bounds.left + bounds.right) / 2 - b.width / 2 };
      case "right":
        return { ...b, left: bounds.right - b.width };
      case "top":
        return { ...b, top: bounds.top };
      case "middle":
        return { ...b, top: (bounds.top + bounds.bottom) / 2 - b.height / 2 };
      case "bottom":
        return { ...b, top: bounds.bottom - b.height };
    }
  });
}

export function distributeBoxes(boxes: Box[], axis: "x" | "y"): Box[] {
  if (boxes.length < 3) return boxes;

  const key = axis === "x" ? "left" : "top";
  const sorted = [...boxes].sort((a, b) => a[key] - b[key]);
  const first = sorted[0][key];
  const last = sorted[sorted.length - 1][key];
  const step = (last - first) / (sorted.length - 1);

  const moved = new Map<string, number>();
  sorted.forEach((b, index) => moved.set(b.id, first + step * index));

  return boxes.map((b) => ({ ...b, [key]: moved.get(b.id) ?? b[key] }) as Box);
}

export function findSnap(
  moving: Box,
  others: Box[],
  canvas: CanvasSize,
  threshold: number = SNAP_THRESHOLD
): SnapResult {
  const movingX = [moving.left, moving.left + moving.width / 2, moving.left + moving.width];
  const movingY = [moving.top, moving.top + moving.height / 2, moving.top + moving.height];

  const targetX = [0, canvas.width / 2, canvas.width];
  const targetY = [0, canvas.height / 2, canvas.height];
  others.forEach((b) => {
    targetX.push(b.left, b.left + b.width / 2, b.left + b.width);
    targetY.push(b.top, b.top + b.height / 2, b.top + b.height);
  });

  const guides: Guide[] = [];
  const dx = closestDelta(movingX, targetX, threshold, (position) => guides.push({ axis: "x", position }));
  const dy = closestDelta(movingY, targetY, threshold, (position) => guides.push({ axis: "y", position }));

  return { dx, dy, guides };
}

function closestDelta(
  sources: number[],
  targets: number[],
  threshold: number,
  onSnap: (position: number) => void
): number {
  let best = 0;
  let bestDistance = threshold + 1;
  let bestTarget = 0;

  sources.forEach((source) => {
    targets.forEach((target) => {
      const distance = Math.abs(target - source);
      if (distance <= threshold && distance < bestDistance) {
        bestDistance = distance;
        best = target - source;
        bestTarget = target;
      }
    });
  });

  if (bestDistance <= threshold) onSnap(bestTarget);
  return best;
}

export function rescaleBoxes(boxes: Box[], from: CanvasSize, to: CanvasSize): Box[] {
  const scaleX = to.width / from.width;
  const scaleY = to.height / from.height;
  const scale = Math.min(scaleX, scaleY);

  return boxes.map((b) => {
    const centerX = (b.left + b.width / 2) / from.width;
    const centerY = (b.top + b.height / 2) / from.height;
    const width = b.width * scale;
    const height = b.height * scale;

    return {
      ...b,
      width,
      height,
      left: centerX * to.width - width / 2,
      top: centerY * to.height - height / 2,
    };
  });
}

export function exportMultiplier(canvas: CanvasSize, isMobile: boolean): number {
  const cap = isMobile ? MOBILE_PIXEL_CAP : DESKTOP_PIXEL_CAP;
  const maxMultiplier = isMobile ? 1 : 2;
  const pixels = canvas.width * canvas.height;
  const allowed = Math.sqrt(cap / pixels);

  return Math.min(maxMultiplier, allowed);
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/geometry.test.ts`
Expected: PASS (13 tests)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/playground/geometry.ts apps/web/lib/playground/geometry.test.ts
git commit -m "feat: 정렬-스냅-재배치-배율 계산 (#69)"
```

---

## Task 7: GA4 커스텀 이벤트 헬퍼

**Files:**
- Create: `apps/web/lib/analytics/events.ts`
- Test: `apps/web/lib/analytics/events.test.ts`

**Interfaces:**
- Produces: `trackEvent(name: string, params?: Record<string, string | number>): void`.

배경: 현재 코드베이스에 커스텀 이벤트를 보내는 코드가 없다. `gtag`는 `components/Analytics/GoogleAnalytics.tsx`에서 페이지뷰용으로만 설정된다. 설계 문서가 언급한 `font_download_clicked`도 아직 구현돼 있지 않다.

- [ ] **Step 1: 실패하는 테스트 작성**

`apps/web/lib/analytics/events.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { trackEvent } from "./events";

afterEach(() => {
  delete (window as unknown as { gtag?: unknown }).gtag;
  vi.restoreAllMocks();
});

describe("trackEvent", () => {
  it("gtag가 있으면 이벤트를 보낸다", () => {
    const gtag = vi.fn();
    (window as unknown as { gtag: unknown }).gtag = gtag;

    trackEvent("playground_font_applied", { font_slug: "jua", applied_count: 3 });

    expect(gtag).toHaveBeenCalledWith("event", "playground_font_applied", {
      font_slug: "jua",
      applied_count: 3,
    });
  });

  it("gtag가 없으면 조용히 넘어간다", () => {
    expect(() => trackEvent("playground_export_png")).not.toThrow();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/analytics/events.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`apps/web/lib/analytics/events.ts`:

```ts
type EventParams = Record<string, string | number>;

type GtagWindow = Window & {
  gtag?: (command: "event", name: string, params?: EventParams) => void;
};

export function trackEvent(name: string, params?: EventParams): void {
  if (typeof window === "undefined") return;
  const gtag = (window as GtagWindow).gtag;
  if (!gtag) return;
  gtag("event", name, params);
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/analytics/events.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/analytics/events.ts apps/web/lib/analytics/events.test.ts
git commit -m "feat: GA4 커스텀 이벤트 헬퍼 (#69)"
```

---

## Task 8: Fabric 설치와 캔버스 무대

**Files:**
- Modify: `apps/web/package.json` (의존성 추가)
- Create: `apps/web/components/playground/useCanvasController.ts`
- Create: `apps/web/components/playground/CanvasStage.tsx`
- Create: `apps/web/components/playground/CanvasStage.module.css`
- Create: `apps/web/app/playground/page.tsx`
- Create: `apps/web/components/playground/PlaygroundEditor.tsx`
- Create: `apps/web/components/playground/PlaygroundEditor.module.css`

**Interfaces:**
- Consumes: `buildFontCatalog` (Task 1), `CANVAS_PRESETS` / `DEFAULT_PRESET_ID` (Task 3), `getAllFonts()` from `@/lib/db/fonts`.
- Produces: `useCanvasController(options): CanvasController` with `attach(el: HTMLCanvasElement): void`, `getCanvas(): Canvas | null`, `zoomToFit(): void`, `setZoom(ratio: number): void`, `zoom: number`, `selection: SelectionState`.

- [ ] **Step 1: Fabric 설치**

```bash
cd apps/web && pnpm add fabric@^7.4.0
```

확인: `pnpm list fabric` 출력에 `fabric 7.4.x`가 보여야 한다.

- [ ] **Step 2: context7로 v7 변경점 조회 후 메모 작성**

context7 MCP(`/websites/fabricjs`)로 다음을 순서대로 조회하고, 결과를 `apps/web/components/playground/fabric-v7-notes.md`에 정리한다.

1. `Canvas` 생성자 옵션(`selection`, `preserveObjectStacking`, `backgroundColor`)
2. 객체 추가/삭제(`add`, `remove`)와 활성 선택 해제(`discardActiveObject`)
3. `Textbox` 생성자 옵션과 편집 상태 판별 속성
4. `Rect`, `Line` 생성자 옵션
5. 객체 경계 상자 조회 메서드
6. 뷰포트 변환(`setViewportTransform` 또는 `setZoom`)

메모에는 조회로 확인한 시그니처만 적는다. 확인되지 않은 것은 "미확인"으로 남기고 그 API에 의존하는 구현을 시작하지 않는다.

- [ ] **Step 3: 캔버스 컨트롤러 구현**

`apps/web/components/playground/useCanvasController.ts`. Step 2 메모에서 확인한 시그니처만 사용한다. 아래는 이 계획에서 이미 검증한 API로만 구성한 골격이다.

```ts
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Canvas, FabricObject } from "fabric";
import type { CanvasSize } from "@/lib/playground/types";

export interface SelectionState {
  ids: string[];
  kind: "none" | "text" | "shape" | "mixed";
}

export interface CanvasController {
  attach: (el: HTMLCanvasElement | null) => void;
  getCanvas: () => Canvas | null;
  selection: SelectionState;
  zoom: number;
  setZoom: (ratio: number) => void;
  zoomToFit: () => void;
}

export function useCanvasController(size: CanvasSize, viewportWidth: number): CanvasController {
  const canvasRef = useRef<Canvas | null>(null);
  const [selection, setSelection] = useState<SelectionState>({ ids: [], kind: "none" });
  const [zoom, setZoomState] = useState(1);

  const attach = useCallback((el: HTMLCanvasElement | null) => {
    if (!el) return;
    let disposed = false;

    void import("fabric").then(({ Canvas }) => {
      if (disposed) return;
      const canvas = new Canvas(el, {
        width: size.width,
        height: size.height,
        backgroundColor: "#ffffff",
      });

      const syncSelection = () => {
        const active = canvas.getActiveObjects();
        setSelection(toSelectionState(active));
      };

      canvas.on("selection:created", syncSelection);
      canvas.on("selection:updated", syncSelection);
      canvas.on("selection:cleared", syncSelection);

      canvasRef.current = canvas;
    });

    return () => {
      disposed = true;
    };
  }, [size.height, size.width]);

  useEffect(() => {
    return () => {
      const canvas = canvasRef.current;
      canvasRef.current = null;
      void canvas?.dispose();
    };
  }, []);

  const zoomToFit = useCallback(() => {
    const ratio = Math.min(1, viewportWidth / size.width);
    setZoomState(ratio);
  }, [size.width, viewportWidth]);

  const setZoom = useCallback((ratio: number) => {
    setZoomState(Math.min(2, Math.max(0.25, ratio)));
  }, []);

  return {
    attach,
    getCanvas: () => canvasRef.current,
    selection,
    zoom,
    setZoom,
    zoomToFit,
  };
}

function toSelectionState(objects: FabricObject[]): SelectionState {
  if (objects.length === 0) return { ids: [], kind: "none" };
  const ids = objects.map((o) => String((o as { id?: string }).id ?? ""));
  const kinds = new Set(objects.map((o) => o.type));
  if (kinds.size > 1) return { ids, kind: "mixed" };
  return { ids, kind: kinds.has("textbox") ? "text" : "shape" };
}
```

`dispose()`가 Promise를 반환하므로 반환값을 버리되 호출은 반드시 한다. 정리하지 않으면 개발 모드 이중 마운트에서 캔버스와 이벤트 핸들러가 중복 생성된다.

- [ ] **Step 4: 페이지와 편집기 껍데기 작성**

`apps/web/app/playground/page.tsx` (서버 컴포넌트):

```tsx
import type { Metadata } from "next";
import { getAllFonts } from "@/lib/db/fonts";
import { buildFontCatalog } from "@/lib/playground/fontCatalog";
import { PlaygroundEditor } from "@/components/playground/PlaygroundEditor";

export const metadata: Metadata = {
  title: "플레이그라운드 - 무료 폰트로 바로 디자인 실험",
  description: "설치 없이 무료 한글 폰트를 조합해 레이아웃과 배치를 실험하고 이미지로 저장하세요.",
};

export default async function PlaygroundPage() {
  const fonts = await getAllFonts();
  const catalog = buildFontCatalog(fonts);

  return <PlaygroundEditor fonts={catalog} />;
}
```

`apps/web/components/playground/PlaygroundEditor.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import type { PlaygroundFont } from "@/lib/playground/types";
import { CANVAS_PRESETS } from "@/lib/playground/canvasPresets";
import { CanvasStage } from "./CanvasStage";
import styles from "./PlaygroundEditor.module.css";

const MOBILE_BREAKPOINT = 900;

export function PlaygroundEditor({ fonts }: { fonts: PlaygroundFont[] }) {
  const [size, setSize] = useState(CANVAS_PRESETS[1].size);
  const [isNarrow, setIsNarrow] = useState(false);

  useEffect(() => {
    const query = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const sync = () => setIsNarrow(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  return (
    <div className={isNarrow ? styles.narrow : styles.wide} data-font-count={fonts.length}>
      <CanvasStage size={size} onSizeChange={setSize} />
    </div>
  );
}
```

`apps/web/components/playground/CanvasStage.tsx`:

```tsx
"use client";

import { useCanvasController } from "./useCanvasController";
import type { CanvasSize } from "@/lib/playground/types";
import styles from "./CanvasStage.module.css";

export function CanvasStage({
  size,
  onSizeChange,
}: {
  size: CanvasSize;
  onSizeChange: (size: CanvasSize) => void;
}) {
  const controller = useCanvasController(size, 800);

  return (
    <div className={styles.stage}>
      <canvas ref={controller.attach} aria-label="디자인 캔버스" />
      <p className={styles.hint} data-size={`${size.width}x${size.height}`}>
        캔버스 {size.width} x {size.height}
      </p>
      <button type="button" onClick={() => onSizeChange(size)} className={styles.srOnly}>
        캔버스 크기 유지
      </button>
    </div>
  );
}
```

CSS Module 두 개는 레이아웃만 담는다. `PlaygroundEditor.module.css`는 `.wide`를 `display: grid; grid-template-columns: 180px 1fr 150px;`로, `.narrow`를 `display: flex; flex-direction: column;`으로 둔다. `CanvasStage.module.css`의 `.stage`에는 `touch-action: none;`을 넣는다. 이 속성이 없으면 모바일에서 객체를 끌 때 페이지가 함께 스크롤된다.

- [ ] **Step 5: 빌드로 검증**

Run: `cd apps/web && pnpm build 2>&1 | tail -30`
Expected: 빌드 성공. 출력에 `/playground` 라우트가 보여야 한다.

- [ ] **Step 6: 커밋**

```bash
git add apps/web/package.json apps/web/app/playground apps/web/components/playground ../../pnpm-lock.yaml
git commit -m "feat: 플레이그라운드 캔버스 무대와 페이지 뼈대 (#69)"
```

---

## Task 9: 객체 추가와 단축키

**Files:**
- Create: `apps/web/components/playground/EditorToolbar.tsx`
- Create: `apps/web/components/playground/EditorToolbar.module.css`
- Create: `apps/web/components/playground/useEditorShortcuts.ts`
- Create: `apps/web/components/playground/useEditorShortcuts.test.ts`
- Modify: `apps/web/components/playground/PlaygroundEditor.tsx`

**Interfaces:**
- Consumes: `TEXT_PRESETS`, `TextPresetName`, `resolveWeight` (Task 2), `CanvasController` (Task 8).
- Produces: `isEditingContext(target: EventTarget | null): boolean`, `useEditorShortcuts(handlers: ShortcutHandlers): void`.

- [ ] **Step 1: 단축키 컨텍스트 판별 테스트 작성**

`apps/web/components/playground/useEditorShortcuts.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { isEditingContext } from "./useEditorShortcuts";

describe("isEditingContext", () => {
  it("입력 요소에 포커스가 있으면 편집 중으로 본다", () => {
    const input = document.createElement("input");
    expect(isEditingContext(input)).toBe(true);
  });

  it("textarea도 편집 중으로 본다", () => {
    expect(isEditingContext(document.createElement("textarea"))).toBe(true);
  });

  it("contenteditable 요소도 편집 중으로 본다", () => {
    const div = document.createElement("div");
    div.setAttribute("contenteditable", "true");
    expect(isEditingContext(div)).toBe(true);
  });

  it("일반 요소는 편집 중이 아니다", () => {
    expect(isEditingContext(document.createElement("div"))).toBe(false);
  });

  it("대상이 없으면 편집 중이 아니다", () => {
    expect(isEditingContext(null)).toBe(false);
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run components/playground/useEditorShortcuts.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 단축키 훅 구현**

`apps/web/components/playground/useEditorShortcuts.ts`:

```ts
"use client";

import { useEffect } from "react";

export interface ShortcutHandlers {
  onDelete: () => void;
  onDuplicate: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onNudge: (dx: number, dy: number) => void;
  /** 캔버스 위 텍스트를 인라인 편집 중이면 true */
  isTextEditing: () => boolean;
}

export function isEditingContext(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function useEditorShortcuts(handlers: ShortcutHandlers): void {
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isEditingContext(event.target) || handlers.isTextEditing()) return;

      const meta = event.metaKey || event.ctrlKey;
      const step = event.shiftKey ? 10 : 1;

      if (meta && event.key.toLowerCase() === "z") {
        event.preventDefault();
        if (event.shiftKey) handlers.onRedo();
        else handlers.onUndo();
        return;
      }
      if (meta && event.key.toLowerCase() === "d") {
        event.preventDefault();
        handlers.onDuplicate();
        return;
      }
      if (event.key === "Delete" || event.key === "Backspace") {
        event.preventDefault();
        handlers.onDelete();
        return;
      }
      if (event.key === "ArrowLeft") { event.preventDefault(); handlers.onNudge(-step, 0); }
      if (event.key === "ArrowRight") { event.preventDefault(); handlers.onNudge(step, 0); }
      if (event.key === "ArrowUp") { event.preventDefault(); handlers.onNudge(0, -step); }
      if (event.key === "ArrowDown") { event.preventDefault(); handlers.onNudge(0, step); }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handlers]);
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run components/playground/useEditorShortcuts.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 5: 툴바와 객체 추가 구현**

`apps/web/components/playground/EditorToolbar.tsx`는 버튼만 담고 실제 객체 생성은 부모가 넘긴 콜백을 호출한다.

```tsx
"use client";

import { TEXT_PRESETS, type TextPresetName } from "@/lib/playground/textPresets";
import { CANVAS_PRESETS } from "@/lib/playground/canvasPresets";
import type { CanvasSize } from "@/lib/playground/types";
import styles from "./EditorToolbar.module.css";

export interface EditorToolbarProps {
  onAddText: (preset: TextPresetName) => void;
  onAddRect: () => void;
  onAddLine: () => void;
  onUndo: () => void;
  onRedo: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onPresetChange: (size: CanvasSize) => void;
  zoom: number;
  onZoomChange: (zoom: number) => void;
}

export function EditorToolbar(props: EditorToolbarProps) {
  return (
    <div className={styles.bar} role="toolbar" aria-label="편집 도구">
      {(Object.keys(TEXT_PRESETS) as TextPresetName[]).map((name) => (
        <button key={name} type="button" onClick={() => props.onAddText(name)}>
          {TEXT_PRESETS[name].label}
        </button>
      ))}
      <button type="button" onClick={props.onAddRect}>사각형</button>
      <button type="button" onClick={props.onAddLine}>선</button>
      <button type="button" onClick={props.onUndo} disabled={!props.canUndo}>되돌리기</button>
      <button type="button" onClick={props.onRedo} disabled={!props.canRedo}>다시하기</button>
      <select
        aria-label="캔버스 크기"
        onChange={(event) => {
          const preset = CANVAS_PRESETS.find((p) => p.id === event.target.value);
          if (preset) props.onPresetChange(preset.size);
        }}
      >
        {CANVAS_PRESETS.map((preset) => (
          <option key={preset.id} value={preset.id}>{preset.label}</option>
        ))}
      </select>
      <label>
        확대 {Math.round(props.zoom * 100)}%
        <input
          type="range"
          min={25}
          max={200}
          value={Math.round(props.zoom * 100)}
          onChange={(event) => props.onZoomChange(Number(event.target.value) / 100)}
        />
      </label>
    </div>
  );
}
```

객체 생성은 `PlaygroundEditor`에서 Fabric 모듈을 동적으로 불러 처리한다. `Textbox`, `Rect`, `Line` 생성자 옵션은 Task 8 Step 2 메모에서 확인한 것만 쓴다. 새 객체에는 반드시 고유 `id`(예: `crypto.randomUUID()`)와 폰트 `slug`를 붙인다. 텍스트 굵기는 `resolveWeight(TEXT_PRESETS[name].fontWeight, font.availableWeights)`로 정한다.

- [ ] **Step 6: 빌드와 전체 테스트**

Run: `cd apps/web && pnpm test 2>&1 | tail -20 && pnpm build 2>&1 | tail -15`
Expected: 테스트 전부 통과, 빌드 성공

- [ ] **Step 7: 커밋**

```bash
git add apps/web/components/playground
git commit -m "feat: 툴바 객체 추가와 단축키 컨텍스트 분리 (#69)"
```

---

## Task 10: 폰트 패널과 폰트 적용

**Files:**
- Create: `apps/web/components/playground/FontPanel.tsx`
- Create: `apps/web/components/playground/FontPanel.module.css`
- Create: `apps/web/components/playground/FontPanel.test.tsx`
- Create: `apps/web/lib/playground/fontFilter.ts`
- Create: `apps/web/lib/playground/fontFilter.test.ts`

**Interfaces:**
- Consumes: `PlaygroundFont` (Task 1), `createFontLoader` (Task 4), `LazyFontPreview` from `@/components/LazyFontPreview`, `trackEvent` (Task 7).
- Produces: `filterFonts(fonts: PlaygroundFont[], query: string, category: CategoryFilter): PlaygroundFont[]`, `previewPhrase(selectedText: string | null): string`.

- [ ] **Step 1: 필터와 미리보기 문구 테스트 작성**

`apps/web/lib/playground/fontFilter.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { filterFonts, previewPhrase, PREVIEW_PHRASE_LIMIT } from "./fontFilter";
import type { PlaygroundFont } from "./types";

const fonts: PlaygroundFont[] = [
  { slug: "a", nameKo: "가나고딕", nameEn: "Gana Gothic", category: "고딕", availableWeights: [400], canvasFamily: "A", stylesheetUrl: null, detailPath: "/fonts/a" },
  { slug: "b", nameKo: "다라명조", nameEn: "Dara Myeongjo", category: "명조", availableWeights: [400], canvasFamily: "B", stylesheetUrl: null, detailPath: "/fonts/b" },
];

describe("filterFonts", () => {
  it("분류로 거른다", () => {
    expect(filterFonts(fonts, "", "명조").map((f) => f.slug)).toEqual(["b"]);
  });

  it("전체 분류는 거르지 않는다", () => {
    expect(filterFonts(fonts, "", "전체")).toHaveLength(2);
  });

  it("한글 이름으로 검색한다", () => {
    expect(filterFonts(fonts, "가나", "전체").map((f) => f.slug)).toEqual(["a"]);
  });

  it("영문 이름은 대소문자를 가리지 않는다", () => {
    expect(filterFonts(fonts, "dara", "전체").map((f) => f.slug)).toEqual(["b"]);
  });

  it("공백만 입력하면 거르지 않는다", () => {
    expect(filterFonts(fonts, "   ", "전체")).toHaveLength(2);
  });
});

describe("previewPhrase", () => {
  it("선택이 없으면 기본 문구를 쓴다", () => {
    expect(previewPhrase(null)).toBe("가나다라 ABC 123");
  });

  it("빈 문자열도 기본 문구를 쓴다", () => {
    expect(previewPhrase("   ")).toBe("가나다라 ABC 123");
  });

  it("긴 문장은 잘라 쓴다", () => {
    const long = "가".repeat(40);
    expect(previewPhrase(long)).toHaveLength(PREVIEW_PHRASE_LIMIT);
  });

  it("줄바꿈을 공백으로 바꾼다", () => {
    expect(previewPhrase("첫줄\n둘째줄")).toBe("첫줄 둘째줄");
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/fontFilter.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`apps/web/lib/playground/fontFilter.ts`:

```ts
import type { Category } from "@/types/font";
import type { PlaygroundFont } from "./types";

export type CategoryFilter = "전체" | Category;

export const CATEGORY_FILTERS: CategoryFilter[] = ["전체", "고딕", "명조", "손글씨", "장식"];
export const PREVIEW_PHRASE_LIMIT = 12;
export const DEFAULT_PREVIEW_PHRASE = "가나다라 ABC 123";

export function filterFonts(
  fonts: PlaygroundFont[],
  query: string,
  category: CategoryFilter
): PlaygroundFont[] {
  const keyword = query.trim().toLowerCase();

  return fonts.filter((font) => {
    if (category !== "전체" && font.category !== category) return false;
    if (!keyword) return true;
    return (
      font.nameKo.toLowerCase().includes(keyword) ||
      font.nameEn.toLowerCase().includes(keyword)
    );
  });
}

export function previewPhrase(selectedText: string | null): string {
  const normalized = (selectedText ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) return DEFAULT_PREVIEW_PHRASE;
  return normalized.slice(0, PREVIEW_PHRASE_LIMIT);
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/fontFilter.test.ts`
Expected: PASS (9 tests)

- [ ] **Step 5: 폰트 패널 컴포넌트 테스트 작성**

`apps/web/components/playground/FontPanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { FontPanel } from "./FontPanel";
import type { PlaygroundFont } from "@/lib/playground/types";

const fonts: PlaygroundFont[] = [
  { slug: "a", nameKo: "가나고딕", nameEn: "Gana Gothic", category: "고딕", availableWeights: [400], canvasFamily: '"A", sans-serif', stylesheetUrl: null, detailPath: "/fonts/a" },
  { slug: "b", nameKo: "다라명조", nameEn: "Dara Myeongjo", category: "명조", availableWeights: [400], canvasFamily: '"B", serif', stylesheetUrl: null, detailPath: "/fonts/b" },
];

describe("FontPanel", () => {
  it("폰트 목록을 보여준다", () => {
    render(<FontPanel fonts={fonts} usedSlugs={[]} selectedText={null} onApply={vi.fn()} />);
    expect(screen.getByText("가나고딕")).toBeInTheDocument();
    expect(screen.getByText("다라명조")).toBeInTheDocument();
  });

  it("검색으로 목록을 줄인다", async () => {
    render(<FontPanel fonts={fonts} usedSlugs={[]} selectedText={null} onApply={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("폰트 검색"), "가나");
    expect(screen.queryByText("다라명조")).not.toBeInTheDocument();
  });

  it("클릭하면 적용 콜백을 부른다", async () => {
    const onApply = vi.fn();
    render(<FontPanel fonts={fonts} usedSlugs={[]} selectedText={null} onApply={onApply} />);
    await userEvent.click(screen.getByRole("button", { name: /가나고딕/ }));
    expect(onApply).toHaveBeenCalledWith(fonts[0]);
  });

  it("사용 중 폰트를 상단에 상세 링크로 보여준다", () => {
    render(<FontPanel fonts={fonts} usedSlugs={["b"]} selectedText={null} onApply={vi.fn()} />);
    const link = screen.getByRole("link", { name: /다라명조/ });
    expect(link).toHaveAttribute("href", "/fonts/b");
  });

  it("결과가 없으면 안내를 보여준다", async () => {
    render(<FontPanel fonts={fonts} usedSlugs={[]} selectedText={null} onApply={vi.fn()} />);
    await userEvent.type(screen.getByLabelText("폰트 검색"), "없는폰트");
    expect(screen.getByText("검색 결과가 없습니다")).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: 폰트 패널 구현**

`apps/web/components/playground/FontPanel.tsx`. 미리보기 렌더는 기존 `LazyFontPreview`를 재사용해 화면에 들어온 항목만 스타일시트를 주입한다.

```tsx
"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { PlaygroundFont } from "@/lib/playground/types";
import { CATEGORY_FILTERS, filterFonts, previewPhrase, type CategoryFilter } from "@/lib/playground/fontFilter";
import styles from "./FontPanel.module.css";

export interface FontPanelProps {
  fonts: PlaygroundFont[];
  usedSlugs: string[];
  selectedText: string | null;
  onApply: (font: PlaygroundFont) => void;
}

export function FontPanel({ fonts, usedSlugs, selectedText, onApply }: FontPanelProps) {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<CategoryFilter>("전체");

  const visible = useMemo(() => filterFonts(fonts, query, category), [fonts, query, category]);
  const phrase = previewPhrase(selectedText);
  const used = fonts.filter((font) => usedSlugs.includes(font.slug));

  return (
    <aside className={styles.panel}>
      {used.length > 0 && (
        <section className={styles.used}>
          <h2 className={styles.label}>이 작업에 쓴 폰트</h2>
          <ul>
            {used.map((font) => (
              <li key={font.slug}>
                <Link href={font.detailPath}>{font.nameKo} 상세</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <label className={styles.search}>
        <span className={styles.label}>폰트 검색</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="폰트 이름" />
      </label>

      <div className={styles.chips} role="group" aria-label="분류 필터">
        {CATEGORY_FILTERS.map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={category === item}
            onClick={() => setCategory(item)}
          >
            {item}
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className={styles.empty}>검색 결과가 없습니다</p>
      ) : (
        <ul className={styles.list}>
          {visible.map((font) => (
            <li key={font.slug}>
              <button type="button" onClick={() => onApply(font)}>
                <span className={styles.name}>{font.nameKo}</span>
                <span className={styles.sample} style={{ fontFamily: font.canvasFamily }}>{phrase}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
```

검색 입력의 접근성 이름은 `폰트 검색`이어야 테스트가 통과한다.

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run components/playground/FontPanel.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 8: 캔버스에 폰트 적용 연결**

`PlaygroundEditor`에서 `onApply`를 처리한다. 순서를 지킨다.

1. 선택된 텍스트 객체가 없으면 다음 생성 텍스트의 기본 폰트로 기억하고 종료.
2. 선택된 각 텍스트 객체에 대해 `fontLoader.request(font, objectId)` 호출.
3. 결과가 `superseded`면 아무것도 하지 않는다.
4. 반영 직전 `canvas.getObjects()`에 그 객체가 아직 있는지 확인한다. 없으면 버린다.
5. `object.set({ fontFamily: font.canvasFamily, fontWeight: resolveWeight(현재 굵기, font.availableWeights) })` 후 `object.initDimensions()`, `object.setCoords()`, `canvas.requestRenderAll()`.
6. 객체의 커스텀 속성 `slug`를 갱신한다.
7. 결과가 `failed`면 폴백을 유지한 채 "폰트를 불러오지 못했습니다" 안내를 띄운다.
8. 실제로 폰트가 바뀐 경우에만 `trackEvent("playground_font_applied", { font_slug: font.slug, applied_count: 지금까지 쓴 서로 다른 폰트 수 })`.

- [ ] **Step 9: 커밋**

```bash
git add apps/web/lib/playground/fontFilter.ts apps/web/lib/playground/fontFilter.test.ts apps/web/components/playground
git commit -m "feat: 폰트 패널과 캔버스 폰트 적용 (#69)"
```

---

## Task 11: 속성 패널

**Files:**
- Create: `apps/web/components/playground/PropertiesPanel.tsx`
- Create: `apps/web/components/playground/PropertiesPanel.module.css`
- Create: `apps/web/components/playground/PropertiesPanel.test.tsx`

**Interfaces:**
- Consumes: `SelectionState` (Task 8), `resolveWeight` (Task 2).
- Produces: `PropertiesPanel` 컴포넌트. 값 변경은 `onChange(patch: Partial<ObjectStyle>)` 콜백으로 위임한다.

```ts
export interface ObjectStyle {
  fontSize: number;
  fontWeight: number;
  fill: string;
  textAlign: "left" | "center" | "right";
  charSpacing: number;
  lineHeight: number;
  opacity: number;
  stroke: string;
  strokeWidth: number;
}
```

- [ ] **Step 1: 실패하는 테스트 작성**

`apps/web/components/playground/PropertiesPanel.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { PropertiesPanel } from "./PropertiesPanel";

const style = {
  fontSize: 72,
  fontWeight: 700,
  fill: "#111111",
  textAlign: "left" as const,
  charSpacing: 0,
  lineHeight: 1.3,
  opacity: 1,
  stroke: "#000000",
  strokeWidth: 0,
};

describe("PropertiesPanel", () => {
  it("선택이 없으면 안내를 보여준다", () => {
    render(<PropertiesPanel kind="none" style={style} availableWeights={[400]} onChange={vi.fn()} />);
    expect(screen.getByText("객체를 선택하면 속성이 보입니다")).toBeInTheDocument();
  });

  it("텍스트 선택 시 굵기 선택지를 그 폰트의 값으로 제한한다", () => {
    render(<PropertiesPanel kind="text" style={style} availableWeights={[400, 700]} onChange={vi.fn()} />);
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options).toEqual(["400", "700"]);
  });

  it("크기를 바꾸면 콜백이 온다", async () => {
    const onChange = vi.fn();
    render(<PropertiesPanel kind="text" style={style} availableWeights={[400]} onChange={onChange} />);
    const input = screen.getByLabelText("크기");
    await userEvent.clear(input);
    await userEvent.type(input, "48");
    expect(onChange).toHaveBeenCalledWith({ fontSize: 48 });
  });

  it("도형 선택 시 자간 항목을 숨긴다", () => {
    render(<PropertiesPanel kind="shape" style={style} availableWeights={[]} onChange={vi.fn()} />);
    expect(screen.queryByLabelText("자간")).not.toBeInTheDocument();
    expect(screen.getByLabelText("테두리 두께")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run components/playground/PropertiesPanel.test.tsx`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`PropertiesPanel`은 `kind`에 따라 항목을 나눈다. 텍스트는 크기, 굵기, 색, 정렬, 자간, 행간, 불투명도. 도형은 채우기색, 테두리 색, 테두리 두께, 불투명도. `kind === "none"`이면 안내 문구만. 숫자 입력은 `Number(event.target.value)`로 변환해 `onChange({ fontSize: 값 })` 형태로 부분 갱신만 넘긴다. 굵기 `select`의 `option`은 `availableWeights`를 그대로 매핑한다. 라벨 텍스트는 테스트와 정확히 같아야 한다: `크기`, `굵기`, `색`, `정렬`, `자간`, `행간`, `불투명도`, `채우기색`, `테두리 색`, `테두리 두께`.

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run components/playground/PropertiesPanel.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/playground/PropertiesPanel.tsx apps/web/components/playground/PropertiesPanel.module.css apps/web/components/playground/PropertiesPanel.test.tsx
git commit -m "feat: 속성 패널 (#69)"
```

---

## Task 12: 정렬 도구와 스냅 연결

**Files:**
- Modify: `apps/web/components/playground/EditorToolbar.tsx` (정렬 버튼 추가)
- Modify: `apps/web/components/playground/CanvasStage.tsx` (안내선 렌더)
- Modify: `apps/web/components/playground/PlaygroundEditor.tsx` (명령 연결)

**Interfaces:**
- Consumes: `alignBoxes`, `distributeBoxes`, `findSnap`, `rescaleBoxes`, `Guide` (Task 6).

- [ ] **Step 1: 정렬 버튼 추가**

`EditorToolbar`에 `onAlign(mode: AlignMode)`과 `onDistribute(axis: "x" | "y")` props를 더한다. 버튼 라벨은 `왼쪽 맞춤`, `가운데 맞춤`, `오른쪽 맞춤`, `위 맞춤`, `중간 맞춤`, `아래 맞춤`, `가로 간격 균등`, `세로 간격 균등`. 선택 객체가 2개 미만이면 맞춤 버튼을, 3개 미만이면 간격 버튼을 비활성화한다.

- [ ] **Step 2: 정렬 명령 연결**

`PlaygroundEditor`에서 선택 객체를 `Box[]`로 바꿔 `alignBoxes`에 넘기고, 결과의 `left`/`top`을 각 객체에 되돌려 넣은 뒤 `setCoords()`와 `requestRenderAll()`을 부른다. `Box`의 `width`/`height`는 Task 8 Step 2 메모에서 확인한 경계 상자 조회 메서드로 얻는다. 좌표 속성으로 직접 계산하지 않는다.

- [ ] **Step 3: 스냅 연결**

객체 이동 중 이벤트에서 `findSnap(움직이는 객체 박스, 나머지 박스, 캔버스 크기)`를 부르고, `dx`/`dy`가 0이 아니면 좌표에 더해 흡착시킨다. 반환된 `guides`는 상태로 올려 `CanvasStage`가 캔버스 위에 절대 위치 선으로 그린다. 이동이 끝나면 안내선을 지운다. 좁은 화면(900px 미만)에서는 흡착을 적용하지 않고 안내선만 표시한다.

- [ ] **Step 4: 프리셋 변경 연결**

캔버스 크기를 바꿀 때 기존 객체 박스를 `rescaleBoxes(boxes, 이전 크기, 새 크기)`에 넘겨 좌표와 크기를 갱신한 뒤 캔버스 크기를 바꾼다. 순서를 바꾸면 객체가 잠깐 화면 밖으로 나간다.

- [ ] **Step 5: 수동 확인**

Run: `cd apps/web && pnpm dev`
브라우저에서 `http://localhost:3000/playground`를 열고 확인한다.
1. 텍스트 2개를 만들고 Shift로 함께 선택한 뒤 왼쪽 맞춤을 누르면 왼쪽 가장자리가 나란해진다.
2. 객체를 캔버스 가운데 근처로 끌면 분홍 세로선이 뜨고 달라붙는다.
3. 프리셋을 정사각에서 유튜브 썸네일로 바꿔도 객체가 캔버스 안에 남는다.

스냅과 정렬은 눈으로 봐야 아는 기능이라 자동 테스트로 대체할 수 없다. 위 3개 확인 결과를 커밋 메시지 본문에 적는다.

- [ ] **Step 6: 커밋**

```bash
git add apps/web/components/playground
git commit -m "feat: 정렬 도구와 스냅 안내선 (#69)"
```

---

## Task 13: 되돌리기 연결

**Files:**
- Modify: `apps/web/components/playground/PlaygroundEditor.tsx`
- Create: `apps/web/components/playground/useHistory.ts`

**Interfaces:**
- Consumes: `createHistoryStack` (Task 5), Fabric `toObject(propertiesToInclude)` / `loadFromJSON`.

- [ ] **Step 1: 커스텀 속성 직렬화 등록**

Fabric 모듈을 처음 불러오는 지점에서 커스텀 속성을 등록한다. 등록하지 않으면 되돌리기 한 번에 폰트 정보가 사라진다.

```ts
const { FabricObject } = await import("fabric");
FabricObject.customProperties = ["id", "slug"];
```

- [ ] **Step 2: 스냅샷 훅 구현**

`apps/web/components/playground/useHistory.ts`에서 `createHistoryStack<string>()`을 감싼다. 스냅샷은 `JSON.stringify(canvas.toObject(["id", "slug"]))`.

찍는 시점: 객체 추가, 삭제, 이동/크기변경 종료, 속성 변경 확정, 폰트 적용, 프리셋 변경. 드래그 도중에는 찍지 않는다.

복원:

```ts
async function restore(snapshot: string, canvas: Canvas) {
  if (!stack.beginRestore()) return;
  try {
    await canvas.loadFromJSON(snapshot);
    canvas.requestRenderAll();
  } finally {
    stack.endRestore();
  }
}
```

`beginRestore()`가 false를 돌려주면 그 요청은 버린다. 복원 중 스냅샷을 새로 찍지 않도록 복원 상태에서는 이벤트 기반 push를 건너뛴다.

- [ ] **Step 3: 수동 확인**

Run: `cd apps/web && pnpm dev`
1. 텍스트를 만들고 폰트를 바꾼 뒤 Cmd+Z를 누르면 이전 폰트로 돌아간다.
2. 돌아간 뒤에도 왼쪽 "이 작업에 쓴 폰트" 목록이 실제 캔버스 상태와 맞는다.
3. Cmd+Z를 빠르게 5번 눌러도 캔버스와 버튼 활성 상태가 어긋나지 않는다.

- [ ] **Step 4: 전체 테스트**

Run: `cd apps/web && pnpm test 2>&1 | tail -20`
Expected: 기존 테스트 전부 통과

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/playground
git commit -m "feat: 되돌리기 연결과 커스텀 속성 직렬화 (#69)"
```

---

## Task 14: 내보내기와 라이선스 고지

**Files:**
- Create: `apps/web/components/playground/ExportMenu.tsx`
- Create: `apps/web/components/playground/ExportMenu.module.css`
- Create: `apps/web/components/playground/ExportMenu.test.tsx`
- Create: `apps/web/lib/playground/exportName.ts`
- Create: `apps/web/lib/playground/exportName.test.ts`

**Interfaces:**
- Consumes: `exportMultiplier` (Task 6), `trackEvent` (Task 7), `PlaygroundFont` (Task 1).
- Produces: `buildExportFileName(presetLabel: string, date: Date): string`.

- [ ] **Step 1: 파일명 테스트 작성**

`apps/web/lib/playground/exportName.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { buildExportFileName } from "./exportName";

describe("buildExportFileName", () => {
  it("프리셋과 날짜로 이름을 만든다", () => {
    expect(buildExportFileName("정사각", new Date("2026-07-31T09:00:00Z"))).toBe(
      "fontagit-정사각-20260731.png"
    );
  });

  it("공백은 하이픈으로 바꾼다", () => {
    expect(buildExportFileName("유튜브 썸네일", new Date("2026-01-05T00:00:00Z"))).toBe(
      "fontagit-유튜브-썸네일-20260105.png"
    );
  });
});
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/exportName.test.ts`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

`apps/web/lib/playground/exportName.ts`:

```ts
export function buildExportFileName(presetLabel: string, date: Date): string {
  const stamp = [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0"),
  ].join("");
  const label = presetLabel.trim().replace(/\s+/g, "-");

  return `fontagit-${label}-${stamp}.png`;
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run lib/playground/exportName.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: 내보내기 메뉴 테스트 작성**

`apps/web/components/playground/ExportMenu.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExportMenu } from "./ExportMenu";
import type { PlaygroundFont } from "@/lib/playground/types";

const used: PlaygroundFont[] = [
  { slug: "a", nameKo: "가나고딕", nameEn: "Gana Gothic", category: "고딕", availableWeights: [400], canvasFamily: "A", stylesheetUrl: null, detailPath: "/fonts/a" },
];

describe("ExportMenu", () => {
  it("사용한 폰트와 라이선스 안내를 보여준다", () => {
    render(<ExportMenu usedFonts={used} multiplier={2} onExport={vi.fn()} />);
    expect(screen.getByText("사용 전 라이선스 조건을 확인하세요")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /가나고딕/ })).toHaveAttribute("href", "/fonts/a");
  });

  it("배율이 낮아지면 알린다", () => {
    render(<ExportMenu usedFonts={used} multiplier={0.7} onExport={vi.fn()} />);
    expect(screen.getByText(/크기가 자동으로 줄어듭니다/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: 내보내기 구현**

`ExportMenu`는 사용 폰트 목록과 상세 링크, "사용 전 라이선스 조건을 확인하세요" 한 줄, 배율이 1 미만이면 축소 안내를 보여주고 내보내기 버튼을 제공한다.

`PlaygroundEditor`의 내보내기 처리 순서:

1. 이 작업에 쓰인 모든 폰트의 로딩이 끝났는지 확인한다. 아직이면 기다린다.
2. 실패한 폰트가 있으면 "일부 폰트가 기본 글꼴로 저장됩니다. 계속할까요?"를 묻고 사용자가 정하게 한다.
3. `const multiplier = exportMultiplier(캔버스 크기, 좁은 화면 여부)`.
4. `const dataUrl = canvas.toDataURL({ format: "png", multiplier })`.
5. 임시 앵커 요소에 `download = buildExportFileName(프리셋 라벨, new Date())`를 걸어 내려받는다.
6. `trackEvent("playground_export_png", { preset: 프리셋 id, object_count: 객체 수, font_count: 사용 폰트 수 })`.
7. 어느 단계든 예외가 나면 "이미지를 만들지 못했습니다. 다시 시도해주세요" 안내와 재시도 버튼을 띄운다.

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd apps/web && pnpm exec vitest run components/playground/ExportMenu.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 8: 커밋**

```bash
git add apps/web/lib/playground/exportName.ts apps/web/lib/playground/exportName.test.ts apps/web/components/playground
git commit -m "feat: PNG 내보내기와 라이선스 고지 (#69)"
```

---

## Task 15: 모바일 시트

**Files:**
- Modify: `apps/web/components/playground/PlaygroundEditor.tsx`
- Modify: `apps/web/components/playground/PlaygroundEditor.module.css`
- Create: `apps/web/components/playground/MobileSheet.tsx`
- Create: `apps/web/components/playground/MobileSheet.module.css`

- [ ] **Step 1: 시트 컴포넌트 작성**

`MobileSheet`는 캔버스 아래에 붙는 영역으로 `폰트`/`속성` 두 탭을 제공한다. 탭 버튼은 `role="tab"`, 내용은 `role="tabpanel"`. 열린 탭 상태만 갖고 내용은 `children`으로 받는다.

- [ ] **Step 2: 배치 전환 연결**

`PlaygroundEditor`가 900px 미만이면 좌우 패널 대신 `MobileSheet`에 `FontPanel`과 `PropertiesPanel`을 담는다. 툴바는 좁은 화면에서 텍스트 프리셋, 도형, 되돌리기, 내보내기만 남기고 정렬 묶음과 자유 크기 입력을 숨긴다.

- [ ] **Step 3: 터치 동작 제한**

캔버스 컨테이너에 `touch-action: none`을 적용한다. 좁은 화면에서는 Fabric 캔버스 옵션에서 크기 조절 손잡이와 회전 손잡이를 끄고, 다중 선택 드래그 박스를 비활성화한다. 해당 옵션 이름은 Task 8 Step 2 메모에서 확인한 것만 쓴다.

- [ ] **Step 4: 수동 확인**

Run: `cd apps/web && pnpm dev`
브라우저 개발자 도구에서 화면 폭을 390px로 줄이고 확인한다.
1. 캔버스 아래 시트가 보이고 탭 전환이 된다.
2. 객체를 끌 때 페이지가 스크롤되지 않는다.
3. 크기 조절 손잡이가 보이지 않는다.
4. 텍스트 추가, 폰트 적용, 내보내기가 동작한다.

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/playground
git commit -m "feat: 모바일 하단 시트와 터치 동작 제한 (#69)"
```

---

## Task 16: 진입점과 이탈 보호

**Files:**
- Modify: `apps/web/components/Header.tsx`
- Modify: `apps/web/app/fonts/[slug]/page.tsx`
- Modify: `apps/web/components/playground/PlaygroundEditor.tsx`
- Create: `apps/web/components/playground/PlaygroundCtaLink.tsx`
- Create: `apps/web/components/playground/PlaygroundCtaLink.test.tsx`

**Interfaces:**
- Consumes: `isPlayableFont` (Task 1), `trackEvent` (Task 7).

- [ ] **Step 1: 상세 CTA 테스트 작성**

`apps/web/components/playground/PlaygroundCtaLink.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PlaygroundCtaLink } from "./PlaygroundCtaLink";

describe("PlaygroundCtaLink", () => {
  it("렌더 가능한 폰트면 링크를 보여준다", () => {
    render(<PlaygroundCtaLink slug="jua" fontKey="jua" sourceTier="B" />);
    expect(screen.getByRole("link", { name: "이 폰트로 만들어보기" })).toHaveAttribute(
      "href",
      "/playground/?font=jua"
    );
  });

  it("Tier A 폰트도 링크를 보여준다", () => {
    render(<PlaygroundCtaLink slug="noto" fontKey={null} sourceTier="A" />);
    expect(screen.getByRole("link")).toBeInTheDocument();
  });

  it("렌더 불가 폰트면 아무것도 그리지 않는다", () => {
    const { container } = render(<PlaygroundCtaLink slug="paid" fontKey={null} sourceTier="B" />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

주소 끝의 슬래시는 `next.config.ts`의 `trailingSlash: true` 설정과 맞춘 것이다.

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/web && pnpm exec vitest run components/playground/PlaygroundCtaLink.test.tsx`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

```tsx
"use client";

import Link from "next/link";
import type { FontKey, SourceTier } from "@/types/font";
import { isPlayableFont } from "@/lib/playground/fontCatalog";
import { trackEvent } from "@/lib/analytics/events";

export function PlaygroundCtaLink({
  slug,
  fontKey,
  sourceTier,
}: {
  slug: string;
  fontKey: FontKey | null;
  sourceTier?: SourceTier;
}) {
  if (!isPlayableFont({ fontKey, sourceTier })) return null;

  return (
    <Link
      href={`/playground/?font=${slug}`}
      onClick={() => trackEvent("playground_font_cta_clicked", { font_slug: slug, source: "detail" })}
    >
      이 폰트로 만들어보기
    </Link>
  );
}
```

- [ ] **Step 4: 상세 페이지와 헤더에 연결**

`app/fonts/[slug]/page.tsx`의 견본 영역 아래에 `<PlaygroundCtaLink slug={font.slug} fontKey={font.fontKey} sourceTier={font.sourceTier} />`를 넣는다. `components/Header.tsx`의 `nav`에 `<Link href="/playground">플레이그라운드</Link>`를 `트렌드` 다음에 넣는다.

- [ ] **Step 5: 주소 파라미터 읽기**

`PlaygroundEditor`에서 `useSearchParams()`로 `font` 값을 읽어 카탈로그에서 찾고, 있으면 기본 폰트로 설정한다. 없거나 카탈로그에 없으면 조용히 기본 폰트로 시작한다. 서버 단계에서 `searchParams`를 쓰면 정적 내보내기 빌드가 깨지므로 클라이언트에서만 읽는다.

- [ ] **Step 6: 이탈 보호**

편집 내용이 하나라도 있으면 `beforeunload`에서 경고한다. 사이트 내 이동은 편집기 화면 안의 링크(헤더 링크, 폰트 상세 링크)를 감싸 클릭 시 확인 창을 띄우는 방식으로 한정한다. 브라우저 뒤로가기는 막지 않는다.

```ts
useEffect(() => {
  if (!hasContent) return;
  const handler = (event: BeforeUnloadEvent) => {
    event.preventDefault();
  };
  window.addEventListener("beforeunload", handler);
  return () => window.removeEventListener("beforeunload", handler);
}, [hasContent]);
```

- [ ] **Step 7: 테스트와 빌드**

Run: `cd apps/web && pnpm test 2>&1 | tail -20 && pnpm build 2>&1 | tail -15`
Expected: 테스트 전부 통과, 빌드 성공

- [ ] **Step 8: 커밋**

```bash
git add apps/web/components/Header.tsx apps/web/app/fonts apps/web/components/playground
git commit -m "feat: 플레이그라운드 진입점과 이탈 보호 (#69)"
```

---

## Task 17: e2e 여정 3종

**Files:**
- Create: `apps/web/e2e/playground.spec.ts`
- Modify: `apps/web/e2e/smoke.spec.ts` (라우트 추가)

- [ ] **Step 1: 스모크 라우트 추가**

`e2e/smoke.spec.ts`의 `routes` 배열에 `{ path: '/playground', name: 'Playground' }`를 넣는다.

- [ ] **Step 2: e2e 테스트 작성**

`apps/web/e2e/playground.spec.ts`:

```ts
import { test, expect } from '@playwright/test';

test.describe('플레이그라운드', () => {
  test('텍스트 추가 후 폰트를 적용하고 PNG를 내려받는다', async ({ page }) => {
    await page.goto('/playground/');
    await page.getByRole('button', { name: '제목' }).click();
    await page.getByLabel('폰트 검색').fill('고딕');
    await page.locator('button', { hasText: '고딕' }).first().click();

    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: 'PNG 내보내기' }).click();
    const file = await download;

    expect(file.suggestedFilename()).toMatch(/^fontagit-.+\.png$/);
  });

  test('두 객체를 선택해 왼쪽으로 맞춘다', async ({ page }) => {
    await page.goto('/playground/');
    await page.getByRole('button', { name: '제목' }).click();
    await page.getByRole('button', { name: '본문' }).click();
    await page.keyboard.press('Control+a');
    await page.getByRole('button', { name: '왼쪽 맞춤' }).click();

    await expect(page.getByRole('button', { name: '왼쪽 맞춤' })).toBeEnabled();
  });

  test('폰트를 적용하면 사용 중 폰트에서 상세로 이동한다', async ({ page }) => {
    await page.goto('/playground/');
    await page.getByRole('button', { name: '제목' }).click();
    await page.getByLabel('폰트 검색').fill('고딕');
    await page.locator('button', { hasText: '고딕' }).first().click();

    await page.getByRole('link', { name: /상세/ }).first().click();
    await expect(page).toHaveURL(/\/fonts\//);
  });
});
```

두 번째 테스트의 전체 선택 단축키는 Task 9에서 구현하지 않았다. 구현 시점에 전체 선택 버튼이나 드래그 박스 중 실제 동작하는 방식으로 이 테스트를 맞춰 고친다.

- [ ] **Step 3: e2e 실행**

Run: `cd apps/web && pnpm e2e 2>&1 | tail -30`
Expected: 신규 3개 포함 전부 통과. 실패하면 실패한 테스트의 선택자를 실제 구현에 맞게 수정한다.

- [ ] **Step 4: 커밋**

```bash
git add apps/web/e2e
git commit -m "test: 플레이그라운드 e2e 여정 3종 (#69)"
```

---

## Task 18: 마무리 검증

- [ ] **Step 1: 전체 테스트**

Run: `cd apps/web && pnpm test 2>&1 | tail -20`
Expected: 전부 통과

- [ ] **Step 2: 린트**

Run: `cd apps/web && pnpm lint 2>&1 | tail -20`
Expected: 오류 없음

- [ ] **Step 3: 빌드와 SEO 검증**

Run: `cd apps/web && pnpm build 2>&1 | tail -20 && pnpm verify:seo 2>&1 | tail -10`
Expected: 빌드 성공, SEO 검증 통과

- [ ] **Step 4: 접근성 최소 확인**

키보드만으로 다음이 되는지 확인한다: Tab으로 툴바 이동, Enter로 텍스트 추가, Tab으로 폰트 목록 이동, Enter로 폰트 적용, Tab으로 내보내기 도달. 캔버스 요소에는 `aria-label="디자인 캔버스"`가 있어야 한다. 완전한 키보드 편집은 비범위다.

- [ ] **Step 5: 파일 길이 점검**

Run: `cd apps/web && wc -l components/playground/*.tsx | sort -rn | head -5`
300줄을 넘는 컴포넌트가 있으면 로직을 훅이나 `lib/playground/` 유틸로 뽑아낸다.

- [ ] **Step 6: 최종 커밋**

```bash
git add -A apps/web
git commit -m "chore: 플레이그라운드 최종 검증 (#69)"
```

---

## 자체 점검 결과

**설계 문서 대비 범위 확인**

| 설계 항목 | 담당 태스크 |
|---|---|
| 폰트 카탈로그(Tier A 140종, Tier B 제외) | Task 1 |
| 텍스트 프리셋 3종, 굵기 대체 | Task 2, 9 |
| 캔버스 프리셋 3종 + 자유 크기(200~4096) | Task 3, 12 |
| 폰트 로딩 정책(세대 토큰, 5초, 객체 유효성) | Task 4, 10 |
| 되돌리기(깊이 30, 복원 잠금, 커스텀 속성) | Task 5, 13 |
| 정렬-간격-스냅-재배치-배율 | Task 6, 12 |
| 계측 4종 | Task 7, 10, 14, 16 |
| 캔버스 무대, dispose, 줌 | Task 8 |
| 단축키 컨텍스트 분리 | Task 9 |
| 폰트 패널(검색, 칩, 사용 중 폰트, 미리보기 12자) | Task 10 |
| 속성 패널(표준 7종 + 도형) | Task 11 |
| PNG 내보내기, 라이선스 고지, 로딩 보장 | Task 14 |
| 모바일 시트, touch-action, 동작 범위 | Task 15 |
| 헤더 노출, 상세 CTA(Tier 게이트), `?font=`, 이탈 보호 | Task 16 |
| e2e 3종 | Task 17 |
| 접근성 최소 확인 | Task 18 |

**설계 문서와 다르게 잡은 것**

- 설계 문서는 "기존 `font_download_clicked` 이벤트와 이어 퍼널을 완성한다"고 적었으나 코드베이스에 커스텀 이벤트 전송 코드가 없다. `gtag` 사용처는 `components/Analytics/GoogleAnalytics.tsx` 하나이며 페이지뷰용이다. 그래서 Task 7로 이벤트 헬퍼를 새로 만든다. 다운로드 이벤트 연결은 이 계획의 범위 밖이다.
- 설계 문서의 컴포넌트 표에는 없던 `useCanvasController`, `useEditorShortcuts`, `useHistory`, `MobileSheet`, `PlaygroundCtaLink`를 추가했다. 컴포넌트 300줄 제한을 지키기 위한 분리다.

**자동 테스트로 덮이지 않는 것**

스냅 흡착 감각, 정렬 결과의 시각적 정확성, 모바일 터치 조작, 되돌리기 연타 시 화면 일관성. Task 12 Step 5, Task 13 Step 3, Task 15 Step 4에 수동 확인 절차로 남겼다.
