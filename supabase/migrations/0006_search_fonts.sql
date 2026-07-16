-- pg_trgm 확장 설치
create extension if not exists pg_trgm;

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
begin
  if v_normalized = '' then
    return;
  end if;

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
      when exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm like '%' || v_normalized || '%')
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
      or exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm like '%' || v_normalized || '%')
      or exists(select 1 from aliases a where a.font_id = f.id and a.alias_norm operator(public.%) v_normalized)
    )
  order by score desc, f.name_ko asc nulls last
  limit 20;
end;
$$;

revoke execute on function fontagit.search_fonts(text) from public;
grant execute on function fontagit.search_fonts(text) to anon;

comment on function fontagit.search_fonts(text) is
  'Slice 2 알리아스 검색. 입력을 정규화하고 별칭 정확일치(100점)→별칭 부분일치(50점)→trgm 유사도(0~50점) 순 점수화. published 폰트만, 최대 20건.';
