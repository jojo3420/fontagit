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

## 테스트 (`app/fonts/[slug]/page.test.tsx` 추가)

- 무료 웹폰트(`nanum-myeongjo`): "글자 지원 검사" 노출.
- 유료(`sandoll-gothic-neo`): "글자 지원 검사" 없음.
- 로컬(`pretendard`): "글자 지원 검사" 없음.

기존 테스트 영향 없음: `GlyphChecker` 입력 `aria-label`은 "글자 검사 입력"으로 `SpecimenBox`의 "미리보기 입력"과 겹치지 않는다.

## 영향 범위

- playground 화면에서 검사 섹션 사라짐(의도된 이동).
- 폰트 상세(무료 웹폰트)에 검사 UI 추가.
- `GlyphCheckerSection` 삭제 — 다른 사용처 없음(grep 확인).

## 리스크

- 견본-검사기 간 간격: 스타일 한정 조정으로 해결.
- SSG/클라이언트 하이드레이션: 기존 상세 페이지가 이미 클라이언트 컴포넌트를 포함하므로 신규 위험 없음.
