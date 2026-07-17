# 클릭 rate limiting 구현 계획 (슬라이스3 후속)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 슬라이스3 클릭 집계 `record_click` RPC의 어뷰징을 2계층(Kong IP 제한 + DB 함수 최후방어)으로 막되, 이 세션은 DB 함수 계층(B)을 마이그레이션 0008로 구현하고 Kong 계층(A)은 설계 문서로 인계한다.

**Architecture:** `record_click`을 `create or replace`로 교체해 폰트별 슬라이딩 윈도우 상한(10초 20건)과 동시성 직렬화(`pg_advisory_xact_lock`)를 추가한다. 새 SQL 통합 테스트로 경계/시간창/독립성/회귀/동시성-정적을 검증하고, dev에 psql로 적용해 실측한다. Kong 계층은 코드 작업 없이 설계 문서 5장이 산출물이다.

**Tech Stack:** Postgres(Supabase, `fontagit` 스키마) + plpgsql SECURITY DEFINER RPC / psql SQL assert 테스트(`begin; ... rollback;` 래핑).

## Global Constraints

- 스키마는 `fontagit`. RPC는 `security definer` + `set search_path = fontagit, pg_temp` (0007과 동일).
- **0007은 dev 적용 완료 → 절대 수정 금지.** rate limit은 신규 파일 `supabase/migrations/0008_record_click_rate_limit.sql`로.
- **네트워크 작업(psql, git push, gh)은 메인 세션이 직접 수행 — 서브에이전트 위임 금지.** dev 적용/테스트 실행은 메인 담당.
- **prod 쓰기 금지.** Kong(A) 계층은 이 세션에서 적용하지 않고 설계 문서(`docs/superpowers/specs/2026-07-17-click-rate-limiting-design.md` 5장)로 인계.
- **`git add`는 명시된 경로만.** `git add -A`/`git add .` 금지.
- SQL 테스트는 전체를 `begin; ... rollback;`으로 감싸 dev 데이터를 오염시키지 않는다.
- 임계값(설계 4.2): `c_max = 20`, `c_window = interval '10 seconds'`. 함수 상단 `declare` 상수로 명명(매직넘버 회피).
- 커밋 형식: `<타입>: <설명>` (어트리뷰션 비활성).
- 접속 문자열 `$CONN` 구성: 비번=루트 `.env.sandbox`, region=`apps/pipeline/.env`의 `SUPABASE_PROJECT_REGION`, pooler `aws-0-{region}.pooler.supabase.com:5432`, user `postgres.zgxtfcpiokhkcrywlxmc`, db `postgres`. **비밀번호를 파일/문서/로그에 남기지 말 것.**

---

## 참고: Kong(A) 계층은 코드 태스크 없음

A 계층(Kong IP 제한, IP당 분당 30건)은 자체호스팅 prod 앞단 인프라 작업이라 이 세션 범위 밖이다. 산출물은 설계 문서 5장(개념/스니펫/적용 절차/미확인 사항/M2-M3 경고)이며, 실제 적용-검증은 사용자가 prod 배포 트랙에서 수행한다. 아래 태스크는 모두 B 계층이다.

---

### Task 1: 마이그레이션 0008 — `record_click` rate limit 교체

**Files:**
- Create: `supabase/migrations/0008_record_click_rate_limit.sql`
- 참고 패턴: `supabase/migrations/0007_font_clicks.sql`(원본 `record_click` 정의/권한 문)

**Interfaces:**
- Consumes: 0007의 `fontagit.font_clicks`, `fontagit.fonts`, 인덱스 `idx_font_clicks_font_time (font_id, clicked_at)`.
- Produces: `fontagit.record_click(p_slug text) returns void` — 시그니처는 0007과 동일(호출부 무변경). 내부에 advisory lock + 폰트별 10초 20건 상한 추가. Task 2가 이 함수를 검증.

- [ ] **Step 1: 마이그레이션 파일 작성**

`supabase/migrations/0008_record_click_rate_limit.sql`:

