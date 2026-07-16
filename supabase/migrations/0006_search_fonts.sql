-- pg_trgm 확장 설치 (public 스키마에 고정)
create extension if not exists pg_trgm with schema public;

-- pg_trgm이 public 스키마에 설치되었는지 검증
do $$
declare
  v_trgm_schema name;
begin
  select extnamespace::regnamespace::text into v_trgm_schema
  from pg_extension where extname = 'pg_trgm';
  
  if v_trgm_schema != 'public' then
    raise exception 'pg_trgm이 public이 아닌 % 스키마에 설치됨. search_path 재설정 또는 확장 재설치 필요', v_trgm_schema;
  end if;
end $$;

-- 정규화 함수 생성 (SSoT: 파이프라인 규칙 동일, 순서 NFC → 공백제거 → lower)
create or replace function fontagit.normalize_search(q text) returns text
language sql immutable
as $$
  select lower(regexp_replace(normalize(q, NFC), '\s+', '', 'g'))
$$;

comment on function fontagit.normalize_search(text) is
  '별칭 검색 정규화: NFC → 공백제거 → 소문자. 파이프라인 uploader.py normalize_alias와 동일 규칙-순서.';

-- aliases.alias_norm 인덱스 추가 (trgm 유사도 검색용)
create index if not exists idx_aliases_norm_trgm
  on fontagit.aliases using gin (alias_norm gin_trgm_ops);

-- pg_trgm은 public에 설치. search_path(fontagit, pg_temp)에 public을 넣지 않고 스키마 한정 호출로 참조한다.
-- search_fonts RPC 생성 (핵심 로직 — 매칭은 전부 정규화된 aliases.alias_norm 기준)
create or replace function fontagit.search_fonts(q text)
returns table (
  slug text,
  name_ko text,
  name_en text,
  tier text,
  category_ko text,
  score int
)
language plpgsql
security definer
set search_path = fontagit, pg_temp
as $$
declare
  v_normalized text := normalize_search(q);
  v_like_pattern text;
begin
  -- 길이 검증 (MAX_QUERY_LENGTH=100과 동일)
  if v_normalized = '' or char_length(v_normalized) > 100 then
    return;
  end if;
  
  -- LIKE 와일드카드 이스케이프 (%, _)
  v_like_pattern := '%' || replace(replace(replace(v_normalized, '\', '\\'), '%', '\%'), '_', '\_') || '%';

  return query
  select
    f.slug,
    f.name_ko,
    f.name_en,
    case when f.is_commercial_free then 'free'::text else 'paid'::text end as tier,
    f.category_ko,
    case
      when exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm = v_normalized)
        then 100
      when exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm like v_like_pattern escape '\')
        then 50
      else coalesce((
        select (max(public.similarity(a.alias_norm, v_normalized)) * 50)::int
        from aliases a where a.font_id = f.id
      ), 0)
    end as score
  from fonts f
  where f.status = 'published'
    and (
      exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm = v_normalized)
      or exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm like v_like_pattern escape '\')
      or exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm operator(public.%) v_normalized)
    )
  order by score desc, f.name_ko asc nulls last, f.name_en asc, f.slug asc
  limit 20;
end;
$$;

revoke execute on function fontagit.search_fonts(text) from public;
grant execute on function fontagit.search_fonts(text) to anon;

comment on function fontagit.search_fonts(text) is
  'Slice 2 알리아스 검색. 입력을 정규화하고 별칭 정확일치(100점)→별칭 부분일치(50점)→trgm 유사도(0~50점) 순 점수화. published 폰트만, 최대 20건.';
