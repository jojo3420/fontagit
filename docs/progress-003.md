# progress-003: 알리아스 검색 슬라이스2 (2026-07-16)

## 맥락 (이 작업이 왜 필요했나)

F-04(알리아스 검색)는 MUST 기능이자 킬링 포인트 2(검색 우위). 슬라이스 0.5(한글 이름-별칭 적재, PR #14)가 선행 완료되어 실데이터(한글 별칭 44개, name_ko 31종)로 검색 가치를 실증할 수 있는 상태에서 착수. 이전 세션 핸드오프가 지정한 계획 문서 stale 4건(마이그레이션 번호, similarity*0 버그, trgm 대상 불일치, 지마켓 예시)을 v1.1로 교정한 뒤 subagent-driven으로 구현.

## 구현 요약 (무엇을 어디에)

- `supabase/migrations/0006_search_fonts.sql` (신규):
  - `create extension pg_trgm with schema public` + 설치 스키마 검증 DO 블록(다른 스키마면 raise exception)
  - `fontagit.normalize_search(text)`: `lower(regexp_replace(normalize(q, NFC), '\s+', '', 'g'))` — 파이프라인 `uploader.normalize_alias`와 규칙-순서 동일(SSoT)
  - `fontagit.aliases.alias_norm`에 GIN `gin_trgm_ops` 인덱스
  - `fontagit.search_fonts(q text)`: SECURITY DEFINER, `search_path = fontagit, pg_temp`, anon execute 전용(public revoke). 점수 CASE: alias_norm 정확일치=100 > LIKE 부분일치=50(와일드카드 `\`,`%`,`_` 이스케이프) > `max(public.similarity(...))*50`. 필터: `status='published'` + trgm은 `operator(public.%)`(인덱스 활용). 가드: 정규화 후 빈 문자열 또는 100자 초과 → 0건. 정렬: score DESC, name_ko ASC NULLS LAST, name_en, slug. LIMIT 20.
- `apps/web/lib/db/search.ts` (신규): `searchFonts(q)` — 빈/공백/100자 초과(MAX_QUERY_LENGTH) 시 네트워크 없이 [], RPC 오류-예외 시 [] + console.error, RPCSearchRow→SearchResult 매핑(category_ko→category)
- `apps/web/lib/db/types.ts`: `SearchResult` 추가
- `apps/web/app/search/page.tsx|page.module.css` (신규): 'use client' + useSearchParams(Suspense 래핑, output:export 유지), 4상태 UI(입력/로딩/0건/결과), debounce 250ms + cancelled 플래그(stale 응답 경합 차단), 빈 쿼리 분기에서 setLoading(false)(무한 로딩 방지), input aria-label
- `apps/web/components/Header.tsx`: 검색 버튼 → `/search` Link
- 테스트: `search.test.ts` 6케이스(빈/공백/매핑/오류/100-101 경계), `page.test.tsx` 5케이스(4상태 + 요청 중 입력 삭제 회귀). 최종 93/93, tsc 0, SSG 277p

## 시도와 실패 (원인 포함)

1. **pg_trgm 스키마 충돌**: 최초 배포 시 `function similarity(text, text) does not exist`. 원인 — pg_trgm은 public에 설치되는데 SECURITY DEFINER 함수의 search_path(fontagit, pg_temp)에 public이 없음. 해결 — search_path를 넓히지 않고 `public.similarity`, `operator(public.%)` 스키마 한정 호출(보안상 search_path 최소 유지). 마이그레이션에 설치 스키마 가드 DO 블록 추가.
2. **codex CLI 행(재발 방지)**: `/opt/homebrew/bin/codex`(cask 0.144.5)가 `--version`조차 무한 행. `sample` 확인 결과 `_dyld_start`(로더 단계)에서 정지. quarantine xattr 제거로도 미해결. **바이너리를 다른 경로로 복사(cp + xattr -c)하면 즉시 동작** — 원본 경로에 대한 macOS 실행 정책 캐시 문제로 추정. 재발 시 복사 실행으로 우회(`brew reinstall --cask codex --no-quarantine`도 대안).
3. **계획 문서의 부분일치 설계 결함**: 원문 이름 ILIKE는 공백 포함 이름("노토 산스 KR")과 정규화 쿼리("노토산스")가 매칭 불가. alias_norm LIKE로 통일(별칭에 이름 정규화형이 이미 적재됨).

## 결정 근거와 기각된 대안

- **스키마 한정 호출** vs search_path에 public 추가: SECURITY DEFINER에서 search_path는 좁을수록 안전 → 한정 호출 채택.
- **trgm 필터 `operator(public.%)`** vs `similarity() > 0.3`: 후자는 GIN 인덱스를 못 탐 → `%` 연산자(기본 임계 0.3) 채택.
- **RPC 오류 시 빈 배열 유지** vs 오류 상태 구분(Codex Should #2): 계획 v1.1 계약이 "오류 → 빈 배열 + 로깅" 명시 → 유지, UI 오류 상태 구분은 이연.
- **DB 통합 테스트(Codex Should #5) 이연**: pgTAP류 인프라 부재, 계획이 SQL Editor 수동 검증 명시, dev 실측 완료 → 신규 인프라 구축은 스코프 밖.
- **stale 응답 처리 cancelled 플래그** vs AbortController: 후자는 searchFonts 시그니처 변경 필요 → 최소 수정 채택.

## 재현-검증 명령어

```bash
# dev 적용 (pooler 접속정보: .env.sandbox + apps/pipeline/.env)
psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/migrations/0006_search_fonts.sql
# 실측 케이스
psql "$CONN" -c "select * from fontagit.search_fonts('본고딕')"   # noto-sans-kr 100
psql "$CONN" -c "select * from fontagit.search_fonts('본고딩')"   # 오타 → similarity 점수
psql "$CONN" -c "select count(*) from fontagit.search_fonts('%')" # 0 (이스케이프)
# 웹
cd apps/web && pnpm test && pnpm exec tsc --noEmit && pnpm build  # 93/93, 0, SSG
```
