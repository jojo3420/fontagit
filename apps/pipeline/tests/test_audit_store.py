"""승인 legal 근거를 metadata 입력으로 여는 저장소 계약."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from fontagit_pipeline.audit_store import SupabaseAuditStore


def _query(data: list[dict[str, object]]) -> MagicMock:
    query = MagicMock()
    query.select.return_value = query
    query.update.return_value = query
    query.insert.return_value = query
    query.upsert.return_value = query
    query.eq.return_value = query
    query.limit.return_value = query
    query.order.return_value = query
    query.range.return_value = query
    query.in_.return_value = query
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
    """tags 필드, proposed 상태인 finding을 approved로 변경."""
    finding_id = "00000000-0000-0000-0000-000000000901"

    # SELECT 응답: finding 존재, tags, proposed
    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "tags",
                "status": "proposed",
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
    store.approve_finding(UUID(finding_id), reviewed_by="test_user")


def test_approve_finding_raises_on_empty_reviewed_by() -> None:
    """reviewed_by가 비어있으면 ValueError."""
    finding_id = "00000000-0000-0000-0000-000000000901"

    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "tags",
                "status": "proposed",
            }
        ]
    )

    schema = MagicMock()
    schema.table.side_effect = [select_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    with pytest.raises(ValueError, match="reviewed_by는 필수"):
        store.approve_finding(UUID(finding_id), reviewed_by="")


def test_approve_finding_raises_on_nonexistent_finding() -> None:
    """finding이 존재하지 않으면 ValueError."""
    finding_id = "00000000-0000-0000-0000-000000000902"

    select_response = _query([])

    schema = MagicMock()
    schema.table.side_effect = [select_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    with pytest.raises(ValueError, match="존재하지 않는 finding"):
        store.approve_finding(UUID(finding_id), reviewed_by="test_user")


def test_approve_finding_raises_on_legal_field() -> None:
    """download_url(legal) 필드는 승인 대상이 아님."""
    finding_id = "00000000-0000-0000-0000-000000000903"

    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "download_url",  # legal field
                "status": "proposed",
            }
        ]
    )

    schema = MagicMock()
    schema.table.side_effect = [select_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    with pytest.raises(ValueError, match="승인 대상이 아닙니다"):
        store.approve_finding(UUID(finding_id), reviewed_by="test_user")


def test_approve_finding_raises_on_already_approved() -> None:
    """status가 proposed가 아니면 ValueError."""
    finding_id = "00000000-0000-0000-0000-000000000905"

    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "tags",
                "status": "rejected",  # proposed가 아님
            }
        ]
    )

    schema = MagicMock()
    schema.table.side_effect = [select_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    with pytest.raises(ValueError, match="승인 불가"):
        store.approve_finding(UUID(finding_id), reviewed_by="test_user")


def test_approve_finding_raises_on_zero_affected_rows() -> None:
    """UPDATE가 0건 반환하면 ValueError (동시성)."""
    finding_id = "00000000-0000-0000-0000-000000000906"

    # SELECT 응답: finding 존재, 조건 맞음
    select_response = _query(
        [
            {
                "id": finding_id,
                "field_name": "weights",
                "status": "proposed",
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
    with pytest.raises(ValueError, match="동시성 충돌"):
        store.approve_finding(UUID(finding_id), reviewed_by="test_user")


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

    # approved finding
    finding_data = {
        "id": str(uuid4()),
        "run_id": str(run_id),
        "font_id": str(font_id),
        "field_name": "tags",
        "status": "approved",
        "evidence_id": str(snapshot_id),
    }

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

    # Mock 응답 순서: get_approved_findings → snapshots .in_("id",...) → fonts .in_("id",...)
    findings_response = _query([finding_data])
    snapshots_response = _query([snapshot_data])
    fonts_response = _query([font_data])

    schema = MagicMock()
    schema.table.side_effect = [findings_response, snapshots_response, fonts_response]
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


def test_get_current_fonts_with_snapshots_includes_other_run_snapshots() -> None:
    """스냅샷이 타 run 귀속이어도 current rows에 정상 포함 (dedup 재사용 대응)."""
    run_id = UUID("00000000-0000-0000-0000-000000000909")
    other_run_id = UUID("00000000-0000-0000-0000-000000000908")
    font_id = UUID("00000000-0000-0000-0000-000000000810")
    snapshot_id = UUID("00000000-0000-0000-0000-000000000813")

    # 현재 run의 approved finding이 다른 run 귀속 스냅샷을 가리킴 (dedup 때문)
    finding_data = {
        "id": str(uuid4()),
        "run_id": str(run_id),
        "font_id": str(font_id),
        "field_name": "tags",
        "status": "approved",
        "evidence_id": str(snapshot_id),
    }

    font_data = {
        "id": str(font_id),
        "source_key": {"provider": "noonnu", "provider_record_id": "613"},
        "slug": "흰꼬리수리",
    }

    # 스냅샷이 다른 run_id를 가짐
    snapshot_data = {
        "id": str(snapshot_id),
        "run_id": str(other_run_id),  # 다른 run
        "font_id": str(font_id),
        "provider": "noonnu",
        "provider_record_id": "613",
        "document_kind": "download",
    }

    findings_response = _query([finding_data])
    snapshots_response = _query([snapshot_data])
    fonts_response = _query([font_data])

    schema = MagicMock()
    schema.table.side_effect = [findings_response, snapshots_response, fonts_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    results = store.get_current_fonts_with_snapshots(run_id)

    # 다른 run 귀속이어도 포함되어야 함
    assert len(results) == 1
    font = results[0]
    assert font["id"] == str(font_id)
    assert len(font["evidence_snapshots"]) == 1
    assert font["evidence_snapshots"][0]["id"] == str(snapshot_id)
    # run_id가 다르지만 정상 동작
    assert font["evidence_snapshots"][0]["run_id"] == str(other_run_id)


def test_get_current_fonts_with_snapshots_raises_on_missing_evidence_id() -> None:
    """evidence_id가 None인 approved finding 존재 시 RuntimeError."""
    run_id = UUID("00000000-0000-0000-0000-000000000909")
    font_id = UUID("00000000-0000-0000-0000-000000000810")

    # evidence_id가 None
    finding_data = {
        "id": str(uuid4()),
        "run_id": str(run_id),
        "font_id": str(font_id),
        "field_name": "tags",
        "status": "approved",
        "evidence_id": None,  # 결측
    }

    findings_response = _query([finding_data])

    schema = MagicMock()
    schema.table.side_effect = [findings_response]
    client = MagicMock()
    client.schema.return_value = schema

    store = SupabaseAuditStore(client)
    with pytest.raises(RuntimeError, match="has no evidence_id"):
        store.get_current_fonts_with_snapshots(run_id)


def test_get_current_fonts_with_snapshots_with_target_store() -> None:
    """target_store 지정 시 fonts와 font_sources를 대상 스토어에서 조회."""
    run_id = UUID("00000000-0000-0000-0000-000000000909")
    font_id = UUID("00000000-0000-0000-0000-000000000810")
    target_font_id = UUID("00000000-0000-0000-0000-000000000811")
    snapshot_id = UUID("00000000-0000-0000-0000-000000000813")

    # dev: approved finding, snapshot
    finding_data = {
        "id": str(uuid4()),
        "run_id": str(run_id),
        "font_id": str(font_id),
        "field_name": "tags",
        "status": "approved",
        "evidence_id": str(snapshot_id),
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

    # prod: font_sources, fonts with target updated_at
    font_source_data = {
        "font_id": str(target_font_id),
        "provider": "noonnu",
        "provider_record_id": "613",
    }

    target_font_data = {
        "id": str(target_font_id),
        "source_key": {"provider": "noonnu", "provider_record_id": "613"},
        "slug": "흰꼬리수리",
        "name_ko": "흰꼬리수리",
        "name_en": None,
        "foundry": None,
        "official_url": "https://updated.example/link",
        "status": "published",
        "updated_at": "2026-07-23T12:00:00+00:00",  # target 값
        "download_url": None,
        "download_status": "pending",
        "download_evidence_id": None,
        "license_status": "pending",
        "license_verified": True,
    }

    # dev schema: findings, snapshots, fonts는 여기서 조회 안함
    dev_findings_response = _query([finding_data])
    dev_snapshots_response = _query([snapshot_data])

    dev_schema = MagicMock()
    dev_schema.table.side_effect = [dev_findings_response, dev_snapshots_response]
    dev_client = MagicMock()
    dev_client.schema.return_value = dev_schema

    dev_store = SupabaseAuditStore(dev_client)

    # prod schema: font_sources, fonts
    prod_font_sources_response = _query([font_source_data])
    prod_fonts_response = _query([target_font_data])

    prod_schema = MagicMock()
    prod_schema.table.side_effect = [prod_font_sources_response, prod_fonts_response]
    prod_client = MagicMock()
    prod_client.schema.return_value = prod_schema

    target_store = SupabaseAuditStore(prod_client)

    # 호출: target_store 지정
    results = dev_store.get_current_fonts_with_snapshots(run_id, target_store=target_store)

    assert len(results) == 1
    font = results[0]
    assert font["id"] == str(target_font_id)
    assert font["updated_at"] == "2026-07-23T12:00:00+00:00"  # prod 값
    assert font["source_key"] == {"provider": "noonnu", "provider_record_id": "613"}
    assert "evidence_snapshots" in font
    assert len(font["evidence_snapshots"]) == 1


def test_get_current_fonts_with_snapshots_font_sources_no_match() -> None:
    """font_sources 매칭 0건 → RuntimeError."""
    run_id = UUID("00000000-0000-0000-0000-000000000909")
    font_id = UUID("00000000-0000-0000-0000-000000000810")
    snapshot_id = UUID("00000000-0000-0000-0000-000000000813")

    # dev: approved finding, snapshot
    finding_data = {
        "id": str(uuid4()),
        "run_id": str(run_id),
        "font_id": str(font_id),
        "field_name": "tags",
        "status": "approved",
        "evidence_id": str(snapshot_id),
    }

    snapshot_data = {
        "id": str(snapshot_id),
        "run_id": str(run_id),
        "font_id": str(font_id),
        "provider": "noonnu",
        "provider_record_id": "999",  # prod에 없는 id
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

    # dev schema
    dev_findings_response = _query([finding_data])
    dev_snapshots_response = _query([snapshot_data])

    dev_schema = MagicMock()
    dev_schema.table.side_effect = [dev_findings_response, dev_snapshots_response]
    dev_client = MagicMock()
    dev_client.schema.return_value = dev_schema

    dev_store = SupabaseAuditStore(dev_client)

    # prod schema: font_sources 조회 결과 0건
    prod_empty_response = _query([])

    prod_schema = MagicMock()
    prod_schema.table.return_value = prod_empty_response
    prod_client = MagicMock()
    prod_client.schema.return_value = prod_schema

    target_store = SupabaseAuditStore(prod_client)

    # 호출: RuntimeError 발생
    with pytest.raises(RuntimeError, match="font_sources 매칭 실패"):
        dev_store.get_current_fonts_with_snapshots(run_id, target_store=target_store)


def test_get_current_fonts_with_snapshots_chunked_query() -> None:
    """N+1 제거: 2개 provider 그룹이 1회 청크 쿼리로 처리됨."""
    run_id = UUID("00000000-0000-0000-0000-000000000909")
    font_id_1 = UUID("00000000-0000-0000-0000-000000000810")
    font_id_2 = UUID("00000000-0000-0000-0000-000000000811")
    snapshot_id_1 = UUID("00000000-0000-0000-0000-000000000813")
    snapshot_id_2 = UUID("00000000-0000-0000-0000-000000000814")

    # dev: 2개 approved findings, 2개 snapshots (다른 provider)
    finding_1 = {
        "id": str(uuid4()),
        "run_id": str(run_id),
        "font_id": str(font_id_1),
        "field_name": "tags",
        "status": "approved",
        "evidence_id": str(snapshot_id_1),
    }
    finding_2 = {
        "id": str(uuid4()),
        "run_id": str(run_id),
        "font_id": str(font_id_2),
        "field_name": "tags",
        "status": "approved",
        "evidence_id": str(snapshot_id_2),
    }

    snapshot_1 = {
        "id": str(snapshot_id_1),
        "run_id": str(run_id),
        "font_id": str(font_id_1),
        "provider": "noonnu",
        "provider_record_id": "100",
        "source_kind": "official",
        "document_kind": "download",
        "request_url": "https://clova.ai/font1.zip",
        "final_url": "https://clova.ai/font1.zip",
        "http_status": 200,
        "raw_text": "text1",
        "raw_sha256": "a" * 64,
        "normalized_sha256": "b" * 64,
        "extracted": {"download_url": "https://clova.ai/font1.zip"},
        "evidence_locations": {"download_url": "a.download"},
        "extraction_rule_id": "official-download-v1",
        "parser_version": "audit-v1",
        "collected_at": "2026-07-22T08:00:00+00:00",
    }

    snapshot_2 = {
        "id": str(snapshot_id_2),
        "run_id": str(run_id),
        "font_id": str(font_id_2),
        "provider": "google-fonts",
        "provider_record_id": "200",
        "source_kind": "official",
        "document_kind": "download",
        "request_url": "https://fonts.google.com/font2",
        "final_url": "https://fonts.google.com/font2",
        "http_status": 200,
        "raw_text": "text2",
        "raw_sha256": "c" * 64,
        "normalized_sha256": "d" * 64,
        "extracted": {"download_url": "https://fonts.google.com/font2"},
        "evidence_locations": {"download_url": "b.download"},
        "extraction_rule_id": "official-download-v1",
        "parser_version": "audit-v1",
        "collected_at": "2026-07-22T08:00:00+00:00",
    }

    dev_findings_response = _query([finding_1, finding_2])
    dev_snapshots_response = _query([snapshot_1, snapshot_2])

    dev_schema = MagicMock()
    dev_schema.table.side_effect = [dev_findings_response, dev_snapshots_response]
    dev_client = MagicMock()
    dev_client.schema.return_value = dev_schema

    dev_store = SupabaseAuditStore(dev_client)

    # prod schema: font_sources와 fonts 응답
    font_source_1 = {"id": str(uuid4()), "provider": "noonnu", "provider_record_id": "100", "font_id": str(font_id_1)}
    font_source_2 = {"id": str(uuid4()), "provider": "google-fonts", "provider_record_id": "200", "font_id": str(font_id_2)}
    font_1 = {"id": str(font_id_1), "family_name": "Font1"}
    font_2 = {"id": str(font_id_2), "family_name": "Font2"}

    # font_sources 응답: 두 provider 모두 포함 (각 .eq().in_() 호출마다 모든 결과 반환)
    all_font_sources_response = _query([font_source_1, font_source_2])
    fonts_response = _query([font_1, font_2])

    prod_schema = MagicMock()

    # table 호출 시마다 다른 mock 반환
    def table_side_effect(table_name):
        if table_name == "font_sources":
            mock_obj = MagicMock()
            # 각 .eq().in_() 체인이 호출될 때마다 모든 결과 반환
            mock_obj.select.return_value.eq.return_value.in_.return_value = all_font_sources_response
            return mock_obj
        elif table_name == "fonts":
            mock_obj = MagicMock()
            mock_obj.select.return_value.in_.return_value = fonts_response
            return mock_obj
        else:
            raise ValueError(f"Unexpected table: {table_name}")

    prod_schema.table.side_effect = table_side_effect

    prod_client = MagicMock()
    prod_client.schema.return_value = prod_schema

    target_store = SupabaseAuditStore(prod_client)

    # 호출
    result = dev_store.get_current_fonts_with_snapshots(run_id, target_store=target_store)

    # 검증: N+1 제거 확인
    # - 2개 provider가 있으므로 font_sources table 호출은 2회 (provider별 1회씩)
    # - 각 provider별로 in_() 청크 쿼리로 모든 record_id를 한 번에 처리 (개별 쿼리 아님)
    font_sources_calls = [
        call for call in prod_schema.table.call_args_list if call[0][0] == "font_sources"
    ]
    assert len(font_sources_calls) == 2, f"Expected 2 font_sources calls (per provider), got {len(font_sources_calls)}"

    # 결과 검증
    assert len(result) == 2
    assert all(isinstance(font, dict) for font in result)
