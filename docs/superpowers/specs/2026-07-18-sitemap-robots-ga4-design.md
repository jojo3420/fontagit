# FontAgit sitemap, robots, GA4 연동 설계

> 작성일: 2026-07-18
> 대상: `https://fontagit.com`
> 범위: 검색엔진이 읽는 주소 정보 교정, GA4 운영 연동, 배포 후 검증

## 1. 현황과 원인

- 운영 `sitemap.xml`의 URL 137개와 `robots.txt`의 Sitemap 주소가 모두 `https://fontagit.example.com`을 가리킨다.
- `NEXT_PUBLIC_BASE_URL`이 운영 환경에 없고, 코드의 기본값도 예시 도메인이어서 잘못된 주소가 그대로 배포됐다.
- sitemap 생성과 GA4 스크립트 코드는 이미 있다. GA4는 운영 `NEXT_PUBLIC_GA_ID`가 비어 있어 현재 로드되지 않는다.
- `www.fontagit.com`은 `https://fontagit.com`으로 301 이동하므로 대표 도메인은 apex인 `https://fontagit.com`이다.

## 2. URL 기준

- 사이트 기준 주소는 `https://fontagit.com` 한 개로 통일한다.
- `NEXT_PUBLIC_BASE_URL`이 없을 때도 실제 운영 도메인을 사용한다.
- 환경변수에 잘못된 URL이 들어오면 조용히 배포하지 않고 빌드 또는 배포 검증에서 실패시킨다.
- sitemap에는 검색 결과에 노출할 가치가 있고 200으로 응답하는 대표 URL만 넣는다.

## 3. sitemap.xml

포함 대상:

- `/`
- `/fonts/`와 공개 폰트 상세 `/fonts/{slug}/`
- `/collections/`와 공개 컬렉션 상세 `/collections/{slug}/`
- `/trends/`
- `/compare/`
- `/playground/`
- `/about/`

제외 대상:

- 쿼리 조합이 생기는 `/search/`
- 운영·법률 보조 페이지인 `/submit/`, `/contact/`, `/privacy/`, `/disclaimer/`
- 404와 내부 Next.js 경로

Google이 사용하지 않는 `priority`, `changefreq`는 제거한다. 실제 콘텐츠 수정일을 신뢰할 수 있는 데이터가 없으므로 `lastmod`를 임의로 만들지 않는다.

## 4. robots.txt

- 모든 일반 페이지의 크롤링을 허용한다.
- sitemap 주소는 `https://fontagit.com/sitemap.xml`로 고정한다.
- `/search/`를 robots.txt로 막지 않는다. robots 차단은 색인 제외 수단이 아니며, 검색 페이지의 색인 정책이 필요하면 페이지 메타데이터의 `noindex`로 별도 처리한다.

## 5. 재발 방지

- `BASE_URL` 기본값과 URL 정규화를 검증한다.
- 배포 스크립트가 빌드 결과의 `sitemap.xml`, `robots.txt`를 검사한다.
- 두 파일에 `fontagit.example.com`이 남거나 `https://fontagit.com`이 없으면 배포를 중단한다.
- 단순 전달 UI 테스트는 추가하지 않는다. 도메인 기본값과 sitemap 핵심 URL만 기존 테스트에서 검증한다.

## 6. GA4 연동

- 로그인된 Google Analytics에서 FontAgit용 GA4 속성과 웹 데이터 스트림이 없으면 생성한다.
- 권장 설정은 속성명 `FontAgit`, 보고 시간대 `대한민국`, 통화 `KRW`, 웹사이트 URL `https://fontagit.com`, 스트림명 `FontAgit Web`이다.
- 발급된 `G-...` 측정 ID는 공개 클라이언트 설정인 `NEXT_PUBLIC_GA_ID`로 운영 환경 파일에 저장한다. ID는 저장소에 커밋하지 않는다.
- 기존 `GoogleAnalytics` 컴포넌트를 재사용한다. 형식이 올바른 ID가 있을 때만 Google 스크립트를 로드한다.
- 배포 후 HTML에 올바른 측정 ID가 포함되는지 확인하고, GA4 실시간 보고서 또는 Tag Assistant에서 방문 이벤트 수신을 확인한다.

## 7. 배포와 Search Console

1. 테스트, 린트, 정적 빌드를 실행한다.
2. 생성된 sitemap과 robots의 호스트와 URL 개수를 검사한다.
3. Cloudflare Pages에 배포한다.
4. 운영 `sitemap.xml`, `robots.txt`, GA4 스크립트를 다시 확인한다.
5. Google Search Console에 `https://fontagit.com/sitemap.xml`을 제출한다.

배포나 Search Console 제출이 실패하면 이전의 잘못된 sitemap을 성공으로 보고하지 않는다. 운영 URL과 Search Console 처리 상태를 각각 확인한다.

## 8. 완료 조건

- 운영 sitemap의 모든 `<loc>`이 `https://fontagit.com`으로 시작한다.
- sitemap의 각 URL이 대표 URL이며 공개 페이지와 일치한다.
- 운영 robots.txt가 정확한 sitemap 주소를 안내한다.
- 운영 HTML에서 GA4 측정 스크립트가 로드된다.
- GA4에서 실제 방문 이벤트가 확인된다.
- Search Console에서 sitemap 제출이 성공하거나, Google의 처리 대기 상태가 명확히 표시된다.
