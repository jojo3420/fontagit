# 슬라이스3 — Top10 클릭 집계(F-03) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 공식 링크 이동 클릭을 익명 기록하고, 홈/트렌드 Top10을 실측 클릭 집계(`get_top_fonts` RPC)로 교체해 "이동 클릭 기준" 표기를 사실로 만든다.

**Architecture:** 마이그레이션 0007로 `font_clicks`(raw)/`font_click_daily`(롤업, 테이블만) + RPC 2개(`record_click`, `get_top_fonts`)를 만든다. anon은 원본 테이블 접근 불가, RPC로만 읽고 쓴다. 웹은 클릭 시 fire-and-forget 기록, Top10은 빌드타임 SSG가 RPC 조회하고 데이터 0건이면 "최신 등록" 폴백(UI 라벨도 전환).

**Tech Stack:** Postgres(Supabase, `fontagit` 스키마) + plpgsql SECURITY DEFINER RPC / Next.js SSG + @supabase/supabase-js(anon) / vitest + testing-library / psql SQL assert 테스트

## Global Constraints

- **prod DB 쓰기 금지** — dev(`zgxtfcpiokhkcrywlxmc`)만 사용.
- **네트워크 작업(psql, push, gh, pnpm add)은 메인 세션이 직접** — 서브에이전트 위임 금지. Task 2의 dev 적용/테스트 실행은 메인 담당.
- `git add`는 **명시 경로만** (`-A`/`.` 금지).
- **RPC-only 쓰기**: anon은 `font_clicks`/`font_click_daily` 직접 select/insert/update/delete 불가.
- **익명성**: `font_clicks`에 IP/사용자 식별자 컬럼 자체가 없어야 함 (기획서 7-2).
- **정직성(기획서 7-1)**: 클릭 랭킹 표기는 "이동 클릭 기준". 폴백 데이터에는 "이동 클릭 기준"/"인기" 라벨 금지 → "최신 등록"으로 전환.
- SECURITY DEFINER 함수는 `set search_path = fontagit, pg_temp` + public 확장 함수는 `public.fn()` 스키마 한정 호출 (0006 패턴, 세션 결정 5).
- anon 공개 RPC 입력은 서버측에서도 방어 (세션 결정 6).
- DB 테스트는 `supabase/tests/*.sql` psql assert 방식. dev 데이터 오염 금지 — 쓰기 테스트는 `begin; ... rollback;`으로 감싼다(파이프라인이 SSoT, 세션 결정 8).
- Next.js는 학습 데이터와 다른 버전 — 코드 작성 전 `apps/web/node_modules/next/dist/docs/` 확인 (`apps/web/AGENTS.md`).
- 커밋: `<타입>: <설명>` 컨벤셔널 형식.
- 웹 테스트/빌드: `apps/web`에서 `pnpm test`, `pnpm build` (SSG, out/ 산출).

## 파일 구조

| 파일 | 역할 | Task |
|------|------|------|
| Create `supabase/migrations/0007_font_clicks.sql` | 테이블 2 + RLS/revoke + RPC 2 + grant | 1 |
| Create `supabase/tests/font_clicks_test.sql` | SQL 통합 테스트 (psql assert, rollback 래핑) | 2 |
| Create `apps/web/lib/db/clicks.ts` + `clicks.test.ts` | `recordClick` fire-and-forget | 3 |
| Modify `apps/web/lib/db/trends.ts` + Create `trends.test.ts` | `getTrends`(RPC + 폴백) 신설 | 4 |
| Modify `apps/web/lib/data.ts` | 배럴에 `getTrends` 추가 | 4 |
| Create `apps/web/components/OfficialLinkCta.tsx` + `.test.tsx` | 클릭 기록하는 CTA 앵커 (client) | 5 |
| Modify `apps/web/components/LicenseSummaryCard.tsx` | CTA를 OfficialLinkCta로 교체 | 5 |
| Modify `apps/web/components/TrendRow.tsx`, `TrendRankRow.tsx` | `showMoves` prop (폴백 시 이동수 숨김) | 6 |
| Modify `apps/web/components/WeeklyRankPanel.tsx` | `source` prop + 라벨 전환 | 6 |
| Modify `apps/web/app/page.tsx`, `apps/web/app/trends/page.tsx` | `getTrends` 연결 + 라벨 전환 | 6 |
| Modify `apps/web/lib/db/trends.ts`, `lib/data.ts` | `getTemporaryTrends` 제거 | 6 |
| Modify 관련 `*.test.tsx` (`app/page.test.tsx`, `app/trends/page.test.tsx`) | 목/기대값 갱신 | 6 |

**설계 근거 (계획 확정 시 사용자 합의 대상):**
- `record_click(p_slug text)` — slug 기반. 웹 `Font` 타입에 DB uuid가 없고(mappers가 버림), RPC 내부 slug→id 해석이 존재+published 검증을 겸해 draft/임의 uuid 어뷰징을 차단한다. uuid 방식은 `Font` 타입/mappers/픽스처 전반 파급.
- CTA는 `target="_blank"`(새 탭) — 클릭 기록이 이동을 차단할 수 없으므로 스펙의 "timeout 후 window.location" 대신 단순 onClick fire-and-forget으로 충분.
- `getTrends`의 RPC **오류는 throw** → SSG 빌드 실패로 드러냄. 폴백은 "정상 응답 + 0건"일 때만(조용한 폴백은 정직성 위반 은폐).
- 랭킹 `change`는 당분간 `"new"` 고정 — 전주 비교 데이터가 없음(롤업 cron 후속).

