-- =============================================================================
-- 0009_chosung_search.sql
-- 초성 검색(F-16) + 자동완성(F-19) 지원
-- Task 1: to_chosung 초성 추출 함수
-- Task 2: alias_chosung 생성 컬럼 + 색인
-- Task 3: search_fonts 2-인자 재정의 (초성 분기 + lim clamp + foundry)
-- =============================================================================

-- =============================================================================
-- Task 1: 초성 추출 함수 (한글 음절 → 초성, 그 외 문자는 그대로)
-- =============================================================================
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

-- =============================================================================
-- Task 2: 초성 저장 컬럼 (생성 컬럼: 저장/수정 시 자동 계산, 기존 행 자동 백필)
-- =============================================================================
alter table fontagit.aliases
  add column if not exists alias_chosung text
  generated always as (fontagit.to_chosung(alias_norm)) stored;

-- 접두(prefix) LIKE 'x%' 검색이 색인을 타도록 text_pattern_ops
create index if not exists idx_aliases_chosung
  on fontagit.aliases (alias_chosung text_pattern_ops);

-- =============================================================================
-- Task 3: search_fonts 재정의: (q, lim) 2-인자, 초성 분기 + foundry 반환 + lim clamp
-- =============================================================================
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
