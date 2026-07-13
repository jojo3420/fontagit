# progress-001: 웹 프론트엔드 토대 + 핵심 화면 (Phase 1-2) (2026-07-13)

## 맥락
Claude Design 핸드오프 번들(`docs/design/fontagit-v2/`)의 확정 화면을 실제 제품(apps/web)으로 구현. 마스터플랜(v3.0) 확정 스택 = Next.js SSG. origin/main에는 apps/pipeline만 있었고 apps/web은 이 작업으로 처음 도입. 범위는 확정 13화면 중 Phase 1-2(토대 + 홈/목록/상세/트렌드/404). Phase 3-4는 후속.

## 구현 요약 (무엇을 어디에)
- 스택: Next.js 16.2.10 App Router, React 19.2.4, TypeScript. 정적 출력 `output: 'export'`(`next.config.ts`), `images.unoptimized`, `trailingSlash`. 산출물 `out/`. 패키지명 `web`(루트 `pnpm --filter web`와 정합). apps/web은 자체 pnpm-lock.yaml/pnpm-workspace.yaml 보유.
- 스타일: Tailwind 제거. `styles/tokens.css`의 CSS 변수(라이트 `:root` + 다크 `:root[data-theme="dark"]`) + 컴포넌트별 CSS Modules. 인라인 스타일은 데이터 기반 `fontFamily`만 예외.
- 폰트: Pretendard(npm 패키지 CSS import, UI). 견본 한글 8종 `next/font/google`(Black Han Sans/Jua/Do Hyeon/Gowun Batang/Nanum Myeongjo/Kirang Haerang/Gaegu/Song Myung), `preload:false`+`display:swap`, 단일굵기는 weight 명시. Song_Myung은 Next 타입상 subsets/preload 미지원이라 생략(정상). `lib/fonts.ts`가 `fontClassNames`(html에 CSS변수 클래스) + `fontKeyToVar`(FontKey→font-family) export.
- 데이터: `types/font.ts`에 `FontKey` 유니언(9키) + `Font/TrendItem/Collection`. `data/fonts.ts`(10종 목업), `data/trends.ts`(weekly/monthly). `lib/data.ts` 헬퍼: `getFontBySlug`, `getAllSlugs`, `resolveFreeAlternatives`(무료-최대3), `assertDataIntegrity(FONT_KEYS)`(모듈 로드시 호출 = 빌드시 무결성 검사: 중복slug/미매핑fontKey/freeAlt 참조-자기참조-유료 검사).
- 라우트: `/`(홈), `/fonts`(목록), `/fonts/[slug]`(상세, tier 분기 + 무료대안), `/trends`, `not-found.tsx`. 동적 라우트는 async `params: Promise<{slug}>` + `await params` + `generateStaticParams` + `dynamicParams=false` + `notFound()`.
- 컴포넌트: TierChip, LicenseBadge(아이콘+텍스트 WCAG AA, 3상태), Button(href면 next/link/else `type="button"`), FilterChip(`type="button"`+`aria-pressed`, 시각만), Header(로고 A만 포인트색, nav 4), Footer, Hero, TrendRow/TrendTable(named export), FontCard(**Link로 상세 이동** — 리뷰에서 수정됨), FontGrid(3→2→1 반응형), PreviewInput(`"use client"` 컨트롤드 입력, 라이브 반영), Specimen(대체 견본 라벨), AdSlot(90px 고정 CLS 방지). 루트 layout `lang="ko"` + FOUC 방지 인라인 테마 스크립트(localStorage→prefers-color-scheme, `suppressHydrationWarning`).
- 테스트: Vitest(`lib/data.test.ts` 4 + `LicenseBadge.test.tsx` 3 = 7). Playwright 스모크(`e2e/smoke.spec.ts`, 26 케이스): 실제 라우트 콘솔에러0 + 스크린샷 baseline, 404는 브랜드내용 단언. vitest는 e2e 제외 설정.

## 시도와 실패 (재발 방지)
- SDD 서브에이전트 구현 중 반복 결함: (1) 디자인 토큰 임의 생성(정확 값으로 교체), (2) 데이터 테스트가 `assertDataIntegrity`에 필드명을 FontKey로 오용 → tsc 에러 + 가짜 should-throw 테스트(정본 교체, validKeys 실사용), (3) next/font를 `as any`/`@ts-ignore`로 우회(타입 정확 설정으로 교체 — Song_Myung은 subsets 미지원이 정상), (4) 영어 "moves"(→"이동 N회"), (5) Phase3 nav prefetch 404(prefetch=false), (6) 404 스모크 오단언, (7) vitest가 Playwright 스펙 수집 충돌(e2e 제외). 교훈: 순수 전사 태스크도 정확 값 준수 검증 필요(테스트 파일/토큰은 반드시 원문 대조).
- FontCard가 `<article>`이라 상세 이동 링크 없던 버그를 controller 검증이 놓침 → PR 듀얼 리뷰(Codex)가 포착, `<Link>`로 수정.

## 결정 근거와 기각된 대안
- 스타일: CSS Modules+토큰 채택(Tailwind 기각) — 세션 결정. `/web-setup`이 만든 Tailwind 스캐폴드를 세션 결정 우선으로 재정비.
- 데이터: 목업 하드코딩(파이프라인 실연동 기각) — 디자인 95% 재현 우선, 필드명은 파이프라인 `FontRecord`와 정합.
- 폰트: next/font/google self-host(CDN 기각). 리스크: 빌드시 Google 폰트 네트워크 의존(네트워크 차단 CI면 실패 가능 — 이슈화되면 next/font/local 검토).
- 인터랙션: 핵심만 동작(미리보기 입력-다크토글), 필터/검색/트렌드탭은 의도적 비동작 목업.

## 재현-검증 명령어
```
cd apps/web
pnpm install
pnpm exec tsc --noEmit     # 0 errors
pnpm test                  # 7 passed (vitest, e2e 제외)
pnpm build                 # SSG, out/ 16 pages
pnpm exec playwright test  # 26 passed
pnpm exec eslint .         # clean
pnpm --filter web dev      # 육안 확인 (루트에서)
```

## PR 리뷰 (request-pr-dual, PR #4)
Codex(gpt-5.6-sol) 단독 유효(agy는 stdin 프롬프트 미처리로 실패 → Degraded). Must-fix 1건(FontCard 링크 누락) 확인-수정. 함께 수정: 상세 여백, `start`=`serve out`/`e2e`=`next build && playwright test`, 확인일 표시. 리포트: `docs/review/pr-review-4-dual-20260713-120348.md`. PR #4 merge 커밋 `4fe1da5`로 main 반영.