---

### Task 1: 마이그레이션 0007 작성

**Files:**
- Create: `supabase/migrations/0007_font_clicks.sql`
- 참고 패턴: `supabase/migrations/0006_search_fonts.sql` (SECURITY DEFINER + search_path + revoke/grant)

**Interfaces:**
- Produces: `fontagit.record_click(p_slug text) returns void` — anon execute 가능, 비정상 입력/미존재/미공개 slug는 조용히 무시
- Produces: `fontagit.get_top_fonts(p_days int default 7, p_limit int default 10) returns table (slug text, name_ko text, name_en text, tier text, clicks bigint)` — published만, 최근 p_days일 클릭수 내림차순
- Produces: `fontagit.font_clicks`, `fontagit.font_click_daily` (anon 접근 불가)

- [ ] **Step 1: 마이그레이션 파일 작성**

```sql
-- 0007: Top10 클릭 집계 (F-03, 기획서 7장 / 스펙 슬라이스3)

-- 이동 클릭 이벤트 (익명 — IP/사용자 식별자 컬럼 자체가 없음, 기획서 7-2)
create table fontagit.font_clicks (
  id         uuid primary key default gen_random_uuid(),
  font_id    uuid not null references fontagit.fonts(id) on delete cascade,
  clicked_at timestamptz not null default now()
);

create index idx_font_clicks_font_time
  on fontagit.font_clicks (font_id, clicked_at);

-- get_top_fonts가 기간 필터를 선두 조건으로 쓰므로 별도 시간 인덱스
create index idx_font_clicks_time
  on fontagit.font_clicks (clicked_at);

-- 일별 롤업 — 테이블만 선행, 롤업 cron/보관정책은 후속 (기획서 7-3, 7-4)
create table fontagit.font_click_daily (
  font_id uuid not null references fontagit.fonts(id) on delete cascade,
  day     date not null,
  count   int  not null default 0,
  primary key (font_id, day)
);

-- anon/authenticated 직접 접근 차단 (RPC-only).
-- 0001의 grant는 기존 테이블에만 적용되지만 default privileges 가능성에 대비해 명시 revoke + RLS 이중 방어
revoke all on table fontagit.font_clicks from anon, authenticated;
revoke all on table fontagit.font_click_daily from anon, authenticated;
alter table fontagit.font_clicks enable row level security;
alter table fontagit.font_click_daily enable row level security;

-- 클릭 기록 RPC (anon 공개 — 서버측 방어 필수)
create or replace function fontagit.record_click(p_slug text)
returns void
language plpgsql
security definer
set search_path = fontagit, pg_temp
as $$
declare
  v_font_id uuid;
begin
  -- fire-and-forget 계약: 비정상 입력은 오류 대신 조용히 무시
  if p_slug is null or p_slug = '' or char_length(p_slug) > 200 then
    return;
  end if;

  select id into v_font_id
  from fonts
  where slug = p_slug and status = 'published';

  -- 미존재/미공개(draft) 폰트 클릭은 기록하지 않음 (어뷰징 차단)
  if v_font_id is null then
    return;
  end if;

  insert into font_clicks (font_id) values (v_font_id);
end;
$$;

revoke execute on function fontagit.record_click(text) from public;
grant execute on function fontagit.record_click(text) to anon;

comment on function fontagit.record_click(text) is
  '슬라이스3 공식 링크 이동 클릭 기록(익명). published slug만 기록, 그 외 조용히 무시. anon 공개 fire-and-forget RPC.';

-- Top10 조회 RPC (MVP: raw + 기간 쿼리 — 기획서 7-5, 롤업 전환은 후속)
create or replace function fontagit.get_top_fonts(p_days int default 7, p_limit int default 10)
returns table (
  slug text,
  name_ko text,
  name_en text,
  tier text,
  clicks bigint
)
language plpgsql
security definer
set search_path = fontagit, pg_temp
as $$
begin
  -- anon 공개 RPC 서버측 방어: 비정상 범위는 기본값으로 강제
  if p_days is null or p_days < 1 or p_days > 90 then
    p_days := 7;
  end if;
  if p_limit is null or p_limit < 1 or p_limit > 50 then
    p_limit := 10;
  end if;

  return query
  select
    f.slug,
    f.name_ko,
    f.name_en,
    case when f.is_commercial_free then 'free'::text else 'paid'::text end,
    count(*)::bigint
  from font_clicks c
  join fonts f on f.id = c.font_id
  where c.clicked_at >= now() - make_interval(days => p_days)
    and f.status = 'published'
  group by f.id
  order by count(*) desc, f.name_ko asc nulls last, f.slug asc
  limit p_limit;
end;
$$;

revoke execute on function fontagit.get_top_fonts(int, int) from public;
grant execute on function fontagit.get_top_fonts(int, int) to anon;

comment on function fontagit.get_top_fonts(int, int) is
  '슬라이스3 Top 폰트 랭킹(이동 클릭 기준). 최근 p_days일 raw 클릭 집계, published만, 최대 p_limit건.';
```

