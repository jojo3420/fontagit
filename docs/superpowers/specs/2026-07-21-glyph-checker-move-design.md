# 글자 지원 검사 이동 설계 (#97)

- 이슈: #97 "화면 요소 이동"
- 작성일: 2026-07-21
- 목적: `/playground` 하단의 "글자 지원 검사"를 폰트 상세(`/fonts/{slug}`) 페이지로 이동

## 배경 (AS-IS)

- `/playground`는 `PlaygroundCanvas` + `GlyphCheckerSection`을 렌더한다.
- `GlyphCheckerSection`은 **폰트 선택 드롭다운** + 실제 검사기 `GlyphChecker`로 구성된다. playground에는 대상 폰트가 정해져 있지 않아 드롭다운이 필요하다.
- `GlyphCheckerSection`/`GlyphChecker`는 현재 playground에서만 쓰인다. 전용 테스트 파일은 없다.
- 폰트 상세 페이지는 이미 `font` 하나로 고정되며, 그 객체에 검사기가 필요한 `fontKey`, `nameKo`, `tier`가 모두 있다.
- 검사 가능 판정식(현재 `GlyphChecker.tsx` 내부 인라인): `tier === "free" && fontKey !== null && fontKey !== "pretendard"`.
- `document.fonts.load` 호출은 검사 버튼 클릭 시에만 발생 → 초기 렌더는 jsdom에서 안전.

## 결정 (사용자 확정)

1. **완전 이동**: playground에서 제거하고 상세 페이지에만 둔다.
2. **드롭다운 제거**: 상세 페이지의 현재 폰트로 고정. `GlyphCheckerSection` 대신 `GlyphChecker`를 직접 사용.
3. **배치**: `PublishedFontDetail`의 메인 컬럼, `SpecimenBox` 바로 아래.
4. **미지원 폰트**: 유료/로컬(웹폰트 없음) 폰트는 검사 섹션 자체를 숨긴다. 검사 가능한 무료 웹폰트에서만 노출.

## 변경 (TO-BE)

### 코드
- `app/playground/page.tsx`: `GlyphCheckerSection`, `fonts` import 제거. `PlaygroundCanvas`만 렌더.
- `app/fonts/[slug]/page.tsx`: `PublishedFontDetail`의 `SpecimenBox` 아래에 조건부 렌더.
  ```tsx
  {isGlyphCheckSupported(font.fontKey, font.tier) && (
    <GlyphChecker fontKey={font.fontKey} fontName={font.nameKo} tier={font.tier} />
  )}
  ```
  상세는 서버 컴포넌트이나 클라이언트 컴포넌트(`GlyphChecker`) 렌더는 정상. `output: "export"` SSG에서도 브라우저 하이드레이션으로 동작(서버 라우트 불필요).
- `lib/glyphSupport.ts`: 판정식을 함수로 추출.
  ```ts
  export function isGlyphCheckSupported(fontKey: FontKey | null, tier: Tier): boolean {
    return tier === "free" && fontKey !== null && fontKey !== "pretendard";
  }
  ```
- `components/GlyphChecker.tsx`: 내부 인라인 판정식을 `isGlyphCheckSupported(fontKey, tier)` 호출로 교체(1줄).

### 삭제 (dead code)
- `components/GlyphCheckerSection.tsx`
- `components/GlyphCheckerSection.module.css`

### 스타일 (필요 시)
- `GlyphChecker.module.css`: 견본과의 간격을 위해 상단 여백 소폭 조정. 시각 확인 후 필요할 때만.

## 판정 로직 공유 근거

페이지 게이트(섹션 노출 여부)와 `GlyphChecker` 내부 게이트(안내문 vs 검사 폼)가 **동일 조건**을 봐야 한다. 인라인 중복으로 두면 두 조건이 어긋나 "섹션은 보이는데 안내문만 뜨는" 불일치가 발생할 수 있다. 단일 함수로 묶어 오용을 원천 차단한다(misuse-proof).

## 적대적 리뷰 결과 (폰트 로딩 검증)

가장 큰 잠재 구멍: "상세 페이지에서 웹폰트 @font-face가 로드되지 않아 검사가 모든 글자를 미지원으로 오판정"할 위험. 코드로 검증한 결과 **닫혀 있음**.

