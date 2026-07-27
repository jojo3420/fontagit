# 폰트 상세 굵기별 견본 + 이탤릭 지원 정보 설계 (#107)

- 작성일: 2026-07-27
- 관련: 이슈 #107, 선행 데이터 #104(Tier B weights 1,075종 보강 완료)
- 상태: 브레인스토밍 확정 + Codex 리뷰 반영(docs/review/review-result-20260727-093138.md)

## 1. 목표

폰트 상세 화면에서 "몇 가지 굵기를 지원하는가"를 숫자 하나가 아니라 **확인된 굵기별 실제 견본**으로 보여주고, 이탤릭 지원 여부를 정직하게(지원/미지원/미확인) 표시한다. 확인되지 않은 정보는 추정으로 채우지 않고, 브라우저가 합성한 가짜 굵기-이탤릭을 실제처럼 보여주지 않는다.

## 2. 사용자 확정 사항

| 항목 | 결정 |
|---|---|
| 배치 | 기존 견본 박스는 그대로 두고 그 아래 "지원 굵기" 섹션 신설 |
| 이탤릭 노출 | 지원이 확인된 굵기x이탤릭 조합은 전부 견본 행으로 노출. 미지원-미확인이면 이탤릭 견본 없음(배지만) |
| 라벨 표기 | 숫자 먼저, 오름차순: `400 Regular`, `700 Bold` |
| 로드 실패 행 | 행을 유지하고 견본 대신 "견본을 불러오지 못했습니다" 안내 표시 |

## 3. 데이터 계층

### 3.1 화면 모델 추가 필드
- `confirmedWeights: number[] | null` — DB `weights`가 비면 `null`(미확인). **개수 표시와 헤더 나열 전용**.
- `variants: string[] | null` — DB `variants` 컬럼 노출. **견본 행 구성의 SSoT**(어떤 굵기x스타일 조합이 실제 존재하는가).
- 기존 `availableWeights`(빈 값 `[400]` 폴백)는 기존 화면 회귀 방지를 위한 렌더링 폴백 전용으로 유지. 신규 UI에서 사용 금지.
- mapper의 weights 정규화: 숫자 변환 실패-1~1000 범위 밖 값 제거, 중복 제거, 오름차순 정렬. 결과가 비면 `confirmedWeights = null`.

### 3.2 variants 정규화 (Google Fonts 4형태)
`normalizeVariants(variants) → VariantCombination[]` (`{ weight: number, style: "normal" | "italic" }`):

| 원본 | 정규화 |
|---|---|
| `"regular"` | `{400, normal}` |
| `"italic"` | `{400, italic}` |
| `"700"` | `{700, normal}` |
| `"700italic"` | `{700, italic}` |

해석 불가능한 값은 무시(행 미생성). 중복 제거, weight 오름차순-normal 우선 정렬.

### 3.3 이탤릭 판정 `resolveItalicSupport(font)` (순수 함수)
- 정규화 조합에 italic 존재 → `supported` + 해당 조합 목록
- Tier A이고 variants가 비어 있지 않은데 italic 없음 → `unsupported`
- 그 외(variants 없음-빈 배열, Tier B/C) → `unknown` (Tier A라도 variants 미보유 구데이터면 unknown)

## 4. "지원 굵기" 섹션

### 4.1 컴포넌트 경계 (SSG 보존)
- `app/fonts/[slug]/page.tsx`는 **서버 컴포넌트 유지**(generateStaticParams/generateMetadata 불변).
- 신규 클라이언트 래퍼 `DetailSpecimenPanel`("use client")이 미리보기 문장 상태를 소유하고 SpecimenBox와 `WeightSpecimenSection`을 감싼다. SpecimenBox에는 선택적 controlled props(`text`/`onTextChange`)를 추가하되 단독 사용 하위 호환 유지.
- 폰트 스타일시트 로드는 래퍼에서 **1회로 통합**: 상세 화면에서는 전체 조합 시트(5.1)만 로드하고 SpecimenBox의 개별 시트 로드는 생략한다(중복 요청 방지).

### 4.2 표시 규칙
- 헤더: 확인 굵기 나열(`300 Light - 400 Regular - 700 Bold`) + 이탤릭 배지(`이탤릭 지원/미지원/정보 미확인`). 이름 매핑 상수 `weightLabels.ts`(100 Thin ~ 900 Black), 매핑 없는 값은 숫자만 표시.
- `confirmedWeights === null`: "굵기 정보 미확인" 표시, 견본 행 없음, 추정 금지.
- 견본 행(Tier A 한정): **정규화된 variants 조합마다 1행**(normal 먼저, italic 뒤). 각 행 = 라벨 + 공유 미리보기 문장. confirmedWeights에 있으나 variants에 없는 굵기는 행을 만들지 않는다(합성 방지).
- 미제공(정책)과 실패(오류) 구분:
  - Tier B/C: "이 폰트는 웹 견본을 제공하지 않습니다" + 공식 배포 페이지 링크(공식 URL 없으면 링크 없이 안내만). 유료 여부는 별도 문구(기존 유료 안내 유지)로 Tier와 혼동하지 않는다.
  - Tier A 미확인(variants 비어 있음): "굵기별 견본 정보를 확인하지 못했습니다"(공식 링크 미표시).
  - Tier A 로드 실패: 행 유지 + "견본을 불러오지 못했습니다".
