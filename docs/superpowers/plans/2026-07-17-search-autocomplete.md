# 검색 자동완성(F-19) + 초성 검색(F-16) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 헤더 검색바에 입력하는 동안 별칭/오타/초성으로 매칭된 폰트를 실시간 드롭다운으로 제안하고, 결과 페이지 검색에도 초성 매칭을 추가한다.

**Architecture:** 기존 `fontagit.search_fonts` RPC를 재활용한다. DB에 초성 추출 함수와 저장 컬럼(생성 컬럼)을 추가해 초성 접두 검색을 붙이고, RPC에 `lim` 파라미터와 `foundry` 반환을 더한다. 웹은 얇은 Route Handler(`/api/suggest`)로 상위 8건을 받아 드롭다운을 그린다.

**Tech Stack:** PostgreSQL(Supabase, 스키마 `fontagit`), pg_trgm, Next.js App Router(Route Handler), React, TypeScript, vitest(웹 단위 테스트), psql(SQL 통합 테스트).

**설계 출처:** `docs/superpowers/specs/2026-07-17-search-autocomplete-chosung-design.md`

## Global Constraints

- 스키마명은 항상 `fontagit`. RPC는 `security definer` + `set search_path = fontagit, pg_temp`.
- RPC 권한: `revoke execute ... from public; grant execute ... to anon;`. published 폰트만 노출.
- 입력 정규화는 기존 `fontagit.normalize_search`(NFC + 공백제거 + 소문자) 재사용. 검색어 100자 초과는 빈 결과.
- 웹 코드: TypeScript 타입 100%, 주석/도크스트링 한국어, `print`/`console.log` 대신 서버 로그. 하드코딩 상수는 명명.
- SQL 통합 테스트는 dev DB 커넥션(`$DEV_CONN`, `.env.sandbox`)에 `psql -v ON_ERROR_STOP=1 -f`로 실행. read-only(select/assert만).
- 웹 단위 테스트는 `apps/web`에서 `pnpm test <path>`(vitest). db 모듈은 `vi.mock('./client')`로 mock.
- 커밋: `<타입>: <설명>` 컨벤셔널 커밋. 브랜치 `feat/search-autocomplete`.
- 마이그레이션 파일은 `supabase/migrations/0008_chosung_search.sql` 하나에 Task 1~3을 누적 추가한다.

---

## 파일 구조

| 파일 | 책임 |
|------|------|
| `supabase/migrations/0008_chosung_search.sql` | to_chosung 함수, alias_chosung 생성 컬럼+색인, search_fonts 재정의, notify pgrst, 롤백 주석 |
| `supabase/tests/chosung_search_test.sql` | to_chosung/초성 RPC/lim/권한 SQL 어서션 |
| `apps/web/lib/db/search.ts` | `searchSuggestions` 추가, `RPCSearchRow`/`SearchResult`에 `foundry` |
| `apps/web/lib/db/search.test.ts` | searchSuggestions 매핑/인자 테스트 |
| `apps/web/app/api/suggest/route.ts` | GET 핸들러, 200/503 분리 |
| `apps/web/app/api/suggest/route.test.ts` | 정상/빈쿼리/오류 응답 |
| `apps/web/hooks/useDebouncedSuggestions.ts` | 디바운스+취소+시퀀스 |
| `apps/web/hooks/useDebouncedSuggestions.test.ts` | 디바운스/최신응답 반영 |
| `apps/web/components/SearchSuggestions.tsx` | 드롭다운 렌더, 하이라이트, ARIA |
| `apps/web/components/SearchSuggestions.test.tsx` | 렌더/하이라이트/선택 |
| `apps/web/components/HeaderSearch.tsx` | 드롭다운 연동, 키보드, IME |
| `apps/web/components/HeaderSearch.test.tsx` | 기존 회귀 + 키보드/IME |

---

## Task 1: 초성 추출 함수 `to_chosung`

**Files:**
- Create: `supabase/migrations/0008_chosung_search.sql`
- Test: `supabase/tests/chosung_search_test.sql`

**Interfaces:**
- Produces: `fontagit.to_chosung(text) returns text` — 한글 음절의 초성만 뽑고 나머지는 그대로. IMMUTABLE STRICT.

- [ ] **Step 1: SQL 테스트 작성 (실패 어서션)**

Create `supabase/tests/chosung_search_test.sql`:

```sql
-- =============================================================================
-- 초성 검색 + 자동완성 SQL 통합 테스트
-- 실행: psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/tests/chosung_search_test.sql
-- 전제: 0008_chosung_search.sql 적용 완료, dev DB에 published 실데이터(지마켓 산스 등) 존재
-- read-only (assert만)
-- =============================================================================

-- C1: 한글 초성 추출
do $$
declare r text;
begin
  r := fontagit.to_chosung('지마켓산스');
  if r != 'ㅈㅁㅋㅅㅅ' then
    raise exception 'C1 failed: expected ''ㅈㅁㅋㅅㅅ'', got ''%''', r;
  end if;
end $$;

-- C2: 영문/숫자/공백은 그대로 통과
do $$
declare r text;
begin
  r := fontagit.to_chosung('gmarket 2024');
  if r != 'gmarket 2024' then
    raise exception 'C2 failed: got ''%''', r;
  end if;
end $$;

-- C3: 혼합(한글+영문)
do $$
declare r text;
begin
  r := fontagit.to_chosung('본고딕abc');
  if r != 'ㅂㄱㄷabc' then
    raise exception 'C3 failed: got ''%''', r;
  end if;
end $$;
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/tests/chosung_search_test.sql`
Expected: FAIL — `function fontagit.to_chosung(text) does not exist`