```sql
-- 0008: record_click 폰트별 rate limit (슬라이스3 후속, 2차 DB 최후방어)
-- 0007의 record_click을 교체. 시그니처 동일(호출부 무변경).
-- 추가: (1) 동시성 직렬화(advisory lock) (2) 폰트별 슬라이딩 윈도우 상한.
create or replace function fontagit.record_click(p_slug text)
returns void
language plpgsql
security definer
set search_path = fontagit, pg_temp
as $$
declare
  v_font_id uuid;
  c_window  constant interval := interval '10 seconds';  -- 슬라이딩 윈도우
  c_max     constant int      := 20;                     -- 윈도우 내 폰트별 상한
  v_recent  int;
begin
  -- fire-and-forget 계약: 비정상 입력은 오류 대신 조용히 무시 (0007과 동일)
  if p_slug is null or p_slug = '' or char_length(p_slug) > 200 then
    return;
  end if;

  select id into v_font_id
  from fonts
  where slug = p_slug and status = 'published';

  -- 미존재/미공개(draft) 폰트 클릭은 기록하지 않음 (0007과 동일)
  if v_font_id is null then
    return;
  end if;

  -- race 제거(M1): 같은 폰트 동시 요청을 트랜잭션 단위로 직렬화 → count 후 insert의 TOCTOU 차단.
  -- hashtext/pg_advisory_xact_lock은 pg_catalog 함수라 search_path 무관. 다른 폰트는 다른 락값이라 병렬 유지.
  perform pg_advisory_xact_lock(hashtext(p_slug));

  -- 2차 안전밸브: 폰트별 최근 윈도우 삽입량이 상한 이상이면 조용히 무시
  select count(*) into v_recent
  from font_clicks
  where font_id = v_font_id
    and clicked_at >= now() - c_window;

  if v_recent >= c_max then
    return;
  end if;

  insert into font_clicks (font_id) values (v_font_id);
end;
$$;

-- 권한 재확인(0007과 동일 — create or replace가 grant를 보존하지만 재현성 위해 명시)
revoke execute on function fontagit.record_click(text) from public;
grant execute on function fontagit.record_click(text) to anon;

comment on function fontagit.record_click(text) is
  '슬라이스3 클릭 기록(익명). published slug만 기록. 폰트별 10초 20건 상한 + advisory lock 직렬화(0008 후속). anon 공개 fire-and-forget RPC.';
```

- [ ] **Step 2: 문법 정적 확인 (파일만, 적용은 Task 2)**

Run: `grep -c "perform pg_advisory_xact_lock" supabase/migrations/0008_record_click_rate_limit.sql`
Expected: `1` (advisory lock 실제 호출 존재. `perform` 접두로 좁혀 매치 — 넓은 패턴은 설명 주석까지 세어 2가 나온다)

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0008_record_click_rate_limit.sql
git commit -m "feat: record_click rate limit 마이그레이션 0008 (폰트별 10초 20건 + advisory lock)"
```

---

### Task 2: SQL 통합 테스트 작성 + dev 적용 + 실측 — ⚠️ 메인 세션 직접 (psql 네트워크)

**Files:**
- Create: `supabase/tests/click_rate_limit_test.sql`
- 참고 패턴: `supabase/tests/font_clicks_test.sql` (`do $$` assert, `begin; ... rollback;` 래핑)

**Interfaces:**
- Consumes: Task 1의 0008 `record_click`.
- Produces: dev에 0008 적용 완료 상태 + rate limit 동작 실측 근거.

**RED→GREEN 흐름**: 테스트를 먼저 작성하고 **0008 적용 전(현재 0007 상태)에 실행하면 R1이 실패**한다(0007엔 상한이 없어 21번째도 기록됨). 0008 적용 후 통과한다.

- [ ] **Step 1: 테스트 파일 작성** (전체를 `begin; ... rollback;`으로 래핑)

`supabase/tests/click_rate_limit_test.sql`:

```sql
-- =============================================================================
-- record_click rate limit SQL 통합 테스트 (0008)
-- 실행: psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/tests/click_rate_limit_test.sql
-- 전제: 0008 적용 완료, dev에 published 폰트 2종 이상 존재(noto-sans-kr 포함)
-- 쓰기는 전부 이 트랜잭션 안에서만 발생하고 마지막에 rollback → dev 데이터 무오염
-- =============================================================================
begin;

-- R1: 폰트별 상한 경계 — 같은 폰트 20건까지 기록, 21번째부터 무시
do $$
declare
  i int;
  v_n bigint;
  v_font_id uuid;
begin
  delete from fontagit.font_clicks;
  for i in 1..25 loop
    perform fontagit.record_click('noto-sans-kr');
  end loop;
  select id into v_font_id from fontagit.fonts where slug = 'noto-sans-kr';
  select count(*) into v_n from fontagit.font_clicks where font_id = v_font_id;
  if v_n <> 20 then
    raise exception 'R1: 폰트별 상한 미작동. 25회 호출 후 count=% (기대 20)', v_n;
  end if;
end $$;

-- R2: 시간창 리셋 — 윈도우 밖(11초 전) 클릭은 카운트에서 제외되어 새 클릭 기록됨
do $$
declare
  i int;
  before_n bigint;
  after_n bigint;
  v_font_id uuid;
begin
  delete from fontagit.font_clicks;
  select id into v_font_id from fontagit.fonts where slug = 'noto-sans-kr';
  -- 윈도우 밖 과거 클릭 20건 직접 삽입(테스트 전용, postgres 역할)
  for i in 1..20 loop
    insert into fontagit.font_clicks (font_id, clicked_at)
    values (v_font_id, now() - interval '11 seconds');
  end loop;
  select count(*) into before_n from fontagit.font_clicks where font_id = v_font_id;
  perform fontagit.record_click('noto-sans-kr');  -- 최근 10초 count=0이라 기록되어야 함
  select count(*) into after_n from fontagit.font_clicks where font_id = v_font_id;
  if after_n <> before_n + 1 then
    raise exception 'R2: 시간창 리셋 미작동. before=%, after=% (기대 +1)', before_n, after_n;
  end if;
end $$;

-- R3: 폰트 독립 카운트 — 폰트 A 상한 도달이 폰트 B 기록을 막지 않음
do $$
declare
  i int;
  v_other text;
  v_other_id uuid;
  v_n bigint;