- 모바일: 라벨 위-견본 아래 세로 스택, 가로 스크롤 금지.

## 5. 폰트 로딩-검증 (상세 전용)

### 5.1 로더
- 기존 `resolveFontPreview`(목록-공용 400/700)는 변경하지 않는다.
- 신규 `resolveDetailFontPreview(font)`: Tier A 한정, 정규화 조합 전체를 담은 Google Fonts CSS2 URL 생성(`ital,wght@` axis). Tier B/C는 외부 요청 자체를 만들지 않는다.

### 5.2 실로드 검증
- 시트 로드 후 조합마다 `document.fonts.load("italic 700 16px '<family>'", 검사문자열)` 형태로 확인. 검사 문자열은 고정 상수(예: "다람쥐 한글Aa1") — 사용자 입력과 무관하게 판정 일관성 유지.
- 로드 성공 판정은 반환된 FontFace의 weight/style이 요청 조합과 일치하는지 대조(관용 매칭으로 인한 오판 방지).
- 견본 행 CSS에 `font-synthesis: none` 적용 — 브라우저 합성 굵기-이탤릭 원천 차단.
- 방어 로직: link onerror 처리, 로드 검증 타임아웃(5초 → 실패 처리), 컴포넌트 unmount 후 setState 가드, 상태는 조합별로 관리(부분 실패 허용).

## 6. 화면 상태

1. 확인 중: 행 자리 스켈레톤
2. 미제공(Tier B/C)-굵기 미확인: 정보 목록 + 안내(4.2 문구)
3. 로드 실패(전체/부분): 해당 행 유지 + "견본을 불러오지 못했습니다"
4. 성공: 조합별 견본 행
- 섹션 하단 정적 안내 1줄: "폰트가 지원하지 않는 글자는 대체 글꼴로 표시될 수 있습니다."
- Meta 영역 `N가지 굵기`는 `confirmedWeights` 기준, 미확인이면 `굵기 정보 미확인`.

## 7. 테스트-검증

핵심 변환 로직만 최대 3개(핸드오프 원칙), vitest 기존 패턴:
1. `normalizeVariants` + `resolveItalicSupport`: 4형태 정규화와 지원/미지원/미확인 판정(불가값 무시 포함)
2. mapper weights 정규화: 중복-비수치-범위 밖 제거, 빈 결과 → `confirmedWeights null`
3. `resolveDetailFontPreview`: 조합 → CSS2 URL(ital,wght) 생성 + Tier B/C에서 URL 미생성

게이트: `pnpm --filter web test` + `pnpm --filter web lint` + `pnpm --filter web build`(SSG 2,500+ 페이지) 그린.

## 8. 예상 수정 파일 (10개)

- `apps/web/types/font.ts`, `apps/web/lib/db/types.ts`, `apps/web/lib/db/mappers.ts` — confirmedWeights-variants-정규화
- `apps/web/lib/fontPreview.ts` — resolveDetailFontPreview
- `apps/web/lib/weightLabels.ts` (신규) — 라벨 상수 + normalizeVariants + resolveItalicSupport
- `apps/web/components/DetailSpecimenPanel.tsx` (신규) — 클라이언트 래퍼(문장 상태 + 로더 통합)
- `apps/web/components/WeightSpecimenSection.tsx` (신규)
- `apps/web/components/SpecimenBox.tsx` — 선택적 controlled props
- `apps/web/app/fonts/[slug]/page.tsx` — 래퍼 배치(서버 컴포넌트 유지)
- 테스트 1파일 (`weightLabels.test.ts` 중심)

## 9. 수동 확인 완료 조건

- Tier A 다굵기 폰트: 조합별 견본 정상, 이탤릭 지원 폰트는 이탤릭 행 노출
- Tier A 이탤릭 미지원 폰트: "이탤릭 미지원" 배지, 이탤릭 행 없음
- Tier B 폰트: 미제공 안내 + 공식 링크, 견본 행 없음
- 굵기 미확인 폰트: "굵기 정보 미확인"
- 네트워크 차단 시: 로드 실패 안내(합성 견본 미노출)
- 모바일 뷰포트: 세로 스택, 가로 스크롤 없음

## 10. 제외 범위 (이슈 동일)

- Tier B/C 폰트 파일 신규 수집-셀프호스팅, 눈누 등 외부 사이트 추가 요청 없음
- 확인되지 않은 굵기-이탤릭 추정 표시 없음
- 목록 카드의 굵기 표시 변경 없음(상세 화면 한정)
- 입력 글자 단위 글리프 전수 검사 없음(기존 GlyphChecker 역할, 6장의 정적 안내로 갈음)
