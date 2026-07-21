# progress-009: /fonts 용도별 섹션 계층화 + 타입 캔버스 통합 (2026-07-21)

## 맥락 (왜 필요했나)
- 이슈 #60(에픽). 원 요청: "/fonts 경로 고도화 및 컬렉션 페이지와 합치기".
- 진짜 문제: 서체 입문자가 고딕이 많은데 그룹이 없어 "언제 뭘 쓰는지" 모름. 용도 섹션 그룹화 + 실시간 미리보기로 선택 가이드 제공.
- 범위: 1단계(섹션 계층화) + 3단계(타입 캔버스). 2단계(데이터 확충)는 #28로 분리.

## 구현 요약 (무엇을 어디에)
- `apps/web/lib/sections.ts`(신규): `SectionSlug`(body/headline/brand/handwriting/decorative), `SECTIONS`(라벨+가이드+order 1~5), `sectionOf(font)` 순수 매핑(category+availableWeights), `groupFontsBySection`, `orderByCuration(fonts, recommendedSlugs=[])`(추천 앞 정렬, 안정). DB 스키마 무변경.
  - sectionOf 규칙: 손글씨→handwriting, 장식→decorative, 명조→brand, 고딕→(availableWeights에 700미만 있으면 body, 아니면 headline), 그외 default→body.
- `apps/web/data/sectionCuration.ts`(신규): `SECTION_CURATION: Record<SectionSlug,string[]>` 에디터 추천 slug. 시작 세트=유명폰트(body: pretendard/do-hyeon, brand: nanum-myeongjo/gowun-batang, handwriting: kirang-haerang/gaegu, decorative: jua, headline: []). 유효성 테스트가 실존+sectionOf 일관성 보증.
- 컴포넌트(신규): `FontSection`, `SectionOverview`(섹션당 top 12, useMemo로 grouping/정렬 캐싱, 빈 섹션 생략), `TypeCanvasBar`(스티키 입력+초기화, controlled), `SectionedFontsView`(useState+useDeferredValue로 문구 소유), `FontsViewWrapper`(클라 useSearchParams 개요/평면 분기).
- 수정: `FontCard`(previewText prop: 있으면 통문구, 공백-only는 팬그램 fallback, 기존 LazyFontPreview 지연로딩 경로 유지), `FontGrid`/`FontSection`/`SectionOverview`(previewText 전파), `ClientFontsList`(?section=slug를 sectionOf로 선필터 — lib/filters.ts 미오염), `app/fonts/page.tsx`(서버는 getAllFonts만, 렌더 분기는 FontsViewWrapper).
- 데이터 흐름(캔버스): TypeCanvasBar 입력 → SectionedFontsView setText → useDeferredValue(text) → SectionOverview.previewText → FontSection→FontGrid→FontCard 실시간 갱신.
- 라우팅: 파라미터 없으면 개요, section/category/tier/source 있으면 평면(ClientFontFilters+ClientFontsList). ?section=all=전체, ?section=slug=해당 섹션. 필터 UI는 평면 모드에서만(사용자 결정).

## 시도와 실패 (다시 밟지 말 것)
- **output:'export' 정적빌드 함정(핵심)**: 최초 page.tsx를 서버 컴포넌트로 두고 `await searchParams`로 개요/평면 분기하게 구현(Task 4). 유닛테스트는 통과했으나 `next build`(정적 export)에서 깨짐 — 정적 export는 빌드 타임 사전렌더라 request-time searchParams가 없음. 해결: 클라이언트 `FontsViewWrapper`가 `useSearchParams`로 분기(page.tsx는 폰트만 서버 fetch). 이후 /fonts 관련 라우팅은 반드시 클라 훅으로.
- agy 설계리뷰가 "지연로딩 미구현/weights 파싱 방어 필요"를 지적했으나 코드 대조 결과 이미 `LazyFontPreview` 존재 + weights는 number[]/매퍼 [400] 보장이라 대부분 무효(환각/맥락오해). 유효한 건 useDeferredValue(입력 랙) 하나.
- SDD 서브에이전트가 자기를 오케스트레이터로 오해해 "위임"만 하고 작업 미수행한 사고 1회 → 재디스패치 시 "너는 leaf 구현자, 직접 Edit, 2파일 제한은 서브에이전트 비적용" 명시 + read-loop bypass 토큰으로 해결.

## 결정 근거와 기각된 대안
- 조직 방식: 용도별 섹션(A) 채택 vs 컬렉션 우선(B)/하이브리드(C) 기각 — 입문자 "상황→서체" 안내에 용도 섹션이 정공법.
- 배정: 하이브리드(자동 매핑 뼈대 + LLM 큐레이션 오버레이) 채택 vs 순수 자동(부정확)/순수 큐레이션(커버리지 빈약, 데이터 대기) 기각. LLM 큐레이터는 메타데이터 기반(글리프 렌더 못 봄)이라 유명폰트 정확+무명 사람 스팟검수 전제.
- 캔버스 배치: 상단 슬림 스티키(A) 채택 vs 히어로(B)/축소형(C) 기각 — "한번 입력 어디서나 미리보기"를 최소 복잡도로.
- M1(빈 weights→headline) 방어 미추가: 매퍼가 [400] 보장(경계 방어 완료), 내부 중복 방어는 coding-style 위반이라 패스.

## 재현-검증 명령어
- 전체 테스트: `cd apps/web && npm test` (229/229 green)
- 정적 빌드: `cd apps/web && npm run build` (정적 export 성공, 1,240여 페이지)
- 핵심 로직: `npx vitest run lib/sections.test.ts data/sectionCuration.test.ts`
- 리뷰 기록: agy 설계리뷰 `docs/review/review-result-agy-20260720-214801.md`, agy PR리뷰 `docs/review/pr-review-agy-92-20260721-091817.md`
- 설계/계획: `docs/superpowers/specs/2026-07-20-fonts-section-hierarchy-canvas-design.md`, `docs/superpowers/plans/2026-07-20-fonts-section-hierarchy-canvas.md`
