-- 증거(스냅샷)를 콘텐츠 기준으로 통일: dedup 재사용으로 타 run 스냅샷이 증거가 되므로
-- run_id는 최초 수집 provenance일 뿐 정합성 기준이 아님. RPC 삽입은 매니페스트 run으로 기록.
-- 컬렉션 0단계: 눈누 폰트파일에서 추출한 tags/weights는 noonnu metadata font-file-script 증거로 reference 신뢰도 허용.
-- 변경: (a) content-conflict 검사에서 run_id 비교 제거 (b) INSERT에서 run_id를 매니페스트 run으로 (c) tags/weights 눈누 증거 경로 허용

create or replace function fontagit.apply_font_audit_manifest(
  p_manifest_text text, p_expected_sha256 text, p_schema_version integer
) returns integer language plpgsql security definer set search_path = '' as $$
declare
  v_manifest jsonb; v_entry jsonb; v_snapshot jsonb; v_finding jsonb;
  v_run jsonb; v_font_id uuid; v_key text; v_value jsonb; v_count integer;
  v_updated integer := 0; v_rows integer; v_rollback boolean; v_existing record;
  v_allowed constant text[] := array[
    'foundry','foundry_url','download_url','license_source_url','license_summary',
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
      or s.extracted is distinct from v_snapshot->'extracted' or s.evidence_locations is distinct from v_snapshot->'evidence_locations'
      or s.extraction_rule_id is distinct from v_snapshot->>'extraction_rule_id' or s.parser_version is distinct from v_snapshot->>'parser_version'
      or s.collected_at is distinct from (v_snapshot->>'collected_at')::timestamptz)) then raise exception 'snapshot UUID content conflict'; end if;
  end loop;
  for v_finding in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') loop
    perform fontagit._audit_manifest_exact_keys(v_finding,
      array['id','run_id','field_name','before_value','proposed_value','evidence_id','confidence','auto_applicable','review_reason','status','reviewed_by','reviewed_at','source_key'], 'finding');
    perform fontagit._audit_manifest_exact_keys(v_finding->'source_key', array['provider','provider_record_id'], 'finding.source_key');
    if not fontagit._audit_manifest_approval_metadata_valid(v_finding) then raise exception 'approval metadata is invalid'; end if;
    select font_id into v_font_id from pg_temp.font_audit_targets where entry#>>'{source_key,provider}'=v_finding#>>'{source_key,provider}' and entry#>>'{source_key,provider_record_id}'=v_finding#>>'{source_key,provider_record_id}';
    if exists(select 1 from fontagit.font_audit_findings f where f.id=(v_finding->>'id')::uuid and (
      f.run_id is distinct from (v_finding->>'run_id')::uuid or f.font_id is distinct from v_font_id
      or f.field_name is distinct from v_finding->>'field_name' or f.before_value is distinct from v_finding->'before_value'
      or f.proposed_value is distinct from v_finding->'proposed_value' or f.evidence_id is distinct from (v_finding->>'evidence_id')::uuid
      or f.confidence is distinct from v_finding->>'confidence' or f.auto_applicable is distinct from (v_finding->>'auto_applicable')::boolean
      or f.review_reason is distinct from v_finding->>'review_reason' or f.status not in ('approved','applied')
      or f.reviewed_by is distinct from v_finding->>'reviewed_by' or f.reviewed_at is distinct from (v_finding->>'reviewed_at')::timestamptz)) then raise exception 'finding UUID content conflict'; end if;
  end loop;

  insert into fontagit.font_audit_runs(id,stage,target_environment,target_count,success_count,verified_count,review_count,broken_count,parser_version,baseline_sha256,manifest_sha256,dry_run,status,started_at,finished_at)
  values((v_run->>'id')::uuid,v_run->>'stage',v_run->>'target_environment',(v_run->>'target_count')::integer,(v_run->>'success_count')::integer,(v_run->>'verified_count')::integer,(v_run->>'review_count')::integer,(v_run->>'broken_count')::integer,v_run->>'parser_version',v_run->>'baseline_sha256',nullif(v_run->>'manifest_sha256',''),(v_run->>'dry_run')::boolean,v_run->>'status',(v_run->>'started_at')::timestamptz,nullif(v_run->>'finished_at','')::timestamptz)
  on conflict (id) do nothing;
  for v_snapshot in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,snapshots}') loop
    select font_id into v_font_id from pg_temp.font_audit_targets where entry#>>'{source_key,provider}'=v_snapshot#>>'{source_key,provider}' and entry#>>'{source_key,provider_record_id}'=v_snapshot#>>'{source_key,provider_record_id}';
    insert into fontagit.font_source_snapshots(id,run_id,font_id,provider,provider_record_id,source_kind,document_kind,request_url,final_url,http_status,raw_text,raw_sha256,normalized_sha256,extracted,evidence_locations,extraction_rule_id,parser_version,collected_at)
    values((v_snapshot->>'id')::uuid,(v_run->>'id')::uuid,v_font_id,v_snapshot->>'provider',v_snapshot->>'provider_record_id',v_snapshot->>'source_kind',v_snapshot->>'document_kind',v_snapshot->>'request_url',v_snapshot->>'final_url',nullif(v_snapshot->>'http_status','')::integer,v_snapshot->>'raw_text',v_snapshot->>'raw_sha256',v_snapshot->>'normalized_sha256',v_snapshot->'extracted',v_snapshot->'evidence_locations',v_snapshot->>'extraction_rule_id',v_snapshot->>'parser_version',(v_snapshot->>'collected_at')::timestamptz) on conflict(id) do nothing;
  end loop;
  for v_finding in select value from jsonb_array_elements(v_manifest#>'{evidence_bundle,findings}') loop
    select font_id into v_font_id from pg_temp.font_audit_targets where entry#>>'{source_key,provider}'=v_finding#>>'{source_key,provider}' and entry#>>'{source_key,provider_record_id}'=v_finding#>>'{source_key,provider_record_id}';
    insert into fontagit.font_audit_findings(id,run_id,font_id,field_name,before_value,proposed_value,evidence_id,confidence,auto_applicable,review_reason,status,reviewed_by,reviewed_at)
    values((v_finding->>'id')::uuid,(v_finding->>'run_id')::uuid,v_font_id,v_finding->>'field_name',v_finding->'before_value',v_finding->'proposed_value',(v_finding->>'evidence_id')::uuid,v_finding->>'confidence',(v_finding->>'auto_applicable')::boolean,v_finding->>'review_reason','approved',v_finding->>'reviewed_by',(v_finding->>'reviewed_at')::timestamptz) on conflict(id) do nothing;
  end loop;

  for v_font_id,v_entry in select font_id,entry from pg_temp.font_audit_targets loop
    update fontagit.fonts f set
      foundry=case when v_entry->'after'?'foundry' then v_entry#>>'{after,foundry}' else f.foundry end,
      foundry_url=case when v_entry->'after'?'foundry_url' then v_entry#>>'{after,foundry_url}' else f.foundry_url end,
      download_url=case when v_entry->'after'?'download_url' then v_entry#>>'{after,download_url}' else f.download_url end,
      license_source_url=case when v_entry->'after'?'license_source_url' then v_entry#>>'{after,license_source_url}' else f.license_source_url end,
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
