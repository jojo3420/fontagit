# 라이선스 검수 + 크롤 고도화 파이프라인 구현 계획 (S0~S3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 감사 체인에 출처 등급 체계(archive 포함)-Tier A 공식 수집기-눈누 승격-KOGL 파서를 추가해 제작사/다운로드/KOGL 데이터를 안전하게 적용 가능하게 만든다.

**Architecture:** 기존 감사 체인(수집 → FindingDraft → auto-approve → manifest 청크 → apply RPC)을 확장한다. 신규 모듈 2개(tier_a_meta, audit_kogl)와 정책 확장(archive 등급), manifest 무결성 가드가 핵심이다.

**Tech Stack:** Python 3.12+, pydantic, httpx, pytest(uv), Supabase REST(PostgREST)

**Spec:** `docs/superpowers/specs/2026-07-27-license-audit-crawl-design.md`

## Global Constraints

- prod 쓰기는 사용자 확인 필수(`FONTAGIT_PROD_MANIFEST_ENABLED=true` 게이트), legal 값 적용은 사람 승인 게이트
- 눈누 크롤 실행은 사용자 승인 후에만 (하드 게이트)
- manifest 청크 100, prod REST in-list 40
- dev 조회 `Accept-Profile: fontagit`, 쓰기 `Content-Profile: fontagit`
- 등급 우선순위 official > public > archive > null. 같거나 높은 등급만 갱신
- Type Hints 100%, Docstring 한국어, print 금지(logging), 하드코딩 금지(상수/데이터 파일)
- 테스트 실행: `cd apps/pipeline && uv run pytest tests/<파일> -q`
- 커밋 형식: `<타입>: <설명>` (feat/fix/test/docs/chore)

---

### Task 1: manifest 청크 참조 무결성 가드 (S0, #114)

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/audit_manifest.py` (`split_manifest_into_chunks`, 753행 부근)
- Test: `apps/pipeline/tests/test_audit_manifest.py`
- Modify: `scripts/audit-chain.sh` (청크 apply 실패 메시지)

**Interfaces:**
- Consumes: `split_manifest_into_chunks(bundle: ManifestBundle, chunk_size: int) -> list[ManifestBundle]`, `ManifestError(ValueError)` (audit_manifest.py:126), `ManifestEntry.evidence_ids/finding_ids`
- Produces: 동일 시그니처 유지(내부에 검증 추가). 신규 헬퍼 `_validate_chunk_references(chunk_index: int, chunk: ManifestBundle) -> None`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_audit_manifest.py`의 기존 픽스처 헬퍼(`_run()`, `_snapshot()`, `_finding(field_name)`)와 기존 청크 테스트의 번들 생성 방식을 그대로 재사용해 다음 4개 테스트를 추가한다. 번들 생성은 기존 테스트가 쓰는 `build_manifest(run, approved_findings, current_rows)` 호출 패턴을 복사한다(파일 상단 기존 테스트 참조).

```python
def test_chunk_split_preserves_entry_union() -> None:
    """3엔트리 chunk_size=2 분할 시 전체 엔트리 합집합이 보존된다."""
    bundle = _bundle_with_three_entries()  # 기존 픽스처 패턴으로 서로 다른 폰트 3건 생성
    chunks = split_manifest_into_chunks(bundle, chunk_size=2)
    assert len(chunks) == 2
    original = {str(e.source_key) for e in _entries_of(bundle)}
    merged = {str(e.source_key) for c in chunks for e in _entries_of(c)}
    assert merged == original


def test_chunk_evidence_matches_entry_references() -> None:
    """각 청크의 entries가 참조하는 evidence_ids가 그 청크의 evidence에 전부 포함된다."""
    bundle = _bundle_with_three_entries()
    for chunk in split_manifest_into_chunks(bundle, chunk_size=2):
        included = _evidence_ids_of(chunk)
        for entry in _entries_of(chunk):
            assert set(entry.evidence_ids) <= included
            assert set(entry.finding_ids) <= _finding_ids_of(chunk)


def test_chunk_reverse_swaps_before_after() -> None:
    """청크 분할 후에도 reverse 매니페스트의 before/after가 forward와 대칭이다."""
    bundle = _bundle_with_three_entries()
    for chunk in split_manifest_into_chunks(bundle, chunk_size=2):
        for fwd, rev in zip(_entries_of(chunk), _reverse_entries_of(chunk)):
            assert fwd.before == rev.after
            assert fwd.after == rev.before


def test_chunk_missing_evidence_raises_manifest_error() -> None:
    """엔트리가 참조하는 evidence가 청크 evidence 목록에서 빠지면 ManifestError."""
    bundle = _bundle_with_three_entries()
    _drop_one_referenced_evidence(bundle)  # 번들 evidence 목록에서 참조 1건 제거
    with pytest.raises(ManifestError):
        split_manifest_into_chunks(bundle, chunk_size=2)
```

