begin;

create or replace function fontagit.sync_tier_a_fonts(p_active_slugs text[])
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_active_count integer;
  v_distinct_count integer;
  v_stale_count integer;
begin
  if p_active_slugs is null then
    raise exception 'active slug 목록은 null일 수 없습니다'
      using errcode = '22023';
  end if;

  if exists (
    select 1
    from unnest(p_active_slugs) as slug
    where slug is null or btrim(slug) = ''
  ) then
    raise exception 'active slug에 null/빈 문자열이 있습니다'
      using errcode = '22023';
  end if;

  v_active_count := cardinality(p_active_slugs);
  select count(distinct slug)
    into v_distinct_count
    from unnest(p_active_slugs) as slug;

  if v_active_count <> v_distinct_count then
    raise exception 'active slug에 중복이 있습니다'
      using errcode = '22023';
  end if;

  if v_distinct_count < 100 then
    raise exception 'active Tier A가 100종 미만입니다: %', v_distinct_count
      using errcode = '22023';
  end if;

  lock table fontagit.fonts in share row exclusive mode;

  select count(*)
    into v_stale_count
    from fontagit.fonts as f
   where f.source_tier = 'A'
     and f.status = 'published'
     and not (f.slug = any(p_active_slugs));

  if v_stale_count > 5 then
    raise exception 'stale published Tier A가 5종을 초과합니다: %', v_stale_count
      using errcode = '22023';
  end if;

  update fontagit.fonts as f
     set status = 'draft',
         updated_at = now()
   where f.source_tier = 'A'
     and f.status = 'published'
     and not (f.slug = any(p_active_slugs));

  return v_stale_count;
end;
$$;

revoke execute on function fontagit.sync_tier_a_fonts(text[]) from public;
revoke execute on function fontagit.sync_tier_a_fonts(text[]) from anon, authenticated;
grant execute on function fontagit.sync_tier_a_fonts(text[]) to service_role;

commit;