- [ ] **Step 3: to_chosung 함수 작성**

Create `supabase/migrations/0008_chosung_search.sql` (첫 블록):

```sql
-- =============================================================================
-- 0008_chosung_search.sql
-- 초성 검색(F-16) + 자동완성(F-19) 지원: to_chosung 함수, alias_chosung 컬럼, search_fonts 재정의
-- =============================================================================

-- 1) 초성 추출 함수 (한글 음절 → 초성, 그 외 문자는 그대로)
-- IMMUTABLE: 생성 컬럼에 사용하려면 필수. STRICT: NULL 입력 방어.
create or replace function fontagit.to_chosung(p text)
returns text
language sql
immutable
strict
as $$
  select coalesce(
    string_agg(
      case
        when ascii(ch) between 44032 and 55203  -- 가(U+AC00)~힣(U+D7A3)
        then (array[
          'ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ',
          'ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ'
        ])[((ascii(ch) - 44032) / 588)::int + 1]
        else ch
      end,
      '' order by ord
    ),
    ''
  )
  from regexp_split_to_table(p, '') with ordinality as t(ch, ord);
$$;
```

- [ ] **Step 4: dev 적용 후 테스트 실행 → 통과 확인**

Run:
```bash
psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/migrations/0008_chosung_search.sql
psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/tests/chosung_search_test.sql
```
Expected: PASS (에러 없이 종료, exit 0)

- [ ] **Step 5: 커밋**

```bash
git add supabase/migrations/0008_chosung_search.sql supabase/tests/chosung_search_test.sql
git commit -m "feat: 초성 추출 함수 to_chosung 추가 (F-16)"
```

---

## Task 2: 초성 저장 컬럼 `alias_chosung` + 색인

**Files:**
- Modify: `supabase/migrations/0008_chosung_search.sql` (블록 추가)
- Test: `supabase/tests/chosung_search_test.sql` (어서션 추가)

**Interfaces:**
- Consumes: `fontagit.to_chosung(text)` (Task 1), 기존 컬럼 `fontagit.aliases.alias_norm`(일반 컬럼).
- Produces: `fontagit.aliases.alias_chosung` 생성 컬럼 + 색인 `idx_aliases_chosung`.

- [ ] **Step 1: 컬럼 존재/값 어서션 추가**

`supabase/tests/chosung_search_test.sql` 하단에 추가:

```sql
-- C4: alias_chosung 생성 컬럼이 alias_norm 초성과 일치
do $$
declare cnt int;
begin
  select count(*) into cnt
  from fontagit.aliases
  where alias_chosung is distinct from fontagit.to_chosung(alias_norm);
  if cnt != 0 then
    raise exception 'C4 failed: alias_chosung mismatch rows=%', cnt;
  end if;
end $$;
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/tests/chosung_search_test.sql`
Expected: FAIL — `column "alias_chosung" does not exist`

- [ ] **Step 3: 생성 컬럼 + 색인 추가**

`supabase/migrations/0008_chosung_search.sql`에 이어서:

```sql
-- 2) 초성 저장 컬럼 (생성 컬럼: 저장/수정 시 자동 계산, 기존 행 자동 백필)
alter table fontagit.aliases
  add column if not exists alias_chosung text
  generated always as (fontagit.to_chosung(alias_norm)) stored;

-- 접두(prefix) LIKE 'x%' 검색이 색인을 타도록 text_pattern_ops
create index if not exists idx_aliases_chosung
  on fontagit.aliases (alias_chosung text_pattern_ops);
```

- [ ] **Step 4: dev 재적용 후 테스트 통과 확인**

Run:
```bash
psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/migrations/0008_chosung_search.sql
psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/tests/chosung_search_test.sql
```
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add supabase/migrations/0008_chosung_search.sql supabase/tests/chosung_search_test.sql
git commit -m "feat: aliases.alias_chosung 생성 컬럼 + 색인 추가 (F-16)"
```

---

## Task 3: `search_fonts` 재정의 (초성 분기 + lim + foundry)

**Files:**
- Modify: `supabase/migrations/0008_chosung_search.sql` (블록 추가)
- Test: `supabase/tests/chosung_search_test.sql` (어서션 추가)

**Interfaces:**
- Consumes: `alias_chosung`(Task 2), 기존 `fontagit.normalize_search`, `fontagit.fonts`, `fontagit.aliases`, `public.similarity`.
- Produces: `fontagit.search_fonts(q text, lim int default 20)` returns table(slug text, name_ko text, name_en text, tier text, category_ko text, foundry text, score int). 초성 전용 입력이면 초성 접두 매칭, 아니면 정확/부분/trgm. lim은 1~100 clamp.

- [ ] **Step 1: 초성 RPC/lim/권한 어서션 추가**

`supabase/tests/chosung_search_test.sql` 하단에 추가:

```sql
-- C5: 초성 입력으로 지마켓 산스가 잡힌다 (dev 실데이터 전제)
do $$
declare cnt int;
begin
  select count(*) into cnt
  from fontagit.search_fonts('ㅈㅁㅋ', 8) s
  where s.slug = 'gmarket-sans';
  if cnt < 1 then
    raise exception 'C5 failed: chosung search did not match gmarket-sans (cnt=%)', cnt;
  end if;