주의: `returns table`의 OUT 변수명과 테이블 컬럼명 충돌(plpgsql ambiguity)을 피하려고 쿼리 내 컬럼 참조는 전부 `f.`/`c.`로 한정했다. 수정 시에도 비한정 참조를 넣지 말 것.

- [ ] **Step 2: 문법 셀프 체크**

파일을 다시 읽어 확인: (1) 모든 테이블/함수가 `fontagit.` 접두사, (2) SECURITY DEFINER 함수 2개 모두 `set search_path = fontagit, pg_temp`, (3) revoke가 grant보다 먼저, (4) 비한정 컬럼 참조 없음. (실행 검증은 Task 2에서 dev 적용으로)

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0007_font_clicks.sql
git commit -m "feat: 0007 클릭 집계 테이블+RPC (record_click/get_top_fonts, anon 직접 접근 차단)"
```

---

### Task 2: dev 적용 + SQL 통합 테스트 — ⚠️ 메인 세션 직접 (psql 네트워크)

**Files:**
- Create: `supabase/tests/font_clicks_test.sql`
- 참고 패턴: `supabase/tests/search_fonts_test.sql` (do $$ assert 방식)

**Interfaces:**
- Consumes: Task 1의 0007 전체 (테이블/RPC/권한)
- Produces: dev에 0007 적용 완료 상태 (Task 4~6의 빌드타임 RPC 호출 전제)

접속: 비번=루트 `.env.sandbox`, region=`apps/pipeline/.env`의 `SUPABASE_PROJECT_REGION`, pooler `aws-0-{region}.pooler.supabase.com:5432`, user `postgres.zgxtfcpiokhkcrywlxmc`, db `postgres`. 아래 `$CONN`은 이 조합의 접속 문자열 (비밀번호를 파일/문서에 남기지 말 것).

- [ ] **Step 1: 테스트 파일 작성** (쓰기 흔적 방지: 전체를 `begin; ... rollback;`으로 래핑)

```sql
-- =============================================================================
-- font_clicks SQL 통합 테스트
-- 실행: psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/tests/font_clicks_test.sql
-- 전제: 0007 적용 완료, dev에 published 폰트 존재(noto-sans-kr)
-- 쓰기는 전부 이 트랜잭션 안에서만 발생하고 마지막에 rollback → dev 데이터 무오염
-- =============================================================================
begin;

-- C1: 익명성 — font_clicks 컬럼이 정확히 clicked_at/font_id/id (IP-식별자 컬럼 부재)
do $$
declare
  cols text;
begin
  select string_agg(column_name, ',' order by column_name) into cols
  from information_schema.columns
  where table_schema = 'fontagit' and table_name = 'font_clicks';
  if cols is distinct from 'clicked_at,font_id,id' then
    raise exception 'C1: font_clicks 컬럼 불일치(개인식별 컬럼 의심). got %', cols;
  end if;
end $$;

-- C2: record_click 정상 기록 (published slug)
do $$
declare
  before_n bigint;
  after_n bigint;
begin
  select count(*) into before_n from fontagit.font_clicks;
  perform fontagit.record_click('noto-sans-kr');
  select count(*) into after_n from fontagit.font_clicks;
  if after_n != before_n + 1 then
    raise exception 'C2: record_click 후 count 미증가. before=%, after=%', before_n, after_n;
  end if;
end $$;

-- C3: 미존재 slug → 오류 없이 무시, 기록 없음
do $$
declare
  before_n bigint;
  after_n bigint;
begin
  select count(*) into before_n from fontagit.font_clicks;
  perform fontagit.record_click('no-such-font-slug-xyz');
  perform fontagit.record_click('');
  perform fontagit.record_click(null);
  perform fontagit.record_click(repeat('a', 300));
  select count(*) into after_n from fontagit.font_clicks;
  if after_n != before_n then
    raise exception 'C3: 무효 slug가 기록됨. before=%, after=%', before_n, after_n;
  end if;
end $$;

-- C4: 미공개(draft) slug → 무시. rollback 트랜잭션 내 임시 update라 dev에 흔적 없음
do $$
declare
  v_slug text;
  before_n bigint;
  after_n bigint;
begin
  select f.slug into v_slug from fontagit.fonts f where f.status = 'published' limit 1;
  update fontagit.fonts set status = 'draft' where slug = v_slug;
  select count(*) into before_n from fontagit.font_clicks;
  perform fontagit.record_click(v_slug);
  select count(*) into after_n from fontagit.font_clicks;
  if after_n != before_n then
    raise exception 'C4: draft 폰트 클릭이 기록됨 (slug=%)', v_slug;
  end if;
  update fontagit.fonts set status = 'published' where slug = v_slug;
end $$;

-- C5: get_top_fonts 랭킹 반영 + 반환 계약 (클릭 많은 폰트가 상위)
do $$
declare
  top_row record;
  n int;
