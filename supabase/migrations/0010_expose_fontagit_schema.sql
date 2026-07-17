-- PostgREST REST API가 fontagit 스키마를 노출하도록 authenticator 역할에 설정.
-- 미적용 시 앱(anon)의 REST 조회가 PGRST125 'Invalid path'로 실패(스키마 미노출).
-- 반드시 전체 목록을 명시해야 기존 노출(public/storage/graphql_public)이 유지됨.
-- in-db 설정은 env(PGRST_DB_SCHEMAS)보다 우선하며 notify로 무중단 reload. 멱등.

alter role authenticator set pgrst.db_schemas = 'public, storage, graphql_public, fontagit';

notify pgrst, 'reload config';
notify pgrst, 'reload schema';
