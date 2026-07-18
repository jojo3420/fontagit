-- 0018은 로컬 임시 PostgreSQL에서만 실행한다. 원격 DB에 적용하지 않는다.
begin;
set local request.jwt.claim.role = 'service_role';

truncate fontagit.font_audit_findings, fontagit.font_source_snapshots,
  fontagit.font_audit_runs, fontagit.font_sources, fontagit.fonts cascade;

insert into fontagit.fonts(id, slug, name_en, name_ko, category_ko, source_tier,
  official_url, status, license_verified, license_status)
values
 ('00000000-0000-0000-0000-000000001001', 'audit-one', 'Audit One', '감사 하나', '고딕', 'B', 'https://example.test/one', 'published', true, 'pending'),
 ('00000000-0000-0000-0000-000000001002', 'audit-two', 'Audit Two', '감사 둘', '고딕', 'B', 'https://example.test/two', 'published', true, 'pending');
insert into fontagit.font_sources(font_id, provider, provider_record_id, source_role, source_url) values
 ('00000000-0000-0000-0000-000000001001', 'noonnu', '1001', 'reference', 'https://noonnu.cc/font_page/1001'),
 ('00000000-0000-0000-0000-000000001002', 'noonnu', '1002', 'reference', 'https://noonnu.cc/font_page/1002');

do $$
declare v_manifest jsonb; v_text text; v_hash text; v_changed integer;
begin
  select jsonb_build_object(
    'schema_version', 1, 'run_id', '00000000-0000-0000-0000-000000001100',
    'baseline_sha256', repeat('a', 64), 'generated_at', now(),
    'rollback_mode', false,
    'evidence_bundle', jsonb_build_object(
      'run', jsonb_build_object('id','00000000-0000-0000-0000-000000001100','stage','legal','target_count',2,'parser_version','test-v1'),
      'snapshots', jsonb_build_array(
        jsonb_build_object('id','00000000-0000-0000-0000-000000001201','source_key',jsonb_build_object('provider','noonnu','provider_record_id','1001'),'provider','noonnu','provider_record_id','1001','source_kind','official','document_kind','download','request_url','https://example.test/one','final_url','https://example.test/one','http_status',200,'raw_text',null,'raw_sha256',repeat('b',64),'normalized_sha256',repeat('c',64),'extracted','{}'::jsonb,'evidence_locations','{}'::jsonb,'parser_version','test-v1','collected_at',now()),
        jsonb_build_object('id','00000000-0000-0000-0000-000000001202','source_key',jsonb_build_object('provider','noonnu','provider_record_id','1002'),'provider','noonnu','provider_record_id','1002','source_kind','official','document_kind','download','request_url','https://example.test/two','final_url','https://example.test/two','http_status',200,'raw_text',null,'raw_sha256',repeat('d',64),'normalized_sha256',repeat('e',64),'extracted','{}'::jsonb,'evidence_locations','{}'::jsonb,'parser_version','test-v1','collected_at',now())
      ), 'findings', '[]'::jsonb),
    'entries', jsonb_agg(jsonb_build_object(
      'source_key', jsonb_build_object('provider','noonnu','provider_record_id', case slug when 'audit-one' then '1001' else '1002' end),
      'before', jsonb_build_object('download_url',null,'license_status','pending','license_verified',true),
      'after', jsonb_build_object('download_url','https://downloads.example/' || slug || '.zip','license_status','needs_review','license_verified',false),
      'evidence_ids','[]'::jsonb,'expected_updated_at',updated_at))
  ) into v_manifest from fontagit.fonts;
  v_text := v_manifest::text;
  v_hash := encode(extensions.digest(convert_to(v_text, 'UTF8'), 'sha256'), 'hex');
  v_changed := fontagit.apply_font_audit_manifest(v_text, v_hash, 1);
  if v_changed <> 2 or (select count(*) from fontagit.fonts where license_status = 'needs_review' and license_verified = false) <> 2 then
    raise exception 'normal manifest apply failed';
  end if;
end;
$$;