begin
  perform fontagit.record_click('noto-sans-kr');
  perform fontagit.record_click('noto-sans-kr');
  perform fontagit.record_click('noto-sans-kr');

  select * into top_row from fontagit.get_top_fonts() limit 1;
  if top_row.slug is null or top_row.clicks < 3 then
    raise exception 'C5: get_top_fonts 상위 결과 이상. slug=%, clicks=%', top_row.slug, top_row.clicks;
  end if;
  if top_row.tier not in ('free', 'paid') then
    raise exception 'C5: tier 값 계약 위반. got %', top_row.tier;
  end if;

  select count(*) into n from fontagit.get_top_fonts(7, 10);
  if n > 10 then
    raise exception 'C5: limit 초과. got %건', n;
  end if;
end $$;

-- C6: 권한 경계 — anon은 원본 테이블 직접 접근 불가, RPC는 실행 가능
do $$
declare
  denied boolean := false;
  dummy bigint;
begin
  execute 'set local role anon';

  begin
    select count(*) into dummy from fontagit.font_clicks;
  exception when insufficient_privilege then
    denied := true;
  end;
  if not denied then
    execute 'reset role';
    raise exception 'C6: anon이 font_clicks를 직접 select 가능 (권한 경계 실패)';
  end if;

  denied := false;
  begin
    insert into fontagit.font_clicks (font_id) select id from fontagit.fonts limit 1;
  exception when insufficient_privilege then
    denied := true;
  end;
  if not denied then
    execute 'reset role';
    raise exception 'C6: anon이 font_clicks에 직접 insert 가능 (권한 경계 실패)';
  end if;

  denied := false;
  begin
    select count(*) into dummy from fontagit.font_click_daily;
  exception when insufficient_privilege then
    denied := true;
  end;
  if not denied then
    execute 'reset role';
    raise exception 'C6: anon이 font_click_daily를 직접 select 가능 (권한 경계 실패)';
  end if;

  -- anon으로 RPC는 정상 실행되어야 함
  perform fontagit.record_click('noto-sans-kr');
  select count(*) into dummy from fontagit.get_top_fonts();

  execute 'reset role';
end $$;

-- C7: get_top_fonts 이상 파라미터 방어 (오류 없이 기본값 동작)
do $$
declare
  n int;
begin
  select count(*) into n from fontagit.get_top_fonts(-1, 99999);
  if n > 50 then
    raise exception 'C7: 파라미터 방어 실패. got %건', n;
  end if;
  select count(*) into n from fontagit.get_top_fonts(null, null);
end $$;

select 'font_clicks_test: ALL PASS' as result;

rollback;
```

- [ ] **Step 2: dev에 0007 적용 (메인 psql 직접)**

```bash
psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/migrations/0007_font_clicks.sql
```
Expected: CREATE TABLE x2, CREATE INDEX x2, REVOKE/ALTER/CREATE FUNCTION/GRANT, 오류 0

- [ ] **Step 3: 테스트 실행**

```bash
psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/tests/font_clicks_test.sql
```
Expected: `font_clicks_test: ALL PASS` + `ROLLBACK`. 실패 시 `C{n}:` 접두 예외 메시지로 원인 특정 → 0007 수정 시 dev에서 `drop function`/`drop table` 후 재적용이 아니라, `create or replace function`으로 함수만 교체 가능(테이블 변경은 별도 판단).

- [ ] **Step 4: 쓰기 흔적 없음 확인**

```bash
psql "$CONN" -Atc "select count(*) from fontagit.font_clicks"
```
Expected: `0` (rollback으로 테스트 클릭 미잔존)

- [ ] **Step 5: Commit**

```bash
git add supabase/tests/font_clicks_test.sql
git commit -m "test: font_clicks SQL 통합 테스트 (익명성/권한 경계/랭킹 계약, rollback 래핑)"
```

---

### Task 3: `recordClick` fire-and-forget (`lib/db/clicks.ts`)

**Files:**
- Create: `apps/web/lib/db/clicks.ts`
- Test: `apps/web/lib/db/clicks.test.ts`
- 참고 패턴: `apps/web/lib/db/search.ts`(RPC 호출), `apps/web/lib/db/search.test.ts`(supabaseClient 모킹)

**Interfaces:**
- Consumes: `supabaseClient` (`./client`), DB RPC `record_click(p_slug text)`
- Produces: `recordClick(slug: string): void` — 어떤 경우에도 throw하지 않음 (Task 5가 onClick에서 사용)

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";

const rpcMock = vi.fn();
vi.mock("./client", () => ({
  supabaseClient: { rpc: (...args: unknown[]) => rpcMock(...args) },
}));

import { recordClick } from "./clicks";

describe("recordClick", () => {
  beforeEach(() => {
    rpcMock.mockReset();
  });

  it("record_click RPC를 p_slug로 호출한다", () => {
    rpcMock.mockResolvedValue({ data: null, error: null });
    recordClick("noto-sans-kr");
    expect(rpcMock).toHaveBeenCalledWith("record_click", { p_slug: "noto-sans-kr" });
  });

  it("RPC 오류가 나도 throw하지 않는다 (fire-and-forget)", async () => {
    rpcMock.mockResolvedValue({ data: null, error: { message: "boom" } });
    expect(() => recordClick("noto-sans-kr")).not.toThrow();
    await vi.waitFor(() => expect(rpcMock).toHaveBeenCalled());
  });

  it("RPC reject(네트워크 예외)여도 unhandled rejection 없이 삼킨다", async () => {
    rpcMock.mockRejectedValue(new Error("network down"));
    expect(() => recordClick("noto-sans-kr")).not.toThrow();
    await vi.waitFor(() => expect(rpcMock).toHaveBeenCalled());
  });

  it("빈 slug는 RPC를 호출하지 않는다", () => {
    recordClick("");
    expect(rpcMock).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run lib/db/clicks.test.ts`
