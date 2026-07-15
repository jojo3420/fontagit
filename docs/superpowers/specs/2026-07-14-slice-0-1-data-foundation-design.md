# Slice 0+1 설계 — 데이터 기반 + 실데이터 전환

> 작성일: 2026-07-14 | 기반: `docs/fontagit-master-plan-v3.0.md`, `docs/superpowers/specs/2026-07-12-fontagit-initial-setup-design.md`
> 범위: Supabase 스키마 4종 + RLS + 파이프라인 Supabase 업로드 + 웹 목업→실데이터 전환.
> 전제: ollidam과 **같은 Supabase 인스턴스 공유** → fontagit 전용 `fontagit` 스키마로 격리. `output:'export'`(순수 SSG) 불가침. 동적 기능은 브라우저→Supabase 직결(publishable key + RLS). 키는 Supabase 신형 체계(publishable/secret).

## 1. 목표와 비목표

목표
- Supabase `fontagit` 스키마에 `fonts`-`aliases`-`collections`-`collection_items` + RLS 생성.
- 파이프라인이 Tier A 수집 결과를 Supabase에 업로드(멱등 upsert). OFL/Apache/UFL은 자동 공개(published).
- 웹이 목업(`data/*.ts`) 대신 Supabase 실데이터를 빌드타임에 읽어 SSG. 미리보기는 구글폰트 지연 로딩.

비목표(다음 슬라이스)
- F-04 알리아스 검색(pg_trgm RPC) → Slice 2. 스키마(aliases 테이블-alias_norm)만 이번에 준비, 검색 함수-gin_trgm 인덱스는 Slice 2.
- F-05 필터 → Slice 3. F-03 클릭집계(`font_clicks`/`font_click_daily`) → Slice 4. F-08/10/11 → Slice 5.
- Tier B/C 크롤링-수동수집, `free_alternatives` 수동 큐레이션.

## 2. 결정 사항 (확정)

| 항목 | 결정 | 근거 |
|---|---|---|
| 인스턴스/격리 | ollidam과 같은 인스턴스 공유 + 전용 `fontagit` 스키마 | ollidam 테이블(`public`)과 이름충돌-혼선 방지, 물리적 분리 |
| 키 체계 | 신형: 웹=`PUBLISHABLE_KEY`(anon role), 서버=`SECRET_KEY`(service_role) | ollidam .env 실측. 구형 anon/service_role 자리와 동일 역할 |
| 동적 서빙 | 브라우저→Supabase 직결(publishable key + RLS) | `output:'export'`는 서버 라우트 불가. publishable은 공개 전제 키, RLS로 보호 |
| 라이선스 공개 | OFL/Apache/UFL → `verified=true`+`published`, 그 외 `draft` | 구글폰트 표준 라이선스라 허위위험 낮음. 실데이터가 화면에 실제 노출 |
| 폰트 미리보기 | 구글폰트 웹폰트 지연 로딩(뷰포트 진입 시 CSS 동적 삽입) | 기획 F-06 "Tier A 웹폰트". self-host는 재호스팅 위반이라 배제 |
| 별칭 저장 | 별도 `aliases` 테이블 + 정규화 컬럼(`alias_norm`) | Slice 2 pg_trgm 검색 최적화. 배열 컬럼보다 유사도 인덱싱 유리 |
| `tier` 의미분리 | 파이프라인 A/B/C=`source_tier`, 웹 free/paid=`is_commercial_free` | 두 tier는 의미가 다름(수집등급 vs 라이선스성격) |
| 스키마 범위 | 이번은 4개 테이블만 | YAGNI. clicks/review_queue/change_log는 필요 슬라이스에서 |

