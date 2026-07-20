# 설계: /fonts 용도별 섹션 계층화 + 타입 캔버스 통합

- 이슈: #60 (에픽) — /fonts 컬렉션 계층화 + 타입 캔버스 통합
- 브랜치: `feat/60-fonts-section-canvas`
- 작성일: 2026-07-20
- 목업: `docs/mockups/2026-07-20-fonts-section-canvas/` (구조안/분류안/캔버스배치안)

## 1. 목표와 문제

**목표**: 서체 입문자가 "언제 어떤 서체를 써야 하는지" 스스로 고를 수 있도록 `/fonts`를 용도별로 안내한다.

**문제(AS-IS)**: 현재 `/fonts`는 폰트를 평면(flat) 목록으로 나열한다. 고딕체가 다수인데 그룹화가 없어, 입문자는 수많은 고딕 중 무엇이 본문용인지 제목용인지 구분하지 못하고 선택에 막힌다.

**해결(TO-BE)**: 폰트를 5개 **용도 섹션**으로 그룹화해 각 섹션에 한 줄 가이드와 대표 폰트를 보여주고, 상단 **타입 캔버스**(문구 입력창)로 원하는 문구를 모든 섹션 폰트에 실시간 미리보기한다.

## 2. 확정된 결정 (브레인스토밍 결과)

1. **조직 방향**: 용도별 섹션 중심 (구조안 A). 컬렉션은 섹션 내부 큐레이션으로 편입.
2. **섹션 분류 (5분류)**:
   - `body` 본문-긴 글 — 오래 읽어도 편안한 서체 (문서/블로그/앱 본문)
   - `headline` 제목-강조 — 시선을 잡는 굵고 큰 서체 (헤드라인/배너)
   - `brand` 브랜드-감성 — 분위기를 만드는 명조-세리프 (에디토리얼/감성)
   - `handwriting` 손글씨-캐주얼 — 친근한 손글씨 (SNS/인사말)
   - `decorative` 개성-장식 — 튀는 디스플레이 (포스터/이벤트/굿즈)
3. **폰트 배정 = 하이브리드 (C안)**: 자동 매핑으로 전체를 즉시 배치(커버리지 100%) + LLM 큐레이션으로 각 섹션 "에디터 추천" 오버레이 + 사람 스팟 검수. 한 폰트는 **한 대표 섹션에만** 배정(MVP).
4. **타입 캔버스 배치 = 상단 슬림 스티키 바 (A안)**: 스크롤해도 상단 고정. 기본 문구는 팬그램, 초기화 버튼 제공.
5. **섹션 "더보기" = 별도 필터 뷰** `/fonts?section=<슬러그>`: 기존 URL searchParams 필터+무한스크롤 재사용.
6. **컬렉션 페이지 유지**: `/collections`, `/collections/[slug]` 그대로 유지(SEO/링크 보존). 컬렉션은 섹션의 에디터 추천 큐레이션 소스로도 활용.
7. **전체 폰트 보기**: 상단 "전체 폰트 보기" 링크 → `/fonts?section=all`(기존 평면 목록+필터).

## 3. 아키텍처

### 3.1 데이터 계층 (신규)

- `apps/web/lib/sections.ts`
  - `SECTIONS`: 5개 섹션 정의 상수 배열 (`slug`, `label`, `guide`, `order`).
  - `sectionOf(font): SectionSlug` — 자동 매핑 순수 함수. DB 변경 없음. 규칙:
    - 손글씨 분류 → `handwriting`
    - 장식/디스플레이 분류 → `decorative`
    - 명조/세리프 분류 → `brand`
    - 고딕/산세리프 분류 → `font.availableWeights`(number[], 매퍼가 빈 배열 시 [400] 기본값 보장)에서 굵은 굵기(700 이상)만 있고 본문 굵기(400)가 없으면 `headline`, 아니면 `body`
    - 미분류/기타 → `body` (fallback)
    - (정확 임계값-키워드 보조는 TDD로 확정)
  - `groupFontsBySection(fonts): Record<SectionSlug, Font[]>` — 섹션별 그룹핑. 빈 섹션은 UI에서 숨김.
- `apps/web/data/sectionCuration.ts` (신규, LLM 큐레이션 오버레이)
  - 섹션별 "에디터 추천" 폰트 slug 목록 + (선택) 연결 컬렉션 slug. 정적 데이터로 시작(DB 마이그레이션 불필요). 유효성 테스트로 slug 실존 보장.

### 3.2 라우팅/페이지

- `apps/web/app/fonts/page.tsx` (서버 컴포넌트, 개편)
  - `searchParams.section` 없음 → **섹션 개요 모드**: `getAllFonts()` → `groupFontsBySection` → **서버에서 섹션별 top N + 총개수만 추려** `SectionedFontsView`로 전달(클라이언트 직렬화 페이로드 절감).
  - `section=all` 또는 기타 필터 존재 → **평면 목록 모드**: 기존 `ClientFontFilters` + `ClientFontsList`(섹션 필터 반영).
- 섹션 상세는 별도 라우트가 아니라 `/fonts?section=<슬러그>` 쿼리로 평면 목록 모드 + 섹션 필터.

### 3.3 클라이언트 컴포넌트 (신규/수정)

