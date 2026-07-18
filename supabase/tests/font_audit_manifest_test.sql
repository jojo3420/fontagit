-- 0018은 로컬 임시 PostgreSQL에서만 실행한다. 원격 DB에는 적용하지 않는다.
begin;
set local request.jwt.claim.role = 'service_role';

truncate fontagit.font_audit_findings, fontagit.font_source_snapshots,
  fontagit.font_audit_runs, fontagit.font_sources, fontagit.fonts cascade;

insert into fontagit.fonts(id,slug,name_en,name_ko,category_ko,source_tier,official_url,status,license_verified,license_status)
values
 ('00000000-0000-0000-0000-000000001001','audit-one','Audit One','감사 하나','고딕','B','https://example.test/one','published',true,'pending'),
 ('00000000-0000-0000-0000-000000001002','audit-two','Audit Two','감사 둘','고딕','B','https://example.test/two','published',true,'pending');
insert into fontagit.font_sources(font_id,provider,provider_record_id,source_role,source_url) values
 ('00000000-0000-0000-0000-000000001001','noonnu','1001','reference','https://noonnu.cc/font_page/1001'),
 ('00000000-0000-0000-0000-000000001002','noonnu','1002','reference','https://noonnu.cc/font_page/1002');

create function pg_temp.manifest(p_run uuid, p_reverse boolean default false)
returns jsonb language sql as $$
  with f as (select * from fontagit.fonts where slug in ('audit-one','audit-two') order by slug),
  r as (select jsonb_build_object(
    'id',p_run,'stage','legal','target_environment','dev','target_count',2,
    'success_count',2,'verified_count',0,'review_count',2,'broken_count',0,
    'parser_version','test-v1','baseline_sha256',repeat('a',64),'manifest_sha256',null,
    'dry_run',true,'status','completed','started_at','2026-07-18T00:00:00+00:00',
    'finished_at','2026-07-18T00:01:00+00:00') run),
  s as (select jsonb_agg(jsonb_build_object(
    'id',case slug when 'audit-one' then '00000000-0000-0000-0000-000000001201' else '00000000-0000-0000-0000-000000001202' end,
    'run_id',p_run,'provider','noonnu','provider_record_id',case slug when 'audit-one' then '1001' else '1002' end,
    'source_kind','official','document_kind',case slug when 'audit-one' then 'download' else 'metadata' end,'request_url',official_url,'final_url',official_url,
    'http_status',200,'raw_text',null,'raw_sha256',case slug when 'audit-one' then repeat('b',64) else repeat('c',64) end,
    'normalized_sha256',case slug when 'audit-one' then repeat('d',64) else repeat('e',64) end,
    'extracted','{}'::jsonb,'evidence_locations','{}'::jsonb,'extraction_rule_id',null,'parser_version','test-v1',
    'collected_at','2026-07-18T00:00:00+00:00','source_key',jsonb_build_object('provider','noonnu','provider_record_id',case slug when 'audit-one' then '1001' else '1002' end)) order by slug) snapshots from f),
  q as (select jsonb_agg(jsonb_build_object(
    'id',case slug when 'audit-one' then '00000000-0000-0000-0000-000000001301' else '00000000-0000-0000-0000-000000001302' end,
    'run_id',p_run,'field_name',case slug when 'audit-one' then 'download_url' else 'script_status' end,
    'before_value',case slug when 'audit-one' then 'null'::jsonb else '"pending"'::jsonb end,
    'proposed_value',case slug when 'audit-one' then '"https://downloads.example/audit-one.zip"'::jsonb else '"needs_review"'::jsonb end,
    'evidence_id',case slug when 'audit-one' then '00000000-0000-0000-0000-000000001201' else '00000000-0000-0000-0000-000000001202' end,
    'confidence','official','auto_applicable',false,'review_reason','human approved','status','approved',
    'reviewed_by','reviewer','reviewed_at','2026-07-18T00:02:00+00:00',
    'source_key',jsonb_build_object('provider','noonnu','provider_record_id',case slug when 'audit-one' then '1001' else '1002' end)) order by slug) findings from f),
  e as (select jsonb_agg(jsonb_build_object(
    'source_key',jsonb_build_object('provider','noonnu','provider_record_id',case slug when 'audit-one' then '1001' else '1002' end),
    'current',jsonb_build_object('slug',slug,'name_en',name_en,'name_ko',name_ko,'foundry',foundry,'source_tier',source_tier,'official_url',official_url,'status',status),
    'before',case when not p_reverse and slug='audit-one' then jsonb_build_object('download_url',null)
                  when not p_reverse then jsonb_build_object('script_status','pending')
                  when slug='audit-one' then jsonb_build_object('download_url','https://downloads.example/audit-one.zip')
                  else jsonb_build_object('script_status','needs_review') end,
    'after',case when not p_reverse and slug='audit-one' then jsonb_build_object('download_url','https://downloads.example/audit-one.zip')
                 when not p_reverse then jsonb_build_object('script_status','needs_review')
                 when slug='audit-one' then jsonb_build_object('download_url',null)
                 else jsonb_build_object('script_status','pending') end,
    'evidence_ids',jsonb_build_array(case slug when 'audit-one' then '00000000-0000-0000-0000-000000001201' else '00000000-0000-0000-0000-000000001202' end),
    'finding_ids',jsonb_build_array(case slug when 'audit-one' then '00000000-0000-0000-0000-000000001301' else '00000000-0000-0000-0000-000000001302' end),
    'expected_updated_at',updated_at) order by slug) entries from f)
  select jsonb_build_object('schema_version',1,'run_id',p_run,'baseline_sha256',repeat('a',64),'generated_at','2026-07-18T00:01:00+00:00','rollback_mode',p_reverse,
    'evidence_bundle',jsonb_build_object('run',(select run from r),'snapshots',(select snapshots from s),'findings',(select findings from q)),'entries',(select entries from e));
