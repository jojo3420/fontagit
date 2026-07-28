"""승인된 폰트 감사 manifest의 핵심 안전 계약."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from fontagit_pipeline.audit_manifest import (
    ManifestBundle,
    ManifestEntry,
    ManifestError,
    _evidence_role_is_valid,
    build_manifest,
    split_manifest_into_chunks,
    verify_manifest_bytes,
    verify_manifest_file,
    write_chunked_manifest_bundles,
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


def _finding(
    field_name: str, before: object, proposed: object, font_id: str | None = None
) -> dict[str, object]:
    evidence_id = (
        LICENSE_SNAPSHOT_ID
        if field_name.startswith("license_") or field_name == "license_verified"
        else SNAPSHOT_ID
    )
    return {
        "id": str(FINDING_ID if field_name == "download_url" else UUID(int=FINDING_ID.int + 1)),
        "run_id": str(RUN_ID),
        "font_id": font_id or str(FONT_ID),
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

    noonnu_script_row = deepcopy(_row())
    noonnu_script_row["script_status"] = "pending"
    noonnu_script_row["weights"] = [400]
    noonnu_script_row["evidence_snapshots"][0].update(
        {
            "source_kind": "noonnu",
            "document_kind": "metadata",
            "extracted": {"evidence_role": "font-file-script"},
        }
    )
    script_finding = _finding("script_status", "pending", "needs_review")
    script_finding["confidence"] = "reference"
    assert build_manifest(_run(), [script_finding], [noonnu_script_row]).forward.entries

    # 컬렉션 0단계: tags/weights도 noonnu metadata font-file-script reference 허용
    weight_finding = _finding("weights", [400], [700])
    weight_finding["confidence"] = "reference"
    assert build_manifest(_run(), [weight_finding], [noonnu_script_row]).forward.entries

    license_finding = _finding("license_status", "pending", "needs_review")
    license_finding["evidence_id"] = str(SNAPSHOT_ID)
    license_finding["confidence"] = "reference"
    with pytest.raises(ManifestError, match="document/source kind"):
        build_manifest(_run(), [license_finding], [noonnu_script_row])

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


def test_evidence_role_is_valid_tags_noonnu_font_file_script_reference() -> None:
    """컬렉션 0단계: tags + noonnu metadata font-file-script → reference 신뢰도 허용."""
    snapshot = {
        "source_kind": "noonnu",
        "document_kind": "metadata",
        "extracted": {
            "evidence_role": "font-file-script",
        },
    }
    assert _evidence_role_is_valid("tags", snapshot, "reference") is True


def test_evidence_role_is_valid_tags_noonnu_missing_evidence_role() -> None:
    """tags + noonnu metadata이지만 evidence_role 없으면 False."""
    snapshot = {
        "source_kind": "noonnu",
        "document_kind": "metadata",
        "extracted": {},  # evidence_role 없음
    }
    assert _evidence_role_is_valid("tags", snapshot, "reference") is False


_NOONNU_SCRIPT_EVIDENCE = {
    "source_kind": "noonnu",
    "document_kind": "metadata",
    "extracted": {"evidence_role": "font-file-script"},
}
_TIER_A_EVIDENCE = {
    "source_kind": "archive",  # 이슈 #133: Tier A 스냅샷 저장 등급
    "provider": "google-fonts",
    "document_kind": "metadata",
    "extracted": {"evidence_role": "tier-a-metadata-pb"},
}
_REFERENCE_EVIDENCE_TEST_FIELDS = (
    "foundry",
    "foundry_url",
    "download_url",
    "download_source_kind",
    "license_source_url",
)


@pytest.mark.parametrize("snapshot", [_NOONNU_SCRIPT_EVIDENCE, _TIER_A_EVIDENCE], ids=["noonnu", "tier_a"])
@pytest.mark.parametrize("field_name", _REFERENCE_EVIDENCE_TEST_FIELDS)
def test_evidence_role_is_valid_reference_fields_allow_noonnu_and_tier_a(
    field_name: str, snapshot: dict[str, object]
) -> None:
    """이슈 #131: foundry/foundry_url/download_url/download_source_kind/license_source_url은
    눈누 font-file-script 및 Tier A(google-fonts) metadata를 reference 신뢰도로 허용한다."""
    assert _evidence_role_is_valid(field_name, snapshot, "reference") is True
    # confidence가 reference가 아니면(예: official) 여전히 거부된다.
    assert _evidence_role_is_valid(field_name, snapshot, "official") is False


@pytest.mark.parametrize("snapshot", [_NOONNU_SCRIPT_EVIDENCE, _TIER_A_EVIDENCE], ids=["noonnu", "tier_a"])
@pytest.mark.parametrize(
    "field_name",
    [
        "license_source_kind",
        "allow_commercial",
        "license_verified",
        "allow_modify",
        "allow_redistribute",
        "allow_embedding",
        "allow_font_sale",
        "attribution_requirement",
        "is_commercial_free",
    ],
)
def test_evidence_role_is_valid_protected_fields_reject_reference_evidence(
    field_name: str, snapshot: dict[str, object]
) -> None:
    """legal 필드(allow_*)와 license_source_kind는 눈누/Tier A reference 우회 대상이 아니다."""
    assert _evidence_role_is_valid(field_name, snapshot, "reference") is False


def test_evidence_role_is_valid_tier_a_rejects_non_google_fonts_provider() -> None:
    """이슈 #133: provider가 google-fonts가 아니면 Tier A 우회가 성립하지 않는다."""
    snapshot = {**_TIER_A_EVIDENCE, "source_kind": "public", "provider": "some-other-provider"}
    assert _evidence_role_is_valid("foundry_url", snapshot, "reference") is False