실측 구조(적대적 리뷰 확인, audit_manifest.py:239,368-373): `ManifestBundle`은 `forward`/`reverse`(각 `FontAuditManifest`)와 `forward_sha256`/`reverse_sha256`을 가진다. `FontAuditManifest`는 `entries: list[ManifestEntry]`와 `evidence_bundle`(snapshots/findings — dict 행 목록)을 가진다. 테스트에서 헬퍼 자리에는 다음을 그대로 풀어쓴다: `_entries_of(c)` → `c.forward.entries`, `_reverse_entries_of(c)` → `c.reverse.entries`, `_evidence_ids_of(c)` → `{str(s["id"]) for s in c.forward.evidence_bundle.snapshots}`, `_finding_ids_of(c)` → `{str(f["id"]) for f in c.forward.evidence_bundle.findings}`.

- [ ] **Step 2: 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_manifest.py -q -k chunk`
Expected: 신규 4건 FAIL(참조 검증 미구현) 또는 ERROR(누락 evidence에도 예외 없음)

- [ ] **Step 3: 최소 구현**

`split_manifest_into_chunks` 내부에서 각 청크 생성 직후 호출하는 검증을 추가한다.

```python
def _validate_chunk_references(chunk_index: int, chunk: "ManifestBundle") -> None:
    """청크 entries가 참조하는 evidence/finding id가 청크에 실재하는지 단정한다.

    잔여 참조가 있으면 부분 적용 사고로 이어지므로 ManifestError로 차단한다.
    """
    included_evidence = {str(s["id"]) for s in chunk.forward.evidence_bundle.snapshots}
    included_findings = {str(f["id"]) for f in chunk.forward.evidence_bundle.findings}
    for entry in chunk.forward.entries:
        missing_ev = {str(i) for i in entry.evidence_ids} - included_evidence
        missing_fd = {str(i) for i in entry.finding_ids} - included_findings
        if missing_ev or missing_fd:
            raise ManifestError(
                f"청크 {chunk_index}: 참조 무결성 위반 evidence={sorted(map(str, missing_ev))} "
                f"finding={sorted(map(str, missing_fd))}"
            )
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_manifest.py -q`
Expected: 전체 PASS (기존 테스트 회귀 없음)

- [ ] **Step 5: audit-chain.sh 부분 적용 메시지**

청크 apply 루프(280행 부근)의 실패 분기에 다음 메시지를 추가한다.

```bash
echo "[audit-chain] 부분 적용 상태: 청크 ${idx}/${total} 실패. 이전 청크는 적용 유지됨." >&2
echo "[audit-chain] 원인 수정 후 동일 명령 재실행 시 이미 적용된 청크는 멱등 처리된다." >&2
```

- [ ] **Step 6: 문서 표현 정정**

Run: `grep -rn "무결성 검증 포함" docs/ scripts/`
검색된 문구를 "무결성 검증 포함(청크 참조 무결성은 build 시 단정, apply는 해시 검증)"으로 실제 구현 수준에 맞게 수정한다. 검색 결과 0건이면 이 스텝은 건너뛴다.

- [ ] **Step 7: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/audit_manifest.py apps/pipeline/tests/test_audit_manifest.py scripts/audit-chain.sh
git commit -m "feat: manifest 청크 참조 무결성 가드 + 부분 적용 메시지 (#114)"
```

---

### Task 2: archive 출처 등급 도입 (정책 + DB + 강등 차단)

**Files:**
- Create: `supabase/migrations/0021_download_source_kind_archive.sql`
- Modify: `apps/pipeline/src/fontagit_pipeline/audit_policy.py` (RegistryKind, classify, 신규 헬퍼)
- Modify: `apps/pipeline/src/fontagit_pipeline/data/source_registry.json` (archive 엔트리)
- Modify: `apps/pipeline/src/fontagit_pipeline/audit_manifest.py` (`_evidence_role_is_valid` download_* 허용 등급, build 시 강등 차단)
- Test: `apps/pipeline/tests/test_audit_policy.py`, `apps/pipeline/tests/test_audit_manifest.py`

**Interfaces:**
- Consumes: `SourceRegistry.classify(url) -> RegistryKind` (audit_policy.py:92), `RegistryEntry`(:20)
- Produces: `RegistryKind = Literal["official", "public", "archive", "discovery"]`, `may_update_source_kind(current: str | None, proposed: str | None) -> bool` (audit_policy.py 신규 — Task 3, 4가 사용)

- [ ] **Step 1: 마이그레이션 작성** (0017의 문법 스타일을 그대로 따른다)