begin
  delete from fontagit.font_clicks;
  select f.slug, f.id into v_other, v_other_id
  from fontagit.fonts f
  where f.status = 'published' and f.slug <> 'noto-sans-kr' limit 1;
  for i in 1..25 loop
    perform fontagit.record_click('noto-sans-kr');  -- A는 상한 도달
  end loop;
  perform fontagit.record_click(v_other);           -- B는 독립적으로 기록되어야 함
  select count(*) into v_n from fontagit.font_clicks where font_id = v_other_id;
  if v_n <> 1 then
    raise exception 'R3: 폰트 독립 카운트 실패. 다른 폰트 count=% (기대 1)', v_n;
  end if;
end $$;

-- R4: 동시성 직렬화 정적 확인 — 함수 정의에 advisory lock 존재 (SQL 단일 세션은 진짜 병렬 재현 불가)
do $$
declare
  v_def text;
begin
  v_def := pg_get_functiondef('fontagit.record_click(text)'::regprocedure);
  if position('pg_advisory_xact_lock' in v_def) = 0 then
    raise exception 'R4: record_click에 advisory lock 부재 (race 방어 누락)';
  end if;
end $$;

select 'click_rate_limit_test: ALL PASS' as result;

rollback;
```

- [ ] **Step 2: 적용 전 RED 확인 (현재 0007 상태에서 실행 → R1 실패 기대)**

```bash
psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/tests/click_rate_limit_test.sql
```
Expected: `R1: 폰트별 상한 미작동. 25회 호출 후 count=25 (기대 20)` 예외로 중단 (0007엔 상한 없음 → RED 확인)

- [ ] **Step 3: dev에 0008 적용 (메인 psql 직접)**

```bash
psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/migrations/0008_record_click_rate_limit.sql
```
Expected: `CREATE FUNCTION`, `REVOKE`, `GRANT`, `COMMENT` 출력, 오류 0

- [ ] **Step 4: 새 rate limit 테스트 실행 (GREEN 확인)**

```bash
psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/tests/click_rate_limit_test.sql
```
Expected: `click_rate_limit_test: ALL PASS` + `ROLLBACK`

- [ ] **Step 5: 기존 0007 테스트 회귀 확인 (0008이 기존 계약을 깨지 않음)**

```bash
psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/tests/font_clicks_test.sql
```
Expected: `font_clicks_test: ALL PASS` + `ROLLBACK` (익명성/권한 경계/랭킹 계약 무변경)

- [ ] **Step 6: 쓰기 흔적 없음 확인**

```bash
psql "$CONN" -Atc "select count(*) from fontagit.font_clicks"
```
Expected: `0` (rollback으로 테스트 클릭 미잔존. 단 이 값은 dev의 실제 클릭 누적에 따라 다를 수 있으니, 테스트 전후 값이 동일한지로 판단)

- [ ] **Step 7: Commit**

```bash
git add supabase/tests/click_rate_limit_test.sql
git commit -m "test: record_click rate limit SQL 통합 테스트 (경계/시간창/독립/advisory lock)"
```

---

## Self-Review 결과

**Spec 커버리지:**
- 설계 4장(B안 DB 함수) → Task 1(0008) + Task 2(테스트).
- 설계 4.1 M1 advisory lock → Task 1 Step 1 SQL + Task 2 R4.
- 설계 6.1 SQL 테스트(경계/시간창/독립) → Task 2 R1/R2/R3. 회귀 → Task 2 Step 5.
- 설계 6.1 S1 병렬-정적 확인 + 한계 → Task 2 R4(정적) + 흐름 노트(동시성 실측은 dev 병렬 curl은 선택).
- 설계 5장(A안 Kong) → "참고: Kong 계층은 코드 태스크 없음"으로 스코프 제외 명시(문서 인계).
- 설계 9장 롤백 → 코드 산출물 아님(운영 절차 문서). 태스크 없음.
- 마이그 번호 재배치(등록폼 0009) → 등록폼 파일 미존재라 지금 변경 대상 없음. 설계 문서 2장이 SSoT. 세션 종료 시 progress 일지에 기록.

**Placeholder 스캔:** TBD/TODO/"적절히 처리" 없음. 모든 SQL/명령 완전 기재.

**타입 일관성:** `record_click(p_slug text) returns void` 시그니처가 Task 1/Task 2 전체에서 일치. 상수명 `c_window`/`c_max`/`v_recent` 일관.

## 남은 의존/리스크

- dev 실측은 **psql 경로**로 수행(MCP 아님) → `supabase-dev` MCP 인증서 블로커와 무관. slice3에서 psql로 0007 적용/테스트 성공 이력 있음.
- Task 2는 psql 네트워크라 메인 세션 직접. Task 1(파일 작성)은 서브에이전트 위임 가능.
- 동시성(R4)은 정적 확인만. 진짜 병렬 실측이 필요하면 dev에서 `seq/xargs -P`로 동시 curl 후 총 insert가 상한을 넘지 않는지 확인(선택, 설계 6.1 한계).
