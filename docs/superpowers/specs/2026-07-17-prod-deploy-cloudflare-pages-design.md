# FontAgit prod 배포 런북 — Cloudflare Pages (v1, 완료)

> 작성일: 2026-07-17 | 성격: 배포 설계 + 실행 런북 | 상태: **라이브 완료**(fontagit.com)
> 범위: 인프라-도메인 먼저 띄우기(fontagit.com 라이브 + prod 데이터). 콘텐츠 확장-측정 연동-AdSense는 후속.
> 마스터: `docs/fontagit-master-plan-v3.0.md` 12장의 VM2 Nginx를 **Cloudflare Pages로 대체**.

---

## 0. 결론 (BLUF)

`apps/web`는 순수 정적(`output:"export"` → `out/`)이라 VM2 Nginx가 불필요하다. **Cloudflare Pages**에 정적 빌드를 배포하고, 이미 Cloudflare로 위임된 fontagit.com을 커스텀 도메인으로 붙였다. prod Supabase(ollidam)에 이미 130종이 있어 빈 사이트 문제는 없었다.

확정 결정:
- 배포 범위 = 인프라-도메인 먼저
- 호스팅 = Cloudflare Pages(프로젝트 `fontagit`, production branch `main`)
- 접근 = Cloudflare API 토큰. Pages 배포용 `CF_TOKEN`(`apps/web/.env.local`), DNS용 `CF_API_TOKEN_1`(`~/.zsh_secrets`)
- 빌드 데이터 = prod ollidam
- www = `www→apex` 301, http→https 301

---

## 1. 검증된 사실 (2026-07-17)

| 항목 | 상태 |
|---|---|
| fontagit.com Cloudflare zone | active, NS 위임 완료. 레지스트라 작업 불필요 |
| Cloudflare account id | `2686c11634da0d924f089b7e56a9e227` |
| prod ollidam 폰트 | total 136 / **published 130** / collections 3 / aliases 319 (이미 적재됨) |
| 빌드 env 함정 | `next build`는 `.env.local`(dev)이 `.env.production`(prod)을 덮어씀 → prod 값 process env 주입 필요 |
| 토큰 권한 | `CF_TOKEN`=Pages Edit + Single Redirect Edit. `CF_API_TOKEN_1`=DNS Edit만. 둘 다 SSL/TLS 모드 변경 불가(9109) |

---

## 2. 목표 아키텍처

```
[로컬 파이프라인]  →  [prod Supabase(ollidam)]  →  빌드(out/)  →  [Cloudflare Pages]  →  fontagit.com
```

VM2(Nginx) 제거, Cloudflare Pages로 대체. 동적 경로(검색 자동완성-이동 클릭)는 정적 export라 브라우저→Supabase RPC 직접 호출(anon + RLS).

---

## 3. 실행 결과 (슬라이스)

| # | 슬라이스 | 상태 | 결과 |
|---|---|---|---|
| 1 | 런북 문서 | 완료 | 본 문서 |
| 2 | prod 폰트 적재 | 이미 완료 | ollidam published 130(핸드오프의 "미적재"는 오정보) |
| 3 | prod 대상 빌드 | 완료 | `set -a && source apps/web/.env.production && set +a && pnpm --filter web build` → 폰트 130 + 컬렉션 3 정적 생성 |
| 4 | Pages 프로젝트+배포 | 완료 | `wrangler pages deploy apps/web/out --project-name fontagit --branch main`, 2624 파일 |
| 5 | 커스텀 도메인 | 완료 | apex CNAME→pages.dev(proxied), www CNAME→apex(proxied), www→apex 301, http→https 301 |
| 6 | 스모크 테스트 | 완료 | 홈/목록/상세/sitemap 200, 실 폰트 데이터 노출 |

배포 자동화: `scripts/deploy.sh`(빌드+배포+스모크), `make deploy`.

---

## 4. 재배포 방법

```bash
./scripts/deploy.sh        # 또는  make deploy
```
내부 2단계: (1) `.env.production` 주입 후 `pnpm --filter web build`, (2) `wrangler pages deploy apps/web/out --project-name fontagit --branch main`(토큰은 `.env.local`의 CF_TOKEN).

---

## 5. 도메인/리다이렉트 세부 (API로 세팅됨)

- DNS: apex `fontagit.com` CNAME→`fontagit.pages.dev`(proxied), `www` CNAME→`fontagit.com`(proxied).
- www→apex 301: `http_request_dynamic_redirect` 규칙셋. entrypoint PUT은 `{"rules":[...]}`만 받음(kind/name/phase 넣으면 "unknown field").
- 표현식 `(http.host eq "www.fontagit.com")` → 301 `concat("https://fontagit.com", http.request.uri.path)`, 쿼리 보존.
- http→https 301 자동. apex `""→"/"` 301은 trailingSlash:true 정규화(정상).
- ⚠️ 함정 기록: 대시보드 오설정 redirect 규칙이 apex 무한 301 루프를 유발한 적 있음(SSL Flexible 아님). 규칙셋 통째 교체로 복구. 배포 직후 옛 301이 edge 캐시에 잠깐 잔존.

---

## 6. 롤백-리스크

- Pages는 배포별 이력 보존 → 문제 시 이전 배포로 즉시 롤백.
- prod 데이터는 fontagit 스키마 내에서만 정정(ollidam 공유 인프라).
- ⚠️ 공유 워킹트리: 다른 세션이 같은 디렉터리에서 브랜치 전환-커밋. 착수 전 `git status`-브랜치 확인, 명시 경로만 스테이징. 미커밋 신규 파일은 브랜치 전환 시 유실 가능 → 조기 커밋.

---

## 7. 후속(범위 밖)

데이터 시드 확장-컬렉션-GA4/서치콘솔/서치어드바이저-필수 문서 4종-AdSense-CWV 정식 통과-일별 롤업 cron-Kong rate limit. 마스터 15장 로드맵 S3.
