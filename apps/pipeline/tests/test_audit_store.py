"""승인 legal 근거를 metadata 입력으로 여는 저장소 계약."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

from fontagit_pipeline.audit_store import SupabaseAuditStore


def _query(data: list[dict[str, object]]) -> MagicMock:
    query = MagicMock()
    query.select.return_value = query
    query.update.return_value = query
    query.insert.return_value = query
    query.upsert.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.execute.return_value = SimpleNamespace(data=data)
    return query


def test_supabase_candidates_require_approved_same_run_font_and_exact_url() -> None:
    font_id = UUID("00000000-0000-0000-0000-000000000811")
    run_id = "00000000-0000-0000-0000-000000000812"
    evidence_id = "00000000-0000-0000-0000-000000000813"
    findings = _query(
        [
            {
                "run_id": run_id,
                "font_id": str(font_id),
                "proposed_value": "https://official.example/font.woff2",
                "evidence_id": evidence_id,
                "status": "approved",
            },
            {
                "run_id": run_id,
                "font_id": str(font_id),
                "proposed_value": "https://official.example/applied.woff2",
                "evidence_id": evidence_id,
                "status": "applied",
            },
            {
                "run_id": run_id,
                "font_id": "00000000-0000-0000-0000-000000000899",
                "proposed_value": "https://official.example/wrong.woff2",
                "evidence_id": evidence_id,
                "status": "approved",
            },
        ]
    )
    snapshots = _query(
        [
            {
                "id": evidence_id,
                "run_id": run_id,
                "font_id": str(font_id),
                "provider": "noonnu",
                "provider_record_id": "613",
                "source_kind": "official",
                "document_kind": "download",
                "request_url": "https://official.example/download",
                "extracted": {
                    "download_url": "https://official.example/font.woff2"
                },
            }
        ]
    )
    schema = MagicMock()
    schema.table.side_effect = {
        "font_audit_findings": findings,
        "font_source_snapshots": snapshots,
    }.__getitem__
    client = MagicMock()
    client.schema.return_value = schema

    candidates = SupabaseAuditStore(client).approved_font_file_candidates(
        font_id, "noonnu", "613"
    )

    assert [(item.source_kind, item.url) for item in candidates] == [
        ("official", "https://official.example/font.woff2")
    ]


def test_approve_finding_updates_status_on_valid_tags_finding() -> None:
    """tags 필드, needs_review 상태인 finding을 approved로 변경."""
    finding_id = "00000000-0000-0000-0000-000000000901"

    # SELECT 응답: finding 존재, tags, needs_review, stage 일치
    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "tags",
                "status": "needs_review",
                "stage": "metadata",
            }
        ]
    )

    # UPDATE 응답: 1건 업데이트됨
    update_response = _query([{"id": finding_id}])

    # 호출 순서: SELECT 첫번째, UPDATE 두번째
    schema = MagicMock()
    schema.table.side_effect = [select_response, update_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    # 호출 시 ValueError 발생 안 함
    store.approve_finding(UUID(finding_id), reviewed_by="test_user", stage="metadata")


def test_approve_finding_raises_on_nonexistent_finding() -> None:
    """finding이 존재하지 않으면 ValueError."""
    finding_id = "00000000-0000-0000-0000-000000000902"

    select_response = _query([])

    schema = MagicMock()
    schema.table.side_effect = [select_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    try:
        store.approve_finding(UUID(finding_id), reviewed_by="test_user", stage="metadata")
        assert False, "should raise ValueError"
    except ValueError:
        pass


def test_approve_finding_raises_on_legal_field() -> None:
    """download_url(legal) 필드는 승인 대상이 아님."""
    finding_id = "00000000-0000-0000-0000-000000000903"

    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "download_url",  # legal field
                "status": "needs_review",
                "stage": "metadata",
            }
        ]
    )

    schema = MagicMock()
    schema.table.side_effect = [select_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    try:
        store.approve_finding(UUID(finding_id), reviewed_by="test_user", stage="metadata")
        assert False, "should raise ValueError"
    except ValueError:
        pass


def test_approve_finding_raises_on_stage_mismatch() -> None:
    """stage가 일치하지 않으면 ValueError."""
    finding_id = "00000000-0000-0000-0000-000000000904"

    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "tags",
                "status": "needs_review",
                "stage": "metadata",  # DB의 stage
            }
        ]
    )

    schema = MagicMock()
    schema.table.side_effect = [select_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    try:
        # 요청 stage: "audit" (불일치)
        store.approve_finding(UUID(finding_id), reviewed_by="test_user", stage="audit")
        assert False, "should raise ValueError"
    except ValueError:
        pass


def test_approve_finding_raises_on_already_approved() -> None:
    """이미 status="approved"면 ValueError."""
    finding_id = "00000000-0000-0000-0000-000000000905"

    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "tags",
                "status": "approved",  # 이미 approved
                "stage": "metadata",
            }
        ]
    )

    schema = MagicMock()
    schema.table.side_effect = [select_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    try:
        store.approve_finding(UUID(finding_id), reviewed_by="test_user", stage="metadata")
        assert False, "should raise ValueError"
    except ValueError:
        pass


def test_approve_finding_raises_on_zero_affected_rows() -> None:
    """UPDATE가 0건 반환하면 ValueError (동시성)."""
    finding_id = "00000000-0000-0000-0000-000000000906"

    # SELECT 응답: finding 존재, 조건 맞음
    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "weights",
                "status": "needs_review",
                "stage": "metadata",
            }
        ]
    )

    # UPDATE 응답: 0건 (다른 스레드가 이미 업데이트)
    update_response = _query([])

    schema = MagicMock()
    schema.table.side_effect = [select_response, update_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    try:
        store.approve_finding(UUID(finding_id), reviewed_by="test_user", stage="metadata")
        assert False, "should raise ValueError"
    except ValueError:
        pass


def test_get_run_returns_correct_audit_run() -> None:
    """get_run(run_id)는 font_audit_runs 레코드를 dict로 반환."""
    run_id = UUID("00000000-0000-0000-0000-000000000907")

    run_data = {
        "id": str(run_id),
        "stage": "legal",
        "target_environment": "dev",
        "target_count": 5,
        "success_count": 5,
        "verified_count": 2,
        "review_count": 3,
        "broken_count": 0,
        "parser_version": "audit-v1",
        "baseline_sha256": "a" * 64,
        "manifest_sha256": None,
        "dry_run": False,
        "status": "completed",
        "started_at": "2026-07-22T10:00:00+00:00",
        "finished_at": "2026-07-22T11:00:00+00:00",
    }

    select_response = _query([run_data])

    schema = MagicMock()
    schema.table.return_value = select_response
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    result = store.get_run(run_id)

    assert result == run_data
    assert result["id"] == str(run_id)
    assert result["stage"] == "legal"
    assert result["status"] == "completed"


def test_get_approved_findings_returns_findings_list() -> None:
    """get_approved_findings(run_id)는 approved 상태 findings 리스트 반환."""
    run_id = UUID("00000000-0000-0000-0000-000000000908")
    font_id = UUID("00000000-0000-0000-0000-000000000809")
    evidence_id = UUID("00000000-0000-0000-0000-000000000810")

    findings_data = [
        {
            "id": "00000000-0000-0000-0000-000000000911",
            "run_id": str(run_id),
            "font_id": str(font_id),
            "field_name": "download_url",
            "before_value": None,
            "proposed_value": "https://example.com/font.woff2",
            "evidence_id": str(evidence_id),
            "confidence": "official",
            "auto_applicable": False,
            "review_reason": "사람 검수 완료",
            "status": "approved",
            "reviewed_by": "reviewer",
            "reviewed_at": "2026-07-22T10:30:00+00:00",
        },
        {
            "id": "00000000-0000-0000-0000-000000000912",
            "run_id": str(run_id),
            "font_id": str(font_id),
            "field_name": "license_status",
            "before_value": "pending",
            "proposed_value": "verified",
            "evidence_id": str(evidence_id),
            "confidence": "official",
            "auto_applicable": False,
            "review_reason": "OFL 라이선스 확인",
            "status": "approved",
            "reviewed_by": "reviewer",
            "reviewed_at": "2026-07-22T10:35:00+00:00",
        },
    ]

    select_response = _query(findings_data)

    schema = MagicMock()
    schema.table.return_value = select_response
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    results = store.get_approved_findings(run_id)

    assert len(results) == 2
    assert results[0]["status"] == "approved"
    assert results[0]["field_name"] == "download_url"
    assert results[1]["field_name"] == "license_status"
    assert results[1]["reviewed_by"] == "reviewer"


def test_get_current_fonts_with_snapshots_returns_fonts_with_evidence() -> None:
    """get_current_fonts_with_snapshots(run_id)는 evidence_snapshots가 포함된 fonts 리스트 반환."""
    run_id = UUID("00000000-0000-0000-0000-000000000909")
    font_id = UUID("00000000-0000-0000-0000-000000000810")
    snapshot_id = UUID("00000000-0000-0000-0000-000000000813")

    font_data = {
        "id": str(font_id),
        "source_key": {"provider": "noonnu", "provider_record_id": "613"},
        "slug": "흰꼬리수리",
        "name_ko": "흰꼬리수리",
        "name_en": None,
        "foundry": None,
        "official_url": "https://instagram.com/wrong-old-link",
        "status": "published",
        "updated_at": "2026-07-22T09:00:00+00:00",
        "download_url": None,
        "download_status": "pending",
        "download_evidence_id": None,
        "license_status": "pending",
        "license_verified": True,
    }

    snapshot_data = {
        "id": str(snapshot_id),
        "run_id": str(run_id),
        "font_id": str(font_id),
        "provider": "noonnu",
        "provider_record_id": "613",
        "source_kind": "official",
        "document_kind": "download",
        "request_url": "https://clova.ai/handwriting/list.html",
        "final_url": "https://clova.ai/handwriting/list.html",
        "http_status": 200,
        "raw_text": "내부 원문은 정책 승인 전 내보내지 않는다.",
        "raw_sha256": "b" * 64,
        "normalized_sha256": "c" * 64,
        "extracted": {"download_url": "https://clova.ai/font.zip"},
        "evidence_locations": {"download_url": "a.download"},
        "extraction_rule_id": "official-download-v1",
        "parser_version": "audit-v1",
        "collected_at": "2026-07-22T08:00:00+00:00",
    }

    fonts_response = _query([font_data])
    snapshots_response = _query([snapshot_data])

    schema = MagicMock()
    schema.table.side_effect = [fonts_response, snapshots_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    results = store.get_current_fonts_with_snapshots(run_id)

    assert len(results) == 1
    font = results[0]
    assert font["id"] == str(font_id)
    assert font["slug"] == "흰꼬리수리"
    assert font["source_key"] == {"provider": "noonnu", "provider_record_id": "613"}
    assert "evidence_snapshots" in font
    assert len(font["evidence_snapshots"]) == 1
    assert font["evidence_snapshots"][0]["id"] == str(snapshot_id)
    assert font["evidence_snapshots"][0]["document_kind"] == "download"
