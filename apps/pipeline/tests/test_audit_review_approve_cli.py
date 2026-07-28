"""사람 검수 findings 배치 승인 CLI(`font-audit-review approve`)의 핵심 회귀 테스트.

이슈 #128 - 감사 findings 사람 승인 경로. auto-approve(evidence-values 대조 필수)와
달리 이 액션은 사람이 이미 findings 내용을 확인했다는 전제로 MANUAL_APPROVABLE_FIELDS에
속하는 proposed findings만 골라 approve_finding을 호출한다.
"""

import argparse
import logging
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

from fontagit_pipeline.__main__ import main_audit_review


def _approve_args(
    *,
    run_id: str,
    reviewed_by: str | None = "reviewer",
    field: list[str] | None = None,
    dry_run: bool = False,
) -> argparse.Namespace:
    """approve 액션용 argparse.Namespace를 만든다(CLI 실제 인자 구조와 동일)."""
    return argparse.Namespace(
        action="approve",
        run_id=run_id,
        reviewed_by=reviewed_by,
        field=field,
        dry_run=dry_run,
    )


def _mock_finding(run_id: str, field_name: str) -> dict:
    return {
        "id": str(uuid4()),
        "run_id": run_id,
        "font_id": str(uuid4()),
        "field_name": field_name,
        "status": "proposed",
        "before_value": None,
        "proposed_value": "some-value",
        "confidence": "reference",
        "review_reason": "test finding",
        "auto_applicable": False,
        "evidence_id": str(uuid4()),
    }


def test_approve_default_fields_approves_all_manual_approvable_findings() -> None:
    """--field 생략 시 MANUAL_APPROVABLE_FIELDS 전체를 대상으로 조회하고 전건 승인한다."""
    run_id = str(uuid4())
    findings = [
        _mock_finding(run_id, "foundry"),
        _mock_finding(run_id, "download_url"),
    ]
    args = _approve_args(run_id=run_id)

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_store.get_proposed_findings_by_fields.return_value = findings
        mock_store.approve_finding.return_value = None
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 0
        called_run_id, called_fields = mock_store.get_proposed_findings_by_fields.call_args[0]
        assert called_run_id == UUID(run_id)
        assert set(called_fields) == {
            "tags",
            "weights",
            "foundry",
            "foundry_url",
            "download_url",
            "download_source_kind",
            "license_source_url",
        }
        assert mock_store.approve_finding.call_count == 2
        for call in mock_store.approve_finding.call_args_list:
            assert call.kwargs.get("reviewed_by") == "reviewer"


def test_approve_narrows_to_requested_field() -> None:
    """--field로 지정하면 그 필드만 조회 대상이 된다."""
    run_id = str(uuid4())
    findings = [_mock_finding(run_id, "foundry")]
    args = _approve_args(run_id=run_id, field=["foundry"])

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_store.get_proposed_findings_by_fields.return_value = findings
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 0
        called_run_id, called_fields = mock_store.get_proposed_findings_by_fields.call_args[0]
        assert called_fields == ["foundry"]
        assert mock_store.approve_finding.call_count == 1


def test_approve_rejects_legal_field_via_field_flag() -> None:
    """--field로 legal 필드를 넘기면 exit 1이고 DB 조회 자체가 일어나지 않는다."""
    run_id = str(uuid4())
    args = _approve_args(run_id=run_id, field=["allow_commercial"])

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 1
        mock_store.get_proposed_findings_by_fields.assert_not_called()
        mock_store.approve_finding.assert_not_called()


def test_approve_rejects_mixed_legal_and_allowed_fields() -> None:
    """허용 필드와 legal 필드를 함께 넘겨도(부분 오염) 전체 요청이 거부된다."""
    run_id = str(uuid4())
    args = _approve_args(run_id=run_id, field=["foundry", "license_verified"])

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 1
        mock_store.get_proposed_findings_by_fields.assert_not_called()


def test_approve_missing_reviewed_by_returns_1() -> None:
    """--reviewed-by 누락이면 exit 1이고 DB 조회가 일어나지 않는다."""
    run_id = str(uuid4())
    args = _approve_args(run_id=run_id, reviewed_by=None)

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 1
        mock_store.get_proposed_findings_by_fields.assert_not_called()


def test_approve_invalid_run_id_returns_1() -> None:
    """invalid run-id 문자열은 UUID 파싱 실패로 exit 1."""
    args = _approve_args(run_id="not-a-uuid")

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials"):
        result = main_audit_review(args)

        assert result == 1


def test_approve_dry_run_does_not_call_approve_finding() -> None:
    """--dry-run이면 대상 건수만 로깅하고 approve_finding은 호출하지 않는다."""
    run_id = str(uuid4())
    findings = [_mock_finding(run_id, "foundry"), _mock_finding(run_id, "download_url")]
    args = _approve_args(run_id=run_id, dry_run=True)

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_store.get_proposed_findings_by_fields.return_value = findings
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 0
        mock_store.approve_finding.assert_not_called()


def test_approve_no_proposed_findings_returns_0() -> None:
    """승인 대상이 0건이면 exit 0이고 approve_finding은 호출되지 않는다."""
    run_id = str(uuid4())
    args = _approve_args(run_id=run_id)

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_store.get_proposed_findings_by_fields.return_value = []
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 0
        mock_store.approve_finding.assert_not_called()


def test_approve_partial_failure_returns_3_and_continues() -> None:
    """일부 finding 승인이 실패해도 나머지는 계속 처리하고 exit 3."""
    run_id = str(uuid4())
    findings = [
        _mock_finding(run_id, "foundry"),
        _mock_finding(run_id, "download_url"),
        _mock_finding(run_id, "license_source_url"),
    ]
    args = _approve_args(run_id=run_id)

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_store.get_proposed_findings_by_fields.return_value = findings
        mock_store.approve_finding.side_effect = [None, ValueError("동시성 충돌"), None]
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 3
        assert mock_store.approve_finding.call_count == 3


def test_approve_skips_finding_not_in_manual_approvable_fields_defensively() -> None:
    """store가 방어선을 뚫고 legal 필드 finding을 반환해도(레이스/버그 가정) 승인하지 않고 건너뛴다."""
    run_id = str(uuid4())
    tampered_finding = _mock_finding(run_id, "allow_commercial")
    args = _approve_args(run_id=run_id)

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
        mock_store = MagicMock()
        mock_store.get_proposed_findings_by_fields.return_value = [tampered_finding]
        mock_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 0
        mock_store.approve_finding.assert_not_called()


def test_approve_success_log_reports_counts(caplog) -> None:  # type: ignore[no-untyped-def]
    """정상: 승인 결과 로그에 승인/건너뜀/실패 건수가 명확히 남는다."""
    run_id = str(uuid4())
    findings = [_mock_finding(run_id, "foundry"), _mock_finding(run_id, "download_url")]
    args = _approve_args(run_id=run_id)

    with caplog.at_level(logging.INFO):
        with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_ctor:
            mock_store = MagicMock()
            mock_store.get_proposed_findings_by_fields.return_value = findings
            mock_ctor.return_value = mock_store

            result = main_audit_review(args)

            assert result == 0
            summary_logs = [rec for rec in caplog.records if "승인=" in rec.message]
            assert len(summary_logs) > 0
            assert "승인=2" in summary_logs[0].message
            assert "건너뜀=0" in summary_logs[0].message
            assert "실패=0" in summary_logs[0].message