def test_evidence_role_is_valid_public_metadata_without_tier_a_marker_rejects_reference() -> None:
    """이슈 #133: public metadata라도 tier-a-metadata-pb 마커가 없으면 reference 우회가 되지 않는다."""
    snapshot = {
        "source_kind": "public",
        "provider": "google-fonts",
        "document_kind": "metadata",
        "extracted": {},  # evidence_role 없음
    }
    assert _evidence_role_is_valid("foundry_url", snapshot, "reference") is False


def test_build_manifest_accepts_reference_evidence_for_link_role_fields() -> None:
    """이슈 #131: foundry/foundry_url/download_url/download_source_kind/license_source_url이
    눈누 font-file-script metadata 근거(reference 신뢰도)로 정상 승인된다."""
    row = deepcopy(_row())
    row["evidence_snapshots"][0].update(_NOONNU_SCRIPT_EVIDENCE)
    row["evidence_snapshots"][1].update(_NOONNU_SCRIPT_EVIDENCE)

    findings = []
    for offset, (field_name, proposed) in enumerate(
        (
            ("foundry", "네이버"),
            ("foundry_url", "https://hangeul.naver.com/fonts"),
            ("download_url", "https://fonts.google.com/specimen/Noto+Sans"),
            ("download_source_kind", "archive"),
            (
                "license_source_url",
                "https://raw.githubusercontent.com/google/fonts/main/ofl/notosans/LICENSE.txt",
            ),
        )
    ):
        finding = _finding(field_name, None, proposed)
        finding["id"] = str(UUID(int=FINDING_ID.int + 10 + offset))
        finding["confidence"] = "reference"
        findings.append(finding)

    bundle = build_manifest(_run(), findings, [row])
    assert set(bundle.forward.entries[0].after) == set(_REFERENCE_EVIDENCE_TEST_FIELDS)


def test_build_manifest_snapshot_run_id_invalid_uuid() -> None:
    """비정상: snapshot run_id가 유효한 UUID가 아니면 ManifestError."""
    row = deepcopy(_row())
    row["evidence_snapshots"][0]["run_id"] = "not-a-uuid"  # 유효하지 않은 UUID

    with pytest.raises(ManifestError, match="snapshot.run_id"):
        build_manifest(_run(), [_finding("download_url", None, "https://clova.ai/font.zip")], [row])


