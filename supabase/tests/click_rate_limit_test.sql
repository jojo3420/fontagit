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
