# Sitemap, Robots, GA4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영 sitemap·canonical·robots의 도메인을 교정하고 재발 방지 검증을 추가한 뒤 GA4와 Search Console을 실제 운영 환경에 연결한다. 제출 완료와 실제 색인 완료는 구분한다.

**Architecture:** Next.js 정적 메타 라우트는 `https://fontagit.com`을 단일 기준 주소로 사용한다. sitemap 데이터 조회는 상태 페이지 생성과 분리해 published 항목만 반환한다. 배포 스크립트는 정적 결과물을 Cloudflare에 올리기 전에 별도 Node 검증기로 sitemap·robots·indexable HTML canonical 집합을 전수 검사한다.

**Tech Stack:** Next.js 16 Metadata API, TypeScript, Vitest, Node.js, Cloudflare Pages, Google Analytics 4, Google Search Console

## Global Constraints

- 대표 origin은 정확히 `https://fontagit.com`이다.
- sitemap URL은 후행 슬래시를 사용하고 `priority`, `changefreq`, 임의 `lastmod`를 넣지 않는다.
- sitemap 폰트 상세는 `status = published`만 포함한다.
- `/search/`와 보류·배포종료 폰트는 접근을 유지하되 `noindex,follow`를 적용한다.
- GA4 ID와 배포 토큰은 커밋하지 않는다.
- 배포는 `origin/main`과 같은 커밋의 깨끗한 전용 worktree에서만 실행한다. 기능 브랜치나 추적 파일이 dirty인 worktree에서는 실행하지 않는다.
- 운영 배포·main push는 검증 결과와 대상 커밋 SHA를 제시한 뒤 사용자 승인을 받는다.
- 이번 계획은 기술 색인 복구까지다. 검색 순위·실제 색인·실사용자 INP 통과를 완료로 주장하지 않는다.
- 이 계획에 명시된 파일만 수정·스테이징한다. 다른 기능과 `docs/review/`의 기존·신규 사용자 파일은 건드리지 않는다.

---

### Task 1: 대표 URL과 published sitemap 데이터 분리

**Files:**
- Modify: `apps/web/lib/seo.ts`
- Modify: `apps/web/lib/seo.test.ts`
- Modify: `apps/web/lib/db/fonts.ts`
- Modify: `apps/web/lib/db/fonts.test.ts`
- Modify: `apps/web/app/sitemap.ts`
- Modify: `apps/web/app/sitemap.test.ts`
- Verify: `apps/web/app/robots.ts`

**Interfaces:**
- Produces: `BASE_URL = "https://fontagit.com"`
- Produces: `getPublishedSlugs(): Promise<string[]>`
- Consumes: `getAllCollectionSlugs(): Promise<string[]>`

- [x] **Step 1: 실패 테스트 작성**

`seo.test.ts`가 실제 origin을 요구하고, `fonts.test.ts`가 published 전용 쿼리를 요구하며, `sitemap.test.ts`가 정적 7개와 published slug만 포함하고 빈 메타 필드를 요구하도록 수정한다.

- [x] **Step 2: RED 확인**

Run: `pnpm --dir apps/web test -- lib/seo.test.ts lib/db/fonts.test.ts app/sitemap.test.ts`

Expected: 기존 `fontagit.example.com`, 없는 `getPublishedSlugs`, 누락된 정적 경로 때문에 FAIL.

- [x] **Step 3: 최소 구현**

`BASE_URL`을 실제 origin으로 고정하고 `NEXT_PUBLIC_BASE_URL` 읽기 자체를 제거한다. `robots.ts`가 같은 상수를 사용해 실제 sitemap 주소를 내는지 확인한다. `getPublishedSlugs()`는 Supabase `fonts`에서 `status = published`인 slug만 조회한다. sitemap은 정적 7개와 published 폰트·컬렉션을 URL만 가진 항목으로 반환한다.

- [x] **Step 4: GREEN 확인**

Run: `pnpm --dir apps/web test -- lib/seo.test.ts lib/db/fonts.test.ts app/sitemap.test.ts`

Expected: 대상 테스트 전부 PASS.

### Task 2: canonical과 noindex 정합

**Files:**
- Modify: `apps/web/app/layout.tsx`
- Create: `apps/web/app/search/layout.tsx`
- Modify: `apps/web/app/fonts/[slug]/page.tsx`
- Modify: `apps/web/app/fonts/[slug]/page.test.tsx`
- Modify: `apps/web/app/collections/[slug]/page.tsx`
- Modify: sitemap에 포함되는 정적 페이지의 `page.tsx`

**Interfaces:**
- Consumes: `getSiteUrl(path: string): string`
- Produces: sitemap 페이지별 `alternates.canonical`
- Produces: 검색 및 비공개 상태의 `robots: { index: false, follow: true }`

- [x] **Step 1: 실패 테스트 작성**

