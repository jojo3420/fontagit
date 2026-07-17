# Sitemap, Robots, GA4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 운영 sitemap과 robots의 도메인을 교정하고 재발 방지 검증을 추가한 뒤 GA4와 Search Console을 실제 운영 환경에 연결한다.

**Architecture:** Next.js 정적 메타 라우트는 `https://fontagit.com`을 단일 기준 주소로 사용한다. sitemap 데이터 조회는 상태 페이지 생성과 분리해 published 항목만 반환한다. 배포 스크립트는 정적 결과물을 Cloudflare에 올리기 전에 별도 Node 검증기로 sitemap과 robots를 전수 검사한다.

**Tech Stack:** Next.js 16 Metadata API, TypeScript, Vitest, Node.js, Cloudflare Pages, Google Analytics 4, Google Search Console

## Global Constraints

- 대표 origin은 정확히 `https://fontagit.com`이다.
- sitemap URL은 후행 슬래시를 사용하고 `priority`, `changefreq`, 임의 `lastmod`를 넣지 않는다.
- sitemap 폰트 상세는 `status = published`만 포함한다.
- `/search/`와 보류·배포종료 폰트는 접근을 유지하되 `noindex,follow`를 적용한다.
- GA4 ID와 배포 토큰은 커밋하지 않는다.
- 사용자 소유 변경인 `docs/superpowers/plans/2026-07-18-issue-62-tracking-execution.md`와 `docs/review/review-result-20260718-010244.md`는 수정·스테이징하지 않는다.

---

### Task 1: 대표 URL과 published sitemap 데이터 분리

**Files:**
- Modify: `apps/web/lib/seo.ts`
- Modify: `apps/web/lib/seo.test.ts`
- Modify: `apps/web/lib/db/fonts.ts`
- Modify: `apps/web/lib/db/fonts.test.ts`
- Modify: `apps/web/app/sitemap.ts`
- Modify: `apps/web/app/sitemap.test.ts`

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

`BASE_URL`을 실제 origin으로 고정한다. `getPublishedSlugs()`는 Supabase `fonts`에서 `status = published`인 slug만 조회한다. sitemap은 정적 7개와 published 폰트·컬렉션을 URL만 가진 항목으로 반환한다.

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
- Create: `apps/web/scripts/verify-seo-output.test.mjs`
- Modify: `apps/web/package.json`
- Modify: `scripts/deploy.sh`

**Interfaces:**
- Produces: `validateSeoOutput(sitemapXml: string, robotsText: string): { urlCount: number }`
- Produces: `pnpm --dir apps/web verify:seo`

- [x] **Step 1: 실패 테스트 작성**

Node 내장 테스트로 정상 파일 1개, 잘못된 origin 또는 중복 URL을 거부하는 치명적 예외 2개만 작성한다.

- [x] **Step 2: RED 확인**

Run: `node --test apps/web/scripts/verify-seo-output.test.mjs`

Expected: 검증 모듈이 없어 FAIL.

- [x] **Step 3: 최소 구현**

검증기는 sitemap XML의 `<loc>`을 읽어 필수 정적 URL 7개, origin 전수 일치, 중복 없음, 금지 origin 없음과 robots의 정확한 Sitemap 행을 검사한다. `deploy.sh`는 빌드 후 업로드 전에 `verify:seo`를 실행한다.

- [x] **Step 4: GREEN 확인**

Run: `node --test apps/web/scripts/verify-seo-output.test.mjs`

Expected: 3 tests PASS.

### Task 4: 전체 검증과 자체 적대적 리뷰

**Files:**
- Review: 이번 기능의 전체 diff와 호출처

- [x] **Step 1: 전체 검사**

Run: `pnpm --dir apps/web test && pnpm --dir apps/web lint && pnpm --dir apps/web build && pnpm --dir apps/web verify:seo`

Expected: 모든 명령 exit 0, sitemap origin 전수 일치.

- [x] **Step 2: 실패 경로 적대적 리뷰**

`unhappy-path-check` 기준으로 DB 빈 결과, 잘못된 origin, 중복 URL, 누락 robots, GA4 ID 누락, 배포 롤백을 추적한다. HIGH/MEDIUM이 있으면 테스트를 먼저 추가한 뒤 수정한다.

- [x] **Step 3: 품질 게이트 재실행**

수정 후 전체 테스트·lint·build·SEO 검증을 새로 실행하고 AS-IS/TO-BE 증거를 기록한다.

### Task 5: GA4, 배포, Search Console

**Files:**
- Modify without commit: `apps/web/.env.production`
- External: Google Analytics, Cloudflare Pages, Google Search Console

- [x] **Step 1: GA4 생성**

로그인된 Chrome에서 `FontAgit` 속성, 대한민국 시간대, KRW 통화, `https://fontagit.com` 웹 스트림을 생성한다. 향상된 측정의 페이지 로드와 기록 변경을 켠다.

- [x] **Step 2: 측정 ID 연결**

발급된 `G-...` 값을 `.env.production`의 `NEXT_PUBLIC_GA_ID`에 저장하되 커밋하지 않는다.

- [ ] **Step 3: 기능 커밋·푸시·병합·배포**

`$commit` 절차로 기능 파일만 스테이징하고 develop을 push한다. main에 병합·push한 뒤 승인된 태그와 `scripts/deploy.sh` 배포를 실행한다.

- [ ] **Step 4: 운영 검증**

`curl`로 운영 sitemap, robots, canonical, GA 스크립트를 확인한다. GA4 DebugView에서 최초 진입과 내부 이동의 `page_view`가 경로별 한 번인지 확인한다.

- [ ] **Step 5: Search Console 제출**

로그인된 Chrome의 `fontagit.com` 도메인 속성에서 `https://fontagit.com/sitemap.xml`을 제출하고 처리 상태를 확인한다.
