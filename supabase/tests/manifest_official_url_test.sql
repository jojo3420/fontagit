-- 0026은 로컬 임시 PostgreSQL에서만 실행한다. 원격 DB에는 적용하지 않는다.
-- #150: official_url을 apply_font_audit_manifest 정정 대상 필드로 허용한 변경의 회귀 테스트.
begin;
set local request.jwt.claims = '{"role":"service_role"}';

truncate fontagit.font_audit_findings, fontagit.font_source_snapshots,
  fontagit.font_audit_runs, fontagit.font_sources, fontagit.fonts cascade;

insert into fontagit.fonts(id,slug,name_en,name_ko,category_ko,source_tier,official_url,status,license_verified,license_status)
values
 ('00000000-0000-0000-0000-000000009001','probe-one','Probe One','프로브 하나','고딕','B','https://example.test/dirty','published',true,'pending');
insert into fontagit.font_sources(font_id,provider,provider_record_id,source_role,source_url) values
 ('00000000-0000-0000-0000-000000009001','noonnu','9001','reference','https://noonnu.cc/font_page/9001');

-- p_run/p_snapshot/p_finding을 케이스마다 바꿔서 evidence UUID 충돌을 피한다.
-- p_current_url=entry.current.official_url(잠금 대조값), p_after=entry.after.official_url(jsonb, null 가능).
create function pg_temp.official_url_manifest(
  p_run uuid, p_snapshot uuid, p_finding uuid, p_current_url text, p_after jsonb
) returns jsonb language sql as $$
  select jsonb_build_object(
    'schema_version',1,'run_id',p_run,'baseline_sha256',repeat('a',64),
    'generated_at','2026-07-29T00:01:00+00:00','rollback_mode',false,
    'evidence_bundle',jsonb_build_object(
      'run',jsonb_build_object(
        'id',p_run,'stage','legal','target_environment','dev','target_count',1,
        'success_count',1,'verified_count',0,'review_count',1,'broken_count',0,
        'parser_version','test-v1','baseline_sha256',repeat('a',64),'manifest_sha256',null,
        'dry_run',true,'status','completed','started_at','2026-07-29T00:00:00+00:00',
        'finished_at','2026-07-29T00:01:00+00:00'),
      'snapshots',jsonb_build_array(jsonb_build_object(
        'id',p_snapshot,'run_id',p_run,'provider','noonnu','provider_record_id','9001',
        'source_kind','official','document_kind','metadata',
        'request_url','https://example.test/dirty','final_url','https://example.test/dirty',
        'http_status',200,'raw_text',null,'raw_sha256',md5(p_snapshot::text||'raw'),'normalized_sha256',md5(p_snapshot::text||'norm'),
        'extracted','{}'::jsonb,'evidence_locations','{}'::jsonb,'extraction_rule_id',null,
        'parser_version','test-v1','collected_at','2026-07-29T00:00:00+00:00',
        'source_key',jsonb_build_object('provider','noonnu','provider_record_id','9001'))),
      'findings',jsonb_build_array(jsonb_build_object(
        'id',p_finding,'run_id',p_run,'field_name','official_url',
        'before_value',to_jsonb((select official_url from fontagit.fonts where slug='probe-one')),
        'proposed_value',p_after,
        'evidence_id',p_snapshot,'confidence','official','auto_applicable',false,
        'review_reason','human approved','status','approved','reviewed_by','reviewer',
        'reviewed_at','2026-07-29T00:02:00+00:00',
        'source_key',jsonb_build_object('provider','noonnu','provider_record_id','9001')))),
    'entries',jsonb_build_array(jsonb_build_object(
      'source_key',jsonb_build_object('provider','noonnu','provider_record_id','9001'),
      'current',jsonb_build_object('slug','probe-one','name_en','Probe One','name_ko','프로브 하나',
        'foundry',null,'source_tier','B','official_url',p_current_url,'status','published'),
      'before',jsonb_build_object('official_url',(select official_url from fontagit.fonts where slug='probe-one')),
      'after',jsonb_build_object('official_url',p_after),
      'evidence_ids',jsonb_build_array(p_snapshot),
      'finding_ids',jsonb_build_array(p_finding),
      'expected_updated_at',(select updated_at from fontagit.fonts where slug='probe-one')))
  );
$$;