폰트 메타데이터 테스트에 `hold` 상태의 `noindex,follow` 사례를 추가하고 published 사례는 canonical과 index 허용을 확인한다.

- [x] **Step 2: RED 확인**

Run: `pnpm --dir apps/web test -- 'app/fonts/[slug]/page.test.tsx'`

Expected: hold 상태가 현재 robots 메타데이터를 반환하지 않아 FAIL.

- [x] **Step 3: 최소 구현**

검색 전용 layout에 `noindex,follow`를 선언한다. 폰트 `generateMetadata()`는 published가 아니면 `noindex,follow`를 반환한다. sitemap 정적 페이지와 컬렉션 상세는 후행 슬래시 canonical을 반환한다.

- [x] **Step 4: GREEN 확인**

Run: `pnpm --dir apps/web test -- 'app/fonts/[slug]/page.test.tsx'`

Expected: 대상 테스트 PASS.

### Task 3: 배포 전 SEO 산출물 검증

**Files:**
- Create: `apps/web/scripts/verify-seo-output.mjs`
- Create: `apps/web/scripts/verify-seo-output.node-test.mjs`
- Modify: `apps/web/package.json`
- Modify: `scripts/deploy.sh`

**Interfaces:**
- Produces: `validateSeoOutput(sitemapXml: string, robotsText: string): { urlCount: number }`
- Produces: `pnpm --dir apps/web verify:seo`

- [x] **Step 1: 실패 테스트 작성**

Node 내장 테스트로 정상 파일 1개, 잘못된 origin 또는 중복 URL을 거부하는 치명적 예외 2개만 작성한다.

- [x] **Step 2: RED 확인**

Run: `node --test apps/web/scripts/verify-seo-output.node-test.mjs`

Expected: 검증 모듈이 없어 FAIL.

- [x] **Step 3: 최소 구현**

검증기는 sitemap XML의 `<loc>`을 읽어 필수 정적 URL 7개, origin 전수 일치, 중복 없음, 금지 origin 없음과 robots의 정확한 Sitemap 행을 검사한다. `deploy.sh`는 빌드 후 업로드 전에 `verify:seo`를 실행한다. 이 단계의 구현은 최소 1개 폰트·컬렉션만 요구하므로 부분 누락까지 증명하지 못한다. 아래 Task 4A에서 빌드 HTML 집합 대조를 추가한다.

- [x] **Step 4: GREEN 확인**

Run: `node --test apps/web/scripts/verify-seo-output.node-test.mjs`

Expected: 3 tests PASS.

### Task 4: 1차 전체 검증과 자체 적대적 리뷰

> 당시 정의된 origin·robots 기준의 1차 검증은 완료했다. 이후 문서 적대적 리뷰에서 부분 누락·canonical 집합·dirty 배포 문제가 추가로 발견됐으므로, 이 Task의 `[x]`는 최종 배포 가능을 뜻하지 않는다. 최종 게이트는 Task 4A다.

**Files:**
- Review: 이번 기능의 전체 diff와 호출처

- [x] **Step 1: 전체 검사**

Run: `pnpm --dir apps/web test && pnpm --dir apps/web lint && pnpm --dir apps/web build && pnpm --dir apps/web verify:seo`

Expected: 모든 명령 exit 0, sitemap origin 전수 일치.

- [x] **Step 2: 실패 경로 적대적 리뷰**

`unhappy-path-check` 기준으로 DB 빈 결과, 잘못된 origin, 중복 URL, 누락 robots, GA4 ID 누락, 배포 롤백을 추적한다. HIGH/MEDIUM이 있으면 테스트를 먼저 추가한 뒤 수정한다.

- [x] **Step 3: 품질 게이트 재실행**

수정 후 전체 테스트·lint·build·SEO 검증을 새로 실행하고 AS-IS/TO-BE 증거를 기록한다.

### Task 4A: 문서 적대적 리뷰 후 발견된 잔여 배포 게이트

**Files:**
- Modify: `apps/web/scripts/verify-seo-output.mjs`
- Modify: `apps/web/scripts/verify-seo-output.node-test.mjs`
- Modify: `scripts/deploy.sh`
- Modify: `apps/web/lib/db/fonts.ts`
- Modify: `apps/web/lib/db/fonts.test.ts`
- Modify: `apps/web/lib/db/collections.ts`
- Modify: `apps/web/lib/db/collections.test.ts`
- Modify: `apps/web/app/fonts/[slug]/page.tsx`
- Modify: `apps/web/app/fonts/[slug]/page.test.tsx`

> **Hard dependency:** Task 4A 전체가 끝나기 전에는 Task 5의 main 승격·운영 배포를 실행하지 않는다.

- [ ] **Step 1: 빌드 산출물 집합 대조 추가**

