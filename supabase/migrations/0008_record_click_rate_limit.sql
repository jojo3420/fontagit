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
