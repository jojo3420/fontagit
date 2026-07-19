# #54 /compare 제거 → 홈 통합 설계

> 작성 2026-07-18, 개정 2026-07-18(codex 리뷰 반영) - SSOT: [GitHub 이슈 #54](https://github.com/jojo3420/fontagit/issues/54)
> 목적: 별도 라우트 `/compare`의 비교 기능을 메인 홈("/")으로 통합하고 라우트를 제거한다.
> 미리보기 목업: `docs/mockups/2026-07-18-compare-home-merge/index.html`
> 리뷰: `docs/review/review-result-20260718-152110.md`(codex 7/10 + 크로스리뷰)

## 1. 배경 - 목표
- 배경: 폰트 비교 기능이 `/compare` 별도 라우트로 분리돼 있음. 이슈 #54가 메인 통합 요청.
- 목표: (a) 비교 기능을 홈에서 사용 가능하게, (b) `/compare` 라우트 제거, (c) 기존 `CompareBoard` 재사용.
- 범위 경계(이슈 코멘트): 본 이슈는 "화면 구성/상호작용" 담당. 캔버스 자체 기능은 #55, 문구 동기화 통합은 #60 3단계 — 본 작업 범위 아님.

## 2. 확정 결정 (브레인스토밍 + codex 리뷰 반영)
| # | 항목 | 결정 |
|---|------|------|
| 1 | 통합 위치 | 메인 홈("/") full-width 섹션. 주간랭킹 아래-광고 위 |
| 2 | /compare URL | 라우트 완전 제거(404) + sitemap에서 삭제 |
| 3 | 데스크톱 헤더 "비교" | `/#compare` 앵커로 변경 |
| 4 | 홈 성능(CWV) | `React.lazy` 코드분할 + `IntersectionObserver` 뷰포트 지연으로 `CompareBoard` 지연 로드(프로젝트 기존 패턴 `LazyFontPreview` 준수). Next 16에 `next/dynamic` 진입점 없어 미사용. #25 회귀 방지 |
| 5 | 모바일 탭바 "비교" | **유지** → `/#compare`(모바일은 헤더 tool 링크가 숨겨져 탭바가 유일 진입점, 발견성 보존). 재확정 |
| 6 | 앵커 스크롤 | `#compare`에 `scroll-margin-top`(sticky 헤더 높이). 크로스페이지 이동 동작 Next 문서 확인 |
| 7 | 섹션 소유(신규) | 서버 `page.tsx`가 `<section id="compare">`+자리표시 소유(SSG HTML 상주), 내부 `CompareBoard`만 클라이언트 지연 로드 |
| 8 | 404 안내 | 결정 철회. `not-found.tsx` 미변경(이미 "홈으로" 일반 안내 존재, 전역 404 오염 방지) |

## 3. 변경 범위 (조사 실측)
| 구분 | 파일 | 변경 |
|------|------|------|
| 홈 통합 | `app/page.tsx` | 서버에서 `<section id="compare">`+자리표시 렌더, 내부 보드는 `CompareLazy` 배치. 주간랭킹 아래-광고 위 |
| 지연 로드 | `components/CompareLazy.tsx`(신규) | `React.lazy(() => import('./CompareBoard'))` + `Suspense` 클라이언트 래퍼. IntersectionObserver로 뷰포트 진입 시 마운트, 1회 관찰 후 disconnect+유지, 미지원 즉시 렌더 |
| 라우트 제거 | `app/compare/page.tsx` + `app/compare/` | 삭제 |
| 네비(데스크톱) | `components/Header.tsx:19` | `/compare` → `/#compare` |
| 네비(모바일) | `components/MobileTabBar.tsx:11` | `/compare` → `/#compare`(항목 유지). 홈 앵커라 active 판정 로직 점검 |
| SEO | `app/sitemap.ts:26` | `/compare/` 제거 |
| 스타일 | `components/CompareBoard.module.css` | 홈 섹션 폭 조정 + 자리표시 min-height 반응형(모바일 1열/데스크톱 3열) — CLS 방지 |
| 테스트 | `app/sitemap.test.ts:23` | 기대값에서 /compare 제거 |
| SEO 검증 | `scripts/verify-seo-output.mjs:12`, `.node-test.mjs:13` | 기대 URL 제거 |
| e2e | `e2e/smoke.spec.ts`(10, 82~148) | /compare 페이지 테스트 → 홈 비교 섹션+앵커 검증으로 전환. 모바일 탭바 비교 href `/#compare`로 기대 수정. 스냅샷 `compare-screenshot-*.png` 삭제 |

**재사용 유지**: `CompareBoard.tsx`(로직 무변경). **미변경**: `app/not-found.tsx`.

## 4. 컴포넌트 - 데이터 흐름
- 홈(`page.tsx`, 서버 컴포넌트): `<section id="compare" style=scroll-margin>`와 자리표시(min-height)를 **서버 HTML로 출력**. 내부에 `CompareLazy` 배치. → 앵커가 초기 HTML에 상주해 직접/크로스페이지 이동 안정.
- `CompareLazy`(신규, 클라이언트): 단일 책임 = "`CompareBoard`를 코드분할로 지연 로드". `React.lazy` + `Suspense`(프로젝트 `LazyFontPreview`의 IntersectionObserver 패턴 차용). 로드 전까지 자리표시 유지(CLS 0). IntersectionObserver로 뷰포트 진입 시 로드, 진입 후 disconnect하여 상태(입력/폰트선택) 유지, 미지원 브라우저 즉시 로드.
- `CompareBoard`: 로직 무변경(heading `<h1>`→`<h2>`만 조정). 무료 폰트 3슬롯 + 입력 문장 실시간 렌더. `data/fonts` import도 코드분할로 초기 번들서 제외(부수 이득).

## 5. 검토 포인트 반영 (목업 5 + codex 12)
1. CWV 회귀 → 결정 4(React.lazy 코드분할 + IO 뷰포트 지연). IO만으론 번들 미분리라 React.lazy 병행(codex #1).
2. 홈 길이 → 결정 1 배치 유지(광고 최하단).
3. 모바일 발견성 → 결정 5(탭바 유지). 헤더 숨김 실증으로 재확정(codex #6).
4. 앵커 가림/크로스페이지 → 결정 6(`scroll-margin-top`) + 결정 7(서버 상주).
5. 404 → 결정 8(not-found 미변경, codex #10).

## 6. 완료 조건 (게이트)
- **/compare 링크 잔존 0**: grep으로 네비/메타데이터/구조화데이터/테스트/문서에 활성 `/compare` 링크-경로 없음(sitemap 포함).
- **앵커 3경우 동작**: (a) 홈 내 헤더 클릭 (b) 타 페이지(/fonts 등)에서 이동 (c) 주소창 `/#compare` 직접 입력 — 모두 비교 섹션으로 스크롤.
- **성능(#25 실측 대비 회귀 없음)**: 홈 mobile Lighthouse 3회 중앙값 기준 LCP ≤ 2.5s, CLS ≤ 0.02, TBT ≤ 100ms(현 실측 LCP 2.1s/CLS 0/TBT 40ms 대비 여유). INP는 lab 한계로 TBT를 proxy로 사용.
- **/compare 404**: 빌드 산출물에 `/compare` 없음 + 실배포(Cloudflare Pages)에서 404 상태코드 반환 확인.

## 7. 테스트 전략 (핵심 시나리오 한정)
- e2e: 홈 진입 → `#compare` 섹션 존재 + 슬롯 폰트 전환 동작(기존 로직 이식). 앵커 3경우. 모바일 탭바 비교 href `/#compare`.
- 지연 로드: 초기 미마운트 → 스크롤 후 1회 마운트(가능 범위).
- 유닛: `sitemap.test.ts` /compare 부재. `verify-seo-output` 기대 URL 동기화.

## 8. 검증 방법
`[빌드] pnpm build → 검증: out에 /compare 없음 + sitemap에 /compare 없음 + 홈 HTML에 #compare 섹션 상주`
`[성능] 홈 Lighthouse(mobile) 3회 → 검증: 6절 수치 충족`
`[e2e] pnpm test:e2e smoke → 검증: 그린`
`[배포후] curl -I <배포URL>/compare → 검증: 404`

## 9. 리스크 - 롤백
- 리스크: (a) 홈 CWV 회귀 — 코드분할로 완화, 빌드 후 3회 실측. (b) `React.lazy`+`IntersectionObserver`는 프레임워크 독립 API라 output:'export'에서 안전 — 빌드 후 `CompareBoard` 별도 청크 생성 확인. (c) 크로스페이지 해시 스크롤 미동작 가능 — 미동작 시 홈 로드 후 스크롤 보정. (d) 404 유입 손실 — 최근 배포(v0.1.0)라 인덱싱 축적 적어 영향 제한적(사용자 확정, 근거 기록).
- 롤백: 단일 브랜치. 문제 시 미병합/revert. prod DB 무관(코드만).

## 10. 제약 (사용자)
공유 워킹트리 — worktree 격리, 매 작업 전 브랜치 재확인, 내 파일만 스테이징. PR base=develop, squash merge. codex 리뷰는 사용자 직접. prod DB 쓰기 없음(해당 없음).
