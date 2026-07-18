# FontAgit 검색 발견성·색인 기반 복구 설계

> 작성일: 2026-07-18
> 대상: `https://fontagit.com`
> 범위: 검색엔진이 읽는 주소 정보 교정, GA4 운영 연동, 안전한 배포, Search Console 제출·기준선 확인
> 비범위: 검색 순위 상승 보장, 키워드·콘텐츠 확장, 실사용자 Core Web Vitals 판정

## 1. 현황과 원인

- 운영 `sitemap.xml`의 URL 137개와 `robots.txt`의 Sitemap 주소가 모두 `https://fontagit.example.com`을 가리킨다.
- `NEXT_PUBLIC_BASE_URL`이 운영 환경에 없고, 코드의 기본값도 예시 도메인이어서 잘못된 주소가 그대로 배포됐다.
- 대표 폰트 상세의 canonical도 `https://fontagit.example.com/...`을 가리켜 sitemap과 같은 오류가 확인됐다.
- `/search/`는 200으로 접근되지만 `noindex`가 없어 검색어 조합 URL이 색인 후보가 될 수 있었다.
- sitemap 생성과 GA4 스크립트 코드는 이미 있다. GA4는 운영 `NEXT_PUBLIC_GA_ID`가 비어 있어 현재 로드되지 않는다.
- `www.fontagit.com`은 이번 점검의 `curl` 결과 `https://fontagit.com`으로 301 이동했다. 대표 도메인은 apex인 `https://fontagit.com`이다.
- 배포는 Cloudflare 원격 빌드가 아니다. `scripts/deploy.sh`가 로컬에서 `.env.production`을 주입해 정적 빌드한 뒤 `out/`만 Cloudflare Pages에 올린다.
- 제공된 Search Console 화면에서 `fontagit.com` 도메인 속성 접근은 확인됐다.

## 2. URL 기준

- 사이트 기준 주소는 `https://fontagit.com` 한 개로 통일한다.
- canonical·sitemap 기준 주소는 공개 환경변수로 덮어쓰지 않고 코드의 `https://fontagit.com` 상수 한 곳에서 관리한다.
- 예시 도메인·Pages 임시 도메인·인증정보·쿼리·fragment가 sitemap에 섞이면 배포 검증에서 실패시킨다.
- sitemap에는 검색 결과에 노출할 가치가 있고 200으로 응답하는 대표 URL만 넣는다.
- sitemap URL과 페이지 canonical은 모두 후행 슬래시를 사용한다. 이는 현재 `trailingSlash: true` 설정과 일치한다.

## 3. sitemap.xml

포함 대상:

- `/`
- `/fonts/`와 공개 폰트 상세 `/fonts/{slug}/`
- `/collections/`와 공개 컬렉션 상세 `/collections/{slug}/`
- `/trends/`
- `/compare/`
- `/playground/`
- `/about/`

폰트 상세는 `status = published`인 slug만 포함한다. 현재 `getAllSlugs()`는 상태 안내 페이지 생성을 위해 `hold`, `discontinued`도 반환하므로, sitemap용 공개 slug 조회를 별도로 둔다. 컬렉션은 기존처럼 `status = published`만 포함한다.

Supabase/PostgREST의 서버 행 수 상한에 기대지 않는다. 폰트·컬렉션 slug 조회는 명시적으로 페이지를 나누고 exact count와 수집 개수가 같아야 성공한다. 현재 130종에서는 드러나지 않지만 1,000종 이상으로 늘었을 때 조용히 잘린 sitemap이 배포되는 것을 막기 위한 조건이다.

제외 대상:

- 쿼리 조합이 생기는 `/search/`
- 운영·법률 보조 페이지인 `/submit/`, `/contact/`, `/privacy/`, `/disclaimer/`
- 보류·배포종료 상태 안내 폰트 페이지
- 404와 내부 Next.js 경로

Google이 사용하지 않는 `priority`, `changefreq`는 제거한다. 실제 콘텐츠 수정일을 신뢰할 수 있는 데이터가 없으므로 `lastmod`를 임의로 만들지 않는다.

예상 URL 집합은 `정적 페이지 7 + indexable published 폰트 + indexable published 컬렉션`이다. 현재 데이터 130종·3개 기준 예상값은 140이지만 데이터가 바뀌면 계산값도 함께 바뀐다. 단순히 “폰트·컬렉션이 1개 이상”인지만 검사하면 부분 누락을 놓치므로, 빌드 산출물의 indexable HTML canonical 집합과 sitemap URL 집합을 정확히 비교한다.