Expected: FAIL — `clicks.ts` 모듈 없음

- [ ] **Step 3: 구현**

```ts
import { supabaseClient } from "./client";

/**
 * 공식 링크 이동 클릭 기록 (fire-and-forget, 스펙 슬라이스3).
 * 실패/지연이 페이지 이동을 막으면 안 되므로 아무것도 반환하지 않고 오류를 삼킨다.
 */
export function recordClick(slug: string): void {
  if (!slug) {
    return;
  }

  void Promise.resolve(supabaseClient.rpc("record_click", { p_slug: slug }))
    .then(({ error }) => {
      if (error) {
        console.error("[clicks] record_click failed:", error);
      }
    })
    .catch((err: unknown) => {
      console.error("[clicks] record_click failed:", err);
    });
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run lib/db/clicks.test.ts`
Expected: PASS 4건

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/db/clicks.ts apps/web/lib/db/clicks.test.ts
git commit -m "feat: recordClick fire-and-forget 클릭 기록 (record_click RPC)"
```

---

### Task 4: `getTrends` — 빌드타임 랭킹 + 최신 등록 폴백 (`lib/db/trends.ts`)

**Files:**
- Modify: `apps/web/lib/db/trends.ts` (`getTemporaryTrends`는 이 Task에서 유지 — 홈/트렌드가 아직 사용 중, 제거는 Task 6)
- Modify: `apps/web/lib/data.ts` (배럴에 `getTrends`, `TrendsResult` 추가)
- Test: `apps/web/lib/db/trends.test.ts` (신규)

**Interfaces:**
- Consumes: `supabaseClient.rpc("get_top_fonts", {})` → `{ slug, name_ko, name_en, tier, clicks }[]`, `getAllFonts()` (`./fonts`)
- Produces: `getTrends(): Promise<TrendsResult>`, `interface TrendsResult { source: "clicks" | "latest"; items: TrendItem[] }` — Task 6이 페이지에서 사용

- [ ] **Step 1: 실패하는 테스트 작성**

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import type { Font } from "@/types/font";

const rpcMock = vi.fn();
vi.mock("./client", () => ({
  supabaseClient: { rpc: (...args: unknown[]) => rpcMock(...args) },
}));

const getAllFontsMock = vi.fn();
vi.mock("./fonts", () => ({
  getAllFonts: () => getAllFontsMock(),
}));

import { getTrends } from "./trends";

const rpcRow = {
  slug: "noto-sans-kr",
  name_ko: "본고딕",
  name_en: "Noto Sans KR",
  tier: "free",
  clicks: 42,
};

const fallbackFont: Partial<Font> = {
  slug: "latest-font",
  nameKo: "최신폰트",
  fontKey: null,
  tier: "free",
  moves: 0,
};

describe("getTrends", () => {
  beforeEach(() => {
    rpcMock.mockReset();
    getAllFontsMock.mockReset();
  });

  it("클릭 데이터가 있으면 source=clicks로 TrendItem 매핑", async () => {
    rpcMock.mockResolvedValue({ data: [rpcRow], error: null });
    const result = await getTrends();
    expect(result.source).toBe("clicks");
    expect(result.items[0]).toEqual({
      rank: 1,
      change: "new",
      font: { slug: "noto-sans-kr", nameKo: "본고딕", fontKey: null, tier: "free" },
      moves: 42,
    });
    expect(getAllFontsMock).not.toHaveBeenCalled();
  });

  it("name_ko가 null이면 name_en으로 대체", async () => {
    rpcMock.mockResolvedValue({ data: [{ ...rpcRow, name_ko: null }], error: null });
    const result = await getTrends();
    expect(result.items[0].font.nameKo).toBe("Noto Sans KR");
  });

  it("0건이면 source=latest 폴백 (최신 등록 상위 10)", async () => {
    rpcMock.mockResolvedValue({ data: [], error: null });
    getAllFontsMock.mockResolvedValue(
      Array.from({ length: 12 }, (_, i) => ({ ...fallbackFont, slug: `f-${i}` }))
    );
    const result = await getTrends();
    expect(result.source).toBe("latest");
    expect(result.items).toHaveLength(10);
    expect(result.items[0].rank).toBe(1);
  });

  it("RPC 오류면 throw (조용한 폴백 금지 — 빌드 실패로 드러냄)", async () => {
    rpcMock.mockResolvedValue({ data: null, error: { message: "boom" } });
    await expect(getTrends()).rejects.toThrow("TRENDS_RPC_FAILED");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run lib/db/trends.test.ts`
