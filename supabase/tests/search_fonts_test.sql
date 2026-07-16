-- =============================================================================
-- search_fonts SQL 통합 테스트 스크립트
-- =============================================================================
-- 목적: fontagit.normalize_search() 및 fontagit.search_fonts() RPC 함수 동작 검증
--
-- 실행 방법:
--   psql "$CONN" -v ON_ERROR_STOP=1 -f supabase/tests/search_fonts_test.sql
--
-- 전제:
--   - supabase/migrations/0006_search_fonts.sql 적용 완료
--   - dev DB에 슬라이스 0.5 실데이터 적재됨 (noto-sans-kr 등 published 130종)
--   - 이 스크립트는 read-only (select/assert만 사용, 데이터 쓰기 없음)
-- =============================================================================

-- N1: 정규화 공백 제거
do $$
declare
  result text;
begin
  result := fontagit.normalize_search('  본 고 딕  ');
  if result != '본고딕' then
    raise exception 'N1: normalize_search with spaces failed. expected ''본고딕'', got ''%''', result;
  end if;
end $$;

-- N2: 정규화 NFC (NFD 자모분리 입력 변환)
do $$
declare
  result text;
  nfd_input bytea := '\xe18487e185a9e186abe18480e185a9e18483e185b5e186a8'::bytea;
begin
  result := fontagit.normalize_search(convert_from(nfd_input, 'UTF8'));
  if result != '본고딕' then
    raise exception 'N2: normalize_search with NFD normalization failed. expected ''본고딕'', got ''%''', result;
  end if;
end $$;

-- N3: 정규화 소문자 변환
do $$
declare
  result text;
begin
  result := fontagit.normalize_search('ABC Def');
  if result != 'abcdef' then
    raise exception 'N3: normalize_search with lowercase failed. expected ''abcdef'', got ''%''', result;
  end if;
end $$;

-- S1: 정확일치 (본고딕)
do $$
declare
  top_result record;
begin
  select slug, score into top_result from fontagit.search_fonts('본고딕') limit 1;
  if top_result.slug is null then
    raise exception 'S1: search_fonts(''본고딕'') returned no results';
  end if;
  if top_result.slug != 'noto-sans-kr' then
    raise exception 'S1: search_fonts(''본고딕'') top result slug mismatch. expected ''noto-sans-kr'', got ''%''', top_result.slug;
  end if;
  if top_result.score != 100 then
    raise exception 'S1: search_fonts(''본고딕'') top result score mismatch. expected 100, got %', top_result.score;
  end if;
end $$;

-- S2: 부분일치 (나눔) - 3건 이상, 최고 score=50
do $$
declare
  result_count int;
  top_score int;
begin
  select count(*), max(score) into result_count, top_score from fontagit.search_fonts('나눔');
  if result_count < 3 then
    raise exception 'S2: search_fonts(''나눔'') returned fewer than 3 results. got %', result_count;
  end if;
  if top_score != 50 then
    raise exception 'S2: search_fonts(''나눔'') max score mismatch. expected 50, got %', top_score;
  end if;
end $$;

-- S3: 오타 유사도 (본고딩) - noto-sans-kr 포함, 0 < score < 50
do $$
declare
  found_slug text;
  found_score int;
begin
  select slug, score into found_slug, found_score
    from fontagit.search_fonts('본고딩')
   where slug = 'noto-sans-kr' limit 1;
  if found_slug is null then
    raise exception 'S3: search_fonts(''본고딩'') did not include ''noto-sans-kr''';
  end if;
  if found_score <= 0 or found_score >= 50 then
    raise exception 'S3: search_fonts(''본고딩'') noto-sans-kr score out of range (0, 50). got %', found_score;
  end if;
end $$;

-- S4: 공백 정규화 (본 고딕)
do $$
declare
  top_result record;
begin
  select slug, score into top_result from fontagit.search_fonts('본 고딕') limit 1;
  if top_result.slug is null then
    raise exception 'S4: search_fonts(''본 고딕'') returned no results';
  end if;
  if top_result.score != 100 then
    raise exception 'S4: search_fonts(''본 고딕'') top result score mismatch. expected 100, got %', top_result.score;
  end if;
end $$;

-- Note: S5 (published filter) and S6 (limit 20) are smoke-level tests because
-- dev data lacks negative cases (unpublished fonts matching query, 20+ matches).
-- Test data generation not adopted due to "no direct dev insert outside pipeline" decision.

-- S5: published 필터 검증
do $$
declare
  non_published_count int;
begin
  select count(*) into non_published_count
    from fontagit.search_fonts('본고딕') s
    left join fontagit.fonts f on s.slug = f.slug
   where f.status != 'published';
  if non_published_count > 0 then
    raise exception 'S5: search_fonts(''본고딕'') returned non-published fonts. count %', non_published_count;
  end if;
end $$;

-- S6: 결과 상한 (20건 이하)
do $$
declare
  result_count int;
begin
  select count(*) into result_count from fontagit.search_fonts('a');
  if result_count > 20 then
    raise exception 'S6: search_fonts(''a'') exceeded 20 result limit. got %', result_count;
  end if;
end $$;

-- S7: 방어 쿼리 (빈 문자열, 공백, 특수문자, 초과 길이)
do $$
declare
  empty_count int;
  spaces_count int;
  percent_count int;
  underscore_count int;
  long_count int;
begin
  select count(*) into empty_count from fontagit.search_fonts('');
  if empty_count != 0 then
    raise exception 'S7: search_fonts('''') should return 0 results. got %', empty_count;
  end if;

  select count(*) into spaces_count from fontagit.search_fonts('   ');
  if spaces_count != 0 then
    raise exception 'S7: search_fonts(''   '') should return 0 results. got %', spaces_count;
  end if;

  select count(*) into percent_count from fontagit.search_fonts('%');
  if percent_count != 0 then
    raise exception 'S7: search_fonts(''%%'') should return 0 results. got %', percent_count;
  end if;

  select count(*) into underscore_count from fontagit.search_fonts('_');
  if underscore_count != 0 then
    raise exception 'S7: search_fonts(''_'') should return 0 results. got %', underscore_count;
  end if;

  select count(*) into long_count from fontagit.search_fonts(repeat('가', 101));
  if long_count != 0 then
    raise exception 'S7: search_fonts(repeat(''가'', 101)) should return 0 results. got %', long_count;
  end if;
end $$;

-- =============================================================================
-- 모든 테스트 통과
-- =============================================================================
select 'ALL PASS' as result;
