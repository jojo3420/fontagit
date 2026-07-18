# prod 폰트 데이터 전수 조사·보정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** prod 폰트 전체를 공식 출처 우선으로 조사하고, 근거가 있는 다운로드·라이선스·메타데이터만 안전하게 반영하며 같은 오염이 재발하지 않는 감사 파이프라인을 만든다.

**Architecture:** 공개 현재값(fonts), 환경 공통 출처키(font_sources), append-only 증거(font_source_snapshots), 검수 큐(font_audit_findings)를 분리한다. 로컬/dev에서 수집·판정·검수를 끝낸 뒤 안정키와 before 값이 고정된 manifest를 service-role 전용 RPC가 한 트랜잭션으로 적용한다. 웹은 새 nullable 필드를 먼저 읽고 legacy 필드는 임시 fallback으로만 사용한다.

**Tech Stack:** PostgreSQL/Supabase RLS·RPC, Python 3.12, pydantic, httpx, BeautifulSoup4, curl 8+, fontTools, pytest, Next.js 정적 생성, TypeScript, Vitest, GitHub Actions.

## Global Constraints

- 기준선은 2026-07-18 prod published 1,240종(Tier A 130, Tier B 1,110)이며 실행 직전 exact count가 다르면 자동 중단한다.
- 출처 우선순위는 제작사 공식 페이지 → 한국저작권위원회·공유마당 등 승인된 공공기관 → 눈누 참고다.
- 눈누 값과 일반 검색 결과만으로 verified를 만들지 않는다.
- 원문은 내부 증거로만 보관하고 공개 화면에는 FontAgit 요약과 원문 링크만 제공한다.
- 출처 미확인 폰트는 페이지를 유지하되 다운로드 버튼을 제거하고 “라이선스 재확인 필요”를 표시한다.
- prod 쓰기, 마이그레이션, 배포는 사용자 명시 승인 전 실행하지 않는다.
- 기존 official_url은 의미를 바꾸지 않고 legacy로 동결한다.
- 검증 필드의 단일 writer는 fontagit.apply_font_audit_manifest RPC다.
- 기존 noonnu import·enrich·review·publish와 일반 uploader는 검증 필드를 직접 확정하지 않는다.
- 핵심 서비스 테스트만 작성한다. 기능당 해피 패스 1개와 치명적 예외 1~2개, 최대 3개다.
- 단순 UI 컴포넌트, 래퍼, Getter/Setter, 단순 CRUD에는 새 테스트를 만들지 않는다.
- 목록 화면 필터 추가·고도화는 범위에서 제외한다.

---

## 파일 구조와 책임

| 경로 | 책임 |
|---|---|
| supabase/migrations/0017_font_audit_schema.sql | 공개 신규 필드, 감사·링크 관찰 테이블, FK, RLS |
| supabase/migrations/0018_apply_font_audit_manifest.sql | manifest 전체 검증·원자 적용 RPC |
| supabase/migrations/0019_enforce_font_audit_constraints.sql | backfill 이후 CHECK 강화 |
| supabase/tests/font_audit_schema_test.sql | 상태·FK·RLS 핵심 검증 |
| supabase/tests/font_audit_manifest_test.sql | 전량 적용·전량 거부·왕복 복원 검증 |
| apps/pipeline/src/fontagit_pipeline/audit_models.py | 실행·스냅샷·관찰·finding·manifest 타입 |
| apps/pipeline/src/fontagit_pipeline/audit_policy.py | 수집·보관 정책과 승인 도메인 레지스트리 검증 |
| apps/pipeline/src/fontagit_pipeline/audit_bootstrap.py | Tier A/B 안정키 bootstrap |
| apps/pipeline/src/fontagit_pipeline/audit_http.py | URL 정규화, 공개 IP 검증, 고정 IP 요청, 링크 관찰 |
| apps/pipeline/src/fontagit_pipeline/audit_noonnu.py | 눈누의 폰트 직접 관련 정보 전량 추출 |
| apps/pipeline/src/fontagit_pipeline/audit_license.py | 승인 규칙 기반 라이선스 6개 필드와 요약 생성 |
| apps/pipeline/src/fontagit_pipeline/audit_store.py | dev 감사·링크 관찰 테이블 append-only 저장과 artifact import |
| apps/pipeline/src/fontagit_pipeline/audit_runner.py | 50종 파일럿·1단계·2단계 실행 오케스트레이션 |
| apps/pipeline/src/fontagit_pipeline/audit_manifest.py | 정방향·역방향 manifest 생성·해시·검증 |
| apps/pipeline/src/fontagit_pipeline/audit_metadata.py | fontTools 기반 굵기·스타일 후보 생성 |
| apps/pipeline/src/fontagit_pipeline/data/source_registry.json | 승인된 제작사·공공기관 도메인과 근거 |
| apps/pipeline/src/fontagit_pipeline/data/license_rules.json | 승인된 표준·제작사 라이선스 규칙 |
| apps/pipeline/tests/fixtures/audit/ | 고정 HTML·HTTP·manifest·폰트 메타 픽스처 |
| apps/web/lib/db/types.ts | 신규 DB 필드 타입 |
| apps/web/lib/db/mappers.ts | 신규 필드 우선, legacy fallback 변환 |
| apps/web/types/font.ts | 상세 화면용 라이선스·출처 타입 |
| apps/web/components/LicenseSummaryCard.tsx | 6개 권한, 재확인 상태, 출처 링크, 안전한 CTA |
| .github/workflows/font-audit-links.yml | 쓰기 키 없는 매주 다운로드 링크 관찰 |
| .github/workflows/font-audit-license.yml | 쓰기 키 없는 분기 라이선스 해시 관찰 |
| docs/runbooks/prod-font-data-audit.md | 운영 명령, 승인 게이트, 되돌리기 |

## 실행 구간

1. **기반:** Task 1~3 — 스키마, 정책, 안정키 bootstrap
2. **수집·판정:** Task 4~8 — 안전한 요청, 눈누·공식 출처, 검수, manifest
3. **소비자·자동화:** Task 9~11 — 웹 호환, 예약 검사, 2단계 메타데이터
4. **실데이터:** Task 12~13 — dev 파일럿·전수 조사, 사용자 승인 후 prod 적용

---

### Task 1: additive 감사 스키마와 RLS

**Files:**
- Create: supabase/migrations/0017_font_audit_schema.sql
- Create: supabase/tests/font_audit_schema_test.sql

**Interfaces:**
- Consumes: 기존 fontagit.fonts, fontagit.license_proposals
- Produces: fonts 신규 nullable 필드와 font_sources, font_audit_runs, font_source_snapshots, font_link_observations, font_audit_findings

- [ ] **Step 1: 실패하는 스키마 검증 작성**

font_audit_schema_test.sql에 아래 3가지만 검증한다.

~~~sql
do $$
begin
  if to_regclass('fontagit.font_sources') is null then
    raise exception 'font_sources missing';
  end if;
  if to_regclass('fontagit.font_source_snapshots') is null then
    raise exception 'font_source_snapshots missing';
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'fonts_download_evidence_id_fkey'
  ) then
    raise exception 'download evidence FK missing';
  end if;
end $$;

select 'ALL PASS' as result;
~~~

- [ ] **Step 2: 마이그레이션 전 실패 확인**

Run:

~~~bash
psql "$DEV_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/tests/font_audit_schema_test.sql
~~~

Expected: font_sources missing으로 종료 코드 1.

- [ ] **Step 3: additive migration 작성**

0017에는 다음 상태를 정확히 사용한다.

~~~sql
alter table fontagit.fonts
  add column if not exists foundry_url text,
  add column if not exists download_url text,
  add column if not exists license_summary text,
  add column if not exists tags text[] not null default '{}',
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

create index idx_font_sources_font on fontagit.font_sources(font_id);
create index idx_font_snapshots_font on fontagit.font_source_snapshots(font_id, collected_at desc);
create index idx_font_observations_url on fontagit.font_link_observations(normalized_url, observed_at desc);
create index idx_font_findings_review on fontagit.font_audit_findings(status, run_id);
~~~

모든 감사·관찰 테이블에 RLS를 켜고 anon/authenticated 정책은 만들지 않는다. service_role만 CRUD 권한을 가진다. 공개 fonts 읽기 정책은 유지한다. 스키마 테스트는 pg_class.relrowsecurity가 다섯 내부 테이블 모두 true인지도 검사한다.

- [ ] **Step 4: dev 적용과 스키마 검증**

Run:

