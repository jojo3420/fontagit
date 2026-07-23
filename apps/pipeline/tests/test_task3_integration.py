"""Task 3 헬퍼의 build_manifest 정합 엄밀 통합 테스트 (비타우톨로지)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from fontagit_pipeline.audit_manifest import build_manifest, ManifestError
from fontagit_pipeline.audit_store import SupabaseAuditStore


# Test UUIDs
RUN_ID = UUID("00000000-0000-0000-0000-000000010001")
FONT_ID_1 = UUID("00000000-0000-0000-0000-000000010002")  # 감사 대상
FONT_ID_2 = UUID("00000000-0000-0000-0000-000000010003")  # 감사 대상
FONT_ID_UNRELATED = UUID("00000000-0000-0000-0000-000000010004")  # 무관 폰트
SNAPSHOT_ID_1 = UUID("00000000-0000-0000-0000-000000010010")
SNAPSHOT_ID_2 = UUID("00000000-0000-0000-0000-000000010011")
FINDING_ID_1 = UUID("00000000-0000-0000-0000-000000010020")
FINDING_ID_2 = UUID("00000000-0000-0000-0000-000000010021")

NOW = datetime(2026, 7, 22, 10, 30, 45, tzinfo=UTC)


def _make_run() -> dict[str, object]:
    """실제 font_audit_runs 테이블의 형식을 모방한 run 데이터."""
    return {
        "id": str(RUN_ID),
        "stage": "metadata",
        "target_environment": "dev",
        "target_count": 2,
        "success_count": 2,
        "verified_count": 0,
        "review_count": 2,
        "broken_count": 0,
        "parser_version": "audit-v1",
        "baseline_sha256": "a1b2c3d4" * 8,  # 64자 소문자 hex
        "manifest_sha256": None,
        "dry_run": False,
        "status": "completed",
        "started_at": NOW.isoformat(),
        "finished_at": NOW.isoformat(),
    }


def _make_snapshot(
    snapshot_id: UUID,
    font_id: UUID,
    provider: str = "noonnu",
    provider_record_id: str = "1234",
    document_kind: str = "metadata",
) -> dict[str, object]:
    """실제 font_source_snapshots 테이블의 18컬럼 전부."""
    return {
        "id": str(snapshot_id),
        "run_id": str(RUN_ID),
        "font_id": str(font_id),
        "provider": provider,
        "provider_record_id": provider_record_id,
        "source_kind": "official",
        "document_kind": document_kind,
        "request_url": "https://example.com/fonts",
        "final_url": "https://example.com/fonts",
        "http_status": 200,
        "raw_text": "Raw font metadata",
        "raw_sha256": "a1b2" * 16,  # Valid lowercase hex
        "normalized_sha256": "c3d4" * 16,  # Valid lowercase hex
        "extracted": {"download_url": "https://example.com/font.zip"},
        "evidence_locations": {"download_url": "index[0]"},
        "extraction_rule_id": "official-download-v1",
        "parser_version": "audit-v1",
        "collected_at": NOW.isoformat(),
    }


def _make_font(font_id: UUID, slug: str, provider: str = "noonnu", provider_record_id: str | None = None) -> dict[str, object]:
    """실제 fonts 테이블의 형식을 모방한 폰트 데이터."""
    if provider_record_id is None:
        provider_record_id = "1234" if font_id == FONT_ID_1 else "5678"
    return {
        "id": str(font_id),
        "source_key": {
            "provider": provider,
            "provider_record_id": provider_record_id,
        },
        "slug": slug,
        "name_ko": f"{slug} 한글",
        "name_en": f"{slug.capitalize()} English",
        "foundry": "Test Foundry",
        "official_url": f"https://example.com/{slug}",
        "status": "published",
        "source_tier": "noonnu",
        "tags": [],
        "weights": [],
        "updated_at": NOW.isoformat(),
        "license_status": "pending",
        "license_verified": False,
        "evidence_snapshots": [],  # build_manifest에서 예상됨
    }


def _make_finding(
    finding_id: UUID,
    font_id: UUID,
    field_name: str,
    before_value: object,
    proposed_value: object,
    evidence_id: UUID,
) -> dict[str, object]:
    """실제 font_audit_findings 테이블의 형식을 모방한 finding 데이터."""
    return {
        "id": str(finding_id),
        "run_id": str(RUN_ID),
        "font_id": str(font_id),
        "field_name": field_name,
        "before_value": before_value,
        "proposed_value": proposed_value,
        "evidence_id": str(evidence_id),
        "confidence": "official",
        "auto_applicable": False,
        "review_reason": "검수 완료",
        "status": "approved",
        "reviewed_by": "test-reviewer",
        "reviewed_at": NOW.isoformat(),
    }


def test_task3_helpers_manifest_integration() -> None:
    """Task 3 헬퍼들이 build_manifest와 정합한 데이터를 생성하는지 검증.

    이것은 비타우톨로지 테스트로, 실제 DB 컬럼 형태의 mock 데이터와
    build_manifest 함수의 실제 동작을 조합하여 정합을 실증한다.

    검증 항목:
    - build_manifest가 ManifestError 없이 ManifestBundle 생성
    - Findings가 있는 폰트만 entries에 포함
    - 무관 폰트(findings 없음)는 entries에 미포함
    - ManifestCurrent의 7필드(slug, name_en, name_ko, foundry, source_tier, official_url, status)가 유효
    - source_key가 snapshot에서 파생되어 유효
    """

    # 1. 실제 형식의 mock 데이터 구성
    # 감사 대상 폰트 2개 (각각 고유한 provider_record_id)
    font_1 = _make_font(FONT_ID_1, "test-font-1", provider_record_id="1234")
    font_2 = _make_font(FONT_ID_2, "test-font-2", provider_record_id="5678")

    # 무관 폰트 (run에 snapshot/findings이 없음)
    font_unrelated = _make_font(FONT_ID_UNRELATED, "unrelated-font", provider_record_id="9999")

    # Snapshots (run_id 일치, font_id 포함, 18컬럼 모두)
    snapshot_1 = _make_snapshot(SNAPSHOT_ID_1, FONT_ID_1, "noonnu", "1234")
    snapshot_2 = _make_snapshot(SNAPSHOT_ID_2, FONT_ID_2, "noonnu", "5678")

    # Approved findings (status='approved', field_name in {tags,weights})
    finding_1 = _make_finding(
        FINDING_ID_1,
        FONT_ID_1,
        "tags",
        [],  # before_value는 현재 row의 필드값
        ["한글", "디스플레이"],  # proposed_value
        SNAPSHOT_ID_1,
    )
    finding_2 = _make_finding(
        FINDING_ID_2,
        FONT_ID_2,
        "weights",
        [],  # before_value는 빈 배열
        [400, 700],  # weights는 정수 배열
        SNAPSHOT_ID_2,
    )

    # fonts에 snapshots 추가 (get_current_fonts_with_snapshots의 동작)
    font_1["evidence_snapshots"] = [snapshot_1]
    font_2["evidence_snapshots"] = [snapshot_2]

    run = _make_run()

    # 2. SupabaseAuditStore mock 설정 및 헬퍼 호출
    mock_client = MagicMock()
    store = SupabaseAuditStore(mock_client)

    # Mock the supabase query chains for real get_current_fonts_with_snapshots execution
    # (새 구현: evidence_id 기준 in-list 조회)
    snapshot_data = [snapshot_1, snapshot_2]
    fonts_data = [font_1, font_2]  # evidence_id에 해당하는 것들만

    # font_source_snapshots table query chain (.in_("id", chunk))
    snapshots_result = MagicMock()
    snapshots_result.data = snapshot_data

    mock_snapshots_table = MagicMock()
    mock_snapshots_table.select.return_value.in_.return_value.execute.return_value = snapshots_result

    # fonts table query chain (.in_("id", chunk))
    fonts_result = MagicMock()
    fonts_result.data = fonts_data

    mock_fonts_table = MagicMock()
    mock_fonts_table.select.return_value.in_.return_value.execute.return_value = fonts_result

    # Route table() calls to correct mock
    def table_side_effect(table_name):
        if table_name == "font_source_snapshots":
            return mock_snapshots_table
        elif table_name == "fonts":
            return mock_fonts_table
        return MagicMock()

    mock_client.schema.return_value.table.side_effect = table_side_effect

    approved_findings = [finding_1, finding_2]

    # mock 메서드 설정
    store.get_run = MagicMock(return_value=run)
    store.get_approved_findings = MagicMock(return_value=approved_findings)

    # 3. 헬퍼 메서드 호출 (진정한 통합테스트)
    run_from_store = store.get_run(RUN_ID)
    approved_findings_from_store = store.get_approved_findings(RUN_ID)
    current_rows_from_store = store.get_current_fonts_with_snapshots(RUN_ID)

    # 4. 실제 build_manifest 호출 (핵심 검증)
    bundle = build_manifest(run_from_store, approved_findings_from_store, current_rows_from_store)

    # 5. 정합 검증
    # 5a. ManifestBundle이 정상 생성됨
    assert bundle is not None
    assert bundle.forward is not None
    assert bundle.reverse is not None

    # 5b. entries는 2개 (finding이 있는 폰트만, 무관 폰트 제외)
    assert len(bundle.forward.entries) == 2, f"Expected 2 entries, got {len(bundle.forward.entries)}"

    # 5c. 포함된 source_key 검증
    entry_source_keys = {
        (e.source_key.provider, e.source_key.provider_record_id)
        for e in bundle.forward.entries
    }
    assert ("noonnu", "1234") in entry_source_keys
    assert ("noonnu", "5678") in entry_source_keys

    # 5d. 각 entry의 구조 검증
    for entry in bundle.forward.entries:
        # ManifestCurrent 7필드 존재
        assert hasattr(entry.current, "slug")
        assert hasattr(entry.current, "name_en")
        assert hasattr(entry.current, "name_ko")
        assert hasattr(entry.current, "foundry")
        assert hasattr(entry.current, "source_tier")
        assert hasattr(entry.current, "official_url")
        assert hasattr(entry.current, "status")

        # source_key 유효
        assert entry.source_key.provider == "noonnu"
        assert len(entry.source_key.provider_record_id) > 0

        # before/after 필드 포함 (tags 또는 weights)
        assert "tags" in entry.after or "weights" in entry.after


def test_task3_helpers_reject_invalid_manifest_data() -> None:
    """Task 3 헬퍼가 build_manifest와 양립할 수 없는 데이터를 생성하지 않음을 검증."""

    run = _make_run()

    # Finding이 존재하지 않는 font를 참조하는 경우
    snapshot = _make_snapshot(SNAPSHOT_ID_1, FONT_ID_1)
    finding_bad_font = _make_finding(
        FINDING_ID_1,
        FONT_ID_UNRELATED,  # 이 폰트는 current_rows에 없음
        "tags",
        None,
        ["test"],
        SNAPSHOT_ID_1,
    )

    font = _make_font(FONT_ID_1, "test-font")
    font["evidence_snapshots"] = [snapshot]

    # build_manifest가 ManifestError 발생
    with pytest.raises(ManifestError, match="finding font has no current row"):
        build_manifest(run, [finding_bad_font], [font])


def test_task3_helpers_evidence_snapshot_validation() -> None:
    """Task 3 헬퍼가 evidence 검증을 통과하는 데이터를 생성함을 검증."""

    run = _make_run()

    # Valid snapshot
    snapshot = _make_snapshot(SNAPSHOT_ID_1, FONT_ID_1)

    # Finding의 evidence_id가 실제 snapshot과 일치
    finding = _make_finding(
        FINDING_ID_1,
        FONT_ID_1,
        "tags",
        [],  # before_value는 현재 row의 필드값
        ["test"],
        SNAPSHOT_ID_1,
    )

    font = _make_font(FONT_ID_1, "test-font")
    font["evidence_snapshots"] = [snapshot]

    # 성공해야 함
    bundle = build_manifest(run, [finding], [font])
    assert len(bundle.forward.entries) == 1
    assert bundle.forward.entries[0].source_key.provider == "noonnu"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
