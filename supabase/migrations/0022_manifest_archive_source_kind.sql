-- apply_font_audit_manifest RPC의 값 검증자가 여전히 download_source_kind에
-- official/public만 허용해 0021에서 확장한 archive 등급 manifest 적용이 100% 차단됨.
-- 0018의 _audit_manifest_value_valid 함수 원문을 그대로 복사하고
-- download_source_kind 조건에만 'archive'를 추가한다. license_source_kind는
-- official/public만 계속 허용한다(archive로 license 자동 승인 금지, 0021과 동일 원칙).

create or replace function fontagit._audit_manifest_value_valid(p_key text, p_value jsonb)
returns boolean language plpgsql immutable set search_path = '' as $$
declare v_item jsonb;
begin
  if p_key in ('foundry','foundry_url','download_url','license_source_url','license_summary',
               'name_en','name_ko','category_ko') then
    return p_value = 'null'::jsonb or jsonb_typeof(p_value) = 'string';
  elsif p_key = 'download_source_kind' then
    return p_value = 'null'::jsonb or p_value in ('"official"'::jsonb, '"public"'::jsonb, '"archive"'::jsonb);
  elsif p_key = 'license_source_kind' then
    return p_value = 'null'::jsonb or p_value in ('"official"'::jsonb, '"public"'::jsonb);
  elsif p_key in ('download_evidence_id','license_evidence_id','script_evidence_id') then
    if p_value = 'null'::jsonb then return true; end if;
    if jsonb_typeof(p_value) <> 'string' then return false; end if;
    perform (p_value#>>'{}')::uuid; return true;
  elsif p_key = 'download_status' then
    return p_value in ('"pending"'::jsonb,'"verified"'::jsonb,'"needs_review"'::jsonb,'"broken"'::jsonb);
  elsif p_key in ('license_status','script_status') then
    return p_value in ('"pending"'::jsonb,'"verified"'::jsonb,'"needs_review"'::jsonb);
  elsif p_key in ('download_checked_at','license_checked_at','script_checked_at') then
    if p_value = 'null'::jsonb then return true; end if;
    if jsonb_typeof(p_value) <> 'string' then return false; end if;
    perform (p_value#>>'{}')::timestamptz; return true;
  elsif p_key in ('allow_commercial','allow_font_sale','allow_embedding','allow_redistribute','allow_modify') then
    return p_value = 'null'::jsonb or p_value in ('"allowed"'::jsonb,'"conditional"'::jsonb,'"denied"'::jsonb);
  elsif p_key = 'attribution_requirement' then
    return p_value = 'null'::jsonb or p_value in ('"required"'::jsonb,'"recommended"'::jsonb,'"not_required"'::jsonb);
  elsif p_key in ('is_commercial_free','license_verified') then
    return jsonb_typeof(p_value) = 'boolean';
  elsif p_key in ('tags','variants','subsets') then
    if jsonb_typeof(p_value) <> 'array' then return false; end if;
    for v_item in select value from jsonb_array_elements(p_value) loop
      if jsonb_typeof(v_item) <> 'string' then return false; end if;
    end loop; return true;
  elsif p_key = 'weights' then
    if jsonb_typeof(p_value) <> 'array' then return false; end if;
    for v_item in select value from jsonb_array_elements(p_value) loop
      if jsonb_typeof(v_item) <> 'number' or v_item::text !~ '^-?[0-9]+$' then return false; end if;
      perform (v_item::text)::integer;
    end loop; return true;
  end if;
  return false;
exception when others then return false;
end;
$$;