def test_split_manifest_into_chunks_basic() -> None:
    """청크 분할: chunk_size=1로 1개 엔트리 bundle을 분할해도 1개 청크 생성."""
    findings = [
        _finding("download_url", None, "https://clova.ai/font.zip"),
    ]
    bundle = build_manifest(_run(), findings, [_row()])

    chunks = split_manifest_into_chunks(bundle, chunk_size=1)

    assert len(chunks) == 1
    assert len(chunks[0].forward.entries) == 1


def test_split_manifest_into_chunks_evidence_filtering() -> None:
    """청크 분할: 각 청크의 evidence_bundle은 참조하는 snapshot/finding만 포함."""
    findings = [
        _finding("download_url", None, "https://clova.ai/font.zip"),
    ]
    bundle = build_manifest(_run(), findings, [_row()])
    chunks = split_manifest_into_chunks(bundle, chunk_size=1)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert len(chunk.forward.evidence_bundle.snapshots) >= 1
    assert len(chunk.forward.evidence_bundle.findings) == 1


def test_split_manifest_into_chunks_sha_consistency() -> None:
    """청크 분할: 각 청크의 SHA는 계산한 값과 일치."""
    from fontagit_pipeline.audit_manifest import _digest

    findings = [
        _finding("download_url", None, "https://clova.ai/font.zip"),
    ]
    bundle = build_manifest(_run(), findings, [_row()])
    chunks = split_manifest_into_chunks(bundle, chunk_size=1)

    for chunk in chunks:
        expected_sha = _digest(chunk.forward)
        assert chunk.forward_sha256 == expected_sha


def test_write_chunked_manifest_bundles_creates_index(tmp_path: Path) -> None:
    """청크 저장: index.json이 생성되고 메타데이터가 포함된다."""
    findings = [
        _finding("download_url", None, "https://clova.ai/font.zip"),
    ]
    bundle = build_manifest(_run(), findings, [_row()])
    chunks = split_manifest_into_chunks(bundle, chunk_size=1)

    index = write_chunked_manifest_bundles(chunks, tmp_path)

    assert index["total_chunks"] == 1
    assert index["total_entries"] == 1
    assert len(index["chunks"]) == 1

    index_file = tmp_path / "index.json"
    assert index_file.exists()

    chunk_dirs = sorted([d for d in tmp_path.iterdir() if d.is_dir() and d.name.startswith("chunk-")])
    assert len(chunk_dirs) == 1
    assert (chunk_dirs[0] / "forward.json").exists()
    assert (chunk_dirs[0] / "forward.sha256").exists()
    assert (chunk_dirs[0] / "reverse.json").exists()
    assert (chunk_dirs[0] / "reverse.sha256").exists()