```sql
-- 0021: download_source_kind에 'archive' 등급 추가 (아카이브 fallback 링크 구분)
alter table fontagit.fonts drop constraint fonts_download_source_kind_chk;
alter table fontagit.fonts add constraint fonts_download_source_kind_chk
  check (download_source_kind is null or download_source_kind in ('official', 'public', 'archive'));
```

주의: 0017 원문이 스키마 한정자 없이 `alter table fonts`를 쓰면 동일하게 맞춘다. dev 적용은 Task 7 실행 절차에서 수행.

- [ ] **Step 2: 실패하는 테스트 작성** (`tests/test_audit_policy.py`)

```python
def test_classify_archive_domain() -> None:
    """fonts.google.com은 archive 등급으로 분류된다."""
    registry = SourceRegistry.load_default()  # 기존 테스트의 로드 방식 재사용
    assert registry.classify("https://fonts.google.com/specimen/Nanum+Myeongjo") == "archive"


def test_may_update_source_kind_rank() -> None:
    """등급 우선순위: official > public > archive > null. 강등 불가."""
    assert may_update_source_kind(None, "archive") is True
    assert may_update_source_kind("archive", "official") is True
    assert may_update_source_kind("official", "archive") is False
    assert may_update_source_kind("public", "public") is True
```

- [ ] **Step 3: 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_policy.py -q`
Expected: FAIL (archive 미지원, may_update_source_kind 미정의)

- [ ] **Step 4: 구현**

audit_policy.py:

```python
RegistryKind = Literal["official", "public", "archive", "discovery"]

_SOURCE_KIND_RANK: dict[str | None, int] = {"official": 3, "public": 2, "archive": 1, None: 0}


def may_update_source_kind(current: str | None, proposed: str | None) -> bool:
    """출처 등급 강등을 차단한다. 같거나 높은 등급만 갱신을 허용한다."""
    return _SOURCE_KIND_RANK.get(proposed, 0) >= _SOURCE_KIND_RANK.get(current, 0)
```

`classify`(:92)의 반환 조건을 `in {"official", "public"}`에서 `in {"official", "public", "archive"}`로 확장. `require_approval_evidence` 검증자(:68-83)는 official/public에만 승인 필드를 요구하므로 archive는 조건에 추가하지 않는다(참고 등급이라 승인 증적 불요 — 단 official 오인 판정 금지 주석 명시).

source_registry.json에 엔트리 추가(기존 엔트리 스키마 준수):

```json
{ "maker": "Google Fonts (archive)", "domain": "fonts.google.com", "roles": ["download", "homepage"], "source_kind": "archive" },
{ "maker": "google/fonts GitHub (archive)", "domain": "raw.githubusercontent.com", "roles": ["license", "metadata"], "source_kind": "archive" },
{ "maker": "google/fonts GitHub (archive)", "domain": "github.com", "roles": ["download", "license"], "source_kind": "archive" }
```

audit_manifest.py `_evidence_role_is_valid`(:130-167): `download_*` 필드의 허용 source_kind 집합에 "archive"를 추가한다. `license_*` 필드 허용 집합은 변경하지 않는다(archive로 license 자동 승인 금지).

audit_manifest.py 값 검증자(:432-434, `_SOURCE_KIND_FIELDS` 분기)의 허용 집합도 `{"official", "public", "archive"}`로 확장한다 — 적대적 리뷰 실측: 이 지점을 빠뜨리면 archive 값이 전부 ManifestError로 차단된다.

build_manifest(:515) 엔트리 생성부: 필드가 `download_url`/`download_source_kind`일 때 `may_update_source_kind(current_row의 download_source_kind, 제안 kind)`가 False면 해당 엔트리를 제외하고 `rejected` 사유("등급 강등 차단")로 집계에 남긴다.

- [ ] **Step 5: 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_policy.py tests/test_audit_manifest.py -q`
Expected: 전체 PASS

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/0021_download_source_kind_archive.sql apps/pipeline/src/fontagit_pipeline/audit_policy.py apps/pipeline/src/fontagit_pipeline/data/source_registry.json apps/pipeline/src/fontagit_pipeline/audit_manifest.py apps/pipeline/tests/
git commit -m "feat: archive 출처 등급 + 강등 차단 규칙 도입"
```

---

### Task 3: Tier A 공식 수집기 (S1, #96 #120)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/tier_a_meta.py`
- Create: `apps/pipeline/src/fontagit_pipeline/data/brand_normalization.json`
- Modify: `apps/pipeline/src/fontagit_pipeline/__main__.py` (서브커맨드 `font-audit-tier-a-meta`)
- Test: `apps/pipeline/tests/test_tier_a_meta.py`

