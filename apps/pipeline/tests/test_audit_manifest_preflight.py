"""apply 전 manifest-DB 필드 대조(preflight)의 핵심 회귀 테스트."""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import UUID

import httpx

from fontagit_pipeline.__main__ import main_audit_manifest_apply, main_audit_manifest_preflight
from fontagit_pipeline.audit_manifest import FontAuditManifest, build_manifest
from fontagit_pipeline.audit_manifest_preflight import FieldMismatch, PreflightReport, run_preflight

RUN_ID = UUID("00000000-0000-0000-0000-000000000801")
FONT_ID = UUID("00000000-0000-0000-0000-000000000802")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000803")
LICENSE_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000806")
FINDING_DOWNLOAD_ID = UUID("00000000-0000-0000-0000-000000000804")
FINDING_LICENSE_ID = UUID("00000000-0000-0000-0000-000000000805")
NOW = datetime(2026, 7, 18, 1, 2, 3, tzinfo=UTC)
PROVIDER = "noonnu"
PROVIDER_RECORD_ID = "613"
FONT_SOURCES = [{"font_id": str(FONT_ID), "provider": PROVIDER, "provider_record_id": PROVIDER_RECORD_ID}]


def _run() -> dict[str, object]:
    return {
        "id": str(RUN_ID),
        "stage": "legal",
        "target_environment": "dev",
        "target_count": 1,
        "success_count": 1,
        "verified_count": 0,
        "review_count": 1,
        "broken_count": 0,
        "parser_version": "audit-v1",
        "baseline_sha256": "a" * 64,
        "manifest_sha256": None,
        "dry_run": False,
        "status": "completed",
        "started_at": NOW.isoformat(),
        "finished_at": NOW.isoformat(),
    }


def _snapshot(snapshot_id: UUID, document_kind: str, raw_sha256: str, normalized_sha256: str) -> dict[str, object]:
    return {
        "id": str(snapshot_id),
        "run_id": str(RUN_ID),
        "font_id": str(FONT_ID),
        "provider": PROVIDER,
        "provider_record_id": PROVIDER_RECORD_ID,
        "source_kind": "official",
        "document_kind": document_kind,
        "request_url": "https://clova.ai/handwriting/list.html",
        "final_url": "https://clova.ai/handwriting/list.html",
        "http_status": 200,
        "raw_text": None,
        "raw_retention_allowed": False,
        "raw_sha256": raw_sha256,
        "normalized_sha256": normalized_sha256,
        "extracted": {"download_url": "https://clova.ai/font.zip"},
        "evidence_locations": {"download_url": "a.download"},
        "extraction_rule_id": "official-download-v1",
        "parser_version": "audit-v1",
        "collected_at": NOW.isoformat(),
    }


def _row() -> dict[str, object]:
    return {
        "id": str(FONT_ID),
        "source_key": {"provider": PROVIDER, "provider_record_id": PROVIDER_RECORD_ID},
        "slug": "test-font",
        "name_ko": "테스트폰트",
        "name_en": None,
        "foundry": None,
        "official_url": "https://instagram.com/wrong-old-link",
        "status": "published",
        "updated_at": NOW.isoformat(),
        "download_url": None,
        "download_status": "pending",
        "download_evidence_id": None,
        "license_status": "pending",
        "license_verified": True,
        "evidence_snapshots": [
            _snapshot(SNAPSHOT_ID, "download", "b" * 64, "c" * 64),
            _snapshot(LICENSE_SNAPSHOT_ID, "license", "d" * 64, "e" * 64),
        ],
    }


def _finding(
    finding_id: UUID, field_name: str, before: object, proposed: object, evidence_id: UUID
) -> dict[str, object]:
    return {
        "id": str(finding_id),
        "run_id": str(RUN_ID),
        "font_id": str(FONT_ID),
        "field_name": field_name,
        "before_value": before,
        "proposed_value": proposed,
        "evidence_id": str(evidence_id),
        "confidence": "official",
        "auto_applicable": False,
        "review_reason": "사람 검수 완료",
        "status": "approved",
        "reviewed_by": "reviewer",
        "reviewed_at": NOW.isoformat(),
    }