def _bundle_with_three_entries() -> "ManifestBundle":
    """3개의 서로 다른 폰트 엔트리를 가진 manifest bundle을 생성한다."""
    from copy import deepcopy

    findings_data = []
    rows_data = []

    for idx in range(3):
        font_id = UUID(int=FONT_ID.int + idx * 100)  # 큰 간격으로 구분
        snapshot_id = UUID(int=SNAPSHOT_ID.int + idx * 100)
        license_snapshot_id = UUID(int=LICENSE_SNAPSHOT_ID.int + idx * 100)
        download_finding_id = UUID(int=FINDING_ID.int + idx * 100)
        license_finding_id = UUID(int=FINDING_ID.int + idx * 100 + 50)

        # 각 폰트별 snapshot과 license_snapshot 생성
        snapshot_data = {
            "id": str(snapshot_id),
            "run_id": str(RUN_ID),
            "font_id": str(font_id),
            "provider": "noonnu",
            "provider_record_id": str(613 + idx),
            "source_kind": "official",
            "document_kind": "download",
            "request_url": "https://clova.ai/handwriting/list.html",
            "final_url": "https://clova.ai/handwriting/list.html",
            "http_status": 200,
            "raw_text": "내부 원문은 정책 승인 전 내보내지 않는다.",
            "raw_retention_allowed": False,
            "raw_sha256": "b" * 64,
            "normalized_sha256": "c" * 64,
            "extracted": {"download_url": f"https://clova.ai/font{idx}.zip"},
            "evidence_locations": {"download_url": "a.download"},
            "extraction_rule_id": "official-download-v1",
            "parser_version": "audit-v1",
            "collected_at": NOW.isoformat(),
        }

        license_snapshot_data = deepcopy(snapshot_data)
        license_snapshot_data.update({
            "id": str(license_snapshot_id),
            "document_kind": "license",
            "raw_sha256": "d" * 64,
            "normalized_sha256": "e" * 64,
        })

        # 각 폰트별 finding 생성
        download_finding = {
            "id": str(download_finding_id),
            "run_id": str(RUN_ID),
            "font_id": str(font_id),
            "field_name": "download_url",
            "before_value": None,
            "proposed_value": f"https://clova.ai/font{idx}.zip",
            "evidence_id": str(snapshot_id),
            "confidence": "official",
            "auto_applicable": False,
            "review_reason": "사람 검수 완료",
            "status": "approved",
            "reviewed_by": "reviewer",
            "reviewed_at": NOW.isoformat(),
        }

        license_finding = {
            "id": str(license_finding_id),
            "run_id": str(RUN_ID),
            "font_id": str(font_id),
            "field_name": "license_status",
            "before_value": "pending",
            "proposed_value": "needs_review",
            "evidence_id": str(license_snapshot_id),
            "confidence": "official",
            "auto_applicable": False,
            "review_reason": "사람 검수 완료",
            "status": "approved",
            "reviewed_by": "reviewer",
            "reviewed_at": NOW.isoformat(),
        }

        # 각 폰트별 row 생성
        row = {
            "id": str(font_id),
            "source_key": {"provider": "noonnu", "provider_record_id": str(613 + idx)},
            "slug": f"폰트{idx}",
            "name_ko": f"폰트{idx}",
            "name_en": None,
            "foundry": None,
            "official_url": f"https://example.com/font{idx}",
            "status": "published",
            "updated_at": NOW.isoformat(),
            "download_url": None,
            "download_status": "pending",
            "download_evidence_id": None,
            "license_status": "pending",
            "license_verified": True,
            "evidence_snapshots": [snapshot_data, license_snapshot_data],
        }

        findings_data.extend([download_finding, license_finding])
        rows_data.append(row)

    # manifest 생성
    bundle = build_manifest(_run(), findings_data, rows_data)
    return bundle


def _entries_of(bundle: "ManifestBundle") -> list["ManifestEntry"]:
    """번들의 forward entries를 반환한다."""
    return bundle.forward.entries


def _reverse_entries_of(bundle: "ManifestBundle") -> list["ManifestEntry"]:
    """번들의 reverse entries를 반환한다."""
    return bundle.reverse.entries


def _evidence_ids_of(bundle: "ManifestBundle") -> set[str]:
    """번들의 evidence (snapshot) id 집합을 반환한다."""
    return {str(s["id"]) for s in bundle.forward.evidence_bundle.snapshots}


def _finding_ids_of(bundle: "ManifestBundle") -> set[str]:
    """번들의 finding id 집합을 반환한다."""
    return {str(f["id"]) for f in bundle.forward.evidence_bundle.findings}


def test_chunk_split_preserves_entry_union() -> None:
    """3엔트리 chunk_size=2 분할 시 전체 엔트리 합집합이 보존된다."""
    bundle = _bundle_with_three_entries()
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
            entry_evidence = {str(i) for i in entry.evidence_ids}
            entry_findings = {str(i) for i in entry.finding_ids}
            assert entry_evidence <= included
            assert entry_findings <= _finding_ids_of(chunk)


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
    # 번들에서 evidence 목록에서 1개를 제거하여 참조 무결성 위반 생성
    if bundle.forward.evidence_bundle.snapshots:
        bundle.forward.evidence_bundle.snapshots.pop(0)
    with pytest.raises(ManifestError):
        split_manifest_into_chunks(bundle, chunk_size=2)
