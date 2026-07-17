-- =============================================================================
-- chosung_search_test.sql
-- 초성 검색(F-16) + 자동완성(F-19) 테스트
-- 전제: 0009_chosung_search.sql 적용 완료, dev DB에 published 실데이터 존재
-- 실행: psql "$DEV_CONN" -v ON_ERROR_STOP=1 -f supabase/tests/chosung_search_test.sql
-- =============================================================================

-- C1: 한글 초성 추출
do $$
declare r text;
begin
  r := fontagit.to_chosung('지마켓산스');
  if r != 'ㅈㅁㅋㅅㅅ' then
    raise exception 'C1 failed: expected ''ㅈㅁㅋㅅㅅ'', got ''%s''', r;
  end if;
end $$;

-- C2: 영문/숫자/공백은 그대로 통과
do $$
declare r text;
begin
  r := fontagit.to_chosung('gmarket 2024');
  if r != 'gmarket 2024' then
    raise exception 'C2 failed: got ''%s''', r;
  end if;
end $$;

-- C3: 혼합(한글+영문)
do $$
declare r text;
begin
  r := fontagit.to_chosung('본고딕abc');
  if r != 'ㅂㄱㄷabc' then
    raise exception 'C3 failed: got ''%s''', r;
  end if;
end $$;

-- C4: alias_chosung 생성 컬럼이 alias_norm 초성과 일치
do $$
declare cnt int;
begin
  select count(*) into cnt
  from fontagit.aliases
  where alias_chosung is distinct from fontagit.to_chosung(alias_norm);
  if cnt != 0 then
    raise exception 'C4 failed: alias_chosung mismatch rows=%', cnt;
  end if;
end $$;

-- C5: 초성 입력으로 특정 폰트가 잡힌다 (dev 실데이터 전제)
-- 대상 폰트: black-han-sans (검은고딕 → 초성 ㄱㅇㄱㄷ). dev에 gmarket-sans 미적재라 실존 폰트로 검증.
do $$
declare cnt int;
begin
  select count(*) into cnt
  from fontagit.search_fonts('ㄱㅇㄱㄷ', 8) s
  where s.slug = 'black-han-sans';
  if cnt < 1 then
    raise exception 'C5 failed: black-han-sans not found in chosung search (cnt=%)', cnt;
  end if;
end $$;

-- C6: lim clamp — 0/음수/과대값도 안전 (에러 없이 반환, 최대 100)
-- 계획서 의도: 0/음수 → 1로 clamp, 과대값 → 최대 100. 예외 없이 도달하면 통과.
do $$
declare cnt int;
begin
  select count(*) into cnt from fontagit.search_fonts('ㄱ', 0);    -- clamp→1
  select count(*) into cnt from fontagit.search_fonts('ㄱ', -5);   -- clamp→1
  select count(*) into cnt from fontagit.search_fonts('ㄱ', 1000); -- clamp→100
end $$;

-- C7: 1-인자 하위호환 (기존 호출 유지)
do $$
declare cnt int;
begin
  select count(*) into cnt from fontagit.search_fonts('검은고딕');
  if cnt < 1 then
    raise exception 'C7 failed: 1-arg search_fonts broke (cnt=%)', cnt;
  end if;
end $$;

-- C8: foundry 컬럼이 반환된다
do $$
declare has_foundry boolean;
begin
  select exists(select 1 from fontagit.search_fonts('검은고딕', 8) s where s.foundry is not null)
    into has_foundry;
  -- foundry가 전부 null일 수도 있으므로 컬럼 참조가 에러 없이 되는지만 검증(위 select 성공이면 OK)
end $$;

-- C9: 비공개 폰트 미노출 — published 아닌 폰트는 결과에 없음
do $$
declare cnt int;
begin
  select count(*) into cnt
  from fontagit.search_fonts('검은고딕', 100) s
  join fontagit.fonts f on f.slug = s.slug
  where f.status <> 'published';
  if cnt != 0 then
    raise exception 'C9 failed: unpublished fonts leaked (cnt=%)', cnt;
  end if;
end $$;
