-- 0015: 폰트 등록 신청 저장소와 제한된 익명 제출 RPC

create table if not exists fontagit.font_submissions (
  id uuid primary key default gen_random_uuid(),
  font_name text not null check (char_length(trim(font_name)) between 1 and 100),
  category text not null check (category in ('고딕', '명조', '손글씨', '장식')),
  maker text check (maker is null or char_length(trim(maker)) between 1 and 100),
  official_url text not null check (
    char_length(official_url) between 10 and 500
    and official_url ~* '^https?://[^[:space:]]+$'
  ),
  license_note text check (license_note is null or license_note in ('무료', '유료', '조건부')),
  submitter_contact text check (
    submitter_contact is null or (
      char_length(submitter_contact) between 3 and 100
      and submitter_contact ~* '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$'
    )
  ),
  credit text check (credit is null or char_length(trim(credit)) between 1 and 500),
  created_at timestamp with time zone not null default now()
);

comment on table fontagit.font_submissions is
  '폰트 등록 신청: 운영자 검토 전 대기 데이터';
comment on column fontagit.font_submissions.submitter_contact is
  '신청 결과 회신용 선택 이메일';

alter table fontagit.font_submissions enable row level security;

-- 테이블 직접 쓰기는 막고 아래 검증 RPC만 공개한다.
revoke all on fontagit.font_submissions from public, anon, authenticated;
grant select, delete on fontagit.font_submissions to service_role;

create policy "service_role_select_font_submissions"
  on fontagit.font_submissions
  for select
  to service_role
  using (true);

create policy "service_role_delete_font_submissions"
  on fontagit.font_submissions
  for delete
  to service_role
  using (true);

create index if not exists idx_font_submissions_created_at
  on fontagit.font_submissions (created_at desc);

create index if not exists idx_font_submissions_url_created_at
  on fontagit.font_submissions (lower(official_url), created_at desc);

create or replace function fontagit.submit_font_submission(
  p_font_name text,
  p_category text,
  p_maker text,
  p_official_url text,
  p_license_note text,
  p_submitter_contact text,
  p_credit text
) returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_font_name text := trim(p_font_name);
  v_category text := trim(p_category);
  v_maker text := nullif(trim(p_maker), '');
  v_official_url text := trim(p_official_url);
  v_license_note text := nullif(trim(p_license_note), '');
  v_submitter_contact text := nullif(trim(p_submitter_contact), '');
  v_credit text := nullif(trim(p_credit), '');
begin
  if v_font_name is null or char_length(v_font_name) not between 1 and 100 then
    raise exception 'INVALID_SUBMISSION_FONT_NAME';
  end if;
  if v_category is null or v_category not in ('고딕', '명조', '손글씨', '장식') then
    raise exception 'INVALID_SUBMISSION_CATEGORY';
  end if;
  if v_maker is not null and char_length(v_maker) > 100 then
    raise exception 'INVALID_SUBMISSION_MAKER';
  end if;
  if v_official_url is null
     or char_length(v_official_url) not between 10 and 500
     or v_official_url !~* '^https?://[^[:space:]]+$' then
    raise exception 'INVALID_SUBMISSION_URL';
  end if;
  if v_license_note is not null
     and v_license_note not in ('무료', '유료', '조건부') then
    raise exception 'INVALID_SUBMISSION_LICENSE';
  end if;
  if v_submitter_contact is not null and (
    char_length(v_submitter_contact) not between 3 and 100
    or v_submitter_contact !~* '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$'
  ) then
    raise exception 'INVALID_SUBMISSION_CONTACT';
  end if;
  if v_credit is not null and char_length(v_credit) > 500 then
    raise exception 'INVALID_SUBMISSION_CREDIT';
  end if;

  -- 동시 요청도 제한 검사를 우회하지 못하게 짧게 잠근다.
  perform pg_advisory_xact_lock(hashtext('fontagit.submit_font_submission'));

  if (
    select count(*)
    from fontagit.font_submissions
    where created_at >= now() - interval '1 minute'
  ) >= 30 then
    raise exception 'SUBMISSION_RATE_LIMITED';
  end if;

  if (
    select count(*)
    from fontagit.font_submissions
    where lower(official_url) = lower(v_official_url)
      and created_at >= now() - interval '1 hour'
  ) >= 3 then
    raise exception 'SUBMISSION_RATE_LIMITED';
  end if;

  insert into fontagit.font_submissions (
    font_name,
    category,
    maker,
    official_url,
    license_note,
    submitter_contact,
    credit
  ) values (
    v_font_name,
    v_category,
    v_maker,
    v_official_url,
    v_license_note,
    v_submitter_contact,
    v_credit
  );
end;
$$;

revoke all on function fontagit.submit_font_submission(text, text, text, text, text, text, text)
  from public;
grant execute on function fontagit.submit_font_submission(text, text, text, text, text, text, text)
  to anon, authenticated;

comment on function fontagit.submit_font_submission(text, text, text, text, text, text, text) is
  '익명 폰트 등록 신청: 입력 검증과 전체 및 URL별 과다 요청 제한 적용';

notify pgrst, 'reload schema';
