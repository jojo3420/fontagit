# 웹 실데이터 연동 + 검색/클릭/등록 설계

> 작성일: 2026-07-15 | 버전: v1.1 | 상태: 설계 확정(구현 대기)
> 기획서: `docs/fontagit-master-plan-v3.0.md` (F-01~F-14, 6-7장)
> 리뷰: `docs/review/review-result-20260715-175540.md` (Codex 6.0/10 + Claude 교차검증)
> 세션 역할: 파이프라인/기능 전담. 이번 스펙으로 웹 기능 트랙을 다룸.

## 변경 이력
- v1.1 (2026-07-15): Codex 리뷰 P0 5건 반영 — 쓰기 경로 RPC화(보안), Top10 빌드타임+집계 RPC, 재빌드 단일경로, fontagit 스키마 노출, tier 매핑 정정+유료 부재. P1 흡수(async 전환, 정규화 SSoT, SEO, 보안 테스트).
- v1.0 (2026-07-15): 최초 설계.

## 1. 배경 - 문제

파이프라인은 구글폰트(Tier A) 실데이터 136종을 Supabase에 적재했다. 그러나 웹(`apps/web`)은 여전히 목업 데이터(`apps/web/data/*.ts`)만 읽고, Supabase 클라이언트 라이브러리조차 없다. **파이프라인이 채운 데이터와 완성된 화면이 끊겨 있다.** 동시에 MUST 기능 중 검색(F-04)-Top10 클릭집계(F-03)-등록폼 제출(F-14)은 스키마부터 없다.

## 2. 확정 결정사항

| 항목 | 결정 | 근거 |
|---|---|---|
| 동적 처리 위치 | **옵션 1** — 정적(`output:"export"`) 유지 + 브라우저가 anon key로 Supabase 직접 호출 | SSG 우선(12장), 운영비 0, anon key는 공개 전제라 RLS로 보호 |
| **쓰기 경로** | **RPC 전용** — 클릭-등록-Top10 조회는 SECURITY DEFINER RPC로만. 원본 쓰기 테이블은 anon 직접 접근 차단 | RLS insert-only만으로는 status/시간 조작 가능(P0-1) |
| **데이터 갱신** | **재빌드가 유일 경로** — 폰트 추가/변경은 배치→업로드→재빌드(새벽 cron 또는 배치 후). 검색결과 slug는 빌드 스냅샷과 정합 | 정적목록/동적검색 시점 불일치 방지(P0-3, 기획서 12장) |
| 확장 대비 | **데이터 접근 계층 추상화** — 화면은 계층 함수만 호출, 내부만 교체 | 미래 서버/엣지 함수 이전을 값싸게 |
| 견본(미리보기) | **시스템폰트 폴백**만. 구글폰트 실서체 웹폰트는 다음 세션 | 이번 세션 스코프 축소, F-06 폴백 규칙 부합 |
| 클릭 어뷰징 | **초기 미방어(수용된 리스크)** — 동일세션 중복제한 등은 심해지면 도입 | 기획서 7-5, 리스크표 "초기 과설계 안 함" |
| 눈누 Tier B 크롤링 | **이번 세션 밖.** 실데이터 연동 후 별도 스펙 | 연동 선행, 법적 가드레일 별도 설계 필요 |
| 마켓/결제 | **먼 미래 메모만**(6절), 지금 구현 안 함 | YAGNI, 별도 서브시스템 |

용어: anon key(익명 키, 브라우저 노출 허용 공개 키) / RLS(Row Level Security, 행 수준 보안) / RPC(Remote Procedure Call, DB 함수 호출) / SECURITY DEFINER(함수 소유자 권한으로 실행되는 DB 함수, 권한 승격) / pg_trgm(문자 조각 유사도 확장) / PostgREST(Supabase가 DB를 REST API로 노출하는 계층) / SSoT(Single Source of Truth, 단일 출처) / PG(결제대행사).

## 3. 데이터 접근 계층 (모든 슬라이스의 토대)

