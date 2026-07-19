# #54 /compare 제거 → 홈 통합 설계

> 작성 2026-07-18 - SSOT: [GitHub 이슈 #54](https://github.com/jojo3420/fontagit/issues/54)
> 목적: 별도 라우트 `/compare`의 비교 기능을 메인 홈("/")으로 통합하고 라우트를 제거한다.
> 미리보기 목업: `docs/mockups/2026-07-18-compare-home-merge/index.html`

## 1. 배경 - 목표
- 배경: 폰트 비교 기능이 `/compare` 별도 라우트로 분리돼 있음. 이슈 #54가 메인 통합 요청.
- 목표: (a) 비교 기능을 홈에서 사용 가능하게, (b) `/compare` 라우트 제거, (c) 기존 `CompareBoard` 재사용.
- 범위 경계(이슈 코멘트): 본 이슈는 "화면 구성/상호작용" 담당. 캔버스 자체 기능은 #55, 문구 동기화 통합은 #60 3단계 — 본 작업 범위 아님.

## 2. 확정 결정 (브레인스토밍 7건)
| # | 항목 | 결정 |
|---|------|------|
| 1 | 통합 위치 | 메인 홈("/") full-width 섹션. 주간랭킹 아래-광고 위 |
| 2 | /compare URL | 라우트 완전 제거(404) + sitemap에서 삭제 |
| 3 | 데스크톱 헤더 "비교" | `/#compare` 앵커로 변경 |
| 4 | 홈 성능(CWV) | 비교 섹션 지연 렌더(lazy, 뷰포트 진입 시) — #25 LCP 회귀 방지 |
| 5 | 모바일 탭바 "비교" | 탭 제거(홈-비교 목적지 중복-비활성 혼란 해소). 헤더만 앵커 유지 |
| 6 | 앵커 스크롤 | `#compare`에 `scroll-margin-top`(sticky 헤더 높이). 크로스페이지 이동 동작 Next 문서 확인 |
| 7 | 404 안내 | 기존 `not-found.tsx`에 "비교는 홈으로 이동" 안내 링크 추가(소폭) |

## 3. 변경 범위 (조사 실측)
| 구분 | 파일 | 변경 |
|------|------|------|
| 홈 통합 | `app/page.tsx` | `<section id="compare">` 추가, 지연 렌더로 `CompareBoard` 렌더. 주간랭킹 아래-광고 위 |
| 지연 렌더 | `components/CompareSection.tsx`(신규) | `IntersectionObserver`로 뷰포트 진입 시 `CompareBoard` 마운트하는 클라이언트 래퍼 |
| 라우트 제거 | `app/compare/page.tsx` + `app/compare/` | 삭제 |
| 네비(데스크톱) | `components/Header.tsx:19` | `/compare` → `/#compare` |
| 네비(모바일) | `components/MobileTabBar.tsx:11` | `/compare` 탭 항목 제거 |
| SEO | `app/sitemap.ts:26` | `/compare/` 제거 |
| 404 | `app/not-found.tsx` | 홈/비교 안내 링크 추가 |
| 스타일 | `components/CompareBoard.module.css` | 홈 섹션 폭에 맞게 최소 조정(전용 페이지 전제 여백 점검) |
| 테스트 | `app/sitemap.test.ts:23` | 기대값에서 /compare 제거 |
| SEO 검증 | `scripts/verify-seo-output.mjs:12`, `.node-test.mjs:13` | 기대 URL 제거 |
| e2e | `e2e/smoke.spec.ts`(10, 82~148) | /compare 페이지 테스트 → 홈 비교 섹션 검증으로 전환. 스냅샷 `compare-screenshot-*.png` 삭제 |

**재사용 유지**: `CompareBoard.tsx`(로직 무변경).

## 4. 컴포넌트 - 데이터 흐름
- `CompareSection`(신규): 단일 책임 = "뷰포트 진입 감지 후 `CompareBoard` 지연 마운트". 진입 전 자리표시(높이 확보로 CLS 방지). 진입 후 `CompareBoard` 렌더.
- `CompareBoard`: 기존 그대로. 클라이언트에서 무료 폰트 3슬롯 + 입력 문장 실시간 렌더. 데이터 흐름 변경 없음.
- 홈(`page.tsx`, 서버 컴포넌트): `CompareSection`을 import해 섹션 배치. 서버→클라이언트 경계는 `CompareSection`이 담당.

## 5. 검토 포인트 반영 (목업 5건)
1. CWV 회귀 → 결정 4(지연 렌더)로 해소.
2. 홈 길이 → 결정 1 배치 유지(광고 최하단, 콘텐츠 우선).
3. 모바일 탭 중복 → 결정 5(탭 제거)로 해소.
4. 앵커 가림/크로스페이지 → 결정 6(`scroll-margin-top` + 문서 확인).
5. 404 → 결정 7(안내 링크).

## 6. 테스트 전략
- e2e: 홈 진입 → 비교 섹션 존재(`#compare`) + 슬롯 폰트 전환 동작(기존 compare 테스트 로직 이식). `/compare/` 직접 접근은 404 확인.
- 유닛: `sitemap.test.ts` /compare 부재 검증. `verify-seo-output` 기대 URL 동기화.
- 지연 렌더: 뷰포트 밖에서는 비교 보드 미마운트, 스크롤 후 마운트 검증(가능 범위).

## 7. 검증 방법
`[빌드] pnpm build → 검증: out에 /compare 없음 + sitemap에 /compare 없음 + 홈 HTML에 #compare 섹션 존재`
`[성능] 홈 Lighthouse(mobile) → 검증: LCP/CLS/INP #25 기준 유지(회귀 없음)`
`[e2e] pnpm test:e2e smoke → 검증: 그린`

## 8. 리스크 - 롤백
- 리스크: (a) 홈 CWV 회귀 — 지연 렌더로 완화, 빌드 후 실측 필수. (b) 정적 export의 크로스페이지 해시 스크롤 미동작 가능 — 구현 시 Next 문서 확인, 미동작 시 홈 로드 후 스크롤 보정 스크립트. (c) 404 유입 손실 — v0.1.0 최근 배포라 인덱싱 축적 적어 영향 제한적.
- 롤백: 단일 브랜치 작업. 문제 시 브랜치 미병합/revert. prod DB 무관(코드만).

## 9. 제약 (사용자)
공유 워킹트리 — worktree 격리, 매 작업 전 브랜치 재확인, 내 파일만 스테이징. PR base=develop, squash merge. codex 리뷰는 사용자 직접. prod DB 쓰기 없음(해당 없음).