def _build_manifest() -> FontAuditManifest:
    findings = [
        _finding(FINDING_DOWNLOAD_ID, "download_url", None, "https://clova.ai/font.zip", SNAPSHOT_ID),
        _finding(FINDING_LICENSE_ID, "license_status", "pending", "needs_review", LICENSE_SNAPSHOT_ID),
    ]
    return build_manifest(_run(), findings, [_row()]).forward


def _db_row(entity: dict[str, object]) -> dict[str, object]:
    """manifest에 실린 finding/snapshot dict로부터 DB 행(SELECT 응답)을 만든다."""
    row = {key: value for key, value in entity.items() if key != "source_key"}
    row["font_id"] = str(FONT_ID)
    return row


def _in_list(params: httpx.QueryParams, key: str) -> list[str]:
    raw = params.get(key, "")
    inner = raw.removeprefix("in.(").removesuffix(")")
    return [item for item in inner.split(",") if item]


def _table_response(
    params: httpx.QueryParams,
    rows_by_id: dict[str, dict[str, object]],
    null_ids: dict[str, set[str]],
) -> httpx.Response:
    ids = _in_list(params, "id")
    for field_name in ("before_value", "proposed_value", "extracted", "evidence_locations"):
        if params.get(field_name) == "is.null":
            matched = [{"id": item} for item in ids if item in null_ids.get(field_name, set())]
            return httpx.Response(200, json=matched)
    rows = [rows_by_id[item] for item in ids if item in rows_by_id]
    return httpx.Response(200, json=rows)