-- case 1: 정상 교체 - v_allowed에 추가된 official_url이 실제로 UPDATE 절에 반영되는지 확인한다.
do $$
declare v jsonb; v_text text; v_hash text;
begin
  v := pg_temp.official_url_manifest(
    '00000000-0000-0000-0000-000000009101','00000000-0000-0000-0000-000000009201',
    '00000000-0000-0000-0000-000000009301','https://example.test/dirty','"https://official.example/clean"'::jsonb);
  v_text := v::text; v_hash := encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  if fontagit.apply_font_audit_manifest(v_text,v_hash,1)<>1 then raise exception 'official_url replace apply failed'; end if;
  if not exists(select 1 from fontagit.fonts where slug='probe-one' and official_url='https://official.example/clean') then
    raise exception 'official_url replace did not take effect';
  end if;
  if not exists(select 1 from fontagit.font_audit_findings where id='00000000-0000-0000-0000-000000009301' and status='applied') then
    raise exception 'official_url finding was not marked applied';
  end if;
end;
$$;

-- case 2: current mismatch 거부 - current.official_url이 실제 값(clean)과 다르면(dirty) 낙관적 잠금이 막는다.
do $$
declare v jsonb; v_text text; v_hash text; v_failed boolean := false;
begin
  v := pg_temp.official_url_manifest(
    '00000000-0000-0000-0000-000000009102','00000000-0000-0000-0000-000000009202',
    '00000000-0000-0000-0000-000000009302','https://example.test/dirty','"https://official.example/other"'::jsonb);
  v_text := v::text; v_hash := encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  begin
    perform fontagit.apply_font_audit_manifest(v_text,v_hash,1);
  exception when others then
    if sqlerrm not like '%current identity precondition mismatch%' then raise; end if;
    v_failed := true;
  end;
  if not v_failed then raise exception 'stale official_url current was accepted'; end if;
  if not exists(select 1 from fontagit.fonts where slug='probe-one' and official_url='https://official.example/clean') then
    raise exception 'mismatch case mutated official_url';
  end if;
end;
$$;

-- case 3: nullify는 _audit_manifest_value_valid의 official_url 분기(jsonb_typeof=string 요구)가
-- 먼저 명확히 거부해야 한다(회귀 고정). NOT NULL 제약 위반으로 죽는 대신 값 검증 단계에서
-- 'manifest field or value is invalid: official_url'로 잡혀야 "nullify 미지원"이 계약 수준에서 드러난다.
do $$
declare v jsonb; v_text text; v_hash text; v_failed boolean := false;
begin
  v := pg_temp.official_url_manifest(
    '00000000-0000-0000-0000-000000009103','00000000-0000-0000-0000-000000009203',
    '00000000-0000-0000-0000-000000009303','https://official.example/clean','null'::jsonb);
  v_text := v::text; v_hash := encode(extensions.digest(convert_to(v_text,'UTF8'),'sha256'),'hex');
  begin
    perform fontagit.apply_font_audit_manifest(v_text,v_hash,1);
  exception when others then
    if sqlerrm not like '%manifest field or value is invalid: official_url%' then raise; end if;
    v_failed := true;
  end;
  if not v_failed then raise exception 'official_url nullify unexpectedly passed value validation'; end if;
  if not exists(select 1 from fontagit.fonts where slug='probe-one' and official_url='https://official.example/clean') then
    raise exception 'nullify case mutated official_url despite value validation failure';
  end if;
end;
$$;