- 검사 대상 폰트(fontKey 보유 8종: blackHanSans, jua, doHyeon, gowunBatang, nanumMyeongjo, kirangHaerang, gaegu, songMyung)는 `next/font/google`로 로드된다. 이 @font-face는 `app/layout.tsx:38`의 `<html className={fontClassNames}>`를 통해 **전역 적용**되므로 상세 페이지에서도 활성이다.
- 따라서 검사기는 `SpecimenBox`/`LazyFontPreview`의 지연 stylesheet 주입에 **의존하지 않는다**. SpecimenBox 아래 배치는 순수 UX 결정이며 로딩 의존성이 아니다.
- `GlyphChecker.handleCheck`의 `document.fonts.load('48px ' + canvasFamilyOf(fontKey))`는 전역 @font-face를 찾아 실제 다운로드를 트리거하므로 `loadedFaces.length > 0`. `display: "swap"` + `preload: false`라도 규칙 자체는 SSG 산출물에 포함되어 있어 최초 클릭에도 정상 로드된다.
- `FontKey`는 정확히 9종이고 `fontKeyToCanvasFamily`가 전부 커버 → 유효 fontKey에 대해 `canvasFamilyOf`가 null을 반환하지 않는다("검사할 폰트를 찾을 수 없습니다" 발생 안 함).

### 게이트가 정확히 맞는 이유 (미래 유지보수 주의)

게이트 `tier === "free" && fontKey !== null && fontKey !== "pretendard"`는 위 8종과 **정확히 일치**한다.
- pretendard: fontKey는 있으나 `next/font/google` 목록에 없는 로컬 폰트 → 명시적 제외(기존 "로컬 폰트는 글리프 검사를 지원하지 않습니다" 문구와 일치).
- fontKey가 없는 Tier A 폰트: `LazyFontPreview` stylesheet로만 로드되며 `fontKey !== null`에서 제외.
- 유료: `tier === "free"`에서 제외.

주의: 이 게이트를 `resolveFontPreview().stylesheetUrl` 유무로 바꾸면 안 된다. 8종은 stylesheetUrl이 `null`(next/font가 처리)이라 오히려 전부 숨겨진다. 현재 게이트가 정답이며 추가로 조이지 않는다.

## 테스트 (`app/fonts/[slug]/page.test.tsx` 추가)

- 무료 웹폰트(`nanum-myeongjo`): "글자 지원 검사" 노출.
- 유료(`sandoll-gothic-neo`): "글자 지원 검사" 없음.
- 로컬(`pretendard`): "글자 지원 검사" 없음.

기존 테스트 영향 없음: `GlyphChecker` 입력 `aria-label`은 "글자 검사 입력"으로 `SpecimenBox`의 "미리보기 입력"과 겹치지 않는다. 초기 렌더는 `useState`만 실행하고 `document.fonts`/canvas는 클릭 시에만 접근하므로 jsdom에서 안전하다. `next/font/google` 임포트는 기존 상세 테스트가 이미 `SpecimenBox` 경유로 처리하고 있어 신규 위험 없음.

실제 글자 검출 로직(canvas 기반)은 jsdom에서 검증 불가 → 단위 테스트는 노출/숨김만 다룬다. 검출 정상 동작은 빌드 후 상세 페이지에서 수동 확인 또는 e2e로 검증(권장 후속, 이번 범위 밖).

## a11y 참고

상세 페이지는 `<h1>`(폰트명) 다음 `GlyphChecker`의 `<h3>글자 지원 검사</h3>`로 h2를 건너뛴다(경미). 기존 컴포넌트를 최소 변경으로 유지하기 위해 h3 유지. 필요 시 후속에서 조정.

## 영향 범위

- playground 화면에서 검사 섹션 사라짐(의도된 이동).
- 폰트 상세(무료 웹폰트)에 검사 UI 추가.
- `GlyphCheckerSection` 삭제 — 다른 사용처 없음(grep 확인).

## 리스크

- 견본-검사기 간 간격: 스타일 한정 조정으로 해결.
- SSG/클라이언트 하이드레이션: 기존 상세 페이지가 이미 클라이언트 컴포넌트를 포함하므로 신규 위험 없음.