end $$;

-- C6: lim clamp — 0/음수/과대값도 안전 (에러 없이 반환, 최대 100)
do $$
declare cnt int;
begin
  select count(*) into cnt from fontagit.search_fonts('ㄱ', 0);   -- clamp→1
  select count(*) into cnt from fontagit.search_fonts('ㄱ', -5);  -- clamp→1
  select count(*) into cnt from fontagit.search_fonts('ㄱ', 1000);-- clamp→100
  -- 예외 없이 도달하면 통과
end $$;

-- C7: 1-인자 하위호환 (기존 호출 유지)
do $$
declare cnt int;
begin
  select count(*) into cnt from fontagit.search_fonts('지마켓');
  if cnt < 1 then
    raise exception 'C7 failed: 1-arg search_fonts broke (cnt=%)', cnt;
  end if;
end $$;

-- C8: foundry 컬럼이 반환된다
do $$
declare has_foundry boolean;
begin
  select exists(select 1 from fontagit.search_fonts('지마켓', 8) s where s.foundry is not null)
    into has_foundry;
  -- foundry가 전부 null일 수도 있으므로 컬럼 참조가 에러 없이 되는지만 검증(위 select 성공이면 OK)
end $$;

-- C9: 비공개 폰트 미노출 — published 아닌 폰트는 결과에 없음
do $$
declare cnt int;
begin
  select count(*) into cnt
  from fontagit.search_fonts('지마켓', 100) s
  join fontagit.fonts f on f.slug = s.slug
  where f.status <> 'published';
  if cnt != 0 then
    raise exception 'C9 failed: unpublished fonts leaked (cnt=%)', cnt;
  end if;
end $$;
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/tests/chosung_search_test.sql`
Expected: FAIL — `function fontagit.search_fonts(text, integer) does not exist` (C5)

- [ ] **Step 3: search_fonts 재정의**

`supabase/migrations/0008_chosung_search.sql`에 이어서:

```sql
-- 3) search_fonts 재정의: (q, lim) 2-인자, 초성 분기 + foundry 반환 + lim clamp
-- 기존 1-인자 함수 제거 (CASCADE 금지: 의존 객체 없음 전제)
drop function if exists fontagit.search_fonts(text);

create or replace function fontagit.search_fonts(q text, lim int default 20)
returns table(
  slug text, name_ko text, name_en text,
  tier text, category_ko text, foundry text, score int
)
language plpgsql
stable
security definer
set search_path = fontagit, pg_temp
as $$
declare
  v_normalized text := normalize_search(q);
  v_like_pattern text;
  v_lim int := least(greatest(coalesce(lim, 20), 1), 100);  -- 1~100 clamp
  v_is_chosung boolean;