- `SectionedFontsView`(신규, 클라이언트): 그룹핑된 폰트를 받아 (1) 상단 슬림 스티키 **타입 캔버스 바**의 문구 상태 `useState(text)`를 보유, (2) `FontSection[]`을 렌더하며 `previewText`를 아래로 전달.
- `TypeCanvasBar`(신규, 클라이언트): 문구 입력 + 초기화. 상태는 `SectionedFontsView`가 소유(상태 끌어올리기). 스티키 CSS.
- `FontSection`(신규): 섹션 헤더(라벨+가이드) + 에디터 추천(있으면 상단) + 대표 폰트 상위 N개(예: 12) + "더보기" 링크(`/fonts?section=slug`).
- `FontCard`(수정): 선택적 `previewText?: string` prop 추가. 있으면 `getSpecimenText()` 대신 해당 문구 렌더. 없으면 기존 팬그램 유지(하위 호환). `previewText`는 반드시 기존 `LazyFontPreview` 렌더 경로를 통해 표시해 뷰포트 밖 카드의 웹폰트 조기 로딩을 막는다.
- `lib/filters.ts`(수정): `parseFilterQuery`가 `section` 파라미터를 읽고, `filterFonts`가 `sectionOf`로 섹션 필터를 적용.

### 3.4 데이터 흐름 (타입 캔버스 실시간 동기화)

```
사용자 입력 → TypeCanvasBar → SectionedFontsView.setText
  → 모든 FontSection에 previewText prop 전파
  → 각 FontCard가 previewText로 견본 렌더 (실시간)
```

기존 `getSpecimenText(font)` 팬그램 로직은 `previewText`가 비어 있을 때의 기본값으로 재사용한다.

### 3.5 성능 고려 (agy 리뷰 반영)

- **입력 랙 방지**: 캔버스 문구를 `useDeferredValue`로 감싸 FontCard 렌더에 전달한다. 매 키 입력마다 노출 카드가 동기 리렌더되어 버벅이는 것을 막는다.
- **지연 로딩 유지**: 위 3.3의 `LazyFontPreview` 통합으로 뷰포트 밖 카드는 문구가 바뀌어도 로딩/렌더하지 않는다.
- **페이로드 절감**: 3.2의 서버 그룹핑 top N 전달로 개요 모드 초기 페이로드를 현재보다 줄인다.
- **참고**: 현재 `/fonts`는 이미 전체 폰트를 클라이언트로 전달+무한스크롤이므로, 위 조치는 신규 회귀 방지가 아니라 기존 대비 개선/유지 목적이다.

## 4. 범위

**포함(이번 브랜치)**: 위 결정 1~7의 구현.

**제외(YAGNI / 별도 이슈)**:
- 폰트/컬렉션 데이터 시딩 (#28) — 이번엔 "틀"만, 데이터 늘면 자동 반영
- 컬렉션 페이지 제거/리다이렉트
- DB 스키마 변경(`usage_section` 컬럼) — 런타임 순수 함수로 시작
- 한 폰트의 다중 섹션 소속
- 사용자별 저장/로그인

## 5. 구현 순서 (vertical slice)

1. **Slice 1 — 자동 매핑 뼈대**: `sections.ts`(sectionOf/grouping) + `/fonts` 섹션 개요 렌더. (1단계 핵심)
2. **Slice 2 — 타입 캔버스**: `TypeCanvasBar` + `SectionedFontsView` 상태 끌어올리기 + `FontCard.previewText` 실시간 동기화. (3단계)
3. **Slice 3 — 큐레이션 오버레이**: `sectionCuration.ts`(에디터 추천) + 섹션 가이드 문구 + 사람 스팟 검수 대상 산출.
4. **Slice 4 — 섹션 상세/전체 보기**: `?section=slug` 필터 뷰 + `?section=all` 전체 보기 링크.

## 6. 테스트 계획

- `lib/sections.test.ts`: 분류별 → 섹션 매핑, 고딕 굵기 기반 headline/body 분기, 미분류 fallback, `groupFontsBySection` 빈 섹션 처리.
- `data/sectionCuration` 유효성: 추천 slug가 실제 폰트에 존재.
- `lib/filters.test.ts`(확장): `section` 파라미터 파싱 + `filterFonts` 섹션 필터.
- `SectionedFontsView` 통합: 캔버스 입력 → 여러 FontCard 견본 동시 갱신.
- `FontCard.test.tsx`(확장): `previewText` 있으면 우선, 없으면 팬그램.
- `app/fonts/page.test.tsx`(확장): 섹션 개요 렌더 / `?section=` 시 평면 목록 렌더.

## 7. 리스크와 완화

- **자동 매핑 부정확(고딕 본문/제목 애매)**: 큐레이션 오버레이 + 사람 스팟 검수로 상단 품질 확보. 임계값은 TDD로 조정.
- **무명 폰트 오분류(눈누 수집 1,110종)**: 이름+분류만으론 한계 → 스팟 검수 대상으로 산출.
- **서버→클라이언트 렌더 전환 성능/SSG**: 섹션당 상위 N개만 초기 렌더, 상세는 기존 무한스크롤 재사용.
- **`FontCard` 하위 호환**: `previewText` 선택적 prop이라 기존 호출부(컬렉션 페이지 등) 영향 없음.