sitemap에 포함하는 모든 정적 페이지·폰트 상세·컬렉션 상세에는 후행 슬래시가 붙은 자기참조 canonical을 둔다. 페이지가 `noindex`면 sitemap에서 제외한다. 폰트 상세 설명은 제작사 값이 비었을 때 `" 제작 서체"`처럼 깨진 문장을 만들지 않고, 확인 가능한 값만 조합한다.

## 4. robots.txt

- 모든 일반 페이지의 크롤링을 허용한다.
- sitemap 주소는 `https://fontagit.com/sitemap.xml`로 고정한다.
- `/search/`를 robots.txt로 막지 않는다. robots 차단은 색인 제외 수단이 아니므로 검색 페이지에는 `noindex,follow` 메타데이터를 적용한다.
- sitemap에서 제외한 보류·배포종료 폰트 상태 페이지도 접근은 유지하되 `noindex,follow`로 처리한다.

## 5. 재발 방지

- `BASE_URL` 기본값과 URL 정규화를 검증한다.
- `scripts/deploy.sh`가 Cloudflare 업로드 직전에 빌드 결과의 `sitemap.xml`, `robots.txt`를 검사한다. 문서화된 정상 배포 경로는 이 스크립트로 통일한다.
- sitemap XML 파싱 성공, 모든 `<loc>`의 origin·허용 경로·중복을 검사한다.
- 빌드 산출물에서 sitemap 대상 HTML을 전수 읽어 `noindex`가 없는 자기참조 canonical 집합을 만들고 sitemap URL 집합과 정확히 일치하는지 검사한다. 누락·초과·canonical 불일치가 하나라도 있으면 실패한다.
- `/search/index.html`의 `noindex`와 sitemap 제외를 별도로 검사한다.
- robots.txt의 Sitemap 행이 정확히 `Sitemap: https://fontagit.com/sitemap.xml`인지 검사한다.
- 하나라도 다르면 업로드를 중단한다. 일부 문자열만 맞으면 통과하는 검사는 사용하지 않는다.
- 단순 전달 UI 테스트는 추가하지 않는다. 도메인 기본값과 sitemap 핵심 URL만 기존 테스트에서 검증한다.
- 배포는 `origin/main`과 같은 커밋의 깨끗한 전용 worktree에서만 실행한다. 기능 브랜치·추적 파일 변경이 있는 worktree·`--commit-dirty=true` 배포는 금지한다. `.env.production`처럼 gitignore된 운영 입력은 예외다.
- 배포 빌드는 `apps/web/.env.production`만 운영 데이터 소스로 사용한다. `NEXT_PUBLIC_SUPABASE_URL`이 없거나 `.env.local`의 개발 URL과 같으면 빌드 전에 실패시킨다. 실제 URL·키는 로그에 출력하지 않는다.
- 첫 정상 배포 전의 Pages 배포본은 잘못된 sitemap을 포함하므로 롤백 대상으로 사용하지 않는다. 정상 배포 후 커밋 SHA·배포 ID·검증 결과를 기록하고, 이후에는 검증된 배포로만 롤백한다.
- Cloudflare 대시보드의 과거 배포 선택까지 기술적으로 막지는 못한다. 롤백 대상 제한은 배포 ID 기록과 운영 절차로 강제하는 잔존 리스크다.

## 6. GA4 연동

- 로그인된 Google Analytics에서 FontAgit용 GA4 속성과 웹 데이터 스트림이 없으면 생성한다.
- 권장 설정은 속성명 `FontAgit`, 보고 시간대 `대한민국`, 통화 `KRW`, 웹사이트 URL `https://fontagit.com`, 스트림명 `FontAgit Web`이다.
- 향상된 측정에서 페이지 로드와 브라우저 기록 변경 기반 페이지 조회를 활성화한다.
- 발급된 `G-...` 측정 ID는 공개 클라이언트 설정인 `NEXT_PUBLIC_GA_ID`로 로컬 빌드 입력 파일 `.env.production`에 저장한다. 이 파일과 실제 ID는 저장소에 커밋하지 않는다.
- 기존 `GoogleAnalytics` 컴포넌트를 재사용한다. 형식이 올바른 ID가 있을 때만 Google 스크립트를 로드한다.
- 저장소에는 별도 GTM·gtag·Cloudflare Analytics 코드가 없음을 확인했다. 수동 `page_view` 코드는 추가하지 않아 향상된 측정과의 중복을 피한다.
- 배포 후 HTML에 올바른 측정 ID가 포함되는지 확인한다. GA4 DebugView에서 최초 진입과 내부 경로 이동마다 `page_view`가 정확히 한 번 발생하고 `page_location`이 바뀌는지 확인한 뒤 실시간 보고서에서도 방문을 확인한다.