begin
  if v_normalized = '' or char_length(v_normalized) > 100 then
    return;
  end if;

  -- 초성 자모 19자로만 구성된 입력인지 판별
  v_is_chosung := v_normalized ~ '^[ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ]+$';

  if v_is_chosung then
    -- 초성 접두 매칭 (동일 점수 45, 이름순 정렬)
    return query
    select f.slug, f.name_ko, f.name_en,
           case when f.is_commercial_free then 'free' else 'paid' end,
           f.category_ko, f.foundry, 45
    from fonts f
    where f.status = 'published'
      and exists(
        select 1 from aliases a
        where a.font_id = f.id
          and a.alias_chosung like v_normalized || '%'
      )
    order by f.name_ko asc nulls last, f.name_en asc, f.slug asc
    limit v_lim;
    return;
  end if;

  -- 일반 매칭 (정확 100 / 부분 50 / trgm 0~50) — 기존 0006 로직 + foundry + lim
  v_like_pattern := '%' ||
    replace(replace(replace(v_normalized, '\', '\\'), '%', '\%'), '_', '\_') || '%';

  return query
  select f.slug, f.name_ko, f.name_en,
         case when f.is_commercial_free then 'free' else 'paid' end,
         f.category_ko, f.foundry,
         case
           when exists(select 1 from aliases a
                       where a.font_id = f.id and a.alias_norm = v_normalized) then 100
           when exists(select 1 from aliases a
                       where a.font_id = f.id
                         and a.alias_norm like v_like_pattern escape '\') then 50
           else coalesce((
             select (max(public.similarity(a.alias_norm, v_normalized)) * 50)::int
             from aliases a where a.font_id = f.id
           ), 0)
         end as score
  from fonts f
  where f.status = 'published'
    and exists(
      select 1 from aliases a
      where a.font_id = f.id
        and (a.alias_norm = v_normalized
             or a.alias_norm like v_like_pattern escape '\'
             or a.alias_norm operator(public.%) v_normalized)
    )
  order by score desc, f.name_ko asc nulls last, f.name_en asc, f.slug asc
  limit v_lim;
end;
$$;

-- 권한: public 회수 후 anon만 실행 (기존 0006 패턴)
revoke execute on function fontagit.search_fonts(text, int) from public;
grant execute on function fontagit.search_fonts(text, int) to anon;

-- PostgREST 스키마 캐시 리로드 (새 시그니처 즉시 인식)
notify pgrst, 'reload schema';

-- =============================================================================
-- 롤백 순서(역순): 웹을 1-인자 호출 버전으로 먼저 되돌린 뒤 아래 실행
--   drop index if exists fontagit.idx_aliases_chosung;
--   alter table fontagit.aliases drop column if exists alias_chosung;
--   drop function if exists fontagit.to_chosung(text);
--   drop function if exists fontagit.search_fonts(text, int);
--   -- 0006_search_fonts.sql의 1-인자 search_fonts 재적용
--   notify pgrst, 'reload schema';
-- =============================================================================
```

> ⚠️ 주의: `drop function fontagit.search_fonts(text)`에 의존하는 뷰/트리거가 있으면 실패한다. 없음이 전제(0006은 앱/RPC에서만 호출). 있으면 CASCADE 대신 개별 처리.

- [ ] **Step 4: dev 재적용 후 전체 SQL 테스트 통과**

Run:
```bash
psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/migrations/0008_chosung_search.sql
psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/tests/chosung_search_test.sql
```
Expected: PASS (C1~C9 전부)

> C5/C9는 dev 실데이터에 `gmarket-sans`(published, 별칭에 "지마켓" 계열) 존재를 전제. slug가 다르면 실제 slug로 교체.

- [ ] **Step 5: 커밋**

```bash
git add supabase/migrations/0008_chosung_search.sql supabase/tests/chosung_search_test.sql
git commit -m "feat: search_fonts에 초성 분기+lim+foundry 추가 (F-16, F-19)"
```

---

## Task 4: 데이터 계층 `searchSuggestions` + foundry

**Files:**
- Modify: `apps/web/lib/db/search.ts`
- Test: `apps/web/lib/db/search.test.ts`

**Interfaces:**
- Consumes: `supabaseClient.rpc('search_fonts', { q, lim })` (Task 3).
- Produces: `searchSuggestions(q: string, lim?: number): Promise<SearchResult[]>`, `SearchResult.foundry: string | null`.

- [ ] **Step 1: 실패 테스트 작성**

`apps/web/lib/db/search.test.ts` 하단에 추가:

```typescript
import { searchSuggestions } from './search';

describe('searchSuggestions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lim을 RPC 인자로 전달하고 foundry를 매핑한다', async () => {
    vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({
      data: [
        {
          slug: 'gmarket-sans',
          name_ko: '지마켓 산스',
          name_en: 'Gmarket Sans',
          tier: 'free',
          category_ko: '고딕',
          foundry: 'G마켓',
          score: 45,
        },
      ],
      error: null,
    } as never);

    const result = await searchSuggestions('ㅈㅁㅋ', 8);

    expect(supabaseClient.rpc).toHaveBeenCalledWith('search_fonts', { q: 'ㅈㅁㅋ', lim: 8 });
    expect(result[0].foundry).toBe('G마켓');
    expect(result[0].slug).toBe('gmarket-sans');
  });

  it('기본 lim은 8이다', async () => {
    vi.mocked(supabaseClient.rpc).mockResolvedValueOnce({ data: [], error: null } as never);
    await searchSuggestions('지마켓');
    expect(supabaseClient.rpc).toHaveBeenCalledWith('search_fonts', { q: '지마켓', lim: 8 });
  });
});
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd apps/web && pnpm test lib/db/search.test.ts`
Expected: FAIL — `searchSuggestions is not a function`

- [ ] **Step 3: 구현**

`apps/web/lib/db/search.ts`:
1. `RPCSearchRow` 인터페이스에 `foundry: string | null;` 추가.
2. `SearchResult` 인터페이스에 `foundry: string | null;` 추가.
3. 매핑부에 `foundry: row.foundry,` 추가(기존 searchFonts의 map, 그리고 공용 매핑이 있으면 공용에).
4. 함수 추가:

```typescript
/**
 * 자동완성 드롭다운용 검색. searchFonts와 같은 RPC를 쓰되 lim으로 상위 N개만 받는다.
 * @param q 검색어(정규화 전 원문)
 * @param lim 최대 결과 수 (기본 8)
 */
export async function searchSuggestions(q: string, lim = 8): Promise<SearchResult[]> {
  const query = q.trim();
  if (!query || query.length > MAX_QUERY_LENGTH) {
    return [];
  }
  const { data, error } = await supabaseClient.rpc('search_fonts', { q: query, lim });
  if (error) {
    throw new Error('SEARCH_RPC_FAILED');
  }
  return (data as RPCSearchRow[]).map((row: RPCSearchRow): SearchResult => ({
    slug: row.slug,
    nameKo: row.name_ko,
    nameEn: row.name_en,
    tier: row.tier,
    category: row.category_ko,
    foundry: row.foundry,
    score: row.score,
  }));
}
```

> 실제 `SearchResult` 필드명(예: `category` vs `categoryKo`)은 기존 `searchFonts` 매핑을 그대로 따른다. 위 매핑은 기존 코드에 맞춰 필드명을 정렬할 것.

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd apps/web && pnpm test lib/db/search.test.ts`
Expected: PASS (기존 searchFonts 테스트 + 신규 2개)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/lib/db/search.ts apps/web/lib/db/search.test.ts
git commit -m "feat: searchSuggestions 데이터 계층 + foundry 매핑 (F-19)"
```

---

## Task 5: Route Handler `/api/suggest` (미채택 — 아래 노트)

> ⚠️ 구현 변경(PR #19 반영, 2026-07-17): `next.config.ts` `output: 'export'`(정적 내보내기)로 동적 Route Handler 불가. 이 Task는 생략하고, `useDebouncedSuggestions`(Task 6)가 `searchSuggestions` RPC를 브라우저에서 직접 호출한다. `searchFonts`와 동일 패턴이라 일관. 아래 route.ts 절차는 참고용으로 남긴다.

**Files:**
- Create: `apps/web/app/api/suggest/route.ts`
- Test: `apps/web/app/api/suggest/route.test.ts`

**Interfaces:**
- Consumes: `searchSuggestions(q, 8)` (Task 4).
- Produces: `GET /api/suggest?q=...` → 200 `{ items: SearchResult[] }` (정상/빈), 503 `{ items: [] }` (오류).

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/app/api/suggest/route.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GET } from './route';
import * as search from '@/lib/db/search';

vi.mock('@/lib/db/search', () => ({
  searchSuggestions: vi.fn(),
}));

function req(q: string | null): Request {
  const url = q === null ? 'http://x/api/suggest' : `http://x/api/suggest?q=${encodeURIComponent(q)}`;
  return new Request(url);
}

describe('GET /api/suggest', () => {
  beforeEach(() => vi.clearAllMocks());

  it('정상: 200 + items', async () => {
    vi.mocked(search.searchSuggestions).mockResolvedValueOnce([
      { slug: 'gmarket-sans', nameKo: '지마켓 산스', nameEn: 'Gmarket Sans', tier: 'free', category: '고딕', foundry: 'G마켓', score: 45 },
    ] as never);
    const res = await GET(req('ㅈㅁㅋ'));
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.items).toHaveLength(1);
  });

  it('빈 쿼리: 200 + 빈 배열, RPC 미호출', async () => {
    const res = await GET(req(''));
    expect(res.status).toBe(200);
    expect((await res.json()).items).toEqual([]);
    expect(search.searchSuggestions).not.toHaveBeenCalled();
  });

  it('RPC 오류: 503 + 빈 배열', async () => {
    vi.mocked(search.searchSuggestions).mockRejectedValueOnce(new Error('SEARCH_RPC_FAILED'));
    const res = await GET(req('지마켓'));
    expect(res.status).toBe(503);
    expect((await res.json()).items).toEqual([]);
  });
});
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd apps/web && pnpm test app/api/suggest/route.test.ts`
Expected: FAIL — `Cannot find module './route'`

- [ ] **Step 3: 구현**

Create `apps/web/app/api/suggest/route.ts`:

```typescript
import { NextResponse } from 'next/server';
import { searchSuggestions } from '@/lib/db/search';