**Interfaces:**
- Consumes: `fetch_public_url(url, ...) -> FetchResult` (audit_http.py:322), `licenses._LICENSE_DIRS` (licenses.py:17), `may_update_source_kind` (Task 2), `FindingDraft` (audit_store — 필드 구성은 audit_metadata.py:302-368의 생성 패턴을 그대로 따른다)
- Produces: `parse_metadata_pb(text: str) -> TierAMeta`, `extract_rights_holder(copyright_text: str) -> str | None`, `resolve_foundry(noonnu_foundry: str | None, rights_holder: str | None, normalization: BrandNormalization) -> FoundryResolution`, `build_specimen_url(name_en: str) -> str`

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_tier_a_meta.py`)

```python
METADATA_FIXTURE = '''name: "Nanum Myeongjo"
designer: "Sandoll Communication"
license: "OFL"
category: "SERIF"
fonts {
  copyright: "Copyright © 2010 NHN Corporation."
}
'''


def test_parse_metadata_pb() -> None:
    meta = parse_metadata_pb(METADATA_FIXTURE)
    assert meta.designer == "Sandoll Communication"
    assert meta.copyright == "Copyright © 2010 NHN Corporation."


def test_extract_rights_holder() -> None:
    assert extract_rights_holder("Copyright © 2010 NHN Corporation.") == "NHN Corporation"
    assert extract_rights_holder("Copyright (c) 2015, Spoqa Inc.") == "Spoqa Inc"
    assert extract_rights_holder("") is None


def test_resolve_foundry_normalized_match() -> None:
    """눈누 표기와 정규화된 권리사가 일치(approved 항목)하면 auto, 아니면 needs_review."""
    norm = BrandNormalization(entries=[BrandEntry(
        source_name="NHN Corporation", display_name="네이버",
        evidence_url="https://hangeul.naver.com/fonts", status="approved")])
    ok = resolve_foundry("네이버", "NHN Corporation", norm)
    assert ok.value == "네이버" and ok.status == "auto"
    miss = resolve_foundry("어딘가", "NHN Corporation", norm)
    assert miss.status == "needs_review"
    pending = resolve_foundry("네이버", "NHN Corporation", BrandNormalization(entries=[BrandEntry(
        source_name="NHN Corporation", display_name="네이버",
        evidence_url="https://hangeul.naver.com/fonts", status="needs_review")]))
    assert pending.status == "needs_review"


