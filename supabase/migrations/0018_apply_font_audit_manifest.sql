-- 감사 manifest의 유일한 공개 폰트 writer. p_manifest_text는 SHA 검증 뒤에만 JSON으로 읽는다.
create extension if not exists pgcrypto with schema extensions;

alter table fontagit.fonts drop constraint if exists fonts_published_license_chk;
alter table fontagit.fonts add constraint fonts_published_license_compat_chk check (
  status <> 'published'
  or (license_status = 'pending' and license_verified = true
      and (source_tier <> 'A' or license_type in ('OFL', 'Apache-2.0', 'UFL')))
  or (license_status = 'verified' and license_verified = true
      and (source_tier <> 'A' or license_type in ('OFL', 'Apache-2.0', 'UFL')))
  or (license_status = 'needs_review' and license_verified = false)
);

create or replace function fontagit._audit_manifest_service_role()
returns void language plpgsql security definer set search_path = '' as $$
begin
  if coalesce(current_setting('request.jwt.claim.role', true), '') <> 'service_role' then
    raise exception 'font audit manifest requires service_role';
  end if;
end;
$$;

create or replace function fontagit.apply_font_audit_manifest(
  p_manifest_text text, p_expected_sha256 text, p_schema_version integer
) returns integer language plpgsql security definer set search_path = '' as $$
declare
  v_manifest jsonb;
  v_entry jsonb;
  v_finding jsonb;
  v_snapshot jsonb;
  v_font_id uuid;
  v_updated integer := 0;
  v_rollback boolean;
  v_allowed text[] := array[
    'foundry','foundry_url','download_url','license_source_url','license_summary',
    'download_source_kind','license_source_kind','download_evidence_id','license_evidence_id',
    'download_status','license_status','download_checked_at','license_checked_at',
    'allow_commercial','allow_modify','allow_redistribute','allow_embedding',
    'allow_font_sale','attribution_requirement','is_commercial_free','license_verified',
    'name_en','name_ko','category_ko','tags','weights','variants','subsets',
    'script_status','script_checked_at','script_evidence_id'
  ];