/** 자동완성 제안 상위 개수 */
const SUGGEST_LIMIT = 8;

/**
 * 검색어 자동완성 제안. 빈/과길이 입력은 200 빈 배열, RPC 오류는 503 빈 배열로 구분한다.
 * (503은 클라이언트가 드롭다운을 조용히 닫는 신호, 200 빈 배열은 "결과 없음")
 */
export async function GET(request: Request): Promise<Response> {
  const q = new URL(request.url).searchParams.get('q')?.trim() ?? '';
  if (!q) {
    return NextResponse.json({ items: [] }, { headers: { 'Cache-Control': 'no-store' } });
  }
  try {
    const items = await searchSuggestions(q, SUGGEST_LIMIT);
    return NextResponse.json({ items }, { headers: { 'Cache-Control': 'no-store' } });
  } catch {
    return NextResponse.json({ items: [] }, { status: 503, headers: { 'Cache-Control': 'no-store' } });
  }
}
```

> `searchSuggestions`가 과길이 입력을 자체적으로 빈 배열 처리하므로 라우트는 빈 문자열만 선차단한다.

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd apps/web && pnpm test app/api/suggest/route.test.ts`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add apps/web/app/api/suggest/route.ts apps/web/app/api/suggest/route.test.ts
git commit -m "feat: /api/suggest Route Handler (200/503 분리) (F-19)"
```

---

## Task 6: 디바운스 훅 `useDebouncedSuggestions`

**Files:**
- Create: `apps/web/hooks/useDebouncedSuggestions.ts`
- Test: `apps/web/hooks/useDebouncedSuggestions.test.ts`

**Interfaces:**
- Consumes: `GET /api/suggest` (Task 5) via `fetch`.
- Produces: `useDebouncedSuggestions(query: string, delayMs?: number): { items: SuggestItem[]; loading: boolean }`. `SuggestItem` = `/api/suggest` items 요소 타입.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/hooks/useDebouncedSuggestions.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useDebouncedSuggestions } from './useDebouncedSuggestions';

describe('useDebouncedSuggestions', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn());
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllMocks();
  });

  it('디바운스 시간 전에는 fetch하지 않는다', () => {
    renderHook(() => useDebouncedSuggestions('지마켓', 200));
    expect(fetch).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(100); });
    expect(fetch).not.toHaveBeenCalled();
  });

  it('디바운스 후 마지막 응답만 items로 반영한다', async () => {
    vi.mocked(fetch).mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ slug: 'gmarket-sans', nameKo: '지마켓 산스', nameEn: 'Gmarket Sans', tier: 'free', category: '고딕', foundry: 'G마켓', score: 45 }] }),
    } as never);

    const { result } = renderHook(() => useDebouncedSuggestions('ㅈㅁㅋ', 200));
    act(() => { vi.advanceTimersByTime(200); });
    await waitFor(() => expect(result.current.items).toHaveLength(1));
    expect(result.current.items[0].slug).toBe('gmarket-sans');
  });
});
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd apps/web && pnpm test hooks/useDebouncedSuggestions.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: 구현**

Create `apps/web/hooks/useDebouncedSuggestions.ts`:

```typescript
import { useEffect, useRef, useState } from 'react';

