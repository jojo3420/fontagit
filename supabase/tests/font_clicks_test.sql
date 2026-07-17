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
  v_other text;
begin
  delete from fontagit.font_clicks;

  select f.slug into v_other from fontagit.fonts f
    where f.status = 'published' and f.slug <> 'noto-sans-kr' limit 1;

  perform fontagit.record_click('noto-sans-kr');
  perform fontagit.record_click('noto-sans-kr');
  perform fontagit.record_click('noto-sans-kr');
  perform fontagit.record_click(v_other);

  select * into top_row from fontagit.get_top_fonts() limit 1;
  if top_row.slug is distinct from 'noto-sans-kr' then
    raise exception 'C5: 최다 클릭 폰트가 1위 아님. got slug=%, clicks=%', top_row.slug, top_row.clicks;
  end if;
  if top_row.clicks <> 3 then
    raise exception 'C5: 1위 클릭수 불일치. got %', top_row.clicks;
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