-- 한 행 before 불일치는 예외이며 다른 행도 바뀌지 않는다.
do $$
declare v_manifest jsonb; v_text text; v_hash text; v_before integer;
begin
  select count(*) into v_before from fontagit.font_source_snapshots;
  select jsonb_build_object(
    'schema_version',1,'run_id','00000000-0000-0000-0000-000000001101','baseline_sha256',repeat('f',64),'generated_at',now(),
    'evidence_bundle',jsonb_build_object('run',jsonb_build_object('id','00000000-0000-0000-0000-000000001101','stage','legal','target_count',2,'parser_version','test-v1'),'snapshots','[]'::jsonb,'findings','[]'::jsonb),
    'entries',jsonb_agg(jsonb_build_object('source_key',jsonb_build_object('provider','noonnu','provider_record_id',case slug when 'audit-one' then '1001' else '1002' end),
      'before',jsonb_build_object('download_url',case slug when 'audit-one' then 'wrong-before' else 'https://downloads.example/audit-two.zip' end),
      'after',jsonb_build_object('download_url','https://changed.example/' || slug),'evidence_ids','[]'::jsonb,'expected_updated_at',updated_at))
  ) into v_manifest from fontagit.fonts;
  v_text := v_manifest::text; v_hash := encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  begin
    perform fontagit.apply_font_audit_manifest(v_text,v_hash,1);
    raise exception 'stale before should fail';
  exception when others then
    if sqlerrm not like '%stale before%' then raise; end if;
  end;
  if (select count(*) from fontagit.font_source_snapshots) <> v_before
    or exists(select 1 from fontagit.fonts where download_url like 'https://changed.example/%') then
    raise exception 'stale manifest changed a row';
  end if;
end;
$$;

-- reverse는 forward after와 정확히 같을 때만 두 행 모두 되돌린다.
do $$
declare v_manifest jsonb; v_text text; v_hash text;
begin
  select jsonb_build_object(
    'schema_version',1,'run_id','00000000-0000-0000-0000-000000001100','baseline_sha256',repeat('a',64),'generated_at',now(),'rollback_mode',true,
    'evidence_bundle',jsonb_build_object('run',jsonb_build_object('id','00000000-0000-0000-0000-000000001100','stage','legal','target_count',2,'parser_version','test-v1'),'snapshots','[]'::jsonb,'findings','[]'::jsonb),
    'entries',jsonb_agg(jsonb_build_object('source_key',jsonb_build_object('provider','noonnu','provider_record_id',case slug when 'audit-one' then '1001' else '1002' end),
      'before',jsonb_build_object('download_url',download_url,'license_status','needs_review','license_verified',false),
      'after',jsonb_build_object('download_url',null,'license_status','pending','license_verified',true),'evidence_ids','[]'::jsonb,'expected_updated_at',updated_at))
  ) into v_manifest from fontagit.fonts;
  v_text := v_manifest::text; v_hash := encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  perform fontagit.apply_font_audit_manifest(v_text,v_hash,1);
  if exists(select 1 from fontagit.fonts where download_url is not null or license_status <> 'pending' or license_verified <> true) then
    raise exception 'reverse manifest did not restore forward before values';
  end if;
end;
$$;

-- bootstrap은 fonts 공개값을 바꾸지 않고 2건 연결한다. provider 충돌이면 0건이다.
insert into fontagit.fonts(id,slug,name_en,name_ko,category_ko,source_tier,official_url,status,license_verified,license_status) values
 ('00000000-0000-0000-0000-000000001003','bootstrap-one','Bootstrap One','연결 하나','고딕','B','https://example.test/three','draft',false,'pending'),
 ('00000000-0000-0000-0000-000000001004','bootstrap-two','Bootstrap Two','연결 둘','고딕','B','https://example.test/four','draft',false,'pending');
do $$
declare v_manifest jsonb; v_text text; v_hash text;
begin
  select jsonb_build_object('schema_version',1,'entries',jsonb_agg(jsonb_build_object(
    'font_id',id,'provider','noonnu','provider_record_id',case slug when 'bootstrap-one' then '2001' else '2002' end,
    'source_url','https://noonnu.cc/font_page/' || case slug when 'bootstrap-one' then '2001' else '2002' end,
    'before',jsonb_build_object('source_tier',source_tier,'slug',slug,'name_en',name_en,'official_url',official_url),'public_updates','{}'::jsonb)))
  into v_manifest from fontagit.fonts where slug like 'bootstrap-%';
  v_text := v_manifest::text; v_hash := encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  if fontagit.apply_font_source_bootstrap(v_text,v_hash,1) <> 2 then raise exception 'bootstrap normal apply failed'; end if;
  if (select count(*) from fontagit.font_sources where provider_record_id in ('2001','2002')) <> 2
    or exists(select 1 from fontagit.fonts where slug like 'bootstrap-%' and foundry is not null) then raise exception 'bootstrap changed public fonts'; end if;
  v_manifest := jsonb_set(v_manifest,'{entries,1,provider_record_id}','"2001"'::jsonb);
  v_text := v_manifest::text; v_hash := encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  begin
    perform fontagit.apply_font_source_bootstrap(v_text,v_hash,1);
    raise exception 'provider collision should fail';
  exception when others then
    if sqlerrm not like '%provider key collision%' then raise; end if;
  end;
  if (select count(*) from fontagit.font_sources where provider_record_id = '2001') <> 1 then raise exception 'provider collision partially inserted'; end if;
end;
$$;

select 'ALL PASS' as result;
rollback;