### 2-1. 환경변수 (세팅 완료, git 무시 확인)
- `apps/web/.env.local`: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `apps/pipeline/.env`: `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `SUPABASE_DB_PASSWORD`(DDL용)

## 3. DB 스키마 (`fontagit` 스키마)

DDL(스키마-테이블-RLS)은 SQL 마이그레이션 파일(`supabase/migrations/*.sql`)로 버전관리하고, psql(`SUPABASE_DB_PASSWORD`) 또는 Supabase SQL Editor로 1회 적용한다. 파이프라인은 데이터 upsert(DML)만 담당(PostgREST는 DDL 불가).

```sql
create schema if not exists fontagit;
grant usage on schema fontagit to anon, authenticated, service_role;

-- fonts: 폰트 카탈로그(웹 Font + 파이프라인 FontRecord 통합)
create table fontagit.fonts (
  id                uuid primary key default gen_random_uuid(),
  slug              text not null unique,          -- URL용, name_en slugify
  name_en           text not null,
  name_ko           text,
  foundry           text,                          -- 구글폰트 designer/저작자
  source_tier       text not null default 'A',     -- 데이터 출처 등급 A/B/C
  category_ko       text not null,                 -- 고딕/명조/손글씨/장식
  category_google   text,                          -- 원본 sans-serif 등(추적용)
  subsets           text[] not null default '{}',
  variants          text[] not null default '{}',  -- "400","400 italic"
  weights           int[]  not null default '{}',  -- variants 파생, 웹 availableWeights
  is_commercial_free boolean not null default false,-- 웹 tier free/paid 파생
  license_type      text,                          -- OFL/Apache-2.0/UFL/null
  license_verified  boolean not null default false,
  official_url      text not null,
  status            text not null default 'draft', -- draft/published/archived
  version           text,
  last_modified     text,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint fonts_status_chk check (status in ('draft','published','archived')),
  constraint fonts_tier_chk   check (source_tier in ('A','B','C')),
  constraint fonts_cat_chk    check (category_ko in ('고딕','명조','손글씨','장식')),
  -- 검증 전 라이선스 공개 금지(기획 9장): license_type은 verified일 때만
  constraint fonts_license_verify_chk check (license_type is null or license_verified = true)
);
create index idx_fonts_status on fontagit.fonts(status);

-- aliases: 검색용 별칭(정규화 저장). trgm 인덱스는 Slice 2에서 추가.
create table fontagit.aliases (
  id         uuid primary key default gen_random_uuid(),
  font_id    uuid not null references fontagit.fonts(id) on delete cascade,
  alias      text not null,
  alias_norm text not null,                        -- 소문자+공백제거 정규화
  unique (font_id, alias_norm)
);
create index idx_aliases_font on fontagit.aliases(font_id);

-- collections / collection_items
create table fontagit.collections (
  id         uuid primary key default gen_random_uuid(),
  slug       text not null unique,
  title      text not null,
  intro      text not null,
  status     text not null default 'draft' check (status in ('draft','published','archived')),
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);
create table fontagit.collection_items (
  collection_id uuid not null references fontagit.collections(id) on delete cascade,
  font_id       uuid not null references fontagit.fonts(id) on delete cascade,
  comment       text,
  sort_order    int not null default 0,
  primary key (collection_id, font_id)
);

grant select on all tables in schema fontagit to anon, authenticated;
```

Supabase 대시보드: Settings → API → Exposed schemas에 `fontagit` 추가(PostgREST 노출). 미설정 시 API 접근 불가.

### 3-1. 웹 타입 ↔ DB 매핑 (어댑터 규칙)
- `Font.tier`(free/paid) = `is_commercial_free ? 'free' : 'paid'`
- `Font.category`(한글) = `category_ko`
- `Font.availableWeights` = `weights`
- `Font.moves` = 0 (Slice 4 클릭집계 전까지 고정)
- `Font.fontKey` 제거 → 미리보기는 `name_en`(구글 family)으로 동적 로딩(5절)
- `Font.foundry` = `foundry`, `Font.aliases` = `aliases[].alias`
- `Font.freeAlternatives` = [] (수동 큐레이션, 이번 범위 밖)
- `Font.license.commercial` = OFL/Apache/UFL→`yes`, 그 외→`conditional`; `verifiedAt` = `updated_at`(published 시점)

## 4. 파이프라인 변경 (`apps/pipeline`)

수집(collect)은 유지. 뒤에 두 단계 추가.

### 4-1. 라이선스 판별 (신규)
- webfonts API는 라이선스 미제공 → 구글폰트 라이선스 메타데이터를 별도 조회.
  google/fonts 저장소의 라이선스 구분(`ofl`/`apache`/`ufl` 디렉토리 또는 `METADATA.pb`의 `license`)을 소스로 사용.
- 매핑: `OFL`→`'OFL'`, `APACHE2`→`'Apache-2.0'`, `UFL`→`'UFL'`; 셋 중 하나면 `is_commercial_free=true`, `license_verified=true`, `status='published'`.
- 그 외/미확인 → `license_type=null`, `verified=false`, `status='draft'`(비공개).
- `FontRecord`에 필드 추가: `source_tier`, `category_ko`, `weights`, `is_commercial_free`, `license_type`, `status`, `slug`.
- `category_ko` 매핑: sans-serif→고딕, serif→명조, handwriting→손글씨, display→장식, monospace→고딕.
- `slug`: `name_en` slugify(소문자-공백 하이픈-ASCII). 충돌 시 접미 번호.

### 4-2. Supabase 업로드 (신규 `uploader.py`)
- `supabase-py`, `SUPABASE_SECRET_KEY`(서버 전용, 절대 커밋-클라이언트 노출 금지). 쿼리는 `.schema('fontagit')` 지정.
- `fonts` upsert(on_conflict=`slug`). 이어 각 폰트의 `aliases`를 `(font_id, alias_norm)` upsert(멱등). `alias_norm` = 소문자+공백제거.
- writer의 JSON 출력은 유지(검증-롤백-오프라인 재현).
- 실패 시 로그 + 비정상 종료. 부분 실패는 upsert 멱등성으로 재실행 안전.

## 5. 웹 변경 (`apps/web`)

- `lib/supabase.ts`(신규): publishable 클라이언트, `db: { schema: 'fontagit' }`. `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
- `lib/data.ts`: 목업 import 제거 → 빌드타임 Supabase fetch. `status='published'`만. DB row→`Font` 어댑터(3-1). `getFontBySlug`/`getAllSlugs`/`getCollection*`을 async 또는 빌드 프리페치로 전환.
- 상세 라우트 `generateStaticParams` = published 슬러그 목록.
- 미리보기 로딩: `name_en`으로 구글폰트 CSS를 뷰포트 진입 시 동적 `<link>` 삽입(IntersectionObserver), 실패 시 시스템 폰트 폴백(F-06). `fontKey` 기반 self-host 로직 제거.
- 목업 정리: `data/fonts.ts`-`data/collections.ts` 제거. `data/trends.ts`는 Slice 4까지 "최신 등록" 폴백으로 유지.
- UI 폰트 Pretendard(next/font self-host)는 카탈로그와 무관하게 유지. 카탈로그 항목으로서의 Pretendard는 Tier C 수동(이번 범위 밖, 없어도 무방).
- UI 상태: 목록 Empty("등록된 폰트가 없습니다") 처리. (빌드타임 정적이라 Loading/Error는 미해당.)

## 6. RLS / 보안

```sql
alter table fontagit.fonts enable row level security;
alter table fontagit.aliases enable row level security;
alter table fontagit.collections enable row level security;
alter table fontagit.collection_items enable row level security;

create policy anon_read_published_fonts on fontagit.fonts
  for select to anon using (status = 'published');
create policy anon_read_aliases on fontagit.aliases
  for select to anon using (exists (
    select 1 from fontagit.fonts f where f.id = font_id and f.status = 'published'));
create policy anon_read_published_collections on fontagit.collections
  for select to anon using (status = 'published');
create policy anon_read_collection_items on fontagit.collection_items
  for select to anon using (exists (
    select 1 from fontagit.collections c where c.id = collection_id and c.status = 'published'));
```
- publishable 키(=anon role): published read만. INSERT/UPDATE/DELETE 정책 없음(거부). 클릭 insert 정책은 Slice 4.
- 업로드는 secret 키(=service_role, RLS 우회, 파이프라인 서버 전용). 키는 서버 환경변수, 클라이언트 번들-git 금지.
- `fontagit` 스키마 격리로 ollidam(`public`) 데이터와 상호 접근 불가.

## 7. 검증

- 파이프라인 단위: 라이선스 판별(OFL/Apache/UFL→published, 그외→draft), category_ko 매핑, slug 생성/충돌, alias_norm 정규화. 픽스처 기반.
- 파이프라인 통합: `uploader` 실행 후 Supabase에서 `count(*)`-`count(status='published')` 재조회(쓰기→읽기 재검증). upsert 2회 실행해 멱등성(중복 없음) 확인.
- 웹: `next build` 그린, published 슬러그로 상세 페이지 생성 확인, 스모크(`e2e/smoke`)로 실데이터 렌더-미리보기 폴백 확인. 스냅샷 baseline 갱신.
- lint/type: `make lint`, `mypy`, `pnpm typecheck` 통과.

## 8. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| ollidam과 인스턴스 공유 충돌 | `fontagit` 스키마 격리, RLS. 마이그레이션은 fontagit 스키마 대상만 |
| 구글폰트 라이선스 소스 조회 실패 | 조회 실패 폰트는 draft(비공개) 유지 — 안전측 기본값 |
| 잘못된 라이선스 공개(최대 위험) | OFL/Apache/UFL 화이트리스트만 자동공개, DB check 제약으로 verified 없인 license_type 불가 |
| publishable 키 노출로 데이터 조작 | RLS read-only, 쓰기 정책 없음. secret 키는 서버 전용 |
| 구글 CDN 외부의존-개인정보 | 지연 로딩으로 요청 최소화, 실패 시 시스템 폰트 폴백 |
| 목업 제거 후 published 0건 | 라이선스 자동공개로 방지. 통합검증에서 published>0 확인 |
| 웹 데이터 레이어 async 전환 영향 | 호출처(상세/목록/컬렉션/generateStaticParams) 전수 수정, 빌드 그린으로 검증 |

## 9. 기획 추적성

| 설계 항목 | 기획 근거 |
|---|---|
| aliases 별도테이블-정규화 | 6장 검색설계, F-04 |
| OFL/Apache 자동공개 | 4장 Tier A(OFL), 9장 라이선스 정직성 |
| 브라우저→Supabase 직결 | 6장(서버경유 취지=키보호)를 publishable+RLS로 충족, `output:'export'` 양립 |
| 구글폰트 지연 로딩 | F-06 미리보기(Tier A 웹폰트, 지연, 폴백) |
| status/published | 2장 "AI 초안 사람 검수", 9장 검증 전 비공개 |

## 10. 다음 단계

이 스펙 승인 시 `writing-plans`로 구현 계획 작성 → 오케스트레이션 위임 구현.
