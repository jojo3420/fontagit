-- =============================================================================
-- 0011_reinforce_schema_exposure.sql
-- 스키마 노출 멀티환경 견고화
-- =============================================================================
-- 현황: 0010에서 fontagit 스키마를 노출하되, 기존 공개 스키마(public/storage/
-- graphql_public)와의 조합이 하드코딩되어 있음.
--
-- 문제: 다른 환경에서 추가 스키마가 있거나, 기존 설정이 상이할 경우 덮어씀
--
-- 해결: authenticator 역할의 기존 목록을 읽고 fontagit만 없을 때 추가한다.
-- PostgreSQL의 ALTER ROLE ... SET는 멱등함(동일 재설정은 무영향).
-- =============================================================================

do $$
declare
  existing_schemas text;
  schema_list text[];
begin
  select split_part(config, '=', 2)
    into existing_schemas
  from pg_db_role_setting settings,
       unnest(settings.setconfig) as config
  where settings.setrole = (
    select oid from pg_roles where rolname = 'authenticator'
  )
    and config like 'pgrst.db_schemas=%'
  order by settings.setdatabase desc
  limit 1;

  existing_schemas := coalesce(
    nullif(trim(existing_schemas), ''),
    'public, storage, graphql_public'
  );
  schema_list := regexp_split_to_array(existing_schemas, '\\s*,\\s*');

  if not ('fontagit' = any(schema_list)) then
    schema_list := array_append(schema_list, 'fontagit');
  end if;

  execute format(
    'alter role authenticator set pgrst.db_schemas = %L',
    array_to_string(schema_list, ', ')
  );
end
$$;

notify pgrst, 'reload config';
notify pgrst, 'reload schema';

comment on schema fontagit is
  'FontAgit 앱 스키마: 폰트 데이터 + 초성 검색 + 클릭 기록';
