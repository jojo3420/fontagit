"""승인된 폰트 감사 manifest의 핵심 안전 계약."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from fontagit_pipeline.audit_manifest import (
    ManifestError,
    build_manifest,
    verify_manifest_bytes,
    verify_manifest_file,
    write_manifest_bundle,
)


RUN_ID = UUID("00000000-0000-0000-0000-000000000701")
FONT_ID = UUID("00000000-0000-0000-0000-000000000702")
SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000703")
LICENSE_SNAPSHOT_ID = UUID("00000000-0000-0000-0000-000000000706")
FINDING_ID = UUID("00000000-0000-0000-0000-000000000704")
NOW = datetime(2026, 7, 18, 1, 2, 3, tzinfo=UTC)


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


def _snapshot() -> dict[str, object]:
    return {
        "id": str(SNAPSHOT_ID),
        "run_id": str(RUN_ID),
        "font_id": str(FONT_ID),
        "provider": "noonnu",
        "provider_record_id": "613",
        "source_kind": "official",
        "document_kind": "download",
        "request_url": "https://clova.ai/handwriting/list.html",
        "final_url": "https://clova.ai/handwriting/list.html",
        "http_status": 200,
        "raw_text": "내부 원문은 정책 승인 전 내보내지 않는다.",
        "raw_retention_allowed": False,
        "raw_sha256": "b" * 64,
        "normalized_sha256": "c" * 64,
        "extracted": {"download_url": "https://clova.ai/font.zip"},
        "evidence_locations": {"download_url": "a.download"},
        "extraction_rule_id": "official-download-v1",
        "parser_version": "audit-v1",
        "collected_at": NOW.isoformat(),
    }


def _license_snapshot() -> dict[str, object]:
    snapshot = _snapshot()
    snapshot.update(
        {
            "id": str(LICENSE_SNAPSHOT_ID),
            "document_kind": "license",
            "raw_sha256": "d" * 64,
            "normalized_sha256": "e" * 64,
        }
    )
    return snapshot


def _row() -> dict[str, object]:
    return {
        "id": str(FONT_ID),
        "source_key": {"provider": "noonnu", "provider_record_id": "613"},
        "slug": "흰꼬리수리",
        "name_ko": "흰꼬리수리",
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
        "evidence_snapshots": [_snapshot(), _license_snapshot()],
    }


def _finding(field_name: str, before: object, proposed: object) -> dict[str, object]:
    evidence_id = (
        LICENSE_SNAPSHOT_ID
        if field_name.startswith("license_") or field_name == "license_verified"
        else SNAPSHOT_ID
    )
    return {
        "id": str(FINDING_ID if field_name == "download_url" else UUID(int=FINDING_ID.int + 1)),
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


def test_manifest_is_deterministic_reversible_and_hash_verified(tmp_path: Path) -> None:
    findings = [
        _finding("download_url", None, "https://clova.ai/font.zip"),
        _finding("license_status", "pending", "needs_review"),
    ]

    first = build_manifest(_run(), findings, [_row()])
    second = build_manifest(_run(), findings, [_row()])
    entry = first.forward.entries[0]

    assert entry.source_key.model_dump() == {
        "provider": "noonnu",
        "provider_record_id": "613",
    }
    assert entry.current.model_dump()["official_url"] == "https://instagram.com/wrong-old-link"
    assert entry.after == {
        "download_url": "https://clova.ai/font.zip",
        "license_status": "needs_review",
        "license_verified": False,
    }
    assert first.reverse.rollback_mode is True
    assert first.reverse.entries[0].after == entry.before
    assert first.forward.evidence_bundle.snapshots[0]["raw_text"] is None
    assert first.forward.evidence_bundle.snapshots[0]["source_key"] == entry.source_key.model_dump()
    assert first.forward_sha256 == second.forward_sha256
    assert first.reverse_sha256 == second.reverse_sha256
    assert first.forward_sha256 != first.reverse_sha256

    paths = write_manifest_bundle(first, tmp_path)
    assert verify_manifest_file(paths.forward, paths.forward_sha256) == first.forward
    assert verify_manifest_bytes(
        paths.forward.read_bytes(), paths.forward_sha256.read_text(encoding="ascii")
    ) == first.forward
    assert verify_manifest_file(paths.reverse, paths.reverse_sha256) == first.reverse
    tampered = json.loads(paths.forward.read_text(encoding="utf-8"))
    tampered["entries"][0]["after"]["download_url"] = "https://evil.example/font.zip"
    paths.forward.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ManifestError, match="SHA-256"):
        verify_manifest_file(paths.forward, paths.forward_sha256)


def test_manifest_rejects_unapproved_forbidden_stale_or_unbound_evidence(
    tmp_path: Path,
) -> None:
    proposed = _finding("download_url", None, "https://clova.ai/font.zip")
    proposed["status"] = "proposed"
    forbidden = _finding("official_url", "https://instagram.com/wrong-old-link", "https://clova.ai")
    stale = _finding("download_status", "verified", "needs_review")

    for finding, message in (
        (proposed, "approved"),
        (forbidden, "field"),
        (stale, "before"),
    ):
        with pytest.raises(ManifestError, match=message):
            build_manifest(_run(), [finding], [_row()])

    finding = _finding("download_url", None, "https://clova.ai/font.zip")
    finding["reviewed_by"] = ["not-a-human"]
    with pytest.raises(ManifestError, match="reviewed_by"):
        build_manifest(_run(), [finding], [_row()])

    wrong_font_row = deepcopy(_row())
    wrong_font_row["evidence_snapshots"][0]["font_id"] = str(UUID(int=FONT_ID.int + 1))
    with pytest.raises(ManifestError, match="snapshot font_id"):
        build_manifest(
            _run(), [_finding("download_url", None, "https://clova.ai/font.zip")], [wrong_font_row]
        )

    wrong_provider_row = deepcopy(_row())
    wrong_provider_row["evidence_snapshots"][0]["provider_record_id"] = "999"
    with pytest.raises(ManifestError, match="snapshot provider"):
        build_manifest(
            _run(), [_finding("download_url", None, "https://clova.ai/font.zip")], [wrong_provider_row]
        )

    duplicate_uuid_row = deepcopy(_row())
    duplicate_uuid_row["evidence_snapshots"][0]["id"] = str(RUN_ID)
    duplicate_uuid_finding = _finding("download_url", None, "https://clova.ai/font.zip")
    duplicate_uuid_finding["evidence_id"] = str(RUN_ID)
    with pytest.raises(ManifestError, match="globally unique"):
        build_manifest(_run(), [duplicate_uuid_finding], [duplicate_uuid_row])

    metadata_row = deepcopy(_row())
    with pytest.raises(ManifestError, match="document/source kind"):
        build_manifest(_run(), [_finding("foundry", None, "네이버")], [metadata_row])

    noonnu_row = deepcopy(_row())
    noonnu_row["evidence_snapshots"][0]["source_kind"] = "noonnu"
    with pytest.raises(ManifestError, match="document/source kind"):
        build_manifest(
            _run(), [_finding("download_url", None, "https://clova.ai/font.zip")], [noonnu_row]
        )

    bundle = build_manifest(
        _run(), [_finding("download_url", None, "https://clova.ai/font.zip")], [_row()]
    )
    paths = write_manifest_bundle(bundle, tmp_path)
    extra_evidence = json.loads(paths.forward.read_text(encoding="utf-8"))
    unused = _license_snapshot()
    unused.pop("font_id")
    unused.pop("raw_retention_allowed")
    unused["raw_text"] = None
    unused["source_key"] = {"provider": "noonnu", "provider_record_id": "613"}
    extra_evidence["evidence_bundle"]["snapshots"].append(unused)
    extra_evidence["entries"][0]["evidence_ids"].append(str(LICENSE_SNAPSHOT_ID))
    paths.forward.write_text(
        json.dumps(extra_evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths.forward_sha256.write_text(
        __import__("hashlib").sha256(paths.forward.read_bytes()).hexdigest() + "\n",
        encoding="ascii",
    )
    with pytest.raises(ManifestError, match="manifest JSON"):
        verify_manifest_file(paths.forward, paths.forward_sha256)

    paths = write_manifest_bundle(bundle, tmp_path)
    malformed = json.loads(paths.forward.read_text(encoding="utf-8"))
    malformed["entries"][0]["after"]["unexpected"] = "value"
    paths.forward.write_text(
        json.dumps(malformed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    paths.forward_sha256.write_text(
        __import__("hashlib").sha256(paths.forward.read_bytes()).hexdigest() + "\n",
        encoding="ascii",
    )
    with pytest.raises(ManifestError, match="manifest JSON"):
        verify_manifest_file(paths.forward, paths.forward_sha256)