신설 `apps/web/lib/db/`:
- `client.ts` — Supabase 클라이언트 생성. env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`. **커스텀 스키마 지정**: `createClient(url, key, { db: { schema: 'fontagit' } })` (P0-4).
- `mappers.ts` — 실 스키마 row → 앱 `Font`/`Collection` 타입 변환.
- `fonts.ts`, `collections.ts`, `search.ts`, `clicks.ts` — 도메인별 쿼리 함수.

**경계 원칙**: 기존 `lib/data.ts`-`lib/fonts.ts`의 **함수 이름**(`getFontBySlug` 등)을 유지하되, 목업이 동기(배열 find)였던 것과 달리 Supabase 조회는 **비동기**다. 반환 타입은 `Promise<...>`로 바뀌고 호출부에 `await`가 추가된다(서버 컴포넌트는 async라 수용). "화면 완전 무변경"이 아니라 "이름 유지 + async 전환"이 정확하다(P1). 이 계층 경계가 미래 "브라우저 직접 → 엣지 함수" 교체 지점이 된다.

**매핑 규칙**(실 → 앱, P0-5 정정):
- `tier(free/paid)` ← **`is_commercial_free` 기반**(상업적 무료 여부). `source_tier`(A/B/C, 출처 등급)는 의미가 달라 **별도 유지**.
- `weights int[]` → `availableWeights`
- `category_ko` → `category`(값 동일: 고딕/명조/손글씨/장식)
- `moves`(클릭수) → `get_top_fonts` 집계에서 파생, 목록/상세 기본 0
- 앱 전용 `fontKey`(self-host 견본 키)는 견본 폴백 세션에선 미사용 → 시스템폰트 렌더
- **유료 폰트 부재 주의**: `fonts_published_license_chk`가 published를 무료 라이선스(OFL/Apache-2.0/UFL)만 허용 → 현재 `tier='paid'`는 존재 불가. 유료 필터-유료 상세-무료대안(F-13)은 **빈 상태로 처리**하고 유료(Tier C)는 후속 스코프로 명시.

**쓰기/집계 경로 (RPC, SECURITY DEFINER)** — 원본 테이블은 anon 미노출:
- `record_click(font_id uuid)` — 클릭 1건 기록. `clicked_at`은 DB default. 반환 없음.
- `get_top_fonts(period text, lim int)` — 기간별 상위 폰트 집계 반환(원본 미노출). **빌드타임 조회**.
- `submit_font(name, foundry, category, official_url, license_choice)` — 등록 신청. `status='pending'`, `created_at`는 DB 강제(클라이언트 지정 무시).

## 4. 슬라이스 (순차, 각각 독립 완료 가능)

### 슬라이스 1 — 실데이터 연동 + 견본 폴백
- `@supabase/supabase-js` 설치, env 설정, `client.ts`에 `schema:'fontagit'` 지정.
- 서버 컴포넌트가 **빌드 시점**에 Supabase에서 `status='published'` 폰트/컬렉션 fetch → 정적 생성(`generateStaticParams` + `dynamicParams=false` + 미존재 `notFound`).
- 목업 `data/*.ts` 의존 제거, `lib/db/` 경유(async)로 전환. 호출부 `await` 정리.
- 견본은 시스템폰트 폴백(F-06). 정보(이름-라이선스-링크)는 전부 표시. 유료 필터/상세는 빈 상태.
- **SEO(F-09)**: 상세 동적 slug 메타데이터 + 사이트맵 + canonical을 실데이터 기반 생성(완료 기준 포함).
- 완료 기준: 목록/상세/컬렉션이 실데이터 렌더, 링크 오류 0, 사이트맵/메타 생성, 빌드 SSG 성공.

### 슬라이스 2 — 알리아스 검색 (F-04, 6장)
- 마이그레이션 `0003`: `pg_trgm` 확장 + `aliases.alias_norm` GIN trgm 인덱스 + `search_fonts(q text)` RPC(정확 별칭 > 부분일치 > trgm 유사도 점수화). anon에 execute 권한.
- **정규화 SSoT**: 정규화 규칙(소문자 + 공백 제거)을 DB 함수 하나로 두고 파이프라인(`uploader.normalize_alias`)과 검색이 공유. 현재 파이프라인은 `\s+` 제거+lower이므로 동일 규칙으로 통일(불일치 시 정확매칭 실패).
- 검색 페이지: 클라이언트 컴포넌트에서 anon RPC 호출(런타임 동적). 검색결과 slug는 빌드된 상세만 링크.
- **검색 계약**: 입력(정규화 후 최소 1자), 반환 필드(slug, name_ko, name_en, tier, category), 최대 N건, 동점 정렬 기준, 빈 검색어/특수문자 처리, 입력 debounce.
- 0건 검색어 로그 훅 자리만 마련(F-17, 저장은 후속).
- 완료 기준: "지마켓산스/gmarket sans/지마켓 폰트" 등 별칭-오타 매칭 동작, 계약대로 반환.

### 슬라이스 3 — Top10 클릭집계 (F-03, 7장)
- 마이그레이션 `0004`: `font_clicks`(익명, IP-식별자 컬럼 없음, `font_id` FK, `clicked_at` timestamptz default now, 인덱스) + `font_click_daily`(롤업). **anon은 원본 테이블 직접 접근 불가**, `record_click`/`get_top_fonts` RPC로만.
- 공식 링크 이동 시 `record_click(fontId)` 호출을 **fire-and-forget**(실패/지연이 이동 차단 금지, 짧은 timeout 후 무조건 `window.location` 이동).
- **Top10 = 빌드타임 생성**: 홈/트렌드 SSG가 `get_top_fonts`로 랭킹 조회(기획서 7-4). **데이터 없으면 "최신 등록" 폴백**. 표기는 반드시 "이동 클릭 기준". (초기 raw 직접조회 방식은 폐기)
- 일별 롤업 cron-보관정책은 후속.
- 완료 기준: 클릭 기록-랭킹 조회 동작, 원본 테이블 anon 미노출, 개인식별정보 미저장 확인.

### 슬라이스 4 — 등록폼 제출 (F-14)
- 마이그레이션 `0005`: `submissions`(name, foundry, category, official_url, license_choice, status='pending', created_at). anon 직접 insert 차단, `submit_font` RPC로만(status/created_at DB 강제).
- 필드 제약 구체화: 필수 여부, 길이, `license_choice` 허용값(무료/유료/조건부), `official_url` http(s) 형식, 중복 기준.
- `SubmitForm`에 검증(프론트/DB 제약 일치) + RPC 호출 + 중복제출 방지(버튼 disabled).
- **상태 모델**(폼 성격): 입력대기 / 제출중 / 성공 / 실패(재시도). (목록-검색의 로딩/빈결과/오류/성공과 구분)
- 완료 기준: 유효 입력 저장, 무효 입력 차단, 상태 전이 처리, RPC로만 쓰기.

## 5. 테스트 - 검증

- `mappers` 단위 테스트: tier(is_commercial_free 기반)/weights/category 변환, 유료 부재 케이스.
- 검색 RPC: 별칭 정확-부분-오타 케이스 + 계약(반환필드/최대수/빈검색어)(통합 또는 pgTAP).
- **보안경계**: anon이 원본 클릭/등록 테이블 select/update/delete 불가, `status`/시간 조작 불가(RPC가 강제), 미공개(draft) 폰트가 목록/검색/컬렉션에 미노출.
- 클릭 익명성: `font_clicks` 스키마에 IP/식별자 부재 검증.
- 폼 검증: 필수 누락-URL 형식-길이 초과 케이스.
- 각 슬라이스 완료 시 빌드(SSG, unoptimized/trailingSlash/out 검증) + 기존 테스트 스위트 그린 유지.

## 6. 미래 확장 메모 (지금 구현 안 함)

- **눈누 Tier B 크롤링**(다음 스펙): 2단계(눈누 seed → 제작사 공식 사이트) + `review_queue` + 사람 승인. 가드레일: robots.txt 준수, 사실만 수집, 문구 복제 금지(9장). 구글폰트 실서체 견본과 한 트랙으로 묶어 "폰트 다양성-견본 품질" 세션 구성.
- **유료 폰트(Tier C)**: published 제약이 무료 라이선스만 허용하므로 유료 노출은 별도 상태/스키마 설계 필요. 무료대안(F-13) 포함 후속.
- **마켓-결제**(먼 미래): 인증-주문-PG-정산이 얽힌 별도 서브시스템. `/market`을 별도 서브도메인/앱으로 분리, 데이터 계층 검색/클릭을 엣지 함수로 승격. AdSense/SEO용 정적 아카이브는 그대로 유지.

## 7. 구현 전 확인 항목 (착수 시 검증)

- **fontagit 스키마 노출**: PostgREST의 exposed schemas에 `fontagit` 포함 여부. 없으면 anon 조회 불가 → Supabase config 수정 필요(P0-4).
- 실 DB 폰트 `status` 값: `published`인가? `draft`면 anon이 못 읽음(RLS) → 파이프라인 재실행/승격 필요.
- Supabase 연결 env 존재-유효.
- 컬렉션(`collections`/`collection_items`) 실데이터 시드 여부. 없으면 컬렉션 페이지가 빈다 → 시드 선행.
- **Next.js 주의**: `apps/web/AGENTS.md`가 "이 Next.js는 학습 데이터와 다른 breaking change 버전"이라 경고. 코드 작성 전 `node_modules/next/dist/docs/` 확인.
