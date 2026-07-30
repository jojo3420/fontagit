-- 목적(#150): apply_font_audit_manifest RPC가 official_url을 정정 가능한 필드로 다룰 수 있게 한다.
-- official_url은 fonts.official_url이 NOT NULL이라 다른 URL 필드(license_source_url 등,
-- nullable)와 다르게 다룬다: 교체만 허용하고 nullify는 허용하지 않는다(#150 논의 결과,
-- 링크 없는 폰트를 NULL로 둘지는 스캔 리포트 이후 별도 결정으로 보류). 관련 함수 3개를 모두
-- 최신 정의(0018/0022/0025) 원문 그대로 복사한 뒤 official_url 관련 변경만 추가한다.

-- 0018 원문 그대로 복사 + case 목록에 official_url 한 줄만 추가.
-- 이게 빠지면 v_allowed에 official_url이 있어도 이 함수는 else null(SQL NULL)로 떨어져
-- apply_font_audit_manifest의 'stale before value' 검사가 항상 예외를 던진다.
-- official_url은 NOT NULL이라 다른 URL 필드와 달리 coalesce로 감싸지 않는다
-- (download_status/license_status 등 다른 NOT NULL 컬럼과 동일 패턴).
create or replace function fontagit._audit_font_value(p_font_id uuid, p_key text)
returns jsonb language sql stable security definer set search_path = '' as $$
  select case p_key
    when 'foundry' then coalesce(to_jsonb(f.foundry), 'null'::jsonb)
    when 'foundry_url' then coalesce(to_jsonb(f.foundry_url), 'null'::jsonb)
    when 'download_url' then coalesce(to_jsonb(f.download_url), 'null'::jsonb)
    when 'license_source_url' then coalesce(to_jsonb(f.license_source_url), 'null'::jsonb)
    when 'official_url' then to_jsonb(f.official_url)
    when 'license_summary' then coalesce(to_jsonb(f.license_summary), 'null'::jsonb)
    when 'download_source_kind' then coalesce(to_jsonb(f.download_source_kind), 'null'::jsonb)
    when 'license_source_kind' then coalesce(to_jsonb(f.license_source_kind), 'null'::jsonb)
    when 'download_evidence_id' then coalesce(to_jsonb(f.download_evidence_id), 'null'::jsonb)
    when 'license_evidence_id' then coalesce(to_jsonb(f.license_evidence_id), 'null'::jsonb)
    when 'download_status' then to_jsonb(f.download_status)
    when 'license_status' then to_jsonb(f.license_status)
    when 'download_checked_at' then coalesce(to_jsonb(f.download_checked_at), 'null'::jsonb)
    when 'license_checked_at' then coalesce(to_jsonb(f.license_checked_at), 'null'::jsonb)
    when 'allow_commercial' then coalesce(to_jsonb(f.allow_commercial), 'null'::jsonb)
    when 'allow_font_sale' then coalesce(to_jsonb(f.allow_font_sale), 'null'::jsonb)
    when 'allow_embedding' then coalesce(to_jsonb(f.allow_embedding), 'null'::jsonb)
    when 'allow_redistribute' then coalesce(to_jsonb(f.allow_redistribute), 'null'::jsonb)
    when 'allow_modify' then coalesce(to_jsonb(f.allow_modify), 'null'::jsonb)
    when 'attribution_requirement' then coalesce(to_jsonb(f.attribution_requirement), 'null'::jsonb)
    when 'is_commercial_free' then to_jsonb(f.is_commercial_free)
    when 'license_verified' then to_jsonb(f.license_verified)
    when 'name_en' then coalesce(to_jsonb(f.name_en), 'null'::jsonb)
    when 'name_ko' then coalesce(to_jsonb(f.name_ko), 'null'::jsonb)
    when 'category_ko' then to_jsonb(f.category_ko)
    when 'tags' then to_jsonb(f.tags)
    when 'weights' then to_jsonb(f.weights)
    when 'variants' then to_jsonb(f.variants)
    when 'subsets' then to_jsonb(f.subsets)
    when 'script_status' then to_jsonb(f.script_status)
    when 'script_checked_at' then coalesce(to_jsonb(f.script_checked_at), 'null'::jsonb)
    when 'script_evidence_id' then coalesce(to_jsonb(f.script_evidence_id), 'null'::jsonb)
    else null
  end
  from fontagit.fonts f where f.id = p_font_id
$$;

-- 0022 원문(0018 텍스트 필드 목록 + download_source_kind archive 확장) 그대로 복사 + official_url
-- 별도 분기 추가. official_url은 다른 URL 필드(텍스트 필드 목록, null 허용)와 달리 fonts.official_url이
-- NOT NULL이라 null을 허용하지 않는다 — 따로 분기해서 nullify manifest를 UPDATE 단계의 제약 위반이
-- 아니라 여기서 'manifest field or value is invalid: official_url'로 먼저 명확히 거부한다.
create or replace function fontagit._audit_manifest_value_valid(p_key text, p_value jsonb)
returns boolean language plpgsql immutable set search_path = '' as $$
declare v_item jsonb;
begin
  if p_key in ('foundry','foundry_url','download_url','license_source_url','license_summary',
               'name_en','name_ko','category_ko') then
    return p_value = 'null'::jsonb or jsonb_typeof(p_value) = 'string';
  elsif p_key = 'official_url' then
    return jsonb_typeof(p_value) = 'string';
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

-- 0025 원문 그대로 복사 + 아래 2곳만 수정.
-- (a) v_allowed에 official_url 추가.
-- (b) UPDATE 절에 official_url 반영 구문 추가(license_source_url과 동일 패턴).
-- 낙관적 잠금(current 대조)의 official_url 줄은 0025 원문 그대로 coalesce 없이 둔다 —
-- official_url은 fonts.official_url이 NOT NULL이라 SQL NULL이 될 수 없으므로 coalesce는 죽은
-- 코드다. 이 제약을 나중에 없애면 이 줄에 coalesce(to_jsonb(v_existing.official_url),'null'::jsonb)
-- 정규화를 함께 넣어야 한다 — to_jsonb(NULL::text)는 SQL NULL을 반환하고
-- `NULL is distinct from X`는 항상 참이라 official_url이 NULL인 폰트는 잠금을 영원히 통과 못한다.
-- (manifest_official_url_test.sql의 tripwire 케이스가 제약 변경 시 먼저 깨져 이 의존성을 알려준다.)
create or replace function fontagit.apply_font_audit_manifest(
  p_manifest_text text, p_expected_sha256 text, p_schema_version integer
) returns integer language plpgsql security definer set search_path = '' as $$
declare
  v_manifest jsonb; v_entry jsonb; v_snapshot jsonb; v_finding jsonb;
  v_run jsonb; v_font_id uuid; v_key text; v_value jsonb; v_count integer;
  v_updated integer := 0; v_rows integer; v_rollback boolean; v_existing record;
  v_allowed constant text[] := array[
    'foundry','foundry_url','download_url','license_source_url','official_url','license_summary',
    'download_source_kind','license_source_kind','download_evidence_id','license_evidence_id',
    'download_status','license_status','download_checked_at','license_checked_at',
    'allow_commercial','allow_font_sale','allow_embedding','allow_redistribute','allow_modify',
    'attribution_requirement','is_commercial_free','license_verified','name_en','name_ko',
    'category_ko','tags','weights','variants','subsets','script_status','script_checked_at',
    'script_evidence_id'
  ];
begin
  perform fontagit._audit_manifest_service_role();
  if p_expected_sha256 !~ '^[0-9a-f]{64}$'
     or encode(extensions.digest(convert_to(p_manifest_text, 'UTF8'), 'sha256'), 'hex') <> p_expected_sha256 then
    raise exception 'manifest SHA-256 mismatch';
  end if;
  v_manifest := p_manifest_text::jsonb;
  perform fontagit._audit_manifest_exact_keys(v_manifest,
    array['schema_version','run_id','baseline_sha256','generated_at','rollback_mode','evidence_bundle','entries'], 'manifest');
  if p_schema_version <> 1 or jsonb_typeof(v_manifest->'schema_version') <> 'number'
     or (v_manifest->>'schema_version')::integer <> 1 then raise exception 'unsupported manifest schema version'; end if;
  if jsonb_typeof(v_manifest->'entries') <> 'array'
     or jsonb_array_length(v_manifest->'entries') not between 1 and 1240 then
    raise exception 'manifest entries must contain 1..1240 rows';
  end if;
  if jsonb_typeof(v_manifest->'baseline_sha256') <> 'string'
     or v_manifest->>'baseline_sha256' !~ '^[0-9a-f]{64}$' then raise exception 'baseline SHA-256 is invalid'; end if;
  if jsonb_typeof(v_manifest#>'{evidence_bundle,run}') <> 'object'
     or jsonb_typeof(v_manifest#>'{evidence_bundle,snapshots}') <> 'array'
     or jsonb_typeof(v_manifest#>'{evidence_bundle,findings}') <> 'array' then
    raise exception 'evidence bundle shape is invalid';
  end if;
  perform fontagit._audit_manifest_exact_keys(v_manifest->'evidence_bundle', array['run','snapshots','findings'], 'evidence_bundle');
  v_rollback := coalesce((v_manifest->>'rollback_mode')::boolean, false);
  v_run := v_manifest#>'{evidence_bundle,run}';
  perform fontagit._audit_manifest_exact_keys(v_run,
    array['id','stage','target_environment','target_count','success_count','verified_count','review_count','broken_count','parser_version','baseline_sha256','manifest_sha256','dry_run','status','started_at','finished_at'], 'run');
  if (v_run->>'id')::uuid <> (v_manifest->>'run_id')::uuid then raise exception 'run id mismatch'; end if;
  if jsonb_typeof(v_run->'baseline_sha256') <> 'string'
     or v_run->>'baseline_sha256' <> v_manifest->>'baseline_sha256' then raise exception 'baseline SHA-256 does not match run'; end if;

  if exists (select 1 from jsonb_array_elements(v_manifest->'entries') e
    group by e#>>'{source_key,provider}', e#>>'{source_key,provider_record_id}' having count(*) > 1) then
    raise exception 'duplicate source_key';
  end if;
  if exists (select 1 from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') s group by s->>'id' having count(*) > 1)
     or exists (select 1 from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') f group by f->>'id' having count(*) > 1)
     or exists (select 1 from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') s
                join jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') f on s->>'id'=f->>'id')
     or exists (select 1 from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') s where s->>'id'=v_run->>'id')
     or exists (select 1 from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') f where f->>'id'=v_run->>'id') then
    raise exception 'duplicate evidence UUID';
  end if;
  if exists (
    select 1 from jsonb_array_elements(v_manifest->'entries') e
    where jsonb_typeof(e->'evidence_ids') = 'array'
      and jsonb_array_length(e->'evidence_ids') <> (
        select count(distinct value) from jsonb_array_elements_text(e->'evidence_ids') as item(value)
      )
  ) or exists (
    select 1 from jsonb_array_elements(v_manifest->'entries') e
    where jsonb_typeof(e->'finding_ids') = 'array'
      and jsonb_array_length(e->'finding_ids') <> (
        select count(distinct value) from jsonb_array_elements_text(e->'finding_ids') as item(value)
      )
  ) then raise exception 'entry evidence/finding IDs must be unique'; end if;
  if exists (
    select 1 from (
      select jsonb_array_elements_text(e->'evidence_ids') id from jsonb_array_elements(v_manifest->'entries') e
    ) q group by id having count(*) > 1
  ) or exists (
    select 1 from (
      select jsonb_array_elements_text(e->'finding_ids') id from jsonb_array_elements(v_manifest->'entries') e
    ) q group by id having count(*) > 1
  ) then raise exception 'entry evidence IDs must be globally unique'; end if;

  if exists(
    (select jsonb_array_elements_text(e->'evidence_ids') from jsonb_array_elements(v_manifest->'entries') e)
    except (select s->>'id' from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') s)
  ) or exists(
    (select s->>'id' from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') s)
    except (select jsonb_array_elements_text(e->'evidence_ids') from jsonb_array_elements(v_manifest->'entries') e)
  ) or exists(
    (select jsonb_array_elements_text(e->'finding_ids') from jsonb_array_elements(v_manifest->'entries') e)
    except (select f->>'id' from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') f)
  ) or exists(
    (select f->>'id' from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') f)
    except (select jsonb_array_elements_text(e->'finding_ids') from jsonb_array_elements(v_manifest->'entries') e)
  ) then raise exception 'entries must reference the exact evidence set'; end if;

  create temporary table if not exists pg_temp.font_audit_targets(
    font_id uuid primary key, entry jsonb not null
  ) on commit drop;
  truncate pg_temp.font_audit_targets;

  -- 전체 target/finding/snapshot 연결을 먼저 확인하고 fonts 행을 잠근다.
  for v_entry in select value from jsonb_array_elements(v_manifest->'entries') loop
    perform fontagit._audit_manifest_exact_keys(v_entry,
      array['source_key','current','before','after','evidence_ids','finding_ids','expected_updated_at'], 'entry');
    perform fontagit._audit_manifest_exact_keys(v_entry->'source_key', array['provider','provider_record_id'], 'entry.source_key');
    perform fontagit._audit_manifest_exact_keys(v_entry->'current', array['slug','name_en','name_ko','foundry','source_tier','official_url','status'], 'entry.current');
    if jsonb_typeof(v_entry->'before') <> 'object' or jsonb_typeof(v_entry->'after') <> 'object'
       or v_entry->'before' = '{}'::jsonb or (select array_agg(key order by key) from jsonb_object_keys(v_entry->'before') key)
          is distinct from (select array_agg(key order by key) from jsonb_object_keys(v_entry->'after') key)
       or jsonb_typeof(v_entry->'evidence_ids') <> 'array' or jsonb_array_length(v_entry->'evidence_ids') = 0
       or jsonb_typeof(v_entry->'finding_ids') <> 'array' or jsonb_array_length(v_entry->'finding_ids') = 0 then
      raise exception 'before and after must contain identical non-empty fields and evidence';
    end if;
    for v_key, v_value in select key, value from jsonb_each(v_entry->'before') loop
      if v_key <> all(v_allowed) or not fontagit._audit_manifest_value_valid(v_key, v_value)
         or not fontagit._audit_manifest_value_valid(v_key, v_entry->'after'->v_key) then
        raise exception 'manifest field or value is invalid: %', v_key;
      end if;
    end loop;
    select fs.font_id into v_font_id from fontagit.font_sources fs
      where fs.provider=v_entry#>>'{source_key,provider}' and fs.provider_record_id=v_entry#>>'{source_key,provider_record_id}';
    get diagnostics v_count = row_count;
    if v_count <> 1 then raise exception 'stable source key must resolve exactly one font'; end if;
    perform 1 from fontagit.fonts where id=v_font_id for update;
    select * into v_existing from fontagit.fonts where id=v_font_id;
    if to_jsonb(v_existing.slug) is distinct from v_entry#>'{current,slug}'
       or (not (v_entry->'before'?'name_en') and coalesce(to_jsonb(v_existing.name_en),'null'::jsonb) is distinct from v_entry#>'{current,name_en}')
       or (not (v_entry->'before'?'name_ko') and coalesce(to_jsonb(v_existing.name_ko),'null'::jsonb) is distinct from v_entry#>'{current,name_ko}')
       or (not (v_entry->'before'?'foundry') and coalesce(to_jsonb(v_existing.foundry),'null'::jsonb) is distinct from v_entry#>'{current,foundry}')
       or coalesce(to_jsonb(v_existing.source_tier),'null'::jsonb) is distinct from v_entry#>'{current,source_tier}'
       or to_jsonb(v_existing.official_url) is distinct from v_entry#>'{current,official_url}'
       or to_jsonb(v_existing.status) is distinct from v_entry#>'{current,status}' then
      raise exception 'current identity precondition mismatch';
    end if;
    if not v_rollback and v_existing.updated_at is distinct from (v_entry->>'expected_updated_at')::timestamptz then
      raise exception 'stale updated_at';
    end if;
    for v_key, v_value in select key, value from jsonb_each(v_entry->'before') loop
      if fontagit._audit_font_value(v_font_id,v_key) is distinct from v_value then raise exception 'stale before value'; end if;
    end loop;

    if (select count(*) from jsonb_array_elements_text(v_entry->'evidence_ids') as evidence_id(value)
        join jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') as snapshot(value) on snapshot.value->>'id'=evidence_id.value)
       <> jsonb_array_length(v_entry->'evidence_ids')
       or (select count(*) from jsonb_array_elements_text(v_entry->'finding_ids') as finding_id(value)
        join jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') as finding(value) on finding.value->>'id'=finding_id.value)
       <> jsonb_array_length(v_entry->'finding_ids') then raise exception 'entry evidence reference is missing'; end if;

    for v_finding in select f from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') f
      where f->>'id' in (select jsonb_array_elements_text(v_entry->'finding_ids')) loop
      if not fontagit._audit_manifest_approval_metadata_valid(v_finding) then
        raise exception 'approval metadata is invalid';
      end if;
      if (v_finding->>'run_id')::uuid <> (v_manifest->>'run_id')::uuid
         or v_finding#>>'{source_key,provider}' <> v_entry#>>'{source_key,provider}'
         or v_finding#>>'{source_key,provider_record_id}' <> v_entry#>>'{source_key,provider_record_id}'
         or not (v_entry->'after' ? (v_finding->>'field_name'))
         or (case when v_rollback then v_entry->'after' else v_entry->'before' end)->(v_finding->>'field_name') is distinct from v_finding->'before_value'
         or (case when v_rollback then v_entry->'before' else v_entry->'after' end)->(v_finding->>'field_name') is distinct from v_finding->'proposed_value'
         or not (v_entry->'evidence_ids' ? (v_finding->>'evidence_id')) then
        raise exception 'finding does not authorize entry field';
      end if;
      select s into v_snapshot from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') s where s->>'id'=v_finding->>'evidence_id';
      if v_snapshot is null or v_snapshot#>>'{source_key,provider}' <> v_entry#>>'{source_key,provider}'
         or v_snapshot#>>'{source_key,provider_record_id}' <> v_entry#>>'{source_key,provider_record_id}'
         or v_snapshot->>'provider' <> v_entry#>>'{source_key,provider}'
         or v_snapshot->>'provider_record_id' <> v_entry#>>'{source_key,provider_record_id}' then
        raise exception 'finding evidence does not match run/font/source';
      end if;
      v_key := v_finding->>'field_name';
      -- 이슈 #131: foundry/foundry_url/download_url/download_source_kind/license_source_url은
      -- 눈누 font-file-script metadata 또는 Tier A(google-fonts) metadata를 reference
      -- 신뢰도로 허용한다(tags/weights의 눈누 예외와 같은 수준). legal 필드(allow_*)와
      -- license_source_kind는 이 우회 대상이 아니다(사람 게이트 유지).
      -- 이슈 #133: Tier A 스냅샷은 archive로 저장하므로 public과 함께 허용한다
      -- (provider=google-fonts + evidence_role=tier-a-metadata-pb 마커로 판정).
      if v_key in ('foundry','foundry_url','download_url','download_source_kind','license_source_url')
         and v_snapshot->>'document_kind'='metadata'
         and (
           (v_snapshot->>'source_kind'='noonnu' and v_snapshot#>>'{extracted,evidence_role}'='font-file-script')
           or (v_snapshot->>'source_kind' in ('public','archive') and v_snapshot->>'provider'='google-fonts'
               and v_snapshot#>>'{extracted,evidence_role}'='tier-a-metadata-pb')
         )
         and v_finding->>'confidence'='reference' then
        continue;
      end if;
      if (v_key like 'download_%' and (v_snapshot->>'document_kind'<>'download' or v_snapshot->>'source_kind' not in ('official','public')))
         or ((v_key like 'license_%' or v_key in ('allow_commercial','allow_font_sale','allow_embedding','allow_redistribute','allow_modify','attribution_requirement','is_commercial_free'))
             and (v_snapshot->>'document_kind'<>'license' or v_snapshot->>'source_kind' not in ('official','public')))
         or (v_key in ('subsets','script_status','script_checked_at','script_evidence_id') and not (
               (v_snapshot->>'document_kind'='metadata' and v_snapshot->>'source_kind' in ('official','public')
                and v_finding->>'confidence'=v_snapshot->>'source_kind')
               or (v_snapshot->>'document_kind'='metadata' and v_snapshot->>'source_kind'='noonnu'
                   and v_snapshot#>>'{extracted,evidence_role}'='font-file-script'
                   and v_finding->>'confidence'='reference')
             ))
         or (v_key in ('tags','weights') and not (
               (v_snapshot->>'document_kind'='metadata' and v_snapshot->>'source_kind' in ('official','public')
                and v_finding->>'confidence'=v_snapshot->>'source_kind')
               or (v_snapshot->>'document_kind'='metadata' and v_snapshot->>'source_kind'='noonnu'
                   and v_snapshot#>>'{extracted,evidence_role}'='font-file-script'
                   and v_finding->>'confidence'='reference')
             )) then
        raise exception 'evidence document/source kind mismatch';
      end if;
      if (v_key not in ('subsets','script_status','script_checked_at','script_evidence_id','tags','weights')
          and v_finding->>'confidence' <> v_snapshot->>'source_kind')
         or (v_key in ('foundry','foundry_url','name_en','name_ko','category_ko','variants')
             and (v_snapshot->>'document_kind'<>'metadata' or v_snapshot->>'source_kind' not in ('official','public'))) then
        raise exception 'metadata evidence is not official or public';
      end if;
    end loop;
    if exists (
      select jsonb_array_elements_text(v_entry->'evidence_ids')
      except
      select f->>'evidence_id' from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') f
        where f->>'id' in (select jsonb_array_elements_text(v_entry->'finding_ids'))
    ) or exists (
      select f->>'evidence_id' from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') f
        where f->>'id' in (select jsonb_array_elements_text(v_entry->'finding_ids'))
      except
      select jsonb_array_elements_text(v_entry->'evidence_ids')
    ) then raise exception 'entry evidence_ids do not exactly match finding evidence'; end if;
    if (select count(*) from jsonb_object_keys(v_entry->'after') k where k <> 'license_verified')
       <> jsonb_array_length(v_entry->'finding_ids')
       or ((v_entry->'after' ? 'license_verified') and not (v_entry->'after' ? 'license_status')) then
      raise exception 'every changed field requires one approved finding';
    end if;
    insert into pg_temp.font_audit_targets values (v_font_id,v_entry);
  end loop;

  -- 기존 UUID는 모든 저장 컬럼이 같을 때만 재사용한다. finding status의 applied만 정상 전이로 본다.
  if exists(select 1 from fontagit.font_audit_runs r where r.id=(v_run->>'id')::uuid and (
      r.stage is distinct from v_run->>'stage' or r.target_environment is distinct from v_run->>'target_environment'
      or r.target_count is distinct from (v_run->>'target_count')::integer or r.success_count is distinct from (v_run->>'success_count')::integer
      or r.verified_count is distinct from (v_run->>'verified_count')::integer or r.review_count is distinct from (v_run->>'review_count')::integer
      or r.broken_count is distinct from (v_run->>'broken_count')::integer or r.parser_version is distinct from v_run->>'parser_version'
      or r.baseline_sha256 is distinct from v_run->>'baseline_sha256' or r.manifest_sha256 is distinct from nullif(v_run->>'manifest_sha256','')
      or r.dry_run is distinct from (v_run->>'dry_run')::boolean or r.status is distinct from v_run->>'status'
      or r.started_at is distinct from (v_run->>'started_at')::timestamptz
      or r.finished_at is distinct from nullif(v_run->>'finished_at','')::timestamptz)) then raise exception 'run UUID content conflict'; end if;

  for v_snapshot in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') loop
    perform fontagit._audit_manifest_exact_keys(v_snapshot,
      array['id','run_id','provider','provider_record_id','source_kind','document_kind','request_url','final_url','http_status','raw_text','raw_sha256','normalized_sha256','extracted','evidence_locations','extraction_rule_id','parser_version','collected_at','source_key'], 'snapshot');
    perform fontagit._audit_manifest_exact_keys(v_snapshot->'source_key', array['provider','provider_record_id'], 'snapshot.source_key');
    select font_id into v_font_id from pg_temp.font_audit_targets where entry#>>'{source_key,provider}'=v_snapshot#>>'{source_key,provider}' and entry#>>'{source_key,provider_record_id}'=v_snapshot#>>'{source_key,provider_record_id}';
    if v_font_id is null then raise exception 'snapshot source key is not targeted'; end if;
    if exists(select 1 from fontagit.font_source_snapshots s where s.id=(v_snapshot->>'id')::uuid and (
      s.font_id is distinct from v_font_id
      or s.provider is distinct from v_snapshot->>'provider' or s.provider_record_id is distinct from v_snapshot->>'provider_record_id'
      or s.source_kind is distinct from v_snapshot->>'source_kind' or s.document_kind is distinct from v_snapshot->>'document_kind'
      or s.request_url is distinct from v_snapshot->>'request_url' or s.final_url is distinct from v_snapshot->>'final_url'
      or s.http_status is distinct from nullif(v_snapshot->>'http_status','')::integer or s.raw_text is distinct from v_snapshot->>'raw_text'
      or s.raw_sha256 is distinct from v_snapshot->>'raw_sha256' or s.normalized_sha256 is distinct from v_snapshot->>'normalized_sha256'
      or coalesce(s.extracted,'null'::jsonb) is distinct from coalesce(v_snapshot->'extracted','null'::jsonb)
      or coalesce(s.evidence_locations,'null'::jsonb) is distinct from coalesce(v_snapshot->'evidence_locations','null'::jsonb)
      or s.extraction_rule_id is distinct from v_snapshot->>'extraction_rule_id' or s.parser_version is distinct from v_snapshot->>'parser_version'
      or s.collected_at is distinct from (v_snapshot->>'collected_at')::timestamptz)) then raise exception 'snapshot UUID content conflict: id=%', v_snapshot->>'id'; end if;
  end loop;
  for v_finding in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') loop
    perform fontagit._audit_manifest_exact_keys(v_finding,
      array['id','run_id','field_name','before_value','proposed_value','evidence_id','confidence','auto_applicable','review_reason','status','reviewed_by','reviewed_at','source_key'], 'finding');
    perform fontagit._audit_manifest_exact_keys(v_finding->'source_key', array['provider','provider_record_id'], 'finding.source_key');
    if not fontagit._audit_manifest_approval_metadata_valid(v_finding) then raise exception 'approval metadata is invalid'; end if;
    select font_id into v_font_id from pg_temp.font_audit_targets where entry#>>'{source_key,provider}'=v_finding#>>'{source_key,provider}' and entry#>>'{source_key,provider_record_id}'=v_finding#>>'{source_key,provider_record_id}';
    if exists(select 1 from fontagit.font_audit_findings f where f.id=(v_finding->>'id')::uuid and (
      f.run_id is distinct from (v_finding->>'run_id')::uuid or f.font_id is distinct from v_font_id
      or f.field_name is distinct from v_finding->>'field_name'
      or coalesce(f.before_value,'null'::jsonb) is distinct from coalesce(v_finding->'before_value','null'::jsonb)
      or coalesce(f.proposed_value,'null'::jsonb) is distinct from coalesce(v_finding->'proposed_value','null'::jsonb)
      or f.evidence_id is distinct from (v_finding->>'evidence_id')::uuid
      or f.confidence is distinct from v_finding->>'confidence' or f.auto_applicable is distinct from (v_finding->>'auto_applicable')::boolean
      or f.review_reason is distinct from v_finding->>'review_reason' or f.status not in ('approved','applied')
      or f.reviewed_by is distinct from v_finding->>'reviewed_by' or f.reviewed_at is distinct from (v_finding->>'reviewed_at')::timestamptz)) then raise exception 'finding UUID content conflict: id=%, field=%', v_finding->>'id', v_finding->>'field_name'; end if;
  end loop;

  insert into fontagit.font_audit_runs(id,stage,target_environment,target_count,success_count,verified_count,review_count,broken_count,parser_version,baseline_sha256,manifest_sha256,dry_run,status,started_at,finished_at)
  values((v_run->>'id')::uuid,v_run->>'stage',v_run->>'target_environment',(v_run->>'target_count')::integer,(v_run->>'success_count')::integer,(v_run->>'verified_count')::integer,(v_run->>'review_count')::integer,(v_run->>'broken_count')::integer,v_run->>'parser_version',v_run->>'baseline_sha256',nullif(v_run->>'manifest_sha256',''),(v_run->>'dry_run')::boolean,v_run->>'status',(v_run->>'started_at')::timestamptz,nullif(v_run->>'finished_at','')::timestamptz)
  on conflict (id) do nothing;
  for v_snapshot in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') loop
    select font_id into v_font_id from pg_temp.font_audit_targets where entry#>>'{source_key,provider}'=v_snapshot#>>'{source_key,provider}' and entry#>>'{source_key,provider_record_id}'=v_snapshot#>>'{source_key,provider_record_id}';
    insert into fontagit.font_source_snapshots(id,run_id,font_id,provider,provider_record_id,source_kind,document_kind,request_url,final_url,http_status,raw_text,raw_sha256,normalized_sha256,extracted,evidence_locations,extraction_rule_id,parser_version,collected_at)
    values((v_snapshot->>'id')::uuid,(v_run->>'id')::uuid,v_font_id,v_snapshot->>'provider',v_snapshot->>'provider_record_id',v_snapshot->>'source_kind',v_snapshot->>'document_kind',v_snapshot->>'request_url',v_snapshot->>'final_url',nullif(v_snapshot->>'http_status','')::integer,v_snapshot->>'raw_text',v_snapshot->>'raw_sha256',v_snapshot->>'normalized_sha256',nullif(v_snapshot->'extracted','null'::jsonb),nullif(v_snapshot->'evidence_locations','null'::jsonb),v_snapshot->>'extraction_rule_id',v_snapshot->>'parser_version',(v_snapshot->>'collected_at')::timestamptz) on conflict(id) do nothing;
  end loop;
  for v_finding in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') loop
    select font_id into v_font_id from pg_temp.font_audit_targets where entry#>>'{source_key,provider}'=v_finding#>>'{source_key,provider}' and entry#>>'{source_key,provider_record_id}'=v_finding#>>'{source_key,provider_record_id}';
    insert into fontagit.font_audit_findings(id,run_id,font_id,field_name,before_value,proposed_value,evidence_id,confidence,auto_applicable,review_reason,status,reviewed_by,reviewed_at)
    values((v_finding->>'id')::uuid,(v_finding->>'run_id')::uuid,v_font_id,v_finding->>'field_name',nullif(v_finding->'before_value','null'::jsonb),nullif(v_finding->'proposed_value','null'::jsonb),(v_finding->>'evidence_id')::uuid,v_finding->>'confidence',(v_finding->>'auto_applicable')::boolean,v_finding->>'review_reason','approved',v_finding->>'reviewed_by',(v_finding->>'reviewed_at')::timestamptz) on conflict(id) do nothing;
  end loop;

  for v_font_id,v_entry in select font_id,entry from pg_temp.font_audit_targets loop
    update fontagit.fonts f set
      foundry=case when v_entry->'after'?'foundry' then v_entry#>>'{after,foundry}' else f.foundry end,
      foundry_url=case when v_entry->'after'?'foundry_url' then v_entry#>>'{after,foundry_url}' else f.foundry_url end,
      download_url=case when v_entry->'after'?'download_url' then v_entry#>>'{after,download_url}' else f.download_url end,
      license_source_url=case when v_entry->'after'?'license_source_url' then v_entry#>>'{after,license_source_url}' else f.license_source_url end,
      official_url=case when v_entry->'after'?'official_url' then v_entry#>>'{after,official_url}' else f.official_url end,
      license_summary=case when v_entry->'after'?'license_summary' then v_entry#>>'{after,license_summary}' else f.license_summary end,
      download_source_kind=case when v_entry->'after'?'download_source_kind' then v_entry#>>'{after,download_source_kind}' else f.download_source_kind end,
      license_source_kind=case when v_entry->'after'?'license_source_kind' then v_entry#>>'{after,license_source_kind}' else f.license_source_kind end,
      download_evidence_id=case when v_entry->'after'?'download_evidence_id' then nullif(v_entry#>>'{after,download_evidence_id}','')::uuid else f.download_evidence_id end,
      license_evidence_id=case when v_entry->'after'?'license_evidence_id' then nullif(v_entry#>>'{after,license_evidence_id}','')::uuid else f.license_evidence_id end,
      download_status=case when v_entry->'after'?'download_status' then v_entry#>>'{after,download_status}' else f.download_status end,
      license_status=case when v_entry->'after'?'license_status' then v_entry#>>'{after,license_status}' else f.license_status end,
      download_checked_at=case when v_entry->'after'?'download_checked_at' then nullif(v_entry#>>'{after,download_checked_at}','')::timestamptz else f.download_checked_at end,
      license_checked_at=case when v_entry->'after'?'license_checked_at' then nullif(v_entry#>>'{after,license_checked_at}','')::timestamptz else f.license_checked_at end,
      allow_commercial=case when v_entry->'after'?'allow_commercial' then v_entry#>>'{after,allow_commercial}' else f.allow_commercial end,
      allow_font_sale=case when v_entry->'after'?'allow_font_sale' then v_entry#>>'{after,allow_font_sale}' else f.allow_font_sale end,
      allow_embedding=case when v_entry->'after'?'allow_embedding' then v_entry#>>'{after,allow_embedding}' else f.allow_embedding end,
      allow_redistribute=case when v_entry->'after'?'allow_redistribute' then v_entry#>>'{after,allow_redistribute}' else f.allow_redistribute end,
      allow_modify=case when v_entry->'after'?'allow_modify' then v_entry#>>'{after,allow_modify}' else f.allow_modify end,
      attribution_requirement=case when v_entry->'after'?'attribution_requirement' then v_entry#>>'{after,attribution_requirement}' else f.attribution_requirement end,
      is_commercial_free=case when v_entry->'after'?'is_commercial_free' then (v_entry#>>'{after,is_commercial_free}')::boolean else f.is_commercial_free end,
      license_verified=case when v_entry->'after'?'license_verified' then (v_entry#>>'{after,license_verified}')::boolean else f.license_verified end,
      name_en=case when v_entry->'after'?'name_en' then v_entry#>>'{after,name_en}' else f.name_en end,
      name_ko=case when v_entry->'after'?'name_ko' then v_entry#>>'{after,name_ko}' else f.name_ko end,
      category_ko=case when v_entry->'after'?'category_ko' then v_entry#>>'{after,category_ko}' else f.category_ko end,
      tags=case when v_entry->'after'?'tags' then array(select jsonb_array_elements_text(v_entry#>'{after,tags}')) else f.tags end,
      weights=case when v_entry->'after'?'weights' then array(select jsonb_array_elements_text(v_entry#>'{after,weights}'))::integer[] else f.weights end,
      variants=case when v_entry->'after'?'variants' then array(select jsonb_array_elements_text(v_entry#>'{after,variants}')) else f.variants end,
      subsets=case when v_entry->'after'?'subsets' then array(select jsonb_array_elements_text(v_entry#>'{after,subsets}')) else f.subsets end,
      script_status=case when v_entry->'after'?'script_status' then v_entry#>>'{after,script_status}' else f.script_status end,
      script_checked_at=case when v_entry->'after'?'script_checked_at' then nullif(v_entry#>>'{after,script_checked_at}','')::timestamptz else f.script_checked_at end,
      script_evidence_id=case when v_entry->'after'?'script_evidence_id' then nullif(v_entry#>>'{after,script_evidence_id}','')::uuid else f.script_evidence_id end,
      updated_at=now() where f.id=v_font_id;
    get diagnostics v_rows = row_count; v_updated := v_updated + v_rows;
  end loop;

  if not v_rollback then update fontagit.font_audit_findings set status='applied' where run_id=(v_manifest->>'run_id')::uuid and id in (select jsonb_array_elements_text(entry->'finding_ids')::uuid from pg_temp.font_audit_targets); end if;
  return v_updated;
end;
$$;