begin
  perform fontagit._audit_manifest_service_role();
  if encode(extensions.digest(convert_to(p_manifest_text, 'UTF8'), 'sha256'), 'hex') <> p_expected_sha256 then
    raise exception 'manifest SHA-256 mismatch';
  end if;
  v_manifest := p_manifest_text::jsonb;
  if p_schema_version <> 1 or (v_manifest->>'schema_version')::integer <> 1 then
    raise exception 'unsupported manifest schema version';
  end if;
  if jsonb_typeof(v_manifest->'entries') <> 'array'
     or jsonb_array_length(v_manifest->'entries') not between 1 and 1240 then
    raise exception 'manifest entries must contain 1..1240 rows';
  end if;
  v_rollback := coalesce((v_manifest->>'rollback_mode')::boolean, false);

  -- 모든 행을 먼저 검사한다. 함수 예외는 호출 전체 transaction을 rollback한다.
  for v_entry in select value from jsonb_array_elements(v_manifest->'entries') loop
    if exists (
      select 1 from jsonb_object_keys(v_entry->'after') key
      where key <> all(v_allowed)
    ) then raise exception 'manifest includes a forbidden field'; end if;
    select fs.font_id into v_font_id from fontagit.font_sources fs
      where fs.provider = v_entry#>>'{source_key,provider}'
        and fs.provider_record_id = v_entry#>>'{source_key,provider_record_id}';
    if v_font_id is null or (select count(*) from fontagit.font_sources fs
      where fs.provider = v_entry#>>'{source_key,provider}' and fs.provider_record_id = v_entry#>>'{source_key,provider_record_id}') <> 1 then
      raise exception 'stable source key must resolve exactly one font';
    end if;
    if not v_rollback and (select updated_at from fontagit.fonts where id = v_font_id)
         is distinct from (v_entry->>'expected_updated_at')::timestamptz then
      raise exception 'stale updated_at';
    end if;
    if exists (
      select 1 from fontagit.fonts f
      cross join lateral jsonb_each(v_entry->'before') b
      where f.id = v_font_id and case b.key
        when 'foundry' then coalesce(to_jsonb(f.foundry), 'null'::jsonb)
        when 'download_url' then coalesce(to_jsonb(f.download_url), 'null'::jsonb)
        when 'download_status' then coalesce(to_jsonb(f.download_status), 'null'::jsonb)
        when 'license_status' then coalesce(to_jsonb(f.license_status), 'null'::jsonb)
        when 'license_verified' then coalesce(to_jsonb(f.license_verified), 'null'::jsonb)
        when 'license_source_url' then coalesce(to_jsonb(f.license_source_url), 'null'::jsonb)
        when 'foundry_url' then coalesce(to_jsonb(f.foundry_url), 'null'::jsonb)
        else null end is distinct from b.value
    ) then raise exception 'stale before value'; end if;
  end loop;

  -- evidence는 font_id 대신 stable key를 받아 prod FK를 여기서 재해석한다.
  insert into fontagit.font_audit_runs (id, stage, target_environment, target_count, parser_version, baseline_sha256, dry_run, status, started_at, finished_at)
  select (v_manifest#>>'{evidence_bundle,run,id}')::uuid,
         v_manifest#>>'{evidence_bundle,run,stage}', 'dev',
         greatest(1, (v_manifest#>>'{evidence_bundle,run,target_count}')::int),
         v_manifest#>>'{evidence_bundle,run,parser_version}', v_manifest->>'baseline_sha256',
         true, 'completed', now(), now()
  on conflict (id) do nothing;

  for v_snapshot in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') loop
    select fs.font_id into v_font_id from fontagit.font_sources fs
      where fs.provider = v_snapshot#>>'{source_key,provider}'
        and fs.provider_record_id = v_snapshot#>>'{source_key,provider_record_id}';
    insert into fontagit.font_source_snapshots(
      id, run_id, font_id, provider, provider_record_id, source_kind, document_kind,
      request_url, final_url, http_status, raw_text, raw_sha256, normalized_sha256,
      extracted, evidence_locations, extraction_rule_id, parser_version, collected_at
    ) values (
      (v_snapshot->>'id')::uuid, (v_manifest#>>'{evidence_bundle,run,id}')::uuid, v_font_id,
      v_snapshot->>'provider', v_snapshot->>'provider_record_id', v_snapshot->>'source_kind',
      v_snapshot->>'document_kind', v_snapshot->>'request_url', v_snapshot->>'final_url',
      nullif(v_snapshot->>'http_status','')::integer, v_snapshot->>'raw_text',
      v_snapshot->>'raw_sha256', v_snapshot->>'normalized_sha256',
      coalesce(v_snapshot->'extracted','{}'::jsonb), coalesce(v_snapshot->'evidence_locations','{}'::jsonb),
      v_snapshot->>'extraction_rule_id', v_snapshot->>'parser_version',
      (v_snapshot->>'collected_at')::timestamptz
    ) on conflict (id) do nothing;
  end loop;
  for v_finding in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') loop
    select fs.font_id into v_font_id from fontagit.font_sources fs
      where fs.provider = v_finding#>>'{source_key,provider}'
        and fs.provider_record_id = v_finding#>>'{source_key,provider_record_id}';
    insert into fontagit.font_audit_findings(
      id, run_id, font_id, field_name, before_value, proposed_value, evidence_id,
      confidence, auto_applicable, review_reason, status, reviewed_by, reviewed_at
    ) values (
      (v_finding->>'id')::uuid, (v_manifest#>>'{evidence_bundle,run,id}')::uuid, v_font_id,
      v_finding->>'field_name', v_finding->'before_value', v_finding->'proposed_value',
      nullif(v_finding->>'evidence_id','')::uuid, v_finding->>'confidence',
      coalesce((v_finding->>'auto_applicable')::boolean, false), v_finding->>'review_reason',
      v_finding->>'status', v_finding->>'reviewed_by', nullif(v_finding->>'reviewed_at','')::timestamptz
    ) on conflict (id) do nothing;
  end loop;

  for v_entry in select value from jsonb_array_elements(v_manifest->'entries') loop
    select fs.font_id into v_font_id from fontagit.font_sources fs
      where fs.provider = v_entry#>>'{source_key,provider}' and fs.provider_record_id = v_entry#>>'{source_key,provider_record_id}';
    update fontagit.fonts f set
      foundry = case when v_entry->'after' ? 'foundry' then v_entry#>>'{after,foundry}' else f.foundry end,
      foundry_url = case when v_entry->'after' ? 'foundry_url' then v_entry#>>'{after,foundry_url}' else f.foundry_url end,
      download_url = case when v_entry->'after' ? 'download_url' then v_entry#>>'{after,download_url}' else f.download_url end,
      license_source_url = case when v_entry->'after' ? 'license_source_url' then v_entry#>>'{after,license_source_url}' else f.license_source_url end,
      license_summary = case when v_entry->'after' ? 'license_summary' then v_entry#>>'{after,license_summary}' else f.license_summary end,
      download_status = case when v_entry->'after' ? 'download_status' then v_entry#>>'{after,download_status}' else f.download_status end,
      license_status = case when v_entry->'after' ? 'license_status' then v_entry#>>'{after,license_status}' else f.license_status end,
      license_verified = case when v_entry->'after' ? 'license_verified' then (v_entry#>>'{after,license_verified}')::boolean else f.license_verified end,
      updated_at = now()
    where f.id = v_font_id;
    v_updated := v_updated + 1;
  end loop;
  for v_finding in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') loop
    update fontagit.font_audit_findings
      set status = 'applied'::text
      where id = (v_finding->>'id')::uuid
        and font_audit_findings.status = 'approved'::text;
  end loop;
  return v_updated;
end;
$$;

create or replace function fontagit.apply_font_source_bootstrap(
  p_manifest_text text, p_expected_sha256 text, p_schema_version integer
) returns integer language plpgsql security definer set search_path = '' as $$
declare v_manifest jsonb; v_entry jsonb; v_font_id uuid; v_count integer := 0;
begin
  perform fontagit._audit_manifest_service_role();
  if encode(extensions.digest(convert_to(p_manifest_text, 'UTF8'), 'sha256'), 'hex') <> p_expected_sha256 then raise exception 'manifest SHA-256 mismatch'; end if;
  v_manifest := p_manifest_text::jsonb;
  if p_schema_version <> 1 or (v_manifest->>'schema_version')::integer <> 1 then raise exception 'unsupported manifest schema version'; end if;
  for v_entry in select value from jsonb_array_elements(v_manifest->'entries') loop
    select f.id into v_font_id from fontagit.fonts f where f.id = (v_entry->>'font_id')::uuid
      and f.source_tier = v_entry#>>'{before,source_tier}' and f.slug = v_entry#>>'{before,slug}'
      and f.name_en = v_entry#>>'{before,name_en}' and f.official_url = v_entry#>>'{before,official_url}'
      and f.foundry is null;
    if v_font_id is null or coalesce(v_entry->'public_updates', '{}'::jsonb) <> '{}'::jsonb then raise exception 'bootstrap precondition mismatch'; end if;
    if exists(select 1 from fontagit.font_sources where provider = v_entry->>'provider' and provider_record_id = v_entry->>'provider_record_id') then raise exception 'provider key collision'; end if;
  end loop;
  for v_entry in select value from jsonb_array_elements(v_manifest->'entries') loop
    insert into fontagit.font_sources(font_id, provider, provider_record_id, source_role, source_url)
    values ((v_entry->>'font_id')::uuid, v_entry->>'provider', v_entry->>'provider_record_id', 'reference', v_entry->>'source_url');
    v_count := v_count + 1;
  end loop;
  return v_count;
end;
$$;

revoke all on function fontagit.apply_font_audit_manifest(text, text, integer) from public, anon, authenticated;
revoke all on function fontagit.apply_font_source_bootstrap(text, text, integer) from public, anon, authenticated;
grant execute on function fontagit.apply_font_audit_manifest(text, text, integer) to service_role;
grant execute on function fontagit.apply_font_source_bootstrap(text, text, integer) to service_role;