def _make_client(
    *,
    font_sources: list[dict[str, object]],
    findings_by_id: dict[str, dict[str, object]],
    snapshots_by_id: dict[str, dict[str, object]],
    finding_null_ids: dict[str, set[str]] | None = None,
    snapshot_null_ids: dict[str, set[str]] | None = None,
) -> httpx.Client:
    finding_null_ids = finding_null_ids or {}
    snapshot_null_ids = snapshot_null_ids or {}

    def handler(request: httpx.Request) -> httpx.Response:
        params = request.url.params
        path = request.url.path
        if path == "/rest/v1/font_sources":
            return httpx.Response(200, json=font_sources)
        if path == "/rest/v1/font_audit_findings":
            return _table_response(params, findings_by_id, finding_null_ids)
        if path == "/rest/v1/font_source_snapshots":
            return _table_response(params, snapshots_by_id, snapshot_null_ids)
        raise AssertionError(f"unexpected path: {path}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_preflight_reports_clean_when_manifest_matches_db() -> None:
    """DB가 manifest와 필드까지 완전히 일치하면 어긋남이 없다."""
    manifest = _build_manifest()
    findings_by_id = {f["id"]: _db_row(f) for f in manifest.evidence_bundle.findings}
    snapshots_by_id = {s["id"]: _db_row(s) for s in manifest.evidence_bundle.snapshots}
    client = _make_client(font_sources=FONT_SOURCES, findings_by_id=findings_by_id, snapshots_by_id=snapshots_by_id)

    report = run_preflight(manifest, url="https://dev.example.supabase.co", secret_key="secret", client=client)

    assert report.is_clean
    assert not report.new_finding_ids
    assert not report.new_snapshot_ids


def test_preflight_treats_sql_null_and_jsonb_null_as_equal() -> None:
    """SQL NULL로 저장되든 jsonb 'null' 리터럴로 저장되든 manifest의 None과 동일하게 본다."""
    manifest = _build_manifest()
    findings_by_id = {f["id"]: _db_row(f) for f in manifest.evidence_bundle.findings}
    snapshots_by_id = {s["id"]: _db_row(s) for s in manifest.evidence_bundle.snapshots}
    download_finding_id = str(FINDING_DOWNLOAD_ID)
    assert findings_by_id[download_finding_id]["before_value"] is None

    client_sql_null = _make_client(
        font_sources=FONT_SOURCES,
        findings_by_id=findings_by_id,
        snapshots_by_id=snapshots_by_id,
        finding_null_ids={"before_value": {download_finding_id}},
    )
    assert run_preflight(manifest, url="https://x", secret_key="k", client=client_sql_null).is_clean

    client_jsonb_null = _make_client(
        font_sources=FONT_SOURCES, findings_by_id=findings_by_id, snapshots_by_id=snapshots_by_id
    )
    assert run_preflight(manifest, url="https://x", secret_key="k", client=client_jsonb_null).is_clean


def test_preflight_detects_value_mismatch() -> None:
    """DB의 proposed_value가 manifest와 다르면 (id, 필드, manifest값, DB값)으로 보고한다."""
    manifest = _build_manifest()
    findings_by_id = {f["id"]: _db_row(f) for f in manifest.evidence_bundle.findings}
    snapshots_by_id = {s["id"]: _db_row(s) for s in manifest.evidence_bundle.snapshots}
    license_finding_id = str(FINDING_LICENSE_ID)
    findings_by_id[license_finding_id] = {**findings_by_id[license_finding_id], "proposed_value": "different-value"}
    client = _make_client(font_sources=FONT_SOURCES, findings_by_id=findings_by_id, snapshots_by_id=snapshots_by_id)

    report = run_preflight(manifest, url="https://x", secret_key="k", client=client)

    assert not report.is_clean
    mismatch = next(m for m in report.mismatches if m.field_name == "proposed_value")
    assert mismatch.entity_id == FINDING_LICENSE_ID
    assert mismatch.manifest_value == "needs_review"
    assert mismatch.db_value == "different-value"
    assert report.field_summary() == {"proposed_value": 1}


def test_preflight_classifies_missing_db_rows_as_new_insert() -> None:
    """DB에 없는 id는 오류가 아니라 신규 insert 예정으로 분류한다."""
    manifest = _build_manifest()
    client = _make_client(font_sources=FONT_SOURCES, findings_by_id={}, snapshots_by_id={})

    report = run_preflight(manifest, url="https://x", secret_key="k", client=client)

    assert report.is_clean
    assert report.new_finding_ids == frozenset({FINDING_DOWNLOAD_ID, FINDING_LICENSE_ID})
    assert report.new_snapshot_ids == frozenset({SNAPSHOT_ID, LICENSE_SNAPSHOT_ID})


def test_preflight_reports_font_sources_row_count_errors() -> None:
    """font_sources 매칭이 0행이거나 2행 이상이면 font_id 오류로 보고한다."""
    manifest = _build_manifest()
    findings_by_id = {f["id"]: _db_row(f) for f in manifest.evidence_bundle.findings}
    snapshots_by_id = {s["id"]: _db_row(s) for s in manifest.evidence_bundle.snapshots}

    client_zero = _make_client(font_sources=[], findings_by_id=findings_by_id, snapshots_by_id=snapshots_by_id)
    report_zero = run_preflight(manifest, url="https://x", secret_key="k", client=client_zero)
    zero_row_mismatches = [m for m in report_zero.mismatches if m.field_name == "font_id"]
    assert len(zero_row_mismatches) == 4  # finding 2건 + snapshot 2건, 모두 같은 source_key
    assert "0행" in str(zero_row_mismatches[0].db_value)

    duplicated_sources = [
        *FONT_SOURCES,
        {"font_id": str(UUID(int=FONT_ID.int + 1)), "provider": PROVIDER, "provider_record_id": PROVIDER_RECORD_ID},
    ]
    client_multi = _make_client(
        font_sources=duplicated_sources, findings_by_id=findings_by_id, snapshots_by_id=snapshots_by_id
    )
    report_multi = run_preflight(manifest, url="https://x", secret_key="k", client=client_multi)
    multi_row_mismatches = [m for m in report_multi.mismatches if m.field_name == "font_id"]
    assert len(multi_row_mismatches) == 4
    assert "2행" in str(multi_row_mismatches[0].db_value)


def test_preflight_timestamptz_representation_differences_are_equal() -> None:
    """Z/+00:00 표기, 마이크로초 자릿수 차이는 같은 시각이면 동일하게 본다."""
    manifest = _build_manifest()
    findings_by_id = {f["id"]: _db_row(f) for f in manifest.evidence_bundle.findings}
    snapshots_by_id = {s["id"]: _db_row(s) for s in manifest.evidence_bundle.snapshots}
    download_finding_id = str(FINDING_DOWNLOAD_ID)
    assert findings_by_id[download_finding_id]["reviewed_at"] == NOW.isoformat()
    findings_by_id[download_finding_id]["reviewed_at"] = "2026-07-18T01:02:03.000000Z"
    snapshots_by_id[str(SNAPSHOT_ID)]["collected_at"] = "2026-07-18T01:02:03.000000Z"
    client = _make_client(font_sources=FONT_SOURCES, findings_by_id=findings_by_id, snapshots_by_id=snapshots_by_id)

    report = run_preflight(manifest, url="https://x", secret_key="k", client=client)

    assert report.is_clean


def test_main_audit_manifest_preflight_exit_code_reflects_report() -> None:
    """CLI preflight 명령은 report.is_clean에 따라 exit code 0/1을 반환한다."""
    manifest = _build_manifest()
    args = argparse.Namespace(manifest=MagicMock(), sha256=MagicMock(), target="dev")
    clean_report = PreflightReport(mismatches=(), new_finding_ids=frozenset(), new_snapshot_ids=frozenset())
    dirty_report = PreflightReport(
        mismatches=(
            FieldMismatch(
                entity="finding", entity_id=FINDING_DOWNLOAD_ID, field_name="status",
                manifest_value="approved 또는 applied", db_value="pending",
            ),
        ),
        new_finding_ids=frozenset(),
        new_snapshot_ids=frozenset(),
    )

    with patch("fontagit_pipeline.audit_manifest.verify_manifest_file", return_value=manifest), patch(
        "fontagit_pipeline.config.load_audit_settings"
    ) as mock_settings, patch("fontagit_pipeline.audit_manifest_preflight.run_preflight", return_value=clean_report):
        mock_settings.return_value.dev_write_credentials.return_value = ("https://dev.example", "secret")
        assert main_audit_manifest_preflight(args) == 0

    with patch("fontagit_pipeline.audit_manifest.verify_manifest_file", return_value=manifest), patch(
        "fontagit_pipeline.config.load_audit_settings"
    ) as mock_settings, patch("fontagit_pipeline.audit_manifest_preflight.run_preflight", return_value=dirty_report):
        mock_settings.return_value.dev_write_credentials.return_value = ("https://dev.example", "secret")
        assert main_audit_manifest_preflight(args) == 1


def test_main_audit_manifest_apply_blocks_on_dirty_preflight_and_skip_flag_bypasses() -> None:
    """apply는 기본적으로 preflight 어긋남이 있으면 RPC 전에 멈추고, --skip-preflight면 건너뛴다."""
    manifest_bytes = b"{}"
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    manifest_path = MagicMock(read_bytes=MagicMock(return_value=manifest_bytes))
    sha_path = MagicMock(read_text=MagicMock(return_value=digest))
    args = argparse.Namespace(
        manifest=manifest_path,
        sha256=sha_path,
        target="dev",
        confirm_hash=digest,
        approved_hash=None,
        approval_id=None,
        skip_preflight=False,
    )
    fake_manifest = MagicMock(schema_version=1)
    dirty_report = PreflightReport(
        mismatches=(
            FieldMismatch(
                entity="finding", entity_id=FINDING_DOWNLOAD_ID, field_name="status",
                manifest_value="approved 또는 applied", db_value="pending",
            ),
        ),
        new_finding_ids=frozenset(),
        new_snapshot_ids=frozenset(),
    )

    with patch("fontagit_pipeline.audit_manifest.verify_manifest_bytes", return_value=fake_manifest), patch(
        "fontagit_pipeline.config.load_audit_settings"
    ) as mock_settings, patch(
        "fontagit_pipeline.audit_manifest_preflight.run_preflight", return_value=dirty_report
    ) as mock_preflight, patch("supabase.create_client") as mock_create_client:
        mock_settings.return_value.dev_write_credentials.return_value = ("https://dev.example", "secret")
        assert main_audit_manifest_apply(args) == 2
        mock_preflight.assert_called_once()
        mock_create_client.assert_not_called()

    args.skip_preflight = True
    with patch("fontagit_pipeline.audit_manifest.verify_manifest_bytes", return_value=fake_manifest), patch(
        "fontagit_pipeline.config.load_audit_settings"
    ) as mock_settings, patch(
        "fontagit_pipeline.audit_manifest_preflight.run_preflight"
    ) as mock_preflight, patch("supabase.create_client") as mock_create_client:
        mock_settings.return_value.dev_write_credentials.return_value = ("https://dev.example", "secret")
        mock_create_client.return_value.schema.return_value.rpc.return_value.execute.return_value = MagicMock(data=1)
        assert main_audit_manifest_apply(args) == 0
        mock_preflight.assert_not_called()
