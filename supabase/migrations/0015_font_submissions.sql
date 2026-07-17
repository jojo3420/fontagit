-- =============================================================================
-- 0015_font_submissions.sql
-- 폰트 등록 신청 테이블 (이슈 #30)
-- =============================================================================
-- 목적:
--   1. font_submissions 테이블: 창작자가 폰트 등록을 신청
--      폰트명, 제작자, 공식페이지, 라이선스, 신청자 연락처, 크레딧 수집
--   2. anon 사용자만 INSERT 가능 (READ는 service_role만)
--   3. 운영자가 비동기 검토 후 fonts 테이블에 수동 추가
--
-- 제약:
--   - output:'export' 정적 환경: 즉시 자동 반영 불가
--   - 운영자 수동 검토 필수
-- =============================================================================

-- 1. font_submissions 테이블 생성
create table if not exists fontagit.font_submissions (
  id uuid primary key default gen_random_uuid(),
  font_name text not null,
  maker text,
  official_url text,
  license_note text,
  submitter_contact text,
  credit text,
  created_at timestamp with time zone not null default now()
);

comment on table fontagit.font_submissions is '폰트 등록 신청: 창작자의 폰트 등록 신청 수집용 (운영자 검토 대기)';
comment on column fontagit.font_submissions.font_name is '폰트명 (필수)';
comment on column fontagit.font_submissions.maker is '제작자명 (선택)';
comment on column fontagit.font_submissions.official_url is '공식 페이지 URL (선택)';
comment on column fontagit.font_submissions.license_note is '라이선스 (무료/유료/조건부) (선택)';
comment on column fontagit.font_submissions.submitter_contact is '신청자 연락처 - 이메일 형식 (선택)';
comment on column fontagit.font_submissions.credit is '제작자 표기/크레딧 정보 (선택)';

-- 2. RLS 활성화
alter table fontagit.font_submissions enable row level security;

-- 3. RLS 정책: anon은 INSERT만 (등록 신청 제출용)
create policy "anon_insert_font_submissions"
  on fontagit.font_submissions
  for insert
  to anon
  with check (true);

-- 4. RLS 정책: service_role(운영자)은 SELECT만 (검토용)
create policy "service_role_select_font_submissions"
  on fontagit.font_submissions
  for select
  to service_role
  using (true);

-- 5. 인덱스: 등록 신청 시각 조회 및 정렬용
create index if not exists idx_font_submissions_created_at
  on fontagit.font_submissions (created_at desc);
