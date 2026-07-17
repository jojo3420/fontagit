-- 0016_noonnu_enrich.sql
-- 눈누 Tier B 2단계: 라이선스 세부 컬럼 + 발행 제약 완화 + 검수 큐

-- 1) fonts 라이선스 세부 컬럼 (F-01 4행 + 근거)
alter table fontagit.fonts
  add column if not exists allow_embedding    text,
  add column if not exists allow_redistribute text,
  add column if not exists allow_modify       text,
  add column if not exists license_note       text,
  add column if not exists verified_at        timestamptz,
  add column if not exists license_source_url text,
  add column if not exists auto_approved       boolean not null default false;

alter table fontagit.fonts
  add constraint fonts_allow_embedding_chk
    check (allow_embedding is null or allow_embedding in ('allowed','conditional','denied')),
  add constraint fonts_allow_redistribute_chk
    check (allow_redistribute is null or allow_redistribute in ('allowed','conditional','denied')),
  add constraint fonts_allow_modify_chk
    check (allow_modify is null or allow_modify in ('allowed','conditional','denied'));

-- 2) 발행 제약 완화: Tier B는 verified면 발행, Tier A만 라이선스 타입 화이트리스트 유지
alter table fontagit.fonts drop constraint if exists fonts_published_license_chk;
alter table fontagit.fonts
  add constraint fonts_published_license_chk
    check (status <> 'published' or (
      license_verified = true
      and (source_tier <> 'A' or license_type in ('OFL','Apache-2.0','UFL'))
    ));

-- 3) 검수 큐 (기획서 13장 review_queue). 운영 전용, RLS 잠금.
create table fontagit.license_proposals (
  id                       uuid primary key default gen_random_uuid(),
  font_id                  uuid not null references fontagit.fonts(id) on delete cascade,
  slug                     text not null,
  source_url               text not null,
  raw_permissions          jsonb not null,
  proposed_commercial_free boolean,
  proposed_embedding       text check (proposed_embedding is null or proposed_embedding in ('allowed','conditional','denied')),
  proposed_redistribute    text check (proposed_redistribute is null or proposed_redistribute in ('allowed','conditional','denied')),
  proposed_modify          text check (proposed_modify is null or proposed_modify in ('allowed','conditional','denied')),
  proposed_license_type    text,
  proposed_weights         int[]  not null default '{}',
  proposed_italic          boolean,
  proposed_category_ko     text,
  parse_status             text not null check (parse_status in ('parsed','partial','failed')),
  classification           text not null check (classification in ('auto_safe','needs_review')),
  review_status            text not null default 'proposed'
                             check (review_status in ('proposed','approved','rejected','auto_published')),
  scraped_at               timestamptz not null default now(),
  reviewed_at              timestamptz,
  reviewer_note            text,
  unique (font_id)
);
create index idx_license_proposals_review on fontagit.license_proposals(review_status);

alter table fontagit.license_proposals enable row level security;
-- anon 정책 없음 = 공개 읽기 차단. service_role만 접근.
grant select, insert, update, delete on fontagit.license_proposals to service_role;
