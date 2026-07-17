# FontAgit sitemap, robots, GA4 연동 설계

> 작성일: 2026-07-18
> 대상: `https://fontagit.com`
> 범위: 검색엔진이 읽는 주소 정보 교정, GA4 운영 연동, 배포 후 검증

## 1. 현황과 원인

- 운영 `sitemap.xml`의 URL 137개와 `robots.txt`의 Sitemap 주소가 모두 `https://fontagit.example.com`을 가리킨다.
- `NEXT_PUBLIC_BASE_URL`이 운영 환경에 없고, 코드의 기본값도 예시 도메인이어서 잘못된 주소가 그대로 배포됐다.
- sitemap 생성과 GA4 스크립트 코드는 이미 있다. GA4는 운영 `NEXT_PUBLIC_GA_ID`가 비어 있어 현재 로드되지 않는다.
- `www.fontagit.com`은 이번 점검의 `curl` 결과 `https://fontagit.com`으로 301 이동했다. 대표 도메인은 apex인 `https://fontagit.com`이다.
- 배포는 Cloudflare 원격 빌드가 아니다. `scripts/deploy.sh`가 로컬에서 `.env.production`을 주입해 정적 빌드한 뒤 `out/`만 Cloudflare Pages에 올린다.
- 제공된 Search Console 화면에서 `fontagit.com` 도메인 속성 접근은 확인됐다.

## 2. URL 기준

- 사이트 기준 주소는 `https://fontagit.com` 한 개로 통일한다.
- `NEXT_PUBLIC_BASE_URL`이 없을 때도 실제 운영 도메인을 사용한다.
- 환경변수에 잘못된 URL이 들어오면 조용히 배포하지 않고 빌드 또는 배포 검증에서 실패시킨다.
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

제외 대상:

- 쿼리 조합이 생기는 `/search/`
- 운영·법률 보조 페이지인 `/submit/`, `/contact/`, `/privacy/`, `/disclaimer/`
- 보류·배포종료 상태 안내 폰트 페이지
- 404와 내부 Next.js 경로

Google이 사용하지 않는 `priority`, `changefreq`는 제거한다. 실제 콘텐츠 수정일을 신뢰할 수 있는 데이터가 없으므로 `lastmod`를 임의로 만들지 않는다.

예상 URL 수는 고정 숫자가 아니라 `정적 페이지 7 + published 폰트 수 + published 컬렉션 수`로 계산한다. 현재 데이터 130종·3개 기준 예상값은 140이지만 데이터가 바뀌면 계산값도 함께 바뀐다.

sitemap에 포함하는 정적 페이지와 컬렉션 상세에는 후행 슬래시가 붙은 canonical을 추가한다. 폰트 상세의 기존 canonical도 같은 기준을 유지한다.

## 4. robots.txt

- 모든 일반 페이지의 크롤링을 허용한다.
- sitemap 주소는 `https://fontagit.com/sitemap.xml`로 고정한다.
- `/search/`를 robots.txt로 막지 않는다. robots 차단은 색인 제외 수단이 아니므로 검색 페이지에는 `noindex,follow` 메타데이터를 적용한다.
- sitemap에서 제외한 보류·배포종료 폰트 상태 페이지도 접근은 유지하되 `noindex,follow`로 처리한다.

## 5. 재발 방지

- `BASE_URL` 기본값과 URL 정규화를 검증한다.
- `scripts/deploy.sh`가 Cloudflare 업로드 직전에 빌드 결과의 `sitemap.xml`, `robots.txt`를 검사한다. 문서화된 정상 배포 경로는 이 스크립트로 통일한다.
- sitemap XML 파싱 성공, 모든 `<loc>`의 origin이 정확히 `https://fontagit.com`인지, URL 중복이 없는지, URL 수가 계산값과 맞는지 전수 검사한다.
- robots.txt의 Sitemap 행이 정확히 `Sitemap: https://fontagit.com/sitemap.xml`인지 검사한다.
- 하나라도 다르면 업로드를 중단한다. 일부 문자열만 맞으면 통과하는 검사는 사용하지 않는다.
- 단순 전달 UI 테스트는 추가하지 않는다. 도메인 기본값과 sitemap 핵심 URL만 기존 테스트에서 검증한다.
- 첫 정상 배포 전의 Pages 배포본은 잘못된 sitemap을 포함하므로 롤백 대상으로 사용하지 않는다. 정상 배포 후 배포 ID와 검증 결과를 기록하고, 이후에는 검증된 배포로만 롤백한다.

## 6. GA4 연동

- 로그인된 Google Analytics에서 FontAgit용 GA4 속성과 웹 데이터 스트림이 없으면 생성한다.
- 권장 설정은 속성명 `FontAgit`, 보고 시간대 `대한민국`, 통화 `KRW`, 웹사이트 URL `https://fontagit.com`, 스트림명 `FontAgit Web`이다.
- 향상된 측정에서 페이지 로드와 브라우저 기록 변경 기반 페이지 조회를 활성화한다.
- 발급된 `G-...` 측정 ID는 공개 클라이언트 설정인 `NEXT_PUBLIC_GA_ID`로 로컬 빌드 입력 파일 `.env.production`에 저장한다. 이 파일과 실제 ID는 저장소에 커밋하지 않는다.
- 기존 `GoogleAnalytics` 컴포넌트를 재사용한다. 형식이 올바른 ID가 있을 때만 Google 스크립트를 로드한다.
- 저장소에는 별도 GTM·gtag·Cloudflare Analytics 코드가 없음을 확인했다. 수동 `page_view` 코드는 추가하지 않아 향상된 측정과의 중복을 피한다.
- 배포 후 HTML에 올바른 측정 ID가 포함되는지 확인한다. GA4 DebugView에서 최초 진입과 내부 경로 이동마다 `page_view`가 정확히 한 번 발생하고 `page_location`이 바뀌는지 확인한 뒤 실시간 보고서에서도 방문을 확인한다.

## 7. 배포와 Search Console

1. 테스트, 린트, 정적 빌드를 실행한다.
2. 생성된 sitemap과 robots를 XML·origin·중복·계산된 URL 수 기준으로 검사한다.
3. Cloudflare Pages에 배포한다.
4. 새 배포 ID를 기록하고 운영 `sitemap.xml`, `robots.txt`, canonical, GA4 스크립트를 다시 확인한다.
5. Search Console의 `fontagit.com` 도메인 속성을 확인하고 `https://fontagit.com/sitemap.xml`을 제출한다.

배포나 Search Console 제출이 실패하면 이전의 잘못된 sitemap을 성공으로 보고하지 않는다. 운영 URL과 Search Console 처리 상태를 각각 확인한다.

## 8. 완료 조건

- 운영 sitemap의 모든 `<loc>`이 `https://fontagit.com`으로 시작한다.
- sitemap URL 수가 `정적 7 + published 폰트 + published 컬렉션` 계산값과 일치하고 중복이 없다.
- sitemap의 각 URL이 200으로 응답하고 후행 슬래시 canonical과 일치한다.
- 검색 페이지와 보류·배포종료 폰트 상태 페이지에 `noindex,follow`가 있다.
- 운영 robots.txt가 정확한 sitemap 주소를 안내한다.
- 운영 HTML에서 GA4 측정 스크립트가 로드된다.
- GA4 DebugView에서 최초 진입과 내부 이동의 `page_view`가 경로별 한 번씩 확인된다.
- Search Console에서 sitemap 제출이 성공하거나, Google의 처리 대기 상태가 명확히 표시된다.
- 정상 배포 ID와 검증 결과가 기록되어 잘못된 pre-fix 배포로 롤백하지 않는다.