$$;

-- 승인 finding과 snapshot이 모두 있는 정상 문서만 2건을 바꾼다.
do $$
declare v jsonb:=pg_temp.manifest('00000000-0000-0000-0000-000000001100'); v_text text; v_hash text;
begin
  v_text:=v::text; v_hash:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  if fontagit.apply_font_audit_manifest(v_text,v_hash,1)<>2 then raise exception 'normal apply failed'; end if;
  if (select count(*) from fontagit.font_source_snapshots)<>2 or (select count(*) from fontagit.font_audit_findings where status='applied')<>2
     or not exists(select 1 from fontagit.fonts where slug='audit-two' and script_status='needs_review') then raise exception 'approved evidence did not apply'; end if;
end;
$$;

-- 역방향은 forward after 전체와 일치할 때만 원래 값으로 복원한다.
do $$
declare v jsonb:=pg_temp.manifest('00000000-0000-0000-0000-000000001100',true); v_text text; v_hash text;
begin
  v_text:=v::text; v_hash:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex'); perform fontagit.apply_font_audit_manifest(v_text,v_hash,1);
  if exists(select 1 from fontagit.fonts where (slug='audit-one' and download_url is not null) or (slug='audit-two' and script_status<>'pending')) then raise exception 'reverse did not restore every field'; end if;
end;
$$;

-- finding 하나라도 없거나 승인되지 않았거나, UUID 내용이 다르면 evidence/font/finding 어느 것도 부분 적용하지 않는다.
do $$
declare v jsonb; v_text text; v_hash text; v_before int;
begin
  select count(*) into v_before from fontagit.font_source_snapshots;
  v:=pg_temp.manifest('00000000-0000-0000-0000-000000001101'); v:=jsonb_set(v,'{evidence_bundle,findings}','[]'::jsonb); v_text:=v::text; v_hash:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  begin perform fontagit.apply_font_audit_manifest(v_text,v_hash,1); raise exception 'missing finding should fail'; exception when others then null; end;
  if (select count(*) from fontagit.font_source_snapshots)<>v_before then raise exception 'missing finding wrote evidence'; end if;
  v:=pg_temp.manifest('00000000-0000-0000-0000-000000001102'); v:=jsonb_set(v,'{evidence_bundle,snapshots,0,final_url}','"https://different.example"'::jsonb); v_text:=v::text; v_hash:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  begin perform fontagit.apply_font_audit_manifest(v_text,v_hash,1); raise exception 'snapshot collision should fail'; exception when others then if sqlerrm not like '%snapshot UUID content conflict%' then raise; end if; end;
  if (select count(*) from fontagit.font_source_snapshots)<>v_before or exists(select 1 from fontagit.fonts where download_url is not null or script_status<>'pending') then raise exception 'failed evidence manifest partially applied'; end if;
end;
$$;

-- bootstrap도 unknown/duplicate provider key를 쓰기 전에 전부 거부한다.
insert into fontagit.fonts(id,slug,name_en,name_ko,category_ko,source_tier,official_url,status,license_verified,license_status) values
 ('00000000-0000-0000-0000-000000001003','bootstrap-one','Bootstrap One','연결 하나','고딕','B','https://example.test/three','draft',false,'pending'),
 ('00000000-0000-0000-0000-000000001004','bootstrap-two','Bootstrap Two','연결 둘','고딕','B','https://example.test/four','draft',false,'pending');
do $$
declare v jsonb; v_text text; v_hash text;
begin
  select jsonb_build_object('schema_version',1,'matched',2,'unmatched',0,'conflicts',0,'review_rows','[]'::jsonb,'entries',jsonb_agg(jsonb_build_object(
    'font_id',id,'slug',slug,'provider','noonnu','provider_record_id',case slug when 'bootstrap-one' then '2001' else '2002' end,'source_url','https://noonnu.cc/font_page/x',
    'before',jsonb_build_object('source_tier',source_tier,'slug',slug,'name_en',name_en,'name_ko',name_ko,'official_url',official_url,'foundry',foundry,'updated_at',updated_at),'public_updates','{}'::jsonb))) into v from fontagit.fonts where slug like 'bootstrap-%';
  v:=jsonb_set(v,'{entries,1,provider_record_id}','"2001"'::jsonb); v_text:=v::text; v_hash:=encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  begin perform fontagit.apply_font_source_bootstrap(v_text,v_hash,1); raise exception 'duplicate bootstrap should fail'; exception when others then if sqlerrm not like '%bootstrap duplicate key%' then raise; end if; end;
  if exists(select 1 from fontagit.font_sources where provider_record_id in ('2001','2002')) then raise exception 'bootstrap duplicate partially wrote'; end if;
end;
$$;

select 'ALL PASS' as result;
rollback;
