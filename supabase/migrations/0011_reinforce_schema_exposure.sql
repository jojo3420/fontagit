-- =============================================================================
-- 0011_reinforce_schema_exposure.sql
-- 스키마 노출 멀티환경 견고화
-- =============================================================================
-- 현황: 0010에서 fontagit 스키마를 노출하되, 기존 공개 스키마(public/storage/
-- graphql_public)와의 조합이 하드코딩되어 있음.
--
-- 문제: 다른 환경에서 추가 스키마가 있거나, 기존 설정이 상이할 경우 덮어씀
--
-- 해결: 이 마이그레이션은 안전한 기본값으로 재설정하며, 환경별 특수 스키마는
-- .env(PGRST_DB_SCHEMAS)로 수동 설정하도록 문서화.
-- PostgreSQL의 ALTER ROLE ... SET는 멱등함(동일 재설정은 무영향).
-- =============================================================================

alter role authenticator set pgrst.db_schemas = 'public, storage, graphql_public, fontagit';

notify pgrst, 'reload config';
notify pgrst, 'reload schema';

comment on schema fontagit is
  'FontAgit 앱 스키마: 폰트 데이터 + 초성 검색 + 클릭 기록';