/** 자동완성 드롭다운 항목 (/api/suggest 응답 요소) */
export interface SuggestItem {
  slug: string;
  nameKo: string;
  nameEn: string;
  tier: 'free' | 'paid';
  category: string | null;
  foundry: string | null;
  score: number;
}

/** 기본 디바운스(ms) */
const DEFAULT_DELAY = 200;

/**
 * 입력값을 디바운스해 /api/suggest를 호출한다.
 * - 이전 요청은 AbortController로 취소
 * - 요청 시퀀스 번호로 늦게 온 응답은 무시(경쟁 조건 방어)
 * - 오류(503 포함)는 빈 목록으로 흡수해 드롭다운을 닫는다
 */
export function useDebouncedSuggestions(query: string, delayMs = DEFAULT_DELAY) {
  const [items, setItems] = useState<SuggestItem[]>([]);
  const [loading, setLoading] = useState(false);
  const seqRef = useRef(0);

  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setItems([]);
      setLoading(false);
      return;
    }

    const seq = ++seqRef.current;
    const controller = new AbortController();
    setLoading(true);

    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/suggest?q=${encodeURIComponent(q)}`, {
          signal: controller.signal,
        });
        if (seq !== seqRef.current) return; // 더 최신 요청이 있음
        if (!res.ok) {
          setItems([]);
          return;
        }
        const body = (await res.json()) as { items: SuggestItem[] };
        if (seq !== seqRef.current) return;
        setItems(body.items);
      } catch {
        if (seq === seqRef.current) setItems([]);
      } finally {
        if (seq === seqRef.current) setLoading(false);
      }
    }, delayMs);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, delayMs]);

  return { items, loading };
}
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd apps/web && pnpm test hooks/useDebouncedSuggestions.test.ts`
Expected: PASS

> `@testing-library/react`가 devDependencies에 없으면 추가: `pnpm add -D @testing-library/react`. 이미 컴포넌트 테스트가 있으므로 대개 존재.

- [ ] **Step 5: 커밋**

```bash
git add apps/web/hooks/useDebouncedSuggestions.ts apps/web/hooks/useDebouncedSuggestions.test.ts
git commit -m "feat: useDebouncedSuggestions 훅 (디바운스+취소+시퀀스) (F-19)"
```

---

## Task 7: 드롭다운 컴포넌트 `SearchSuggestions`

**Files:**
- Create: `apps/web/components/SearchSuggestions.tsx`
- Test: `apps/web/components/SearchSuggestions.test.tsx`

**Interfaces:**
- Consumes: `SuggestItem` (Task 6).
- Produces: `<SearchSuggestions items activeIndex query listboxId onSelect onHover />`. 표시명 직접 부분일치만 `<mark>` 강조.

- [ ] **Step 1: 실패 테스트 작성**

Create `apps/web/components/SearchSuggestions.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SearchSuggestions } from './SearchSuggestions';
import type { SuggestItem } from '@/hooks/useDebouncedSuggestions';

const item: SuggestItem = {
  slug: 'gmarket-sans', nameKo: '지마켓 산스', nameEn: 'Gmarket Sans',
  tier: 'free', category: '고딕', foundry: 'G마켓', score: 45,
};

describe('SearchSuggestions', () => {
  it('항목과 제작사를 렌더한다', () => {
    render(<SearchSuggestions items={[item]} activeIndex={-1} query="지마켓" listboxId="lb" onSelect={vi.fn()} onHover={vi.fn()} />);
    expect(screen.getByText(/산스/)).toBeInTheDocument();
    expect(screen.getByText('G마켓')).toBeInTheDocument();
  });

  it('표시명 직접일치 구간을 mark로 강조한다', () => {
    const { container } = render(<SearchSuggestions items={[item]} activeIndex={-1} query="지마켓" listboxId="lb" onSelect={vi.fn()} onHover={vi.fn()} />);
    const mark = container.querySelector('mark');
    expect(mark?.textContent).toBe('지마켓');
  });

  it('초성 입력(표시명에 없음)은 강조하지 않는다', () => {
    const { container } = render(<SearchSuggestions items={[item]} activeIndex={-1} query="ㅈㅁㅋ" listboxId="lb" onSelect={vi.fn()} onHover={vi.fn()} />);
    expect(container.querySelector('mark')).toBeNull();
  });

  it('클릭 시 onSelect(slug) 호출', () => {
    const onSelect = vi.fn();
    render(<SearchSuggestions items={[item]} activeIndex={-1} query="지마켓" listboxId="lb" onSelect={onSelect} onHover={vi.fn()} />);
    fireEvent.mouseDown(screen.getByRole('option'));
    expect(onSelect).toHaveBeenCalledWith('gmarket-sans');
  });
});
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd apps/web && pnpm test components/SearchSuggestions.test.tsx`
Expected: FAIL — module not found