def test_build_specimen_url() -> None:
    assert build_specimen_url("Nanum Myeongjo") == "https://fonts.google.com/specimen/Nanum+Myeongjo"
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_tier_a_meta.py -q`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현** (`tier_a_meta.py`)

```python
"""Tier A(google-fonts) 공식 메타데이터 수집기.

METADATA.pb(designer/copyright)를 근거 자료로 권리사(foundry)를 판정하고,
구글폰트 specimen 페이지를 archive 등급 download_url fallback으로 제안한다.
링크 등급과 근거 자료 축은 별개다(스펙 0장).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_METADATA_URL = "https://raw.githubusercontent.com/google/fonts/main/{license_dir}/{family_dir}/METADATA.pb"
_DESIGNER_RE = re.compile(r'^designer:\s*"(?P<v>[^"]+)"', re.MULTILINE)
_COPYRIGHT_RE = re.compile(r'copyright:\s*"(?P<v>[^"]+)"')
_RIGHTS_HOLDER_RE = re.compile(
    r"Copyright\s*(?:\(c\)|©)?\s*[\d,\-\s]*(?:by\s+)?(?P<holder>[^.,()\"]+)", re.IGNORECASE
)


class TierAMeta(BaseModel):
    designer: str | None = None
    copyright: str | None = None


class BrandEntry(BaseModel):
    source_name: str
    display_name: str
    evidence_url: str
    status: str  # "approved" | "needs_review"


class BrandNormalization(BaseModel):
    entries: list[BrandEntry] = []

    def resolve(self, raw_name: str) -> BrandEntry | None:
        needle = raw_name.strip().casefold()
        for entry in self.entries:
            if entry.source_name.casefold() == needle:
                return entry
        return None


class FoundryResolution(BaseModel):
    value: str | None
    status: str  # "auto" | "needs_review"
    reason: str


def parse_metadata_pb(text: str) -> TierAMeta:
    """METADATA.pb 텍스트에서 designer/copyright를 추출한다(프로토버프 의존 없이 라인 파싱)."""
    designer = _DESIGNER_RE.search(text)
    copyright_ = _COPYRIGHT_RE.search(text)
    return TierAMeta(
        designer=designer.group("v") if designer else None,
        copyright=copyright_.group("v") if copyright_ else None,
    )


def extract_rights_holder(copyright_text: str) -> str | None:
    """copyright 문자열에서 권리사 명칭을 추출한다. 실패 시 None(needs_review 경로)."""
    match = _RIGHTS_HOLDER_RE.search(copyright_text or "")
    if not match:
        return None
    holder = match.group("holder").strip().rstrip(".")
    return holder or None


def resolve_foundry(
    noonnu_foundry: str | None,
    rights_holder: str | None,
    normalization: BrandNormalization,
) -> FoundryResolution:
    """제작사 표기를 판정한다. 눈누 표기 == 정규화(approved)된 권리사일 때만 auto."""
    if not rights_holder:
        return FoundryResolution(value=noonnu_foundry, status="needs_review", reason="no_rights_holder")
    entry = normalization.resolve(rights_holder)
    display = entry.display_name if entry else rights_holder
    if entry and entry.status != "approved":
        return FoundryResolution(value=display, status="needs_review", reason="normalization_pending")
    if noonnu_foundry and noonnu_foundry.strip() == display:
        return FoundryResolution(value=display, status="auto", reason="matched")
    return FoundryResolution(value=display, status="needs_review", reason="mismatch_or_missing_noonnu")


def build_specimen_url(name_en: str) -> str:
    """구글폰트 specimen 페이지 URL(archive 등급 fallback)."""
    return f"https://fonts.google.com/specimen/{quote(name_en).replace('%20', '+')}"


def build_metadata_url(license_type: str, name_en: str) -> str:
    """license_type(OFL 등)과 영문명으로 google/fonts METADATA.pb URL을 만든다."""
    dirs = {label: d for d, label in _LICENSE_DIRS_ITEMS}  # licenses._LICENSE_DIRS 역매핑
    license_dir = dirs.get(license_type, "ofl")
    family_dir = name_en.replace(" ", "").lower()
    return _METADATA_URL.format(license_dir=license_dir, family_dir=family_dir)
```

`_LICENSE_DIRS_ITEMS`는 `from .licenses import _LICENSE_DIRS` 후 `.items()`를 상수로 감싼다. 수집 실행 함수 `collect_tier_a_meta(targets, store, registry, normalization, *, dry_run, fetcher=fetch_public_url)`는 대상별로 (1) METADATA.pb fetch-파싱 (2) resolve_foundry (3) FindingDraft 생성(field_name: `foundry`, `foundry_url`, `download_url`, `download_source_kind`, `license_source_url`) — FindingDraft 필드는 실측 기준(audit_store.py:39-49) `font_id`, `field_name`, `before_value`, `proposed_value`, `evidence_id`, `confidence`, `review_reason`, `auto_applicable`이며, 생성 패턴은 `audit_metadata.py:302-368`을 따른다. fetch 실패-파싱 실패는 해당 폰트 skip + logging.warning + 리포트 집계(절대 허용 승격 없음).

`brand_normalization.json` 초기 내용:

```json
{
  "entries": [
    {
      "source_name": "NHN Corporation",
      "display_name": "네이버",
      "evidence_url": "https://hangeul.naver.com/fonts",
      "status": "needs_review"
    }
  ]
}
```

(신규 항목 기본 needs_review — 사용자가 근거 확인 후 approved로 변경하는 것이 승인 행위)

- [ ] **Step 4: 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_tier_a_meta.py -q`
Expected: PASS

- [ ] **Step 5: CLI 서브커맨드 등록**

`__main__.py`의 기존 `font-audit-run`(1297행) 등록 패턴을 복사해 `font-audit-tier-a-meta` 추가: 인자 `--limit`(int), `--dry-run`(flag), `--out`(Path, 리포트 JSON). 실행부는 dev에서 Tier A(published, source_tier='A' 또는 official_url이 구글폰트) 대상 조회 후 `collect_tier_a_meta` 호출.

Run: `cd apps/pipeline && uv run python -m fontagit_pipeline font-audit-tier-a-meta --limit 3 --dry-run --out /tmp/tier-a-meta-dry.json`
Expected: exit 0, 리포트에 3건 preview(적용 없음)

- [ ] **Step 6: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/tier_a_meta.py apps/pipeline/src/fontagit_pipeline/data/brand_normalization.json apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/tests/test_tier_a_meta.py
git commit -m "feat: Tier A 공식 메타 수집기(권리사 판정+specimen fallback) (#96 #120)"
```

---

### Task 4: 눈누 스냅샷 foundry/download 승격 (S2, #120)

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/audit_metadata.py` (`compare_metadata`, 274행 부근)
- Test: `apps/pipeline/tests/test_audit_runner.py` (또는 기존 metadata 비교 테스트 파일)

**Interfaces:**
- Consumes: `NoonnuFontSnapshot.foundry/download_candidates/download_status` (audit_noonnu.py:21-53), `SourceRegistry.classify`, `may_update_source_kind` (Task 2)
- Produces: `compare_metadata`가 기존 6필드에 더해 `foundry`, `download_url`, `download_source_kind` FindingDraft를 생성

- [ ] **Step 1: 실패하는 테스트 작성**

기존 metadata 비교 테스트의 스냅샷 픽스처에 `foundry="네이버"`, `download_candidates=["https://hangeul.naver.com/fonts/search?f=nanum"]`를 넣고:

```python
def test_compare_metadata_emits_foundry_and_download() -> None:
    """스냅샷의 제작사-다운로드 후보가 FindingDraft로 승격된다."""
    drafts = compare_metadata(...)  # 기존 테스트 호출 패턴 재사용
    fields = {d.field_name for d in drafts}
    assert "foundry" in fields
    assert "download_url" in fields
    assert "download_source_kind" in fields


def test_download_official_domain_is_auto() -> None:
    """registry가 official로 분류한 다운로드 URL은 auto, 아니면 needs_review."""
    # hangeul.naver.com이 registry에 official로 있으면 auto 확인
    # 미등록 도메인 예: https://example.com/dl → needs_review 확인
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_runner.py -q -k foundry`
Expected: FAIL

- [ ] **Step 3: 구현**

`compare_metadata`(:274)의 필드 비교 루프에 추가:

- `foundry`: 스냅샷 값 존재 + 현재값과 다름 → FindingDraft. Tier B는 공식 대조 소스가 없으므로 confidence는 "reference"(자동 게이트 미통과 → needs_review 풀. 스펙 5장). Tier A 대상은 Task 3 수집기가 담당하므로 여기서는 눈누 단독 근거로만 생성.
- `download_url`: 후보 중 **파일 직링크는 제외**(경로가 `.ttf/.otf/.woff/.woff2/.zip`로 끝나면 스킵 — 스펙 "download_url = 페이지 URL" 규칙, 파일 후보는 `font_file_candidates` 소관). 남은 첫 후보에 대해 `registry.classify(url)` 결과가 "official"/"public"이면 그 kind로 auto 후보, "archive"/"discovery"면 needs_review. `may_update_source_kind(current_kind, proposed_kind)` False면 draft 생성 생략(강등 금지).
- 추가 실측 항목: `font-audit-review auto-approve`가 승인 필드를 화이트리스트로 제한하는지 `__main__.py`-`audit_store.py`에서 grep으로 확인하고, 제한이 있으면 `foundry`/`download_url`/`download_source_kind`를 비legal 자동 승인 목록에 추가한다(legal 필드 추가 금지).
- `download_source_kind`: download_url draft와 반드시 쌍으로 생성(동일 evidence 참조).

- [ ] **Step 4: 통과 확인 + 전체 회귀**

Run: `cd apps/pipeline && uv run pytest -q`
Expected: 전체 PASS

- [ ] **Step 5: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/audit_metadata.py apps/pipeline/tests/
git commit -m "feat: 눈누 스냅샷 제작사-다운로드 findings 승격 (#120)"
```

---

### Task 5: 크롤 오류 22종 재현 확인-재크롤 (S2, #90) — 실행 절차(runbook)

**Files:**
- Create: `apps/pipeline/data/recrawl_allowlist_20260727.json` (실행 중 생성)

**Interfaces:**
- Consumes: 기존 CLI `font-audit-run --stage metadata --require-slug <slug> --dry-run`, dev REST(`Accept-Profile: fontagit`)

- [ ] **Step 1: 오류 22종 목록 추출**

dev REST OpenAPI로 오류 기록 위치를 먼저 실측한다(테이블-컬럼명 추측 금지):

```bash
curl -s "$SUPABASE_DEV_URL/rest/v1/" -H "apikey: $SUPABASE_DEV_SERVICE_KEY" -H "Accept-Profile: fontagit" | head -50
```

license_proposals(또는 감사 스냅샷 테이블)의 오류 상태 값을 확인한 뒤 해당 조건으로 22건을 조회해 `recrawl_allowlist_20260727.json`에 `[{"slug": ..., "source_url": ..., "error_kind": ...}]` 형태로 저장. 22건이 아니면 실제 건수를 보고하고 진행.

- [ ] **Step 2: 사용자 승인 게이트 (눈누 크롤)**

허용 목록 건수-대상을 보고하고 크롤 실행 승인을 받는다. 승인 전 어떤 외부 요청도 금지.

- [ ] **Step 3: 재현 확인 실행 (allowlist 한정)**

```bash
cd apps/pipeline
while read -r slug; do
  uv run python -m fontagit_pipeline font-audit-run --stage metadata --require-slug "$slug" --limit 1 --out "/tmp/recrawl-$slug.json"
done < <(jq -r '.[].slug' data/recrawl_allowlist_20260727.json)
```

- [ ] **Step 4: 실패 분류 리포트**

결과를 HTTP 오류/파싱 실패/차단 응답/데이터 누락 4분류로 집계해 보고. 해소된 건은 정상 findings 경로로, 지속 실패 건은 needs_review 유지(허용 승격 금지). 분류별 후속(파서 수정/보류)을 사용자에게 제안.

- [ ] **Step 5: Commit** (allowlist + 리포트 문서)

```bash
git add apps/pipeline/data/recrawl_allowlist_20260727.json
git commit -m "chore: 크롤 오류 재현 확인 allowlist-결과 기록 (#90)"
```

---

### Task 6: KOGL 유형 파서 + preview (S3, #90)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/audit_kogl.py`
- Modify: `apps/pipeline/src/fontagit_pipeline/__main__.py` (서브커맨드 `font-audit-kogl-preview`)
- Test: `apps/pipeline/tests/test_audit_kogl.py`

**Interfaces:**
- Produces: `detect_kogl_type(license_text: str) -> KoglDetection` (`kogl_type: int | None`, `reason: str`), `KOGL_PERMISSIONS: dict[int, dict[str, bool | None]]`
- 주의: 이 Task는 **preview 산출까지만**. 권한 findings 생성-적용은 사용자 그룹 승인 후 별도 실행(스펙 S3 선행 체크포인트).

- [ ] **Step 1: 실패하는 테스트 작성** (`tests/test_audit_kogl.py`)

```python
import pytest

from fontagit_pipeline.audit_kogl import KOGL_PERMISSIONS, detect_kogl_type


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("본 저작물은 공공누리 제1유형에 따라 이용할 수 있습니다.", 1),
        ("공공누리 제 4 유형(출처표시+상업적 이용금지+변경금지)", 4),
    ],
)
def test_detect_kogl_type_ok(text: str, expected: int) -> None:
    result = detect_kogl_type(text)
    assert result.kogl_type == expected and result.reason == "ok"


def test_detect_kogl_type_edge_cases() -> None:
    assert detect_kogl_type("자유 라이선스입니다").reason == "no_match"
    assert detect_kogl_type("공공누리 제1유형과 제3유형이 병기").reason == "multiple"
    assert detect_kogl_type("이 폰트는 공공누리 제1유형이 아닙니다").reason == "negation"
    assert detect_kogl_type("").reason == "no_match"


def test_kogl_permissions_table_complete() -> None:
    """4개 유형 전부, DB 권한 필드 5종 + attribution을 커버한다(스펙 S3 표)."""
    keys = {"allow_commercial", "allow_modify", "allow_redistribute", "allow_font_sale", "allow_embedding", "attribution_requirement"}
    for kogl_type in (1, 2, 3, 4):
        assert set(KOGL_PERMISSIONS[kogl_type]) == keys
    assert KOGL_PERMISSIONS[1]["allow_commercial"] is True
    assert KOGL_PERMISSIONS[2]["allow_commercial"] is False
    assert KOGL_PERMISSIONS[3]["allow_modify"] is False
    assert KOGL_PERMISSIONS[4]["allow_commercial"] is False and KOGL_PERMISSIONS[4]["allow_modify"] is False
    assert all(KOGL_PERMISSIONS[t]["allow_embedding"] is None for t in (1, 2, 3, 4))
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_kogl.py -q`
Expected: FAIL (모듈 없음)

- [ ] **Step 3: 구현** (`audit_kogl.py`)

```python
"""공공누리(KOGL) 유형 판별기. 유형 미검출-복수-부정문은 전부 needs_review 경로."""
from __future__ import annotations

import re

from pydantic import BaseModel

_KOGL_TYPE_RE = re.compile(r"공공누리[^0-9제]{0,20}제\s*(?P<n>[1-4])\s*유형")
_NEGATION_MARKERS = ("아님", "아닙니다", "해당하지 않", "적용되지 않", "제외")
_NEGATION_WINDOW = 30

# 값 None = 그룹 승인 시 공식 기준(kogl.or.kr) 대조로 확정(스펙 S3 — 임베딩은 초안값 없음)
KOGL_PERMISSIONS: dict[int, dict[str, bool | str | None]] = {
    1: {"allow_commercial": True, "allow_modify": True, "allow_redistribute": True,
        "allow_font_sale": False, "allow_embedding": None, "attribution_requirement": "required"},
    2: {"allow_commercial": False, "allow_modify": True, "allow_redistribute": True,
        "allow_font_sale": False, "allow_embedding": None, "attribution_requirement": "required"},
    3: {"allow_commercial": True, "allow_modify": False, "allow_redistribute": True,
        "allow_font_sale": False, "allow_embedding": None, "attribution_requirement": "required"},
    4: {"allow_commercial": False, "allow_modify": False, "allow_redistribute": True,
        "allow_font_sale": False, "allow_embedding": None, "attribution_requirement": "required"},
}


class KoglDetection(BaseModel):
    kogl_type: int | None
    reason: str  # "ok" | "no_match" | "multiple" | "negation"


def detect_kogl_type(license_text: str) -> KoglDetection:
    """라이선스 본문에서 공공누리 유형을 판별한다. 애매하면 전부 미검출 처리."""
    matches = list(_KOGL_TYPE_RE.finditer(license_text or ""))
    if not matches:
        return KoglDetection(kogl_type=None, reason="no_match")
    types = {int(m.group("n")) for m in matches}
    if len(types) > 1:
        return KoglDetection(kogl_type=None, reason="multiple")
    for m in matches:
        tail = license_text[m.end(): m.end() + _NEGATION_WINDOW]
        if any(marker in tail for marker in _NEGATION_MARKERS):
            return KoglDetection(kogl_type=None, reason="negation")
    return KoglDetection(kogl_type=types.pop(), reason="ok")
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_kogl.py -q`
Expected: PASS

- [ ] **Step 5: preview CLI**

`font-audit-kogl-preview --out <json>`: dev에서 KOGL 후보 271종(license_type/license_text에 '공공누리' 또는 'KOGL' 포함 — 실제 컬럼은 Task 5 Step 1에서 확인한 스키마 재사용)을 조회해 `detect_kogl_type` 실행, 유형별-미검출별 집계와 폰트 목록을 JSON으로 산출. **DB 쓰기 없음.**

Run: `cd apps/pipeline && uv run python -m fontagit_pipeline font-audit-kogl-preview --out /tmp/kogl-preview.json`
Expected: exit 0, 집계 리포트(제1~4유형 각 N건, 미검출 M건)

- [ ] **Step 6: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/audit_kogl.py apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/tests/test_audit_kogl.py
git commit -m "feat: KOGL 유형 판별기 + preview CLI (#90)"
```

---

### Task 7: dev 적용-검증-prod 게이트 (실행 절차 runbook)

**Files:** 없음(실행 절차). 산출물: manifest 디렉터리(forward/reverse), 적용 리포트

**Interfaces:**
- Consumes: `scripts/audit-chain.sh` 흐름, `font-audit-manifest build --run-id <id> --target dev --out <dir> --chunk-size 100`, `font-audit-manifest apply`

- [ ] **Step 1: 0021 마이그레이션 dev 적용** (사용자에게 dev DDL 실행 보고 후 진행)
- [ ] **Step 2: 비legal 스코프 실행**: Task 3 수집기 + Task 4 승격 run 실행(dry-run 리포트 먼저 보고) → `font-audit-review auto-approve --run-id <id>`(자동 게이트: registry classify + may_update_source_kind)
- [ ] **Step 3: manifest build**: `--chunk-size 100`. forward와 **reverse manifest를 함께 보관**(디렉터리째 아카이브 — 스펙 rollback 요건)
- [ ] **Step 4: dev apply + 검증**: 청크 순차 적용 후 집계 검증 — planned/changed/unchanged/rejected/failed 구분, **기대 변경 수 = 실제 변경 수** 확인 쿼리(REST로 foundry/download_url not null 건수 비교) + 무작위 샘플 5건 육안 대조(나눔명조 포함)
- [ ] **Step 5: KOGL 그룹 승인 게이트**: kogl-preview 리포트를 유형 그룹별로 사용자에게 제시 → 공식 기준(kogl.or.kr) 대조 확인 → 승인된 그룹만 legal findings 생성-적용(미검출 그룹은 승인 대상 아님). 승인 기록: reviewed_by/reviewed_at + 근거 링크를 리포트 문서로 커밋
- [ ] **Step 6: prod 적용**: 사용자 확인(`FONTAGIT_PROD_MANIFEST_ENABLED=true`) 후 0021 DDL → manifest apply(청크 100, in-list 40). reverse manifest 보관 경로 보고
- [ ] **Step 7: 기록**: 적용 결과-리포트를 docs/progress에 반영하고 커밋

---

## Self-Review 결과

- 스펙 커버리지: S0→Task1, 등급-게이트(스펙 S1 등급 규칙)→Task2, S1→Task3, S2→Task4-5, S3→Task6, 적용 절차→Task7. 웹 S4는 별도 계획(`2026-07-27-web-attribution-specimen.md`)
- 미확정 지점 명시: ManifestBundle 내부 필드명(Task1 Step3), FindingDraft 생성 인자(Task3 Step3), 오류 22종 테이블 스키마(Task5 Step1)는 구현 시 해당 파일-OpenAPI를 열어 확인하도록 지시함(추측 코드 금지)
- 타입 일관성: may_update_source_kind(Task2 정의)를 Task3-4가 소비, KOGL_PERMISSIONS 키는 DB allow_* 필드명과 1:1