Expected: FAIL — `getTrends` export 없음

- [ ] **Step 3: 구현** — `trends.ts`를 아래로 교체(기존 `getTemporaryTrends`는 파일 하단에 그대로 유지)

```ts
import type { TrendItem } from "@/types/font";
import { supabaseClient } from "./client";
import { getAllFonts } from "./fonts";

export type TrendsSource = "clicks" | "latest";

export interface TrendsResult {
  source: TrendsSource;
  items: TrendItem[];
}

interface RPCTopFontRow {
  slug: string;
  name_ko: string | null;
  name_en: string;
  tier: "free" | "paid";
  clicks: number;
}

/**
 * 빌드타임 Top10 (이동 클릭 기준, get_top_fonts RPC — 기획서 7-4).
 * 클릭 데이터 0건이면 "최신 등록" 폴백(source='latest') — UI 라벨도 함께 전환해야 정직성 유지.
 * RPC 오류는 throw해 SSG 빌드 실패로 드러낸다(조용한 폴백 금지).
 */
export async function getTrends(): Promise<TrendsResult> {
  const { data, error } = await supabaseClient.rpc("get_top_fonts", {});

  if (error) {
    console.error("[trends] get_top_fonts RPC error:", error);
    const err = new Error("TRENDS_RPC_FAILED");
    err.cause = error;
    throw err;
  }

  const rows = (data ?? []) as RPCTopFontRow[];
  if (rows.length === 0) {
    return { source: "latest", items: await getLatestFallback() };
  }

  return {
    source: "clicks",
    items: rows.map((row, index): TrendItem => ({
      rank: index + 1,
      // 전주 비교 데이터가 아직 없어 변동 표기는 전부 "new" (롤업 도입 후 개선)
      change: "new",
      font: {
        slug: row.slug,
        nameKo: row.name_ko ?? row.name_en,
        fontKey: null,
        tier: row.tier,
      },
      moves: row.clicks,
    })),
  };
}

async function getLatestFallback(): Promise<TrendItem[]> {
  const fonts = await getAllFonts();
  return fonts.slice(0, 10).map((font, index): TrendItem => ({
    rank: index + 1,
    change: "new",
    font: {
      slug: font.slug,
      nameKo: font.nameKo,
      fontKey: font.fontKey,
      tier: font.tier,
    },
    moves: font.moves,
  }));
}
```

`lib/data.ts`에 추가:

```ts
export { getTrends } from "./db/trends";
export type { TrendsResult, TrendsSource } from "./db/trends";
```

- [ ] **Step 4: 통과 확인 (기존 스위트 포함)**

Run: `cd apps/web && pnpm vitest run lib/db/trends.test.ts && pnpm test`
Expected: 신규 4건 PASS + 기존 전체 그린 (`getTemporaryTrends` 유지라 홈/트렌드 테스트 무영향)

- [ ] **Step 5: Commit**

```bash
git add apps/web/lib/db/trends.ts apps/web/lib/db/trends.test.ts apps/web/lib/data.ts
git commit -m "feat: getTrends 빌드타임 클릭 랭킹 + 최신 등록 폴백 (get_top_fonts RPC)"
```

---

### Task 5: OfficialLinkCta — 클릭 기록하는 공식 링크 (client component)

**Files:**
- Create: `apps/web/components/OfficialLinkCta.tsx`
- Modify: `apps/web/components/LicenseSummaryCard.tsx` (CTA `<a>` 교체)
- Test: `apps/web/components/OfficialLinkCta.test.tsx`
- 참고: 기존 컴포넌트 테스트 패턴 `apps/web/components/TrendRankRow.test.tsx`

**Interfaces:**
- Consumes: `recordClick(slug)` (Task 3)
- Produces: `OfficialLinkCta({ slug, href, className, children })` — `target="_blank"` 앵커 + onClick 기록

새 탭(`target="_blank"`) 이동이라 클릭 기록이 네비게이션을 차단할 수 없음 → 스펙의 "timeout 후 window.location 이동"은 불필요, 단순 onClick fire-and-forget으로 충분.

- [ ] **Step 1: 실패하는 테스트 작성**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const recordClickMock = vi.fn();
vi.mock("@/lib/db/clicks", () => ({
  recordClick: (slug: string) => recordClickMock(slug),
}));

import { OfficialLinkCta } from "./OfficialLinkCta";

