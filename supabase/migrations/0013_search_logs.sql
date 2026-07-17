-- =============================================================================
-- 0013_search_logs.sql
-- 검색 실패어 로그 테이블 (F-32)
-- =============================================================================
-- 목적: 결과 0건 검색어를 익명 저장해 등록 우선순위 수집
-- 제약: 개인식별정보(IP, 검색자 식별) 저장 금지, 검색어 텍스트+시각만
--
-- 테이블: search_logs
--   - id: UUID 주키
--   - query: 검색어 텍스트(정규화 전, 사용자가 입력한 그대로)
--   - created_at: 검색 시각(UTC, 자동 타임스탬프)
--
-- 권한:
--   - anon: INSERT만 허용(로깅 목적)
--   - service_role: 모든 권한(운영자 조회)
--   - SELECT 불가(운영자만 service_role로 조회)
-- =============================================================================

create table if not exists fontagit.search_logs (
  id uuid primary key default gen_random_uuid(),
  query text not null,
  created_at timestamp with time zone not null default now()
);

comment on table fontagit.search_logs is '검색 0건 결과 로그: 폰트 등록 우선순위 수집용';
comment on column fontagit.search_logs.query is '검색어 (정규화 전)';

-- 인덱스: created_at으로 로그 기간별 분석 지원
create index if not exists idx_search_logs_created_at
  on fontagit.search_logs (created_at desc);

-- RLS: 기본 거부
alter table fontagit.search_logs enable row level security;

-- 정책: anon은 INSERT만
create policy "anon_insert_search_logs"
  on fontagit.search_logs
  for insert
  to anon
  with check (true);

-- 정책: service_role(운영자)는 모든 권한(UPDATE/DELETE도 선택적 활성화 가능)
create policy "service_role_all_search_logs"
  on fontagit.search_logs
  for select
  to service_role
  using (true);

create policy "service_role_delete_search_logs"
  on fontagit.search_logs
  for delete
  to service_role
  using (true);
