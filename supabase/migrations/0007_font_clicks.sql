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