describe("OfficialLinkCta", () => {
  beforeEach(() => {
    recordClickMock.mockReset();
  });

  it("href/target/rel을 유지한 앵커를 렌더한다", () => {
    render(
      <OfficialLinkCta slug="noto-sans-kr" href="https://example.com" className="cta">
        공식 페이지에서 내려받기
      </OfficialLinkCta>
    );
    const link = screen.getByRole("link", { name: "공식 페이지에서 내려받기" });
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("클릭 시 recordClick(slug)을 호출한다 (이동 차단 없음)", () => {
    render(
      <OfficialLinkCta slug="noto-sans-kr" href="https://example.com" className="cta">
        이동
      </OfficialLinkCta>
    );
    fireEvent.click(screen.getByRole("link", { name: "이동" }));
    expect(recordClickMock).toHaveBeenCalledWith("noto-sans-kr");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run components/OfficialLinkCta.test.tsx`
Expected: FAIL — 모듈 없음

- [ ] **Step 3: 구현**

```tsx
"use client";

import type { ReactNode } from "react";
import { recordClick } from "@/lib/db/clicks";

interface Props {
  slug: string;
  href: string;
  className: string;
  children: ReactNode;
}

/** 공식 페이지 이동 CTA. 클릭을 fire-and-forget 기록하고 새 탭 이동은 절대 차단하지 않는다 */
export function OfficialLinkCta({ slug, href, className, children }: Props) {
  return (
    <a
      className={className}
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={() => recordClick(slug)}
    >
      {children}
    </a>
  );
}
```

`LicenseSummaryCard.tsx`의 기존 CTA(40~43행):

```tsx
<a className={styles.cta} href={font.officialUrl} target="_blank" rel="noreferrer">
  <span>{ctaLabel}</span>
  {price && <span className={styles.price}>{price}</span>}
</a>
```

를 아래로 교체(+상단 `import { OfficialLinkCta } from "./OfficialLinkCta";`):

```tsx
<OfficialLinkCta slug={font.slug} href={font.officialUrl} className={styles.cta}>
  <span>{ctaLabel}</span>
  {price && <span className={styles.price}>{price}</span>}
</OfficialLinkCta>
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run components/OfficialLinkCta.test.tsx && pnpm test`
Expected: 신규 2건 PASS + 기존 전체 그린 (상세 페이지 테스트에 CTA 관련 기대가 있으면 마크업 동일해 통과 유지)

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/OfficialLinkCta.tsx apps/web/components/OfficialLinkCta.test.tsx apps/web/components/LicenseSummaryCard.tsx
git commit -m "feat: 공식 링크 CTA 클릭 기록 (OfficialLinkCta, fire-and-forget)"
```

---

### Task 6: 홈/트렌드 페이지 연결 + 폴백 라벨 전환 + `getTemporaryTrends` 제거

**Files:**
- Modify: `apps/web/app/page.tsx`, `apps/web/app/trends/page.tsx`
- Modify: `apps/web/components/WeeklyRankPanel.tsx`, `apps/web/components/TrendRow.tsx`, `apps/web/components/TrendRankRow.tsx`
- Modify: `apps/web/lib/db/trends.ts`(getTemporaryTrends 삭제), `apps/web/lib/data.ts`(수출 제거)
- Test: `apps/web/app/page.test.tsx`, `apps/web/app/trends/page.test.tsx`(목 갱신), `apps/web/components/WeeklyRankPanel.test.tsx`(있으면 갱신, 없으면 라벨 전환 테스트 신설)

**Interfaces:**
- Consumes: `getTrends(): Promise<TrendsResult>` (Task 4)
- Produces: `WeeklyRankPanel({ items, source })`, `TrendRow({ item, showMoves? })`, `TrendRankRow({ item, showMoves? })` (`showMoves` 기본 true)

라벨 확정(정직성 — 폴백에 "인기"/"이동 클릭" 라벨 금지):

| 위치 | source="clicks" | source="latest" |
|------|-----------------|-----------------|
| 홈 패널 title | 이번 주 인기 TOP 10 | 최신 등록 TOP 10 |
| 홈 패널 hint | 이동 클릭 기준 - 매주 갱신 (기존 유지) | 최근 등록순 - 클릭 데이터 수집 중 |
| 트렌드 h1 | 이번 주 인기 폰트 | 최신 등록 폰트 |
| 트렌드 lead | 이동 클릭 기준 인기 순위입니다 (다운로드 순위 아님). (기존 유지) | 클릭 데이터가 쌓이면 이동 클릭 기준 인기 순위로 전환됩니다. |
| 행 "이동 N회"/"N 이동" | 표시 | 숨김(showMoves=false — "이동 0회" 오표기 방지) |

- [ ] **Step 1: 실패하는 테스트 갱신/작성**

`app/trends/page.test.tsx`, `app/page.test.tsx`의 목을 `getTemporaryTrends` → `getTrends`로 교체하고 라벨 전환 케이스 추가. 예 (trends 페이지):

```tsx
const getTrendsMock = vi.fn();
vi.mock("@/lib/data", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  getTrends: () => getTrendsMock(),
}));

it("clicks 소스면 인기 라벨과 이동수를 보여준다", async () => {
  getTrendsMock.mockResolvedValue({ source: "clicks", items: mockTrends });
  render(await TrendsPage());
  expect(screen.getByText("이번 주 인기 폰트")).toBeInTheDocument();
});

it("latest 폴백이면 최신 등록 라벨로 전환하고 이동수를 숨긴다", async () => {
  getTrendsMock.mockResolvedValue({ source: "latest", items: mockTrends });
  render(await TrendsPage());
  expect(screen.getByText("최신 등록 폰트")).toBeInTheDocument();
  expect(screen.queryByText(/이동/)).not.toBeInTheDocument();
});
```

(기존 목 데이터 `mockTrends`는 파일 내 기존 정의 재사용. 홈 테스트도 동일 요령 — "최신 등록 TOP 10" 기대.)

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run app/page.test.tsx app/trends/page.test.tsx`
Expected: FAIL — `getTrends` 미사용/라벨 미전환

- [ ] **Step 3: 구현**

`TrendRow.tsx` — moves 스팬을 조건부로:

```tsx
export function TrendRow({ item, showMoves = true }: { item: TrendItem; showMoves?: boolean }) {
  // ...기존 마크업 동일, 아래 스팬만 교체
  {showMoves && (
    <span className={styles.moves}>이동 {item.moves.toLocaleString()}회</span>
  )}
}
```

`TrendRankRow.tsx` — 동일 요령 (`showMoves = true` 기본, 클릭수 블록 `styles.clicks` 조건부).

`WeeklyRankPanel.tsx`:

```tsx
import type { TrendsSource } from "@/lib/data";

export function WeeklyRankPanel({ items, source }: { items: TrendItem[]; source: TrendsSource }) {
  const isClicks = source === "clicks";
  return (
    <aside className={styles.panel}>
      <div className={styles.head}>
        <div>
          <h2 className={styles.title}>{isClicks ? "이번 주 인기 TOP 10" : "최신 등록 TOP 10"}</h2>
          <p className={styles.hint}>
            {isClicks
              ? <>이동 클릭 기준 {String.fromCharCode(183)} 매주 갱신</>
              : <>최근 등록순 {String.fromCharCode(183)} 클릭 데이터 수집 중</>}
          </p>
        </div>
        <Link href="/trends" className={styles.all}>전체 →</Link>
      </div>
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.rank}>
            <TrendRow item={item} showMoves={isClicks} />
          </li>
        ))}
      </ul>
    </aside>
  );
}
```

`app/page.tsx`:

```tsx
const { source, items } = await getTrends();
// <WeeklyRankPanel items={items} source={source} />
```

`app/trends/page.tsx`:

```tsx
export default async function TrendsPage() {
  const { source, items } = await getTrends();
  const isClicks = source === "clicks";
  return (
    <main className={styles.main}>
      <div className={styles.head}>
        <h1 className={styles.h1}>{isClicks ? "이번 주 인기 폰트" : "최신 등록 폰트"}</h1>
        <p className={styles.lead}>
          {isClicks
            ? "이동 클릭 기준 인기 순위입니다 (다운로드 순위 아님)."
            : "클릭 데이터가 쌓이면 이동 클릭 기준 인기 순위로 전환됩니다."}
        </p>
        {/* FilterChip 주간/월간은 현행 유지 (스코프 외) */}
        ...
        {items.map((item) => (
          <li key={item.rank}>
            <TrendRankRow item={item} showMoves={isClicks} />
          </li>
        ))}
```

마지막으로 `lib/db/trends.ts`에서 `getTemporaryTrends` 함수와 임시 주석 블록 삭제, `lib/data.ts`에서 해당 수출 제거. `grep -rn "getTemporaryTrends" apps/web`이 0건이어야 함.

- [ ] **Step 4: 전체 검증 (테스트 + SSG 빌드)**

Run: `cd apps/web && pnpm test && pnpm build`
Expected: 전체 그린 + SSG 빌드 성공(빌드 로그에 홈/트렌드 정적 생성). 빌드는 dev DB `get_top_fonts`를 실제 호출 — 현재 클릭 0건이므로 폴백(source=latest) 경로로 생성됨이 정상.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app/page.tsx apps/web/app/trends/page.tsx apps/web/app/page.test.tsx apps/web/app/trends/page.test.tsx apps/web/components/WeeklyRankPanel.tsx apps/web/components/TrendRow.tsx apps/web/components/TrendRankRow.tsx apps/web/lib/db/trends.ts apps/web/lib/data.ts
git commit -m "feat: 홈/트렌드 Top10 실측 클릭 랭킹 연결 + 최신 등록 폴백 라벨 (정직성 게이트 해소)"
```

(WeeklyRankPanel 라벨 테스트를 신설했다면 해당 파일도 `git add`에 명시 추가)

---

## 완료 기준 (스펙 슬라이스3 대조)

- [ ] 클릭 기록 동작: CTA 클릭 → `record_click` → dev `font_clicks` 증가 (SQL 테스트 C2 + 수동 확인)
- [ ] 랭킹 조회 동작: `get_top_fonts` 계약 (C5) + 홈/트렌드 SSG 연동
- [ ] 원본 테이블 anon 미노출 (C6)
- [ ] 개인식별정보 미저장 (C1 — 컬럼 부재 검증)
- [ ] 데이터 0건 폴백 + 라벨 전환 (트렌드/홈 테스트)
- [ ] `pnpm test` 전체 그린 + `pnpm build` SSG 성공
- [ ] 정직성 게이트: 폴백 상태에서 "인기"/"이동 클릭" 라벨이 남지 않음
