alter table fontagit.fonts
  add column if not exists foundry_url text,
  add column if not exists download_url text,
  add column if not exists license_summary text,
  add column if not exists tags text[] not null default '{}',
  add column if not exists script_status text not null default 'pending',
  add column if not exists script_checked_at timestamptz,
  add column if not exists script_evidence_id uuid,
  add column if not exists download_source_kind text,
  add column if not exists license_source_kind text,
  add column if not exists download_status text not null default 'pending',
  add column if not exists license_status text not null default 'pending',
  add column if not exists download_checked_at timestamptz,
  add column if not exists license_checked_at timestamptz,
  add column if not exists allow_commercial text,
  add column if not exists allow_font_sale text,
  add column if not exists attribution_requirement text,
  add column if not exists download_evidence_id uuid,
  add column if not exists license_evidence_id uuid;

alter table fontagit.fonts
  add constraint fonts_download_status_chk
    check (download_status in ('pending', 'verified', 'needs_review', 'broken')),
  add constraint fonts_license_status_chk
    check (license_status in ('pending', 'verified', 'needs_review')),
  add constraint fonts_script_status_chk
    check (script_status in ('pending', 'verified', 'needs_review')),
  add constraint fonts_download_source_kind_chk
    check (download_source_kind is null or download_source_kind in ('official', 'public')),
  add constraint fonts_license_source_kind_chk
    check (license_source_kind is null or license_source_kind in ('official', 'public')),
  add constraint fonts_allow_commercial_chk
    check (allow_commercial is null or allow_commercial in ('allowed', 'conditional', 'denied')),
  add constraint fonts_allow_font_sale_chk
    check (allow_font_sale is null or allow_font_sale in ('allowed', 'conditional', 'denied')),
  add constraint fonts_attribution_requirement_chk
    check (attribution_requirement is null or attribution_requirement in ('required', 'recommended', 'not_required'));

create table fontagit.font_sources (
  id uuid primary key default gen_random_uuid(),
  font_id uuid not null references fontagit.fonts(id) on delete cascade,
  provider text not null,
  provider_record_id text not null,
  source_role text not null check (source_role in ('primary', 'reference')),
  source_url text not null,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  status text not null default 'active' check (status in ('active', 'stale', 'conflict')),
  unique (provider, provider_record_id)
);

create table fontagit.font_audit_runs (
  id uuid primary key default gen_random_uuid(),
  stage text not null check (stage in ('bootstrap', 'legal', 'metadata', 'scheduled')),
  target_environment text not null check (target_environment in ('dev', 'prod-readonly')),
  target_count integer not null check (target_count > 0),
  success_count integer not null default 0,
  verified_count integer not null default 0,
  review_count integer not null default 0,
  broken_count integer not null default 0,
  parser_version text not null,
  baseline_sha256 text not null,
  manifest_sha256 text,
  dry_run boolean not null default true,
  status text not null default 'running'
    check (status in ('running', 'completed', 'failed')),
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create table fontagit.font_source_snapshots (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references fontagit.font_audit_runs(id) on delete restrict,
  font_id uuid not null references fontagit.fonts(id) on delete restrict,
  provider text not null,
  provider_record_id text not null,
  source_kind text not null check (source_kind in ('official', 'public', 'noonnu')),
  document_kind text not null check (document_kind in ('download', 'license', 'metadata')),
  request_url text not null,
  final_url text not null,
  http_status integer,
  raw_text text,
  raw_sha256 text not null,
  normalized_sha256 text not null,
  extracted jsonb not null default '{}'::jsonb,
  evidence_locations jsonb not null default '{}'::jsonb,
  extraction_rule_id text,
  parser_version text not null,
  collected_at timestamptz not null,
  unique (font_id, provider, provider_record_id, document_kind, normalized_sha256)
);

create table fontagit.font_link_observations (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references fontagit.font_audit_runs(id) on delete restrict,
  font_id uuid not null references fontagit.fonts(id) on delete restrict,
  snapshot_id uuid references fontagit.font_source_snapshots(id) on delete restrict,
  normalized_url text not null,
  observed_at timestamptz not null,
  http_status integer,
  final_url text,
  content_sha256 text,
  error_kind text check (error_kind is null or error_kind in ('blocked', 'timeout', 'network', 'oversize')),
  unique (run_id, font_id, normalized_url)
);

create table fontagit.font_audit_findings (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references fontagit.font_audit_runs(id) on delete restrict,
  font_id uuid not null references fontagit.fonts(id) on delete restrict,
  field_name text not null,
  before_value jsonb,
  proposed_value jsonb,
  evidence_id uuid references fontagit.font_source_snapshots(id) on delete restrict,
  confidence text not null check (confidence in ('official', 'public', 'reference', 'unverified')),
  auto_applicable boolean not null default false,
  review_reason text,
  status text not null default 'proposed'
    check (status in ('proposed', 'approved', 'rejected', 'applied')),
  reviewed_by text,
  reviewed_at timestamptz,
  unique (run_id, font_id, field_name)
);

alter table fontagit.fonts
  add constraint fonts_download_evidence_id_fkey
  foreign key (download_evidence_id)
  references fontagit.font_source_snapshots(id) on delete restrict;

alter table fontagit.fonts
  add constraint fonts_license_evidence_id_fkey
  foreign key (license_evidence_id)
  references fontagit.font_source_snapshots(id) on delete restrict;

alter table fontagit.fonts
  add constraint fonts_script_evidence_id_fkey
  foreign key (script_evidence_id)
  references fontagit.font_source_snapshots(id) on delete restrict;

create index idx_font_sources_font on fontagit.font_sources(font_id);
create index idx_font_snapshots_font on fontagit.font_source_snapshots(font_id, collected_at desc);
create index idx_font_observations_url on fontagit.font_link_observations(normalized_url, observed_at desc);
create index idx_font_findings_review on fontagit.font_audit_findings(status, run_id);

alter table fontagit.font_sources enable row level security;
alter table fontagit.font_audit_runs enable row level security;
alter table fontagit.font_source_snapshots enable row level security;
alter table fontagit.font_link_observations enable row level security;
alter table fontagit.font_audit_findings enable row level security;

revoke all on table
  fontagit.font_sources,
  fontagit.font_audit_runs,
  fontagit.font_source_snapshots,
  fontagit.font_link_observations,
  fontagit.font_audit_findings
from anon, authenticated;

grant select, insert, update, delete on table
  fontagit.font_sources,
  fontagit.font_audit_runs,
  fontagit.font_source_snapshots,
  fontagit.font_link_observations,
  fontagit.font_audit_findings
to service_role;
