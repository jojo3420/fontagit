-- 폰트 1개당 fonts upsert + aliases 전량 재삽입을 단일 트랜잭션(원자)으로 실행
create or replace function fontagit.upsert_font(p_font jsonb, p_aliases jsonb)
returns uuid
language plpgsql
security definer
set search_path = fontagit, pg_temp
as $$
declare
  v_font_id uuid;
begin
  insert into fontagit.fonts (
    slug, name_en, name_ko, source_tier, category_ko, category_google,
    subsets, variants, weights, is_commercial_free, license_type,
    license_verified, official_url, status, version, last_modified
  )
  values (
    p_font->>'slug',
    p_font->>'name_en',
    p_font->>'name_ko',
    coalesce(p_font->>'source_tier', 'A'),
    p_font->>'category_ko',
    p_font->>'category_google',
    coalesce(array(select jsonb_array_elements_text(p_font->'subsets')), '{}'),
    coalesce(array(select jsonb_array_elements_text(p_font->'variants')), '{}'),
    coalesce(array(select (jsonb_array_elements_text(p_font->'weights'))::int), '{}'),
    coalesce((p_font->>'is_commercial_free')::boolean, false),
    p_font->>'license_type',
    coalesce((p_font->>'license_verified')::boolean, false),
    p_font->>'official_url',
    coalesce(p_font->>'status', 'draft'),
    p_font->>'version',
    p_font->>'last_modified'
  )
  on conflict (slug) do update set
    name_en = excluded.name_en,
    name_ko = excluded.name_ko,
    source_tier = excluded.source_tier,
    category_ko = excluded.category_ko,
    category_google = excluded.category_google,
    subsets = excluded.subsets,
    variants = excluded.variants,
    weights = excluded.weights,
    is_commercial_free = excluded.is_commercial_free,
    license_type = excluded.license_type,
    license_verified = excluded.license_verified,
    official_url = excluded.official_url,
    status = excluded.status,
    version = excluded.version,
    last_modified = excluded.last_modified,
    updated_at = now()
  returning id into v_font_id;

  delete from fontagit.aliases where font_id = v_font_id;

  if jsonb_array_length(coalesce(p_aliases, '[]'::jsonb)) > 0 then
    insert into fontagit.aliases (font_id, alias, alias_norm)
    select v_font_id, a->>'alias', a->>'alias_norm'
    from jsonb_array_elements(p_aliases) a;
  end if;

  return v_font_id;
end;
$$;

-- SECURITY DEFINER 함수는 RLS를 우회한다. PostgreSQL 기본 PUBLIC EXECUTE를 회수하고
-- service_role만 실행 가능하게 제한(anon/authenticated 쓰기 차단).
revoke execute on function fontagit.upsert_font(jsonb, jsonb) from public;
revoke execute on function fontagit.upsert_font(jsonb, jsonb) from anon, authenticated;
grant execute on function fontagit.upsert_font(jsonb, jsonb) to service_role;