-- case 4 (tripwire): fonts.official_url이 NOT NULL이라는 전제 위에서 0026이 낙관적 잠금의
-- coalesce 정규화를 생략했다. 이 전제가 깨지면(누가 NOT NULL을 제거하면) 이 테스트가 먼저 실패해
-- "낙관적 잠금(current 대조)의 official_url 줄에 coalesce(to_jsonb(v_existing.official_url),
-- 'null'::jsonb) 정규화를 함께 넣어야 한다"는 의존성을 알려준다. to_jsonb(NULL::text)는 SQL NULL을
-- 반환하고 `NULL is distinct from X`는 항상 참이라, 정규화 없이는 official_url이 NULL인 폰트가
-- current 잠금을 영원히 통과하지 못하게 된다(#150 조사 문서가 실제로 겪었던 함정).
do $$
declare v_is_nullable text;
begin
  select is_nullable into v_is_nullable from information_schema.columns
  where table_schema='fontagit' and table_name='fonts' and column_name='official_url';
  if v_is_nullable <> 'NO' then
    raise exception 'fonts.official_url is no longer NOT NULL - add coalesce normalization to the optimistic lock and update _audit_manifest_value_valid/case-3 above before relaxing this constraint';
  end if;
end;
$$;

-- case 5: 일관성 메타 테스트. apply_font_audit_manifest 소스에서 v_allowed 배열을 그대로
-- 파싱해(하드코딩 사본이 소스와 어긋나는 것을 방지) 32개 키 전부에 대해
-- (a) _audit_font_value가 SQL NULL을 반환하지 않고(else null 경로로 안 빠짐)
-- (b) 그 값이 _audit_manifest_value_valid를 통과하는지(현재 DB 값 자체가 유효값)를 확인한다.
-- 픽스처 폰트는 관련 컬럼을 전부 채워 evidence_id/checked_at 등 nullable 필드도 실값으로 검증한다.
insert into fontagit.fonts(
  id,slug,name_en,name_ko,category_ko,source_tier,official_url,status,
  foundry,foundry_url,download_url,license_source_url,license_summary,
  download_source_kind,license_source_kind,
  download_status,license_status,download_checked_at,license_checked_at,
  allow_commercial,allow_font_sale,allow_embedding,allow_redistribute,allow_modify,
  attribution_requirement,is_commercial_free,license_verified,
  tags,weights,variants,subsets,script_status,script_checked_at
) values (
  '00000000-0000-0000-0000-000000009501','probe-meta','Probe Meta','프로브 메타','고딕','B',
  'https://official.example/meta','published',
  'Test Foundry','https://foundry.example','https://download.example/font.zip',
  'https://license.example/meta','상업적 이용 가능',
  'official','official',
  'verified','verified',now(),now(),
  'allowed','allowed','allowed','allowed','allowed',
  'required',true,true,
  array['handwriting'],array[400],array['regular'],array['korean'],'verified',now()
);
insert into fontagit.font_audit_runs(
  id,stage,target_environment,target_count,success_count,verified_count,review_count,broken_count,
  parser_version,baseline_sha256,manifest_sha256,dry_run,status,started_at,finished_at
) values (
  '00000000-0000-0000-0000-000000009600','legal','dev',1,1,0,0,0,'test-v1',repeat('a',64),null,
  true,'completed',now(),now()
);
insert into fontagit.font_source_snapshots(
  id,run_id,font_id,provider,provider_record_id,source_kind,document_kind,
  request_url,final_url,http_status,raw_text,raw_sha256,normalized_sha256,
  extracted,evidence_locations,extraction_rule_id,parser_version,collected_at
) values
 ('00000000-0000-0000-0000-000000009601','00000000-0000-0000-0000-000000009600',
  '00000000-0000-0000-0000-000000009501','noonnu','9501','official','download',
  'https://example.test/meta','https://example.test/meta',200,null,repeat('b',64),repeat('c',64),
  '{}'::jsonb,'{}'::jsonb,null,'test-v1',now()),
 ('00000000-0000-0000-0000-000000009602','00000000-0000-0000-0000-000000009600',
  '00000000-0000-0000-0000-000000009501','noonnu','9501','official','license',
  'https://example.test/meta-license','https://example.test/meta-license',200,null,repeat('d',64),repeat('e',64),
  '{}'::jsonb,'{}'::jsonb,null,'test-v1',now()),
 ('00000000-0000-0000-0000-000000009603','00000000-0000-0000-0000-000000009600',
  '00000000-0000-0000-0000-000000009501','noonnu','9501','noonnu','metadata',
  'https://example.test/meta-script','https://example.test/meta-script',200,null,repeat('f',64),repeat('1',64),
  '{"evidence_role":"font-file-script"}'::jsonb,'{}'::jsonb,null,'test-v1',now());
update fontagit.fonts set
  download_evidence_id='00000000-0000-0000-0000-000000009601',
  license_evidence_id='00000000-0000-0000-0000-000000009602',
  script_evidence_id='00000000-0000-0000-0000-000000009603'
where id='00000000-0000-0000-0000-000000009501';

do $$
declare
  v_font_id uuid := '00000000-0000-0000-0000-000000009501';
  v_list text;
  v_key text;
  v_value jsonb;
  v_key_count integer := 0;
  v_bad_keys text[] := '{}';
begin
  v_list := (regexp_matches(
    pg_get_functiondef('fontagit.apply_font_audit_manifest(text,text,integer)'::regprocedure),
    'v_allowed constant text\[\] := array\[([^\]]*)\]'
  ))[1];
  if v_list is null then raise exception 'could not locate v_allowed declaration in function source'; end if;

  for v_key in select (regexp_matches(v_list, '''([a-z_]+)''', 'g'))[1] loop
    v_key_count := v_key_count + 1;
    v_value := fontagit._audit_font_value(v_font_id, v_key);
    if v_value is null then
      v_bad_keys := array_append(v_bad_keys, v_key || ':sql_null');
      continue;
    end if;
    if not fontagit._audit_manifest_value_valid(v_key, v_value) then
      v_bad_keys := array_append(v_bad_keys, v_key || ':value_invalid(' || v_value::text || ')');
    end if;
  end loop;

  if v_key_count <> 32 then raise exception 'expected 32 v_allowed keys, parsed %', v_key_count; end if;
  if array_length(v_bad_keys, 1) is not null then
    raise exception 'v_allowed consistency failed for: %', v_bad_keys;
  end if;
end;
$$;

select 'ALL PASS' as result;
rollback;