~~~bash
psql "$DEV_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/0017_font_audit_schema.sql
psql "$DEV_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/tests/font_audit_schema_test.sql
~~~

Expected: ALL PASS. 기존 published count는 적용 전후 동일.

- [ ] **Step 5: 커밋**

~~~bash
git add supabase/migrations/0017_font_audit_schema.sql \
  supabase/tests/font_audit_schema_test.sql
git commit -m "feat: add font audit schema"
~~~

---

### Task 2: 감사 타입, 수집 정책, 승인 레지스트리

**Files:**
- Create: apps/pipeline/src/fontagit_pipeline/audit_models.py
- Create: apps/pipeline/src/fontagit_pipeline/audit_policy.py
- Create: apps/pipeline/src/fontagit_pipeline/data/source_registry.json
- Create: apps/pipeline/src/fontagit_pipeline/data/license_rules.json
- Create: apps/pipeline/tests/test_audit_policy.py
- Modify: apps/pipeline/src/fontagit_pipeline/config.py
- Modify: apps/pipeline/tests/test_config.py
- Modify: apps/pipeline/src/fontagit_pipeline/__main__.py
- Create: docs/runbooks/prod-font-data-audit.md

**Interfaces:**
- Produces: AuditRun, SourceSnapshot, LinkObservation, Finding, Manifest, load_source_registry(), assert_collection_allowed()
- Produces: load_audit_settings() -> AuditSettings
- CLI: font-audit-policy-check --out PATH

- [ ] **Step 1: 정책 검증 핵심 테스트 작성**

먼저 문서 디렉터리를 만든다.

~~~bash
mkdir -p docs/runbooks
~~~

