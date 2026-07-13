# progress-002: 웹 Phase 3-4 확장 화면 + 마감 (2026-07-13)

## 맥락
Phase 1-2(토대 + 홈/목록/상세/트렌드/404)가 main에 머지된 상태에서, 확정 13화면 중 Phase 3-4(확장 5 + 마감 3)를 구현. 계획서 `2026-07-13-fontagit-web-phase3-4.md`를 Codex(gpt-5.6-sol) 리뷰로 검증-보강한 뒤 subagent-driven-development로 실행. 브랜치 develop, Base `413e3fb`(계획 + 리뷰 커밋).

## 구현 요약 (무엇을 어디에)
- 타입 캔버스 `/playground`(3a): `PlaygroundCanvas`(use client). 입력 하나가 96px 대표 견본 + 무료 폰트 그리드를 라이브 반영. 프리셋 3종-지우기.
- 비교 `/compare`(5a): `CompareBoard`(use client). 문장 라이브 + 3열 고정 슬롯을 `<select>`로 교체(무료 폰트만).
- 컬렉션 데이터 + 무결성(TDD): `data/collections.ts`(3종, 9참조 실존). `lib/data.ts`에 `getCollectionBySlug`/`getAllCollectionSlugs` + `assertDataIntegrity` 확장(컬렉션 중복 slug-빈 items-미실존 fontSlug). 모듈 로드 시 호출 = 빌드타임 검증. 최종에 `checkIntegrity(fonts,collections,keys)` 순수함수로 추출 + negative 테스트.
- 컬렉션 목록 `/collections` + 상세 `/collections/[slug]`(8a): `CollectionCard`, 동적 라우트 정본(`dynamicParams=false` + `generateStaticParams` + async `params` + `notFound`). 헤더 nav `/collections` 복원.
- 창작자 등록 `/submit`(8b): 서버 page(metadata) + `SubmitForm`(use client, 시맨틱 `<form onSubmit preventDefault>`, 비동작 목업). 헤더 nav `/submit` 복원 → nav 404 블로커 완결.
- 빈 상태 `EmptyState`: 컬렉션 목록의 empty 분기(UI 상태 완전성, 방어적).
- 모바일 `MobileTabBar`(4a/4c): use client, `usePathname`, 하단 고정 56px + `env(safe-area-inset-bottom)`, 620px 이하만 표시. layout 마운트 + globals 하단 패딩.
- 다크 토글 `ThemeToggle`(9b): 헤더 버튼. 최초 useEffect 방식 → 최종 `useSyncExternalStore`(MutationObserver로 `data-theme` 구독)로 근본 전환. FOUC 스크립트(Phase 1-2)와 `suppressHydrationWarning` 재사용.
- 런칭 자산(7a/7b): `app/icon.tsx`(파비콘, 한글 없음), `opengraph-image.tsx`(기본 OG), `fonts/[slug]/opengraph-image.tsx`(폰트별 OG, `generateStaticParams`). satori에 Pretendard-Bold.otf를 `fonts` 옵션으로 임베드해 한글 렌더. OG 파일은 CSS 변수 불가로 인라인 스타일 예외.

## 시도와 실패 (재발 방지)
- SDD 구현 서브에이전트가 브리프의 완전한 코드/CSS를 자주 임의 변경(9 Task 중 6건 리뷰 리젝트): CSS 값을 rem으로/픽셀 다르게, 존재하지 않는 CSS 변수 발명(`--text-primary`/`--bg-hover` 등 → 스타일 깨짐), 브리프에 없는 필드-라벨 추가(scope creep), 카피/테스트 어서션 약화, page 구조 변경. 교훈: 디스패치에 "브리프 CSS를 한 글자도 바꾸지 말고 그대로 옮기라 + 프로젝트 토큰만 + deviation=리뷰 실패"를 명시하니 Task 4 이후 첫 시도 clean율 상승. 리뷰 게이트가 전부 포착-수정.
- 계획(브리프) 코드 자체 결함 2건: (1) ThemeToggle useEffect 동기 setState가 최신 `react-hooks/set-state-in-effect` eslint 규칙 위반 → useSyncExternalStore로 근본 해결. (2) 무결성 negative 테스트 부재(전역 참조라 나쁜 데이터 주입 불가) → 순수함수 추출로 해결.
- OG 한글: satori는 시스템 폰트 접근 불가라 폰트 미임베드 시 한글이 tofu. Codex 리뷰가 사전 포착 → 계획에 폰트 임베드 반영, 구현서 실경로 확인 후 적용.

## 결정 근거와 기각된 대안
- 비교 인터랙션: 문장 라이브 + 3고정 슬롯 select(슬롯 추가/삭제 기각) — 인터랙션 "핵심만" 결정 준수, 스펙 "최대 3종"에 3고정으로 부합.
- 등록 폼: 시맨틱 `<form>` + preventDefault(비동작 `<div>` 기각) — 접근성. Codex 리뷰 반영.
- 다크 토글: useSyncExternalStore(useEffect setState 기각) — eslint 규칙 + React 권장 외부 시스템 동기화.
- OG 폰트: 시스템 sans-serif 기각(한글 깨짐), 견본 웹폰트 임베드 기각(라이선스/빌드 복잡) → Pretendard만 임베드.

## 재현-검증 명령어
```
cd apps/web
pnpm install
pnpm exec tsc --noEmit     # 0 errors
pnpm test                  # vitest 14 passed (10 + negative 4)
pnpm build                 # SSG, out/ 23 pages + OG PNG
pnpm exec eslint .         # clean
pnpm exec playwright test  # 60 passed
```

## 리뷰
- 계획 검증: Codex(gpt-5.6-sol, xhigh) + Claude 크로스 리뷰 → Must 6 + 주요 Should 6 계획 반영(한글 OG 임베드, zsh 글로빙 따옴표, OG 예외 명시, 폼 시맨틱, 검증 문구, 95% 육안 대조 등). 리포트 `docs/review/review-result-20260713-145158.md`.
- Task별 리뷰(9): spec + quality 게이트. 6건 리젝트→수정→clean, 3건 첫 시도 approved.
- 최종 전체 브랜치 리뷰(opus): With fixes, Critical 0. Important 2(무결성 negative 테스트, metadataBase) + eslint 1건을 ONE fix subagent로 처리. metadataBase는 배포 시점 보류.

## 남은 일 / TODO
- 배포 도메인 확정 후 `app/layout.tsx` metadata에 `metadataBase: new URL(...)` 설정(og:image 절대 URL이 현재 localhost).
- 필터/검색/등록 폼은 비동작 목업 → 백엔드 연동 시 실동작 + Defensive Input 검증.
- 실데이터 파이프라인 연동(현재 목업).
