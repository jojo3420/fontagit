-- =============================================================================
-- 0014_report_and_status.sql
-- 신고(report) 기능 + 폰트 상태 확대 (이슈 #24)
-- =============================================================================
-- 목적:
--   1. fonts 상태 확대: published/archived 외에 hold(일시 보류)/discontinued(배포 종료) 추가
--      → 신고 시 운영자가 48h 내 상태 변경(publish→hold로 전환)
--      → 상태 페이지로 404 대신 안내 페이지 렌더(SEO 자산 유지)
--   2. font_reports 테이블: 익명 신고 수집(anon INSERT, select 불가)
--
-- 제약:
--   - output:'export' 정적 환경: 신고 시 "즉시 자동 보류" 불가
--   - 운영자가 48h 내 수동으로 status 변경 처리
--   - anon RLS는 published/hold/discontinued 모두 SELECT 가능 (archived는 숨김)
-- =============================================================================

-- 1. fonts 테이블 status 체크 제약 확대
alter table fontagit.fonts drop constraint fonts_status_chk;
alter table fontagit.fonts add constraint fonts_status_chk check (
  status in ('draft', 'published', 'archived', 'hold', 'discontinued')
);

-- 2. anon SELECT RLS 확대: published/hold/discontinued 모두 허용
drop policy if exists "anon_read_published_fonts" on fontagit.fonts;
create policy "anon_read_fonts_published_hold_discontinued"
  on fontagit.fonts
  for select
  to anon
  using (status in ('published', 'hold', 'discontinued'));

-- 3. aliases RLS 업데이트: hold/discontinued도 표시 대상
drop policy if exists "anon_read_aliases" on fontagit.aliases;
create policy "anon_read_aliases"
  on fontagit.aliases
  for select
  to anon
  using (
    exists (
      select 1 from fontagit.fonts f
      where f.id = font_id and f.status in ('published', 'hold', 'discontinued')
    )
  );

-- 4. font_reports 테이블 생성
create table if not exists fontagit.font_reports (
  id uuid primary key default gen_random_uuid(),
  font_id uuid null references fontagit.fonts(id) on delete set null,
  reason text not null check (
    reason in ('copyright', 'misinformation', 'inappropriate', 'other')
  ),
  detail text check (
    detail is null or char_length(trim(detail)) between 1 and 1000
  ),
  contact text check (
    contact is null or (
      char_length(contact) between 3 and 254
      and contact ~* '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$'
    )
  ),
  created_at timestamp with time zone not null default now()
);

comment on table fontagit.font_reports is '폰트 신고: 저작권/라이선스/콘텐츠 이슈 수집용 (운영자 검토 대기)';
comment on column fontagit.font_reports.font_id is '신고된 폰트 ID (soft delete 대비 null 허용)';
comment on column fontagit.font_reports.reason is '신고 사유 (저작권침해/잘못된정보/부적절한콘텐츠/기타)';
comment on column fontagit.font_reports.detail is '상세 설명 (선택)';
comment on column fontagit.font_reports.contact is '신고자 연락처 - 이메일 형식 선택 제공 (선택)';

-- 5. font_reports RLS 설정
alter table fontagit.font_reports enable row level security;

-- 6. 테이블 직접 쓰기는 차단하고 검증·속도 제한 RPC만 공개
revoke all on fontagit.font_reports from public, anon, authenticated;
grant select, delete on fontagit.font_reports to service_role;

-- 7. font_reports 정책: service_role(운영자) SELECT/DELETE
create policy "service_role_all_font_reports"
  on fontagit.font_reports
  for select
  to service_role
  using (true);

create policy "service_role_delete_font_reports"
  on fontagit.font_reports
  for delete
  to service_role
  using (true);

-- 8. 인덱스: 신고 시각 및 폰트 조회용
create index if not exists idx_font_reports_created_at
  on fontagit.font_reports (created_at desc);

create index if not exists idx_font_reports_font_id
  on fontagit.font_reports (font_id);

-- 9. 익명 신고 RPC: 입력 재검증 + 전체/폰트별 과다 요청 방어
create or replace function fontagit.submit_font_report(
  p_font_id uuid,
  p_reason text,
  p_detail text default null,
  p_contact text default null
) returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if p_reason is null
     or p_reason not in ('copyright', 'misinformation', 'inappropriate', 'other') then
    raise exception 'INVALID_REPORT_REASON';
  end if;

  if p_detail is not null
     and char_length(trim(p_detail)) not between 1 and 1000 then
    raise exception 'INVALID_REPORT_DETAIL';
  end if;

  if p_contact is not null
     and (
       char_length(p_contact) not between 3 and 254
       or p_contact !~* '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$'
     ) then
    raise exception 'INVALID_REPORT_CONTACT';
  end if;

  if p_font_id is not null
     and not exists (
       select 1
       from fontagit.fonts
       where id = p_font_id
         and status in ('published', 'hold', 'discontinued')
     ) then
    raise exception 'INVALID_REPORT_FONT';
  end if;

  -- 짧은 트랜잭션 잠금으로 동시 요청이 제한 검사를 우회하지 못하게 한다.
  perform pg_advisory_xact_lock(hashtext('fontagit.submit_font_report'));

  if (
    select count(*)
    from fontagit.font_reports
    where created_at >= now() - interval '1 minute'
  ) >= 100 then
    raise exception 'REPORT_RATE_LIMITED';
  end if;

  if p_font_id is not null and (
    select count(*)
    from fontagit.font_reports
    where font_id = p_font_id
      and created_at >= now() - interval '10 minutes'
  ) >= 10 then
    raise exception 'REPORT_RATE_LIMITED';
  end if;

  insert into fontagit.font_reports (font_id, reason, detail, contact)
  values (
    p_font_id,
    p_reason,
    nullif(trim(p_detail), ''),
    nullif(trim(p_contact), '')
  );
end;
$$;

revoke all on function fontagit.submit_font_report(uuid, text, text, text)
  from public;
grant execute on function fontagit.submit_font_report(uuid, text, text, text)
  to anon, authenticated;

comment on function fontagit.submit_font_report(uuid, text, text, text) is
  '익명 폰트 신고 접수: 입력 검증과 전체/폰트별 과다 요청 제한 적용';

notify pgrst, 'reload schema';