## 7. 배포와 Search Console

1. `git fetch` 후 별도 worktree에서 `HEAD == origin/main`, 추적 파일 clean을 확인한다.
2. `.env.production`의 운영 Supabase URL이 존재하고 `.env.local` 개발 URL과 다름을 비밀값 출력 없이 확인한다.
3. 테스트, 린트, 정적 빌드를 실행한다.
4. 생성된 sitemap·robots·indexable HTML canonical 집합을 전수 검사한다.
5. 사용자에게 커밋 SHA와 검증 결과를 보여주고 운영 배포 승인을 받는다.
6. Cloudflare Pages에 배포한다.
7. 새 배포 ID를 기록하고 sitemap의 모든 URL을 제한된 동시성으로 요청해 200·자기참조 canonical을 확인한다. `/search/`의 `noindex`, GA4 스크립트, `www`→apex 301도 다시 확인한다.
8. Search Console의 `fontagit.com` 도메인 속성에서 `https://fontagit.com/sitemap.xml`을 제출한다.
9. URL 검사로 홈·대표 폰트·대표 컬렉션 각 1개를 실시간 테스트하고 결과를 기록한다.

배포 성공, 운영 검증, sitemap 제출, 실제 색인은 서로 다른 상태다. 제출이 성공해도 즉시 색인됐다고 표현하지 않는다. 배포나 Search Console 제출이 실패하면 이전의 잘못된 sitemap을 성공으로 보고하지 않는다.

## 8. 완료 조건

- 운영 sitemap의 모든 `<loc>`이 `https://fontagit.com`으로 시작한다.
- sitemap URL 집합이 빌드 산출물의 indexable canonical 집합과 정확히 일치하고 중복이 없다.
- sitemap의 각 URL이 200으로 응답하고 후행 슬래시 canonical과 일치한다.
- 검색 페이지와 보류·배포종료 폰트 상태 페이지에 `noindex,follow`가 있다.
- 운영 robots.txt가 정확한 sitemap 주소를 안내한다.
- 운영 HTML에서 GA4 측정 스크립트가 로드된다.
- GA4 DebugView에서 최초 진입과 내부 이동의 `page_view`가 경로별 한 번씩 확인된다.
- Search Console에서 sitemap 제출 상태와 URL 검사 3종의 실시간 테스트 결과가 기록된다.
- “제출 완료”와 “색인 완료”를 구분하며, 실제 색인 수·제외 사유는 Search Console 처리 후 후속 측정한다.
- 정상 배포 ID와 검증 결과가 기록되어 잘못된 pre-fix 배포로 롤백하지 않는다.

## 9. 검색 노출 최적화 후속 범위

이번 설계는 잘못된 주소 신호를 바로잡는 P0 복구다. 검색 순위나 유입 증가까지 완료했다고 보지 않는다. 복구 후 별도 작업으로 아래를 진행한다.

- Search Console의 실제 노출어·페이지·CTR을 기준선으로 수집한다.
- `/fonts/`, 폰트 상세, 컬렉션의 제목·설명·본문이 검색 의도마다 고유한지 점검한다.
- 제작사·라이선스·확인일·공식 원문 등 사용자 가치가 있는 사실을 보강한다. 값이 비면 문장을 억지로 생성하지 않는다.
- 컬렉션을 내부 링크 허브로 확장하되, 검색 순위만 노린 대량 유사 페이지는 만들지 않는다.
- Breadcrumb 구조화 데이터는 정확한 화면 경로와 일치할 때만 별도 구현하고 Rich Results Test로 검증한다.
- Lighthouse의 TBT는 INP가 아니다. 실사용자 INP는 충분한 현장 데이터가 쌓인 뒤 Search Console Core Web Vitals에서 판정한다.

## 10. 근거 자료

- Google Search Central, sitemap 작성·제출: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap
- Google Search Central, canonical 통합: https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls
- Google Search Central, robots meta: https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag
- Google Search Central, Search Console 시작: https://developers.google.com/search/docs/monitor-debug/search-console-start
- Google Search Central, 스팸 정책: https://developers.google.com/search/docs/essentials/spam-policies
- web.dev, Web Vitals: https://web.dev/articles/vitals