~~~python
def test_registry_requires_approval_evidence(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(
        '{"version":1,"entries":[{"maker":"네이버","domain":"clova.ai",'
        '"roles":["download"],"source_kind":"official","approved_by":"",'
        '"approved_at":"","evidence_snapshot_id":""}]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="approval evidence"):
        load_source_registry(path)


def test_unknown_domain_is_discovery_only(registry):
    assert registry.classify("https://example.org/font") == "discovery"


def test_audit_settings_do_not_require_google_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)
    assert load_audit_settings().supabase_url is None
~~~

- [ ] **Step 2: RED 확인**

Run:

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_policy.py tests/test_config.py -q
~~~

Expected: audit_policy 모듈이 없어 실패.

- [ ] **Step 3: 타입과 정책 구현**

audit_models.py의 공개 타입은 아래 시그니처로 고정한다.

~~~python
AuditStage = Literal["bootstrap", "legal", "metadata", "scheduled"]
SourceKind = Literal["official", "public", "noonnu"]
RegistryKind = Literal["official", "public", "discovery"]
DocumentKind = Literal["download", "license", "metadata"]
DownloadStatus = Literal["pending", "verified", "needs_review", "broken"]
LicenseStatus = Literal["pending", "verified", "needs_review"]
PermissionValue = Literal["allowed", "conditional", "denied"]


class LinkObservation(BaseModel):
    normalized_url: HttpUrl
    observed_at: datetime
    http_status: int | None
    final_url: HttpUrl | None
    content_sha256: str | None
    error_kind: Literal["blocked", "timeout", "network", "oversize"] | None


class SourceKey(BaseModel):
    provider: str
    provider_record_id: str


class ManifestEntry(BaseModel):
    source_key: SourceKey
    before: dict[str, object]
    after: dict[str, object]
    evidence_ids: list[UUID]
    expected_updated_at: datetime


class EvidenceBundle(BaseModel):
    run: dict[str, object]
    snapshots: list[dict[str, object]]
    findings: list[dict[str, object]]


class FontAuditManifest(BaseModel):
    schema_version: Literal[1]
    run_id: UUID
    baseline_sha256: str
    generated_at: datetime
    evidence_bundle: EvidenceBundle
    entries: list[ManifestEntry]
~~~

audit_policy.py는 RegistryEntry의 maker, domain, roles, source_kind, approved_by, approved_at, evidence_snapshot_id가 모두 있어야 official/public로 분류한다. 누락 항목과 일반 검색 후보는 discovery다.

source_registry.json은 빈 entries로 시작하지 않는다. 설계에서 이미 확인된 네이버 후보를 discovery로만 넣는다.

~~~json
{
  "version": 1,
  "entries": [
    {
      "maker": "네이버",
      "domain": "clova.ai",
      "roles": ["download"],
      "source_kind": "discovery",
      "approved_by": null,
      "approved_at": null,
      "evidence_snapshot_id": null
    }
  ]
}
~~~

license_rules.json은 자동 확정 규칙 0건으로 시작한다. 공식 원문 fingerprint와 사람 승인 전에는 자동 verified를 만들지 않는다.

0016에서 이미 만든 allow_embedding, allow_redistribute, allow_modify, license_source_url은 그대로 재사용한다. 0017에서 같은 컬럼을 다른 타입으로 다시 만들지 않는다.

Google Fonts 전용 Settings는 유지하고, 감사 명령은 GOOGLE_FONTS_API_KEY를 요구하지 않는 별도 설정을 사용한다.

~~~python
class AuditSettings(BaseSettings):
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_secret_key: str | None = None
    supabase_prod_url: str | None = None
    supabase_prod_secret_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def load_audit_settings() -> AuditSettings:
    return AuditSettings()
~~~

- [ ] **Step 4: 수집 정책 실행 게이트 작성**

runbook에 robots URL, 확인 시각, 수집 허용 여부, 원문 장기 저장 허용 여부, 증거 해시를 기록하는 표를 만든다. assert_collection_allowed()는 승인된 정책 JSON 없이는 raw_text 저장을 거부하고 structured-only 모드만 허용한다.

font-audit-policy-check 명령은 robots와 이용 조건의 증거 URL·해시를 출력하되 사람이 crawl_allowed와 raw_retention_allowed를 승인하기 전에는 둘 다 unknown으로 기록한다. unknown은 structured-only다.

- [ ] **Step 5: GREEN과 정적 검사**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_policy.py tests/test_config.py -q
uv run ruff check src/fontagit_pipeline/audit_models.py \
  src/fontagit_pipeline/audit_policy.py src/fontagit_pipeline/config.py \
  tests/test_audit_policy.py tests/test_config.py
uv run mypy src
~~~

Expected: 신규 정책 2개와 설정 1개 테스트 PASS, ruff/mypy 오류 0.

- [ ] **Step 6: 커밋**

~~~bash
git add apps/pipeline/src/fontagit_pipeline/audit_models.py \
  apps/pipeline/src/fontagit_pipeline/audit_policy.py \
  apps/pipeline/src/fontagit_pipeline/data/source_registry.json \
  apps/pipeline/src/fontagit_pipeline/data/license_rules.json \
  apps/pipeline/src/fontagit_pipeline/config.py \
  apps/pipeline/src/fontagit_pipeline/__main__.py \
  apps/pipeline/tests/test_config.py \
  apps/pipeline/tests/test_audit_policy.py \
  docs/runbooks/prod-font-data-audit.md
git commit -m "feat: define font audit trust policy"
~~~

---

### Task 3: prod 기준선과 안정 출처키 bootstrap

**Files:**
- Create: apps/pipeline/src/fontagit_pipeline/audit_bootstrap.py
- Create: apps/pipeline/tests/test_audit_bootstrap.py
- Modify: apps/pipeline/src/fontagit_pipeline/__main__.py
- Use: apps/pipeline/output/tier-a.json
- Use: apps/pipeline/output/tier-b-noonnu-seed.json

**Interfaces:**
- Consumes: prod 읽기 전용 fonts snapshot, Tier A snapshot, Tier B seed
- Produces: build_bootstrap_manifest(prod_rows, tier_a, tier_b) -> BootstrapResult
- Produces CLI: font-audit-export-baseline --source prod-public --out PATH
- Produces CLI: font-audit-bootstrap --prod-snapshot PATH --out PATH

- [ ] **Step 1: 정확 일치와 충돌 테스트 작성**

~~~python
def test_tier_b_exact_match_builds_no_public_update():
    result = build_bootstrap_manifest(
        prod_rows=[prod_font("흰꼬리수리", "흰꼬리수리", INSTAGRAM_URL)],
        tier_a=[],
        tier_b=[tier_b_seed(page_id="613", name_ko="흰꼬리수리",
                            slug="흰꼬리수리", official_url=INSTAGRAM_URL)],
    )
    assert result.matched == 1
    assert result.entries[0].provider_record_id == "613"
    assert result.entries[0].public_updates == {}


def test_zero_or_multiple_candidates_are_review_only():
    result = build_bootstrap_manifest(
        prod_rows=[prod_font("same", "동일", INSTAGRAM_URL)],
        tier_a=[],
        tier_b=[
            tier_b_seed(page_id="1", name_ko="동일", slug="same", official_url=INSTAGRAM_URL),
            tier_b_seed(page_id="2", name_ko="동일", slug="same", official_url=INSTAGRAM_URL),
        ],
    )
    assert result.matched == 0
    assert result.conflicts == 1
~~~

- [ ] **Step 2: RED 확인**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_bootstrap.py -q
~~~

Expected: build_bootstrap_manifest가 없어 실패.

- [ ] **Step 3: bootstrap 구현**

Tier A key는 source_tier + name_en + slug + 기존 Google URL, Tier B key는 source_tier + slug + NFC 정규화 name_ko + 당시 official_url을 사용한다. foundry는 초기 조건에서 제외하되 현재값 null을 precondition에 기록한다. 후보 0개·2개 이상은 entries에 넣지 않고 review_rows에 넣는다.

BootstrapResult는 matched, unmatched, conflicts, entries, review_rows를 가진다. 출력 JSON은 원자 저장하고 SHA-256을 같은 이름의 .sha256 파일에 기록한다.

- [ ] **Step 4: CLI 연결**

__main__.py에 아래 명령을 추가한다.

~~~text
fontagit-pipeline font-audit-bootstrap \
  --prod-snapshot output/audit/prod-fonts-baseline.json \
  --out output/audit/bootstrap-manifest.json
~~~

font-audit-export-baseline은 AuditSettings의 anon URL/key만 사용해 exact count, 정렬 slug, 중복 0, 기준선 해시를 검증한다. 쓰기 키를 받지 않는다.

- [ ] **Step 5: GREEN과 실데이터 dry-run**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_bootstrap.py -q
uv run python -m fontagit_pipeline font-audit-bootstrap \
  --prod-snapshot output/audit/prod-fonts-baseline.json \
  --out output/audit/bootstrap-manifest.json
~~~

Expected: matched + unmatched + conflicts = 기준선 exact count. public_updates는 전부 빈 객체.

- [ ] **Step 6: 커밋**

~~~bash
git add apps/pipeline/src/fontagit_pipeline/audit_bootstrap.py \
  apps/pipeline/tests/test_audit_bootstrap.py \
  apps/pipeline/src/fontagit_pipeline/__main__.py
git commit -m "feat: build stable font source bootstrap"
~~~

---

### Task 4: SSRF 방어 링크 검사와 24시간 관찰 판정

**Files:**
- Create: apps/pipeline/src/fontagit_pipeline/audit_http.py
- Create: apps/pipeline/tests/test_audit_http.py
- Create: apps/pipeline/tests/fixtures/audit/link-observations.json

**Interfaces:**
- Produces: fetch_public_url(url, *, max_bytes=1048576, max_redirects=5) -> FetchResult
- Produces: classify_download(observations) -> DownloadStatus

- [ ] **Step 1: 핵심 3개 테스트 작성**

~~~bash
mkdir -p apps/pipeline/tests/fixtures/audit
~~~

~~~python
def test_public_https_uses_pinned_curl_resolution(fake_curl):
    result = fetch_public_url("https://fonts.example/download")
    assert result.status == 200
    assert "--resolve" in fake_curl.argv
    assert "fonts.example:443:203.0.113.10" in fake_curl.argv


def test_private_or_metadata_target_is_blocked(fake_dns):
    fake_dns.returns("169.254.169.254")
    with pytest.raises(UnsafeAddressError):
        fetch_public_url("https://metadata.example/latest")


def test_broken_requires_two_independent_observations():
    first = observation(404, "2026-07-18T00:00:00Z")
    second = observation(404, "2026-07-19T00:01:00Z")
    assert classify_download([first]) == "needs_review"
    assert classify_download([first, second]) == "broken"
~~~

- [ ] **Step 2: RED 확인**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_http.py -q
~~~

Expected: audit_http 모듈이 없어 실패.

- [ ] **Step 3: URL·DNS 방어 구현**

http/https만 허용하고 localhost, loopback, private, link-local, multicast, reserved, unspecified IP를 차단한다. A/AAAA 결과를 모두 검사한다. 요청은 shell=False인 subprocess 인자 배열로 curl을 실행하며, 허용 IP를 --resolve host:port:ip로 고정하고 원래 hostname의 TLS SNI·인증서 검증을 유지한다. 리다이렉트는 자동 추적하지 않고 Location을 읽어 매 단계 DNS를 다시 검사한다.

curl 공통 제한은 다음과 같다.

~~~python
CURL_BASE = [
    "curl", "--silent", "--show-error", "--fail-with-body",
    "--proto", "=http,https", "--max-time", "20",
    "--connect-timeout", "5", "--max-filesize", "1048576",
    "--max-redirs", "0",
]
~~~

- [ ] **Step 4: 상태 판정 구현**

400·401·403·429, 5xx, timeout, 차단은 needs_review다. 2xx라도 폰트명·제작사·문서 역할 확인 전에는 verified가 아니다. 404·410은 서로 다른 run_id이며 observed_at 차이가 24시간 이상인 두 관찰만 broken이다.

- [ ] **Step 5: GREEN과 정적 검사**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_http.py -q
uv run ruff check src/fontagit_pipeline/audit_http.py tests/test_audit_http.py
uv run mypy src
~~~

Expected: 3개 테스트 PASS, ruff/mypy 오류 0.

- [ ] **Step 6: 커밋**

~~~bash
git add apps/pipeline/src/fontagit_pipeline/audit_http.py \
  apps/pipeline/tests/test_audit_http.py \
  apps/pipeline/tests/fixtures/audit/link-observations.json
git commit -m "feat: add safe font link observations"
~~~

---

### Task 5: 눈누 폰트 정보 전량 추출과 라이선스 신뢰 판정

**Files:**
- Create: apps/pipeline/src/fontagit_pipeline/audit_noonnu.py
- Create: apps/pipeline/src/fontagit_pipeline/audit_license.py
- Create: apps/pipeline/tests/test_audit_noonnu.py
- Create: apps/pipeline/tests/test_audit_license.py
- Create: apps/pipeline/tests/fixtures/audit/noonnu-white-tailed-eagle.html
- Create: apps/pipeline/tests/fixtures/audit/noonnu-hoengseong-cow.html
- Modify: apps/pipeline/src/fontagit_pipeline/data/license_rules.json

**Interfaces:**
- Produces: extract_noonnu_font(html, source_url) -> NoonnuFontSnapshot
- Produces: classify_license(snapshot, registry, rules) -> LicenseDecision

- [ ] **Step 1: 눈누 범위 테스트 작성**

~~~python
def test_extracts_only_font_related_information():
    snapshot = extract_noonnu_font(load_fixture("noonnu-white-tailed-eagle.html"), NOONNU_613)
    assert snapshot.name_ko == "흰꼬리수리"
    assert snapshot.foundry == "네이버"
    assert snapshot.download_candidates == ["https://clova.ai/handwriting/list.html"]
    assert snapshot.license_text
    assert snapshot.global_social_links == []


def test_404_download_candidate_is_preserved_as_observation():
    snapshot = extract_noonnu_font(load_fixture("noonnu-hoengseong-cow.html"), HOENGSEONG_URL)
    assert snapshot.download_candidates
    assert snapshot.download_status == "needs_review"
~~~

- [ ] **Step 2: 라이선스 신뢰 테스트 작성**

~~~python
def test_approved_fingerprint_maps_six_fields():
    decision = classify_license(approved_ofl_snapshot(), registry(), rules())
    assert decision.status == "verified"
    assert decision.allow_commercial == "allowed"
    assert decision.allow_redistribute == "allowed"
    assert decision.evidence_locations["allow_redistribute"]


def test_custom_or_llm_extraction_never_verifies():
    decision = classify_license(custom_snapshot(extractor="llm"), registry(), rules())
    assert decision.status == "needs_review"
    assert decision.auto_applicable is False
~~~

- [ ] **Step 3: RED 확인**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_noonnu.py tests/test_audit_license.py -q
~~~

Expected: 두 모듈이 없어 실패.

- [ ] **Step 4: 눈누 parser 구현**

기존 noonnu_seed.py의 “첫 외부 링크” 휴리스틱을 재사용하지 않는다. 폰트 상세 영역 안에서 이름·영문명·제작사·분류·태그·가격·다운로드 CTA·라이선스 본문/허용표·웹폰트 CSS/파일 URL·굵기·스타일·페이지 ID만 추출한다. 하단 SNS·광고·메뉴·관련 폰트는 결과에서 제외한다.

원문 저장 정책이 structured-only면 raw_text는 None, raw_sha256과 evidence_locations는 유지한다.

- [ ] **Step 5: 결정론적 라이선스 판정 구현**

verified 조건은 아래 셋 중 하나다.

1. 표준 라이선스 ID·버전·원문 fingerprint가 license_rules.json과 정확히 일치
2. 승인된 제작사 템플릿의 domain·selector·template_version·fingerprint가 정확히 일치
3. finding이 reviewed_by와 reviewed_at을 가진 approved 상태

6개 필드는 allow_commercial, allow_modify, allow_redistribute, allow_embedding, allow_font_sale, attribution_requirement다. 원문에 없는 값은 null이다. 요약은 이 6개 값과 제한 문구만 사용한 고정 한국어 템플릿으로 만든다.

- [ ] **Step 6: GREEN과 회귀 검사**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_noonnu.py tests/test_audit_license.py -q
uv run pytest tests/test_noonnu_seed.py tests/test_noonnu_enrich.py -q
uv run ruff check src tests
uv run mypy src
~~~

Expected: 신규 테스트 4개와 기존 눈누 테스트 PASS.

- [ ] **Step 7: 커밋**

~~~bash
git add apps/pipeline/src/fontagit_pipeline/audit_noonnu.py \
  apps/pipeline/src/fontagit_pipeline/audit_license.py \
  apps/pipeline/src/fontagit_pipeline/data/license_rules.json \
  apps/pipeline/tests/test_audit_noonnu.py \
  apps/pipeline/tests/test_audit_license.py \
  apps/pipeline/tests/fixtures/audit
git commit -m "feat: extract and classify font license evidence"
~~~

---

### Task 6: append-only 저장, 검수 큐, 50종 파일럿

**Files:**
- Create: apps/pipeline/src/fontagit_pipeline/audit_store.py
- Create: apps/pipeline/src/fontagit_pipeline/audit_runner.py
- Create: apps/pipeline/tests/test_audit_runner.py
- Modify: apps/pipeline/src/fontagit_pipeline/__main__.py

**Interfaces:**
- Produces: AuditStore.start_run(), save_snapshot(), save_observation(), save_finding(), complete_run()
- Produces: select_pilot(fonts, size=50) -> list[FontTarget]
- Produces: run_legal_audit(targets, store, registry, rules) -> AuditReport
- CLI: font-audit-run --stage legal --limit 50 --out output/audit/pilot

- [ ] **Step 1: 파일럿과 멱등성 테스트 작성**

~~~python
def test_pilot_is_deterministic_and_contains_reported_fonts():
    selected = select_pilot(font_targets(), size=50)
    assert len(selected) == 50
    assert {"흰꼬리수리", "횡성한우체"} <= {font.name_ko for font in selected}
    assert selected == select_pilot(font_targets(), size=50)


def test_same_snapshot_and_finding_are_idempotent(fake_store):
    report1 = run_legal_audit([target()], fake_store, registry(), rules())
    report2 = run_legal_audit([target()], fake_store, registry(), rules())
    assert report1.snapshot_ids == report2.snapshot_ids
    assert fake_store.finding_count == 1
~~~

- [ ] **Step 2: RED 확인**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_runner.py -q
~~~

Expected: audit_runner 모듈이 없어 실패.

- [ ] **Step 3: AuditStore 구현**

모든 snapshot은 append-only insert다. 동일 font_id + provider + provider_record_id + document_kind + normalized_sha256면 기존 ID를 반환한다. finding은 run_id + font_id + field_name으로 upsert하되 applied finding은 수정하지 않고 새 run의 finding을 만든다.

- [ ] **Step 4: 파일럿 선택과 보고서 구현**

선택 순서는 흰꼬리수리·횡성한우체 고정 포함 → source tier → 제작사 → domain → slug 정렬의 층화 표본이다. 결과 JSON/Markdown에는 exact target, verified, needs_review, broken, 오류, 도메인별 집계를 기록한다.

후보 탐색 순서는 승인된 제작사 레지스트리 → 승인된 공공기관 레지스트리 → 눈누의 의미 있는 CTA → 기존 DB 주소다. 일반 검색 결과는 discovery finding만 만들며 자동 요청·자동 승인을 하지 않는다. 페이지의 정규화 폰트명, 제작사, 문서 역할(download/license)이 모두 맞아야 공식 후보가 된다. 제작사 홈페이지, 다운로드 페이지, 라이선스 원문 URL은 서로 다른 필드로 저장한다.

게이트는 아래와 같다.

~~~python
if report.pending_count:
    raise AuditGateError("pending remains")
if report.needs_review_count / report.target_count > 0.10:
    raise AuditGateError("pilot review ratio exceeds 10%")
~~~

- [ ] **Step 5: CLI 연결**

~~~text
fontagit-pipeline font-audit-run \
  --stage legal \
  --limit 50 \
  --require-slug 흰꼬리수리 \
  --require-slug 횡성한우체 \
  --out output/audit/pilot-legal
~~~

기본은 dev 쓰기이며 prod URL과 service key를 받지 않는다. --dry-run은 DB 대신 JSON artifact만 만든다.

- [ ] **Step 6: GREEN과 정적 검사**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_runner.py -q
uv run ruff check src tests
uv run mypy src
~~~

Expected: 테스트 2개 PASS, ruff/mypy 오류 0.

- [ ] **Step 7: 커밋**

~~~bash
git add apps/pipeline/src/fontagit_pipeline/audit_store.py \
  apps/pipeline/src/fontagit_pipeline/audit_runner.py \
  apps/pipeline/tests/test_audit_runner.py \
  apps/pipeline/src/fontagit_pipeline/__main__.py
git commit -m "feat: run deterministic font audit pilot"
~~~

---

### Task 7: 정방향·역방향 manifest와 원자 적용 RPC

**Files:**
- Create: apps/pipeline/src/fontagit_pipeline/audit_manifest.py
- Create: apps/pipeline/tests/test_audit_manifest.py
- Create: supabase/migrations/0018_apply_font_audit_manifest.sql
- Create: supabase/tests/font_audit_manifest_test.sql
- Modify: apps/pipeline/src/fontagit_pipeline/__main__.py

**Interfaces:**
- Produces: build_manifest(run, approved_findings, current_rows) -> ManifestBundle
- Produces: verify_manifest_file(path, sha256_path) -> FontAuditManifest
- DB RPC: fontagit.apply_font_source_bootstrap(p_manifest_text text, p_expected_sha256 text, p_schema_version integer) -> integer
- DB RPC: fontagit.apply_font_audit_manifest(p_manifest_text text, p_expected_sha256 text, p_schema_version integer) -> integer

- [ ] **Step 1: manifest 생성 테스트 작성**

~~~python
def test_manifest_contains_stable_key_before_values_and_reverse():
    bundle = build_manifest(run(), approved_findings(), current_rows())
    entry = bundle.forward.entries[0]
    assert entry.source_key.model_dump() == {
        "provider": "noonnu",
        "provider_record_id": "613",
    }
    assert entry.before["official_url"] == INSTAGRAM_URL
    assert bundle.forward.evidence_bundle.snapshots[0].id == entry.evidence_ids[0]
    assert bundle.reverse.entries[0].after == entry.before
    assert bundle.forward_sha256 != bundle.reverse_sha256


def test_manifest_rejects_unapproved_or_unknown_field():
    with pytest.raises(ManifestError):
        build_manifest(run(), [finding(status="proposed", field_name="status")], current_rows())
~~~

- [ ] **Step 2: Python RED 확인**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_manifest.py -q
~~~

Expected: audit_manifest 모듈이 없어 실패.

- [ ] **Step 3: manifest builder 구현**

1단계 허용 필드는 foundry, foundry_url, download_url, license_source_url, license_summary, source kind 2개, evidence ID 2개, status 2개, checked_at 2개, 라이선스 6개, legacy is_commercial_free, license_verified다. 2단계 허용 필드는 name_en, name_ko, category_ko, tags, weights, variants다. official_url, slug, fonts.status는 변경 허용 목록에서 제외한다.

각 entry에는 source_key, current slug/name/foundry, before, after, evidence_ids, expected_updated_at이 있다. license_status가 needs_review면 license_verified를 false로 dual-write하고, verified일 때만 true로 쓴다. manifest의 evidence_bundle에는 참조하는 audit run, 승인된 snapshot, finding을 원래 UUID와 함께 넣되 dev font_id 대신 안정 source_key를 넣는다. RPC가 source_key를 prod font_id로 다시 해석해 FK를 만든다. raw 보관이 허용되지 않은 snapshot은 raw_text가 null이고 structured data·근거 위치·hash만 포함한다. JSON은 key 정렬·UTF-8·개행 LF로 직렬화해 SHA-256을 만든다.

- [ ] **Step 4: SQL RPC와 핵심 3개 DB 테스트 작성**

apply_font_audit_manifest RPC는 다음 순서로 동작한다.

1. service_role인지 확인
2. p_manifest_text의 UTF-8 바이트를 extensions.digest로 계산해 expected SHA-256과 비교
3. 검증이 끝난 text를 jsonb로 변환하고 schema_version = 1, entries 1~1,240인지 확인
4. evidence_bundle의 run·snapshot·finding을 동일 UUID로 insert하고 기존 UUID가 있으면 전체 내용 hash가 같은지 확인
5. stable key가 정확히 한 font_id에 연결되는지 확인
6. before와 updated_at, evidence FK/자료 종류/출처 종류를 전 행 검사
7. 허용 필드만 한 트랜잭션에서 update
8. finding을 applied로 전환하고 변경 수 반환

evidence import부터 fonts update까지 한 트랜잭션이다. evidence 한 건이라도 기존 prod 값과 다르거나 대상 font_id를 안정키로 다시 해석할 수 없으면 evidence insert와 fonts update를 모두 취소한다.

apply_font_source_bootstrap RPC는 같은 service-role·해시·스키마 검증 뒤 현재 source_tier, 이름, slug, 기존 URL, foundry 공란 precondition을 확인한다. 조건이 모두 맞는 행만 font_sources에 넣고 public fonts 값은 바꾸지 않는다. 한 행이라도 불일치·중복이면 전체 insert를 취소한다.

0018은 기존 fonts_published_license_chk를 호환 제약으로 교체한다. pending은 기존 license_verified 규칙을 유지하고, verified는 license_verified = true, needs_review는 license_verified = false인 published 행을 허용한다. 이 호환 제약이 먼저 적용되어야 data manifest가 needs_review 행을 false로 바꿀 수 있다.

~~~sql
alter table fontagit.fonts drop constraint if exists fonts_published_license_chk;
alter table fontagit.fonts
  add constraint fonts_published_license_compat_chk check (
    status <> 'published'
    or (
      license_status = 'pending'
      and license_verified = true
      and (source_tier <> 'A' or license_type in ('OFL', 'Apache-2.0', 'UFL'))
    )
    or (
      license_status = 'verified'
      and license_verified = true
      and (source_tier <> 'A' or license_type in ('OFL', 'Apache-2.0', 'UFL'))
    )
    or (license_status = 'needs_review' and license_verified = false)
  );
~~~

font_audit_manifest_test.sql은 다음 3개 트랜잭션 케이스만 둔다.

- 전부 일치: 2건 모두 적용
- 한 행 before 불일치: 예외 후 0건 변경
- 정방향 적용 후 역방향 적용: 대상 필드 byte-for-byte 동일

같은 SQL 파일에서 bootstrap RPC는 정상 2건 전량 insert와 provider key 충돌 시 0건 insert 두 경우만 검증한다.

- [ ] **Step 5: dev 적용과 GREEN**

~~~bash
psql "$DEV_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/0018_apply_font_audit_manifest.sql
psql "$DEV_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/tests/font_audit_manifest_test.sql
cd apps/pipeline
uv run pytest tests/test_audit_manifest.py -q
~~~

Expected: SQL ALL PASS, Python 테스트 2개 PASS.

- [ ] **Step 6: CLI 연결**

~~~text
fontagit-pipeline font-audit-manifest build \
  --run-id RUN_UUID \
  --out output/audit/manifests

fontagit-pipeline font-audit-manifest apply \
  --manifest output/audit/manifests/forward.json \
  --sha256 output/audit/manifests/forward.sha256 \
  --target dev \
  --confirm-hash FULL_SHA256
~~~

prod target은 --target prod, --confirm-hash, 대화형 yes를 모두 요구한다. 명시적 사용자 승인 전 실행하지 않는다.

- [ ] **Step 7: 커밋**

~~~bash
git add apps/pipeline/src/fontagit_pipeline/audit_manifest.py \
  apps/pipeline/tests/test_audit_manifest.py \
  apps/pipeline/src/fontagit_pipeline/__main__.py \
  supabase/migrations/0018_apply_font_audit_manifest.sql \
  supabase/tests/font_audit_manifest_test.sql
git commit -m "feat: apply font audit manifest atomically"
~~~

---

### Task 8: 기존 파이프라인의 재오염 경로 차단

**Files:**
- Modify: apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py
- Modify: apps/pipeline/src/fontagit_pipeline/noonnu_review.py
- Modify: apps/pipeline/src/fontagit_pipeline/noonnu_publish.py
- Modify: apps/pipeline/src/fontagit_pipeline/__main__.py
- Modify: apps/pipeline/tests/test_noonnu_enrich.py
- Modify: apps/pipeline/tests/test_noonnu_review.py
- Modify: apps/pipeline/tests/test_noonnu_publish.py

**Interfaces:**
- noonnu-enrich: snapshot/finding 후보만 생성
- noonnu-review approve: finding approved만 설정
- noonnu-publish: 쓰기 금지, manifest 생성 안내만 제공

- [ ] **Step 1: 재오염 방지 회귀 테스트 수정**

~~~python
def test_enrich_never_updates_verified_font_fields(mock_schema):
    enrich_fonts(SUPABASE_URL, SECRET, limit=1)
    assert not mock_schema.table("fonts").update.called
    assert mock_schema.table("font_audit_findings").upsert.called


def test_legacy_publish_confirm_is_rejected(mock_schema):
    with pytest.raises(RuntimeError, match="font-audit-manifest"):
        publish_to_prod(mock_schema, PROD_URL, PROD_KEY, dry_run=False)
~~~

- [ ] **Step 2: RED 확인**

~~~bash
cd apps/pipeline
uv run pytest tests/test_noonnu_enrich.py \
  tests/test_noonnu_review.py tests/test_noonnu_publish.py -q
~~~

Expected: 기존 fonts update와 row-by-row prod upsert 때문에 실패.

- [ ] **Step 3: 단일 writer 전환**

noonnu_enrich.py의 _font_update와 fonts update를 제거하고 snapshot + finding만 쓴다. noonnu_review.py approve는 review_status가 아니라 font_audit_findings.status = approved, reviewed_by, reviewed_at만 바꾼다. noonnu_publish.py의 실제 upsert는 RuntimeError로 막고 dry-run은 대상 수·legacy 필드 소비자 경고만 출력한다.

__main__.py의 noonnu-publish --confirm 도움말은 deprecated로 표시하고 실제 적용 명령은 font-audit-manifest apply로 안내한다.

- [ ] **Step 4: GREEN과 전체 파이프라인 검사**

~~~bash
cd apps/pipeline
uv run pytest -q
uv run ruff check .
uv run mypy src
~~~

Expected: 전체 pipeline 테스트 PASS, ruff/mypy 오류 0.

- [ ] **Step 5: 커밋**

~~~bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py \
  apps/pipeline/src/fontagit_pipeline/noonnu_review.py \
  apps/pipeline/src/fontagit_pipeline/noonnu_publish.py \
  apps/pipeline/src/fontagit_pipeline/__main__.py \
  apps/pipeline/tests/test_noonnu_enrich.py \
  apps/pipeline/tests/test_noonnu_review.py \
  apps/pipeline/tests/test_noonnu_publish.py
git commit -m "fix: prevent legacy font audit field writes"
~~~

---

### Task 9: 웹 dual-read와 라이선스 상세 표시

**Files:**
- Modify: apps/web/lib/db/types.ts
- Modify: apps/web/lib/db/mappers.ts
- Modify: apps/web/types/font.ts
- Modify: apps/web/lib/license.ts
- Modify: apps/web/components/LicenseSummaryCard.tsx
- Modify: apps/web/components/LicenseSummaryCard.module.css
- Modify: apps/web/__tests__/mappers.test.ts
- Modify: apps/web/components/LicenseSummaryCard.test.tsx

**Interfaces:**
- FontRow: 신규 nullable DB 필드 추가
- Font.licenseAudit: 6개 권한·상태·근거·확인일
- Font.downloadUrl: verified 다운로드 CTA에만 사용
- Font.foundryUrl: 제작사 홈페이지 전용
- Font.legacyOfficialUrl: migration 직후 pending 호환 모드 전용

- [ ] **Step 1: mapper 핵심 3상태 테스트 수정**

~~~typescript
it("prefers verified audit fields over legacy values", () => {
  const font = rowToFont(verifiedAuditRow(), []);
  expect(font.downloadUrl).toBe("https://clova.ai/handwriting/list.html");
  expect(font.licenseAudit.status).toBe("verified");
  expect(font.licenseAudit.redistribute).toBe("unknown");
});

it("does not fallback to official_url after needs_review classification", () => {
  const font = rowToFont(needsReviewAuditRow({ official_url: INSTAGRAM_URL }), []);
  expect(font.downloadUrl).toBeNull();
  expect(font.licenseAudit.status).toBe("needs_review");
});

it("keeps legacy rendering before backfill", () => {
  const font = rowToFont(legacyRow(), []);
  expect(font.licenseAudit.sourceMode).toBe("legacy");
  expect(font.legacyOfficialUrl).toBe(LEGACY_DOWNLOAD_URL);
});
~~~

- [ ] **Step 2: RED 확인**

~~~bash
pnpm --dir apps/web test --run __tests__/mappers.test.ts
~~~

Expected: licenseAudit/downloadUrl 속성이 없어 실패.

- [ ] **Step 3: 타입과 mapper 구현**

신규 타입은 아래 값을 사용한다.

~~~typescript
export type AuditPermission = "allowed" | "conditional" | "denied" | "unknown";
export type AuditStatus = "pending" | "verified" | "needs_review" | "broken";

export interface FontLicenseAudit {
  status: AuditStatus;
  sourceMode: "audit" | "legacy";
  summary: string | null;
  sourceUrl: string | null;
  sourceKind: "official" | "public" | null;
  checkedAt: string | null;
  commercial: AuditPermission;
  modify: AuditPermission;
  redistribute: AuditPermission;
  embedding: AuditPermission;
  fontSale: AuditPermission;
  attribution: "required" | "recommended" | "not_required" | "unknown";
}
~~~

새 상태가 pending이고 신규 근거가 전혀 없을 때만 sourceMode = legacy로 읽는다. 이 호환 모드에서는 legacyOfficialUrl을 별도로 유지한다. 상태가 verified/needs_review/broken으로 분류된 뒤에는 legacyOfficialUrl을 CTA로 사용하지 않는다. downloadUrl은 download_status = verified일 때만 설정한다.

- [ ] **Step 4: 상세 카드 변경**

verified면 6개 권한, FontAgit 요약, 확인일, 제작사/공공기관 출처 표시, 라이선스 원문 링크를 보여준다. needs_review/broken이면 권한 단정을 숨기고 “라이선스 재확인 필요”를 표시한다. audit 모드에서 downloadUrl이 null이면 CTA 자체를 렌더하지 않는다. migration 직후 pending + evidence 없음인 legacy 모드에서만 기존 CTA를 유지한다. foundryUrl은 별도 “제작사 홈페이지” 링크로 표시한다.

단순 UI 로직이므로 신규 테스트 파일은 만들지 않는다. 기존 LicenseSummaryCard.test.tsx의 기대값만 새 계약에 맞춘다.

- [ ] **Step 5: GREEN과 웹 전체 검증**

~~~bash
pnpm --dir apps/web test --run
pnpm --dir apps/web lint
pnpm --dir apps/web exec tsc --noEmit
pnpm --dir apps/web build
~~~

Expected: 테스트·lint·typecheck·정적 build 모두 성공. 흰꼬리수리 pending fixture에서 다운로드 CTA가 없다.

- [ ] **Step 6: 커밋**

~~~bash
git add apps/web/lib/db/types.ts apps/web/lib/db/mappers.ts \
  apps/web/types/font.ts apps/web/lib/license.ts \
  apps/web/components/LicenseSummaryCard.tsx \
  apps/web/components/LicenseSummaryCard.module.css \
  apps/web/__tests__/mappers.test.ts \
  apps/web/components/LicenseSummaryCard.test.tsx
git commit -m "feat: show verified font license evidence"
~~~

---

### Task 10: 쓰기 키 없는 예약 링크 검사와 artifact import

**Files:**
- Create: .github/workflows/font-audit-links.yml
- Create: .github/workflows/font-audit-license.yml
- Modify: apps/pipeline/src/fontagit_pipeline/audit_runner.py
- Modify: apps/pipeline/src/fontagit_pipeline/audit_store.py
- Modify: apps/pipeline/src/fontagit_pipeline/__main__.py
- Modify: apps/pipeline/tests/test_audit_runner.py

**Interfaces:**
- CLI: font-audit-scan --kind download|license --source prod-public --out observations.json
- CLI: font-audit-import --artifact observations.json --sha256 observations.sha256

- [ ] **Step 1: artifact 인계 핵심 테스트 추가**

~~~python
def test_import_requires_hash_schema_and_previous_observation(fake_store):
    artifact = scheduled_artifact(schema_version=1, status=404)
    first = import_observations(artifact, artifact.sha256, fake_store)
    assert first.status == "needs_review"
    second = import_observations(
        scheduled_artifact(schema_version=1, status=404, hours_after=25),
        artifact.sha256,
        fake_store,
    )
    assert second.status == "broken"


def test_empty_artifact_fails():
    with pytest.raises(AuditGateError, match="empty artifact"):
        build_scheduled_artifact([])


def test_license_hash_change_creates_review_not_auto_update(fake_store):
    result = import_observations(changed_license_artifact(), VALID_SHA256, fake_store)
    assert result.status == "needs_review"
    assert result.applied_count == 0
~~~

- [ ] **Step 2: RED 확인**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_runner.py -k "import_requires or empty_artifact" -q
~~~

Expected: import_observations/build_scheduled_artifact가 없어 실패.

- [ ] **Step 3: scan/import 구현**

scan은 --kind download 또는 --kind license와 prod 공개 anon URL/key만 받는다. artifact는 schema_version, run_id, generated_at, target_count, observations를 갖고 원문 HTML과 시크릿을 포함하지 않는다. target 0건, 빈 observations, 처리하지 못한 오류가 있으면 종료 코드 3이다. 라이선스 해시 변경은 needs_review finding만 만들고 공개값을 자동 변경하지 않는다.

import는 사람이 dev service key로 실행한다. 해시·스키마·run_id 중복을 검사하고 관찰 snapshot/finding만 저장한다. prod를 수정하지 않는다.

- [ ] **Step 4: GitHub Actions 작성**

~~~bash
mkdir -p .github/workflows
~~~

~~~yaml
name: font-audit-links
on:
  workflow_dispatch:
  schedule:
    - cron: "17 18 * * 1"
permissions:
  contents: read
jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
        working-directory: apps/pipeline
      - run: uv run python -m fontagit_pipeline font-audit-scan --kind download --source prod-public --out output/audit/scheduled
        working-directory: apps/pipeline
        env:
          SUPABASE_URL: ${{ secrets.PROD_PUBLIC_SUPABASE_URL }}
          SUPABASE_ANON_KEY: ${{ secrets.PROD_PUBLIC_SUPABASE_ANON_KEY }}
      - uses: actions/upload-artifact@v4
        with:
          name: font-audit-observations
          path: |
            apps/pipeline/output/audit/scheduled/observations.json
            apps/pipeline/output/audit/scheduled/observations.sha256
          retention-days: 7
          if-no-files-found: error
~~~

workflow에는 dev/prod service key 이름을 넣지 않는다.

font-audit-license.yml은 같은 권한·설치·artifact 실패 규칙을 사용하고 아래 일정과 명령을 사용한다.

~~~yaml
name: font-audit-license
on:
  workflow_dispatch:
  schedule:
    - cron: "41 18 1 1,4,7,10 *"
permissions:
  contents: read
jobs:
  scan:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
        working-directory: apps/pipeline
      - run: uv run python -m fontagit_pipeline font-audit-scan --kind license --source prod-public --out output/audit/scheduled-license
        working-directory: apps/pipeline
        env:
          SUPABASE_URL: ${{ secrets.PROD_PUBLIC_SUPABASE_URL }}
          SUPABASE_ANON_KEY: ${{ secrets.PROD_PUBLIC_SUPABASE_ANON_KEY }}
      - uses: actions/upload-artifact@v4
        with:
          name: font-audit-license-observations
          path: |
            apps/pipeline/output/audit/scheduled-license/observations.json
            apps/pipeline/output/audit/scheduled-license/observations.sha256
          retention-days: 7
          if-no-files-found: error
~~~

- [ ] **Step 5: GREEN과 workflow 정적 검증**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_runner.py -q
cd ../..
ruby -e 'require "yaml"; ARGV.each { |f| YAML.load_file(f) }' \
  .github/workflows/font-audit-links.yml .github/workflows/font-audit-license.yml
rg -n "SERVICE|SECRET_KEY|PROD_SECRET" \
  .github/workflows/font-audit-links.yml .github/workflows/font-audit-license.yml
~~~

Expected: 테스트 PASS, YAML 파싱 성공, 마지막 rg 결과 0건.

- [ ] **Step 6: 커밋**

~~~bash
git add .github/workflows/font-audit-links.yml \
  .github/workflows/font-audit-license.yml \
  apps/pipeline/src/fontagit_pipeline/audit_runner.py \
  apps/pipeline/src/fontagit_pipeline/audit_store.py \
  apps/pipeline/src/fontagit_pipeline/__main__.py \
  apps/pipeline/tests/test_audit_runner.py
git commit -m "feat: schedule read-only font link audits"
~~~

---

### Task 11: 2단계 일반 메타데이터 감사

**Files:**
- Create: apps/pipeline/src/fontagit_pipeline/audit_metadata.py
- Create: apps/pipeline/tests/test_audit_metadata.py
- Modify: apps/pipeline/src/fontagit_pipeline/audit_runner.py
- Modify: apps/pipeline/src/fontagit_pipeline/__main__.py
- Modify: apps/pipeline/pyproject.toml
- Modify: apps/pipeline/uv.lock

**Interfaces:**
- Produces: inspect_font_metadata(path) -> FontFileMetadata
- Produces: compare_metadata(target, official_snapshot, file_metadata) -> list[FindingDraft]
- CLI: font-audit-run --stage metadata

- [ ] **Step 1: 핵심 메타데이터 충돌 테스트 작성**

~~~python
def test_official_file_confirms_weight_and_italic():
    metadata = from_name_table_and_os2(name="Example Sans", weight=700, italic=True)
    findings = compare_metadata(target(weights=[400]), official_snapshot(), metadata)
    assert proposed(findings, "weights") == [700]
    assert proposed(findings, "variants") == ["italic"]


def test_page_file_name_conflict_requires_review():
    metadata = from_name_table_and_os2(name="Other Font", weight=400, italic=False)
    findings = compare_metadata(target(name_en="Example Sans"), official_snapshot(), metadata)
    assert all(item.auto_applicable is False for item in findings)
    assert reason(findings, "name_en") == "official page/file name conflict"
~~~

- [ ] **Step 2: RED 확인**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_metadata.py -q
~~~

Expected: audit_metadata 모듈이 없어 실패.

- [ ] **Step 3: fontTools adapter와 비교 규칙 구현**

먼저 dependency와 lock을 갱신한다.

~~~bash
cd apps/pipeline
uv add fonttools
~~~

공식 배포 파일은 최대 크기 제한 내에서 임시 파일로만 읽고 DB에 바이너리를 저장하지 않는다. name table, OS/2 usWeightClass, head/macStyle, post/italicAngle을 구조화 값과 파일 SHA-256으로 저장한다.

페이지와 파일의 폰트명이 다르거나 파일에 여러 family가 있으면 모든 제안을 needs_review로 만든다. 이름이 일치할 때만 weights와 variants를 자동 적용 후보로 만든다. category와 tags는 공식 페이지 값이 있어도 검수 후보로만 둔다.

- [ ] **Step 4: runner/CLI 연결**

metadata stage는 legal stage에서 verified된 official/public source만 입력으로 받는다. 눈누 단독 파일 URL과 discovery 도메인은 다운로드하지 않는다.

- [ ] **Step 5: GREEN과 전체 pipeline 검증**

~~~bash
cd apps/pipeline
uv run pytest tests/test_audit_metadata.py -q
uv run pytest -q
uv run ruff check .
uv run mypy src
~~~

Expected: 신규 2개와 전체 pipeline 테스트 PASS.

- [ ] **Step 6: 커밋**

~~~bash
git add apps/pipeline/src/fontagit_pipeline/audit_metadata.py \
  apps/pipeline/tests/test_audit_metadata.py \
  apps/pipeline/src/fontagit_pipeline/audit_runner.py \
  apps/pipeline/src/fontagit_pipeline/__main__.py \
  apps/pipeline/pyproject.toml apps/pipeline/uv.lock
git commit -m "feat: audit official font metadata"
~~~

---

### Task 12: dev 파일럿과 1,240종 전수 조사

**Files:**
- Modify: docs/runbooks/prod-font-data-audit.md
- Modify: docs/progress/progress.md
- Generate, do not commit raw: apps/pipeline/output/audit/

**Interfaces:**
- Consumes: Task 1~11 코드와 dev migrations
- Produces: 승인 가능한 dev findings, 정·역 manifest, 요약 보고서

- [ ] **Step 1: 착수 전 기준선과 법적 수집 게이트 확인**

~~~bash
git status --short
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-policy-check \
  --out output/audit/source-policy.json
uv run python -m fontagit_pipeline font-audit-export-baseline \
  --source prod-public \
  --out output/audit/prod-fonts-baseline.json
~~~

Expected:

- published exact count = 1,240 또는 사용자가 승인한 새 기준선
- slug 중복 0
- robots/이용 조건 결과에 crawl_allowed와 raw_retention_allowed가 명시됨
- raw_retention_allowed가 false/unknown이면 structured-only

- [ ] **Step 2: 안정키 bootstrap dry-run**

~~~bash
uv run python -m fontagit_pipeline font-audit-bootstrap \
  --prod-snapshot output/audit/prod-fonts-baseline.json \
  --out output/audit/bootstrap-manifest.json
~~~

Expected: matched + unmatched + conflicts = 기준선. unmatched/conflicts는 자동 manifest에서 제외.

- [ ] **Step 3: 50종 파일럿 실행**

~~~bash
uv run python -m fontagit_pipeline font-audit-run \
  --stage legal --limit 50 \
  --require-slug 흰꼬리수리 \
  --require-slug 횡성한우체 \
  --out output/audit/pilot-legal
~~~

Expected:

- pending = 0
- 흰꼬리수리의 눈누 인스타그램은 verified 출처가 아님
- 횡성한우체의 단일 4xx는 needs_review
- needs_review 비율이 10% 이하면 다음 단계
- 10% 초과면 제작사/템플릿별 승인 규칙을 보강하고 Step 3 재실행

- [ ] **Step 4: 1단계 전수 조사와 24시간 재확인**

~~~bash
uv run python -m fontagit_pipeline font-audit-run \
  --stage legal --all --out output/audit/full-legal-pass-1
~~~

첫 실행 후 24시간 이상 지난 별도 실행에서 같은 명령을 full-legal-pass-2로 실행한다. 자동 sleep을 사용하지 않는다. 두 실행의 run_id가 달라야 한다.

Expected: 모든 대상의 download_status와 license_status가 pending이 아님. broken은 두 실행에서 같은 정규화 URL이 404/410인 경우만 존재.

- [ ] **Step 5: 2단계 메타데이터 조사**

~~~bash
uv run python -m fontagit_pipeline font-audit-run \
  --stage metadata --all --out output/audit/full-metadata
~~~

Expected: 공식 파일과 페이지가 일치한 값만 auto_applicable. 이름 충돌은 전부 needs_review.

- [ ] **Step 6: dev 검수·manifest·왕복 적용**

~~~bash
uv run python -m fontagit_pipeline font-audit-manifest build \
  --run-id "$APPROVED_RUN_ID" \
  --out output/audit/manifests
uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/audit/manifests/forward.json \
  --sha256 output/audit/manifests/forward.sha256 \
  --target dev --confirm-hash "$FORWARD_SHA256"
uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/audit/manifests/reverse.json \
  --sha256 output/audit/manifests/reverse.sha256 \
  --target dev --confirm-hash "$REVERSE_SHA256"
~~~

역방향 적용 후 기준선 대상 필드가 byte-for-byte 동일해야 한다. 그 다음 정방향 manifest를 dev에 다시 적용하고 같은 manifest 재실행이 0건 변경인지 확인한다.

- [ ] **Step 7: 전체 품질 게이트**

~~~bash
cd apps/pipeline
uv run pytest -q
uv run ruff check .
uv run mypy src
cd ../web
pnpm test --run
pnpm lint
pnpm exec tsc --noEmit
pnpm build
~~~

Expected: 전부 성공. 보고서에는 target/verified/needs_review/broken/unmatched/conflict와 대표 근거가 있다.

- [ ] **Step 8: 사용자 승인 게이트**

다음 숫자를 사용자에게 보고하고 prod 쓰기를 멈춘다.

- 최신 prod exact count와 기준선 차이
- 안정키 matched/unmatched/conflicts
- 다운로드 verified/needs_review/broken
- 라이선스 verified/needs_review
- 자동 적용 필드 수와 수동 승인 필드 수
- 흰꼬리수리·횡성한우체 최종 판정
- forward/reverse SHA-256

사용자가 미해결 건수와 prod 적용을 명시적으로 승인해야 Task 13으로 진행한다.

- [ ] **Step 9: 진행 문서 커밋**

원문 HTML, prod snapshot, manifest, 시크릿은 커밋하지 않는다. 요약 통계와 실행 ID만 progress에 기록한다.

~~~bash
git add docs/runbooks/prod-font-data-audit.md docs/progress/progress.md
git commit -m "docs: record dev font audit verification"
~~~

---

### Task 13: 승인 후 prod 호환 배포·원자 적용·최종 검증

**Files:**
- Create: supabase/migrations/0019_enforce_font_audit_constraints.sql
- Modify: docs/runbooks/prod-font-data-audit.md
- Modify: docs/progress/progress.md

**Interfaces:**
- Consumes: 사용자 승인된 migration, bootstrap manifest, forward/reverse data manifest
- Produces: prod DB·정적 페이지 검증 증거

- [ ] **Step 1: 사용자 승인과 대상 재확인**

아래 네 값이 승인 보고서와 정확히 같아야 한다.

~~~text
baseline_sha256
bootstrap_manifest_sha256
forward_manifest_sha256
target_count
~~~

하나라도 다르면 prod 반영을 중단하고 Task 12 기준선을 새로 만든다.

적용 직전 prod 공개 필드와 updated_at을 slug 정렬 JSON으로 다시 내보내고 해시를 고정한다.

~~~bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-export-baseline \
  --source prod-public \
  --out output/audit/prod-before-apply.json
~~~

이 해시가 승인 baseline과 다르면 다음 단계로 진행하지 않는다.

- [ ] **Step 2: prod additive migration**

~~~bash
psql "$PROD_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/0017_font_audit_schema.sql
~~~

적용 전후 published count와 기존 official_url/is_commercial_free/license_verified 해시가 같아야 한다.

- [ ] **Step 3: 호환 웹 배포**

새 nullable 필드 우선 + legacy fallback 코드를 먼저 배포한다.

~~~bash
./scripts/deploy.sh
~~~

Expected: 배포 성공, 기존 상세 페이지 3종과 /fonts가 HTTP 200, 다운로드 CTA 동작이 배포 전과 동일.

- [ ] **Step 4: prod RPC migration과 bootstrap 적용**

~~~bash
psql "$PROD_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/0018_apply_font_audit_manifest.sql
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/audit/bootstrap-manifest.json \
  --sha256 output/audit/bootstrap-manifest.sha256 \
  --target prod --confirm-hash "$BOOTSTRAP_SHA256"
~~~

Expected: matched 건수만 적용, public fonts 값 변경 0, unmatched/conflict 자동 적용 0.

- [ ] **Step 5: prod data manifest 원자 적용**

~~~bash
uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/audit/manifests/forward.json \
  --sha256 output/audit/manifests/forward.sha256 \
  --target prod --confirm-hash "$FORWARD_SHA256"
~~~

Expected: 승인 대상 전체 적용. 한 행이라도 before/updated_at/evidence가 다르면 트랜잭션 전체 0건.

- [ ] **Step 6: CHECK 강화**

0019는 아래 불변식을 추가한다.

~~~sql
alter table fontagit.fonts
  drop constraint if exists fonts_published_license_chk;

alter table fontagit.fonts
  drop constraint if exists fonts_published_license_compat_chk;

alter table fontagit.fonts
  add constraint fonts_published_license_chk check (
    status <> 'published'
    or (
      license_status in ('verified', 'needs_review')
      and (
        license_status <> 'verified'
        or (
          license_verified = true
          and (source_tier <> 'A' or license_type in ('OFL', 'Apache-2.0', 'UFL'))
        )
      )
    )
  ),
  add constraint fonts_verified_download_complete check (
    download_status <> 'verified'
    or (
      download_url is not null
      and download_checked_at is not null
      and download_source_kind in ('official', 'public')
      and download_evidence_id is not null
    )
  ),
  add constraint fonts_verified_license_complete check (
    license_status <> 'verified'
    or (
      license_verified = true
      and license_source_url is not null
      and license_checked_at is not null
      and license_source_kind in ('official', 'public')
      and license_evidence_id is not null
    )
  );
~~~

Run:

~~~bash
psql "$PROD_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/0019_enforce_font_audit_constraints.sql
~~~

- [ ] **Step 7: 새 데이터 정적 빌드·배포**

~~~bash
./scripts/deploy.sh
~~~

Expected:

- 정적 font page 수 = prod published count
- 흰꼬리수리: 제작사/다운로드/라이선스 출처가 눈누 인스타그램 아님
- 횡성한우체: verified 대체 주소가 없으면 CTA 없음, 재확인 표시
- verified 폰트: 6개 권한과 원문 링크 표시
- needs_review 폰트: 권한 단정 없음

- [ ] **Step 8: prod DB·라이브 페이지 직접 검증**

~~~bash
psql "$PROD_DATABASE_URL" -v ON_ERROR_STOP=1 -c "
select download_status, count(*) from fontagit.fonts
where status='published' group by 1 order by 1;
select license_status, count(*) from fontagit.fonts
where status='published' group by 1 order by 1;
"
curl -fsS "https://fontagit.com/fonts/%ED%9D%B0%EA%BC%AC%EB%A6%AC%EC%88%98%EB%A6%AC/" >/dev/null
curl -fsS "https://fontagit.com/fonts/%ED%9A%A1%EC%84%B1%ED%95%9C%EC%9A%B0%EC%B2%B4/" >/dev/null
~~~

Expected: DB 집계 합계가 published exact count와 같고 두 페이지 HTTP 200.

- [ ] **Step 9: 실패 시 되돌리기**

DB 이상이면 새 manifest를 만들지 않는다. 승인된 reverse manifest만 적용한다.

~~~bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/audit/manifests/reverse.json \
  --sha256 output/audit/manifests/reverse.sha256 \
  --target prod --confirm-hash "$REVERSE_SHA256"
~~~

그 다음 직전 정상 정적 산출물을 재배포한다. 일부 복원은 허용하지 않는다.

- [ ] **Step 10: 진행 문서와 최종 커밋**

progress에는 최종 exact count, 상태별 수, manifest SHA-256, 배포 URL, 검증 시각, unresolved 건수를 기록한다. 시크릿과 원문은 기록하지 않는다.

~~~bash
git add supabase/migrations/0019_enforce_font_audit_constraints.sql \
  docs/runbooks/prod-font-data-audit.md docs/progress/progress.md
git commit -m "docs: record production font audit rollout"
~~~

---

## 최종 완료 조건

- 기준선 전체가 다운로드·라이선스 상태를 가지며 pending이 없다.
- stable source key가 단일 매칭되지 않는 행은 자동 적용되지 않는다.
- 공식·공공기관 evidence가 없는 값은 verified가 아니다.
- 흰꼬리수리의 잘못된 눈누 인스타그램 출처가 제거된다.
- 횡성한우체는 검증 주소가 없으면 페이지 유지 + CTA 제거 + 재확인 표시다.
- 기존 noonnu/updater가 신규 검증 필드를 직접 쓸 수 없다.
- 정방향·역방향 manifest 왕복이 byte-for-byte 원복된다.
- prod apply는 전량 적용 또는 0건 적용이다.
- 예약 검사는 쓰기 키 없이 실행되고 빈 artifact를 실패 처리한다.
- prod DB 집계, 정적 build 페이지 수, 실제 두 상세 페이지를 직접 확인한다.
- 사용자 승인 없는 prod 쓰기·배포가 없다.