- [ ] **Step 3: 구현**

Create `apps/web/components/SearchSuggestions.tsx`:

```tsx
import type { SuggestItem } from '@/hooks/useDebouncedSuggestions';

interface Props {
  items: SuggestItem[];
  activeIndex: number;
  query: string;
  listboxId: string;
  onSelect: (slug: string) => void;
  onHover: (index: number) => void;
}

/** 표시명에 검색어가 직접 부분일치하면 그 구간만 <mark>로 강조. 없으면 원문 그대로. */
function highlight(name: string, query: string) {
  const q = query.trim();
  if (!q) return name;
  const idx = name.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return name; // 별칭/오타/초성 매칭 → 강조 없음
  return (
    <>
      {name.slice(0, idx)}
      <mark>{name.slice(idx, idx + q.length)}</mark>
      {name.slice(idx + q.length)}
    </>
  );
}

/** 자동완성 제안 드롭다운. 접근성: role=listbox / option. */
export function SearchSuggestions({ items, activeIndex, query, listboxId, onSelect, onHover }: Props) {
  if (items.length === 0) return null;
  return (
    <ul id={listboxId} role="listbox" className="search-suggestions">
      {items.map((it, i) => {
        const name = it.nameKo || it.nameEn;
        return (
          <li
            key={it.slug}
            id={`${listboxId}-opt-${i}`}
            role="option"
            aria-selected={i === activeIndex}
            data-active={i === activeIndex}
            onMouseDown={(e) => {
              e.preventDefault(); // blur가 click보다 먼저 일어나 항목이 사라지는 것 방지
              onSelect(it.slug);
            }}
            onMouseEnter={() => onHover(i)}
          >
            <span className="ss-name">{highlight(name, query)}</span>
            {it.foundry && <span className="ss-foundry">{it.foundry}</span>}
            <span className="ss-tier" data-tier={it.tier}>{it.tier === 'free' ? '무료' : '유료'}</span>
          </li>
        );
      })}
    </ul>
  );
}
```

> 스타일(`.search-suggestions` 등)은 기존 컴포넌트의 CSS Modules 관례를 따른다. 별도 `.module.css`가 관례면 className을 모듈로 교체. 여기서는 최소 마크업만 규정.

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd apps/web && pnpm test components/SearchSuggestions.test.tsx`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/SearchSuggestions.tsx apps/web/components/SearchSuggestions.test.tsx
git commit -m "feat: SearchSuggestions 드롭다운 컴포넌트 (F-19)"
```

---

## Task 8: `HeaderSearch` 확장 (연동 + 키보드 + IME)

**Files:**
- Modify: `apps/web/components/HeaderSearch.tsx`
- Test: `apps/web/components/HeaderSearch.test.tsx`

**Interfaces:**
- Consumes: `useDebouncedSuggestions` (Task 6), `SearchSuggestions` (Task 7), `useRouter`(next/navigation).
- Produces: 헤더 검색바에 자동완성 드롭다운. Enter/방향키/ESC/IME/바깥클릭 동작.

- [ ] **Step 1: 실패 테스트 추가**

`apps/web/components/HeaderSearch.test.tsx`에 추가(기존 제출/ESC 테스트는 유지):

```tsx
// 상단 mock에 추가/보강
vi.mock('@/hooks/useDebouncedSuggestions', () => ({
  useDebouncedSuggestions: vi.fn(() => ({
    items: [
      { slug: 'gmarket-sans', nameKo: '지마켓 산스', nameEn: 'Gmarket Sans', tier: 'free', category: '고딕', foundry: 'G마켓', score: 45 },
    ],
    loading: false,
  })),
}));

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

// 새 테스트
it('↓ 후 Enter: 활성 항목 상세로 이동', async () => {
  render(<HeaderSearch />);
  const input = screen.getByRole('combobox');
  fireEvent.change(input, { target: { value: '지마켓' } });
  fireEvent.keyDown(input, { key: 'ArrowDown' });
  fireEvent.keyDown(input, { key: 'Enter' });
  expect(push).toHaveBeenCalledWith('/fonts/gmarket-sans');
});

it('한글 조합 중 Enter(isComposing)는 무시', () => {
  render(<HeaderSearch />);
  const input = screen.getByRole('combobox');
  fireEvent.change(input, { target: { value: '지마켓' } });
  fireEvent.keyDown(input, { key: 'ArrowDown' });
  fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
  expect(push).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd apps/web && pnpm test components/HeaderSearch.test.tsx`
Expected: FAIL — combobox/ArrowDown 동작 없음