폰트·컬렉션 slug 조회는 명시적 페이지네이션과 exact count를 사용하고 `수집 개수 == count`가 아니면 빌드를 실패시킨다. `out/`의 sitemap 대상 HTML을 읽어 `noindex`가 없는 자기참조 canonical 집합을 만든다. sitemap URL 집합과 누락·초과 없이 정확히 같은지 검사한다. `/search/index.html`은 `noindex`이고 sitemap에는 없는지 별도로 확인한다. 핵심 테스트는 정상 1개와 1,000행 절단·canonical 집합 불일치 같은 치명적 예외 2개 이내로 제한한다.

- [ ] **Step 2: 깨진 메타 설명 방어**

폰트 제작사 값이 null·빈 문자열이면 `" 제작 서체"`가 생기지 않도록 확인 가능한 조각만 이어 붙인다. 빈 제작사와 정상 제작사 사례 중 핵심 사례만 기존 메타데이터 테스트에 반영한다.

- [ ] **Step 3: 배포 출처 고정**

`scripts/deploy.sh`는 `git fetch`가 완료된 전용 worktree에서 현재 브랜치가 `main`, `HEAD == origin/main`, 추적 파일이 clean인지 확인한다. `wrangler pages deploy`의 `--commit-dirty=true`는 제거한다. gitignore된 `.env.production`은 검증 대상에서 제외한다. `.env.production`의 Supabase URL이 존재하고 `.env.local` 개발 URL과 다름을 비밀값 출력 없이 확인한다.

- [ ] **Step 4: 회귀 검증**

Run: `node --test apps/web/scripts/verify-seo-output.node-test.mjs && pnpm --dir apps/web test -- 'app/fonts/[slug]/page.test.tsx' && pnpm --dir apps/web lint && pnpm --dir apps/web build && pnpm --dir apps/web verify:seo`

Expected: 모든 명령 exit 0, DB exact count·sitemap URL 집합·indexable canonical 집합 일치, dirty·비-main·개발 DB 배포 사전 차단.

### Task 5: GA4, 승인 기반 배포, Search Console

**Files:**
- Modify without commit: `apps/web/.env.production`
- External: Google Analytics, Cloudflare Pages, Google Search Console

- [x] **Step 1: GA4 생성 (외부 수행, 운영 검증 전)**

로그인된 Chrome에서 `FontAgit` 속성, 대한민국 시간대, KRW 통화, `https://fontagit.com` 웹 스트림을 생성한다. 향상된 측정의 페이지 로드와 기록 변경을 켠다.

- [x] **Step 2: 측정 ID 연결 (로컬 입력 완료, 운영 검증 전)**

발급된 `G-...` 값을 `.env.production`의 `NEXT_PUBLIC_GA_ID`에 저장하되 커밋하지 않는다.

- [ ] **Step 3: 기능 커밋·푸시·병합 준비**

Task 4A 완료 후 작업 파일만 스테이징해 기능 브랜치에 커밋하고 PR(base=`develop`)로 병합한다. 이어 develop→main 승격 PR의 대상 커밋을 고정하고 `git fetch`로 원격 상태를 다시 확인한다. 사용자에게 대상 커밋 SHA·테스트·빌드·SEO 검증 결과를 제시하고 main 병합·push와 운영 배포 승인을 받는다.

- [ ] **Step 4: 깨끗한 main worktree에서 배포**

별도 worktree에서 `HEAD == origin/main`, 추적 파일 clean을 확인한 뒤 `scripts/deploy.sh`를 실행한다. 새 Cloudflare 배포 ID와 커밋 SHA를 기록한다.

- [ ] **Step 5: 운영 전수 검증**

운영 sitemap의 모든 URL을 제한된 동시성으로 요청해 200·자기참조 canonical을 확인한다. robots의 sitemap 행, `/search/`의 `noindex`, GA 스크립트, `www`→apex 301도 확인한다. 하나라도 실패하면 “배포됨”과 “검증 완료”를 분리해 보고하고 원인을 해결한다. GA4 DebugView에서 최초 진입과 내부 이동의 `page_view`가 경로별 한 번인지 확인한다.

- [ ] **Step 6: Search Console 제출과 기준선 기록**

로그인된 Chrome의 `fontagit.com` 도메인 속성에서 `https://fontagit.com/sitemap.xml`을 제출한다. 홈·대표 폰트·대표 컬렉션 각 1개를 URL 검사로 실시간 테스트하고 결과를 기록한다. 제출 성공을 색인 성공으로 표현하지 않는다.

- [ ] **Step 7: 후속 검색 노출 작업 분리**

Search Console 처리 후 실제 색인 수·제외 사유·노출어·페이지·CTR을 수집한다. 제목·설명·라이선스 근거·컬렉션 내부 링크·Breadcrumb 구조화 데이터는 별도 설계로 진행한다. 대량 유사 페이지 생성은 금지하며, 실사용자 INP는 충분한 현장 데이터가 생긴 뒤 판정한다.
