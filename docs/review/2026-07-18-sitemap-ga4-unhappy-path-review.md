# Sitemap, Robots, GA4 자체 적대적 리뷰

> 대상: `codex/sitemap-ga4` 구현 diff
> 기준: 잘못된 sitemap 또는 분석 설정이 오류 없이 운영 배포되는 경로

## 검사 대상

| # | 파일 | 함수·흐름 |
|---|---|---|
| T1 | `apps/web/lib/db/fonts.ts` | `getPublishedSlugs()` |
| T2 | `apps/web/app/sitemap.ts` | `sitemap()` |
| T3 | `apps/web/app/fonts/[slug]/page.tsx` | `generateMetadata()` |
| T4 | `apps/web/scripts/verify-seo-output.mjs` | `validateSeoOutput()` |
| T5 | `scripts/deploy.sh` | build → XML 검사 → SEO 검사 → upload |

## 실패 시나리오와 판정

| # | 시나리오 | 변경 전 위험 | 조치·현재 동작 | 판정 |
|---|---|---|---|---|
| S1 | Supabase published 조회 오류 | 잘못된 sitemap 생성 가능 | `getPublishedSlugs()`가 오류를 다시 던져 Next 빌드 중단 | SKIP |
| S2 | 조회가 오류 없이 빈 배열 반환 | 정적 7개만 있는 sitemap이 배포될 수 있었음 | 검증기가 폰트 또는 컬렉션 0개면 배포 중단 | 해결 |
| S3 | 일부 URL만 다른 origin 사용 | 부분 문자열 검사로 놓칠 수 있었음 | 모든 `<loc>`을 `URL`로 파싱하고 origin 전수 비교 | 해결 |
| S4 | `/search/` 등 제외 경로 혼입 | origin만 맞으면 통과 가능 | 정적 7개 또는 단일 폰트·컬렉션 상세 경로만 허용 | 해결 |
| S5 | URL 중복 | Search Console 품질 저하 | `Set` 크기와 전체 개수를 비교해 중복 거부 | 해결 |
| S6 | XML 자체 손상 | 정규식 검증만 통과할 여지 | 업로드 전 `xmllint --noout` 실패 시 배포 중단 | 해결 |
| S7 | robots sitemap 누락·중복 | 검색봇 발견 경로 오류 | 정확한 Sitemap 행 1개만 허용 | 해결 |
| S8 | 보류·배포종료 폰트 색인 | 상태 안내 페이지가 검색 결과에 노출 | 접근은 유지하고 `noindex,follow` 적용 | 해결 |
| S9 | GA4 ID 누락·형식 오류 | 분석 스크립트가 조용히 미로드 | 기존 형식 검증 유지, 배포 후 HTML·DebugView 확인을 완료 조건으로 유지 | 외부 검증 대기 |
| S10 | SPA 내부 이동 누락·중복 | 경로별 조회수 왜곡 | 수동 page_view를 추가하지 않고 향상된 측정의 기록 변경 사용, DebugView에서 경로별 1회 확인 | 외부 검증 대기 |
| S11 | 검증 전 배포본으로 롤백 | example.com sitemap 재노출 | 정상 배포 ID를 기록하고 그 이전 배포는 롤백 금지 | 운영 기록 대기 |
| S12 | 수동 `wrangler pages deploy`로 검사 우회 | 검증되지 않은 out 업로드 가능 | 공식 배포 경로를 `scripts/deploy.sh`로 제한. Git hook 강제는 범위 밖 | LOW 잔존 |

## 결론

- HIGH·MEDIUM 코드 결함: 0건
- 외부 검증 대기: GA4 이벤트, Search Console 처리 상태, 새 Cloudflare 배포 ID
- 잔존 LOW: 운영자가 검증 스크립트를 우회해 수동 업로드할 수 있음. 이번 배포는 반드시 `scripts/deploy.sh`를 사용한다.