- [ ] **Step 3: 구현**

`apps/web/components/HeaderSearch.tsx` 수정:
1. import 추가: `useRouter`(next/navigation), `useDebouncedSuggestions`, `SearchSuggestions`.
2. 상태: `const [activeIndex, setActiveIndex] = useState(-1);` `const [open, setOpen] = useState(false);` `const { items } = useDebouncedSuggestions(query);`
3. 입력에 ARIA + onKeyDown:

```tsx
const router = useRouter();
const listboxId = 'header-suggest-listbox';

function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
  if (e.nativeEvent.isComposing) return; // 한글 조합 중이면 방향키/Enter 무시
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    setActiveIndex((i) => Math.min(i + 1, items.length - 1));
    setOpen(true);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    setActiveIndex((i) => Math.max(i - 1, -1));
  } else if (e.key === 'Enter') {
    if (open && activeIndex >= 0 && items[activeIndex]) {
      e.preventDefault();
      router.push(`/fonts/${items[activeIndex].slug}`);
      setOpen(false);
    }
    // activeIndex<0 이면 기존 폼 제출(/search?q=) 그대로
  } else if (e.key === 'Escape') {
    setOpen(false);
    setActiveIndex(-1);
  }
}
```

4. 입력 요소에 속성:
```tsx
role="combobox"
aria-expanded={open && items.length > 0}
aria-controls={listboxId}
aria-autocomplete="list"
aria-activedescendant={activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined}
onKeyDown={onKeyDown}
onChange={(e) => { setQuery(e.target.value); setOpen(true); setActiveIndex(-1); }}
onBlur={() => setOpen(false)}
```

5. 입력 아래에 드롭다운:
```tsx
{open && (
  <SearchSuggestions
    items={items}
    activeIndex={activeIndex}
    query={query}
    listboxId={listboxId}
    onSelect={(slug) => { router.push(`/fonts/${slug}`); setOpen(false); }}
    onHover={setActiveIndex}
  />
)}
```

> 기존 제출 핸들러(`handleSubmit` → `/search?q=`)와 ESC 닫기 로직은 유지. 기존 테스트가 `getByRole('combobox')`로 입력을 못 찾으면 셀렉터를 맞춘다(기존 테스트는 placeholder/label 기반일 수 있음 — 회귀 깨지지 않게 조정).

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `cd apps/web && pnpm test components/HeaderSearch.test.tsx`
Expected: PASS (기존 제출/ESC 회귀 + 신규 키보드/IME)

- [ ] **Step 5: 커밋**

```bash
git add apps/web/components/HeaderSearch.tsx apps/web/components/HeaderSearch.test.tsx
git commit -m "feat: HeaderSearch 자동완성 드롭다운 연동 (키보드/IME) (F-19)"
```

---

## Task 9: 통합 검증 + 전체 스위트

**Files:** (없음 — 검증 전용)

- [ ] **Step 1: 웹 전체 테스트 + 빌드 + lint**

Run:
```bash
cd apps/web && pnpm test && pnpm lint && pnpm build
```
Expected: 전체 PASS, 빌드 성공(SSG out 생성). db env가 필요한 테스트는 메모리 `project-web-test-env-fragility` 유의(깨끗한 env로 실측).

- [ ] **Step 2: dev 실측(수동)**

`pnpm dev` 후 헤더 검색바에서 확인:
- "지마켓" 입력 → 드롭다운에 지마켓 산스 + 제작사, "지마켓" 강조.
- "ㅈㅁㅋ" 입력 → 지마켓 산스 제안, 강조 없음.
- 오타("지마켙") → trgm 매칭 제안.
- ↓/↑ 이동, Enter로 `/fonts/gmarket-sans` 이동, ESC 닫기.
- 한글 조합 중 Enter가 이동시키지 않음.

- [ ] **Step 3: 최종 커밋(없으면 생략) + 요약**

변경 없으면 커밋 생략. progress/PR은 별도 스킬로.

---

## Self-Review 결과

**Spec coverage:** 설계 5~11장 전부 태스크에 매핑 — to_chosung(T1), alias_chosung(T2), search_fonts 초성/lim/foundry/권한/pgrst(T3), 데이터 계층(T4), Route 200/503(T5), 디바운스+취소+시퀀스(T6), 드롭다운+하이라이트+ARIA(T7), 키보드/IME/mousedown(T8), 통합(T9). F-17 로그는 설계상 비범위(0건 안내만).

**Placeholder scan:** 코드 스텝 전부 실제 코드 포함. "기존 매핑 따름"류 주석은 구현 세부 정렬 지시이지 미완 placeholder 아님.

**Type consistency:** `SuggestItem`(T6)을 T7-T8이 그대로 소비. `SearchResult.foundry`(T4)와 RPC `foundry`(T3) 일치. `searchSuggestions(q, lim=8)` 시그니처가 T4→T5에서 동일. RPC 호출 인자 `{ q, lim }`가 T3 함수 시그니처(`q, lim`)와 일치.

**미해결(설계 14장 계승):** 초성 점수 45와 정확/부분 정렬 우선순위는 dev 실측(T9)에서 미세조정. dev slug가 `gmarket-sans`와 다르면 T3 테스트의 slug 교체.
