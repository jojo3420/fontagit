"""metadata findings 무인 승인 CLI의 핵심 회귀 테스트."""

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fontagit_pipeline.__main__ import main_audit_review


def _mock_run() -> dict:
    """audit_review 테스트용 mock run 객체."""
    return {
        "id": str(uuid4()),
        "stage": "metadata",
        "status": "running",
    }


def _mock_finding(run_id: str, field_name: str = "tags") -> dict:
    """metadata findings 구조를 따르는 mock."""
    return {
        "id": str(uuid4()),
        "run_id": run_id,
        "font_id": str(uuid4()),
        "field_name": field_name,
        "stage": "metadata",
        "status": "needs_review",
        "before_value": None,
        "proposed_value": ["tag1", "tag2"],
        "confidence": "high",
        "review_reason": "test finding",
    }


def test_audit_review_auto_approve_all_findings_success() -> None:
    """정상: 모든 findings를 승인하면 exit 0."""
    run = _mock_run()
    findings = [_mock_finding(run["id"], "tags"), _mock_finding(run["id"], "weights")]

    args = argparse.Namespace(
        action="auto-approve",
        run_id=run["id"],
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store.get_needs_review_findings.return_value = findings
        mock_store.approve_finding.return_value = None  # 성공 시 None 반환
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 0, f"Expected exit code 0 but got {result}"
        mock_store.get_run.assert_called_once()
        mock_store.get_needs_review_findings.assert_called_once()
        # 각 finding에 대해 approve_finding이 호출되어야 함
        assert mock_store.approve_finding.call_count == 2


def test_audit_review_no_needs_review_findings() -> None:
    """정상: needs_review 대상이 0건이면 경고하고 exit 0."""
    run = _mock_run()
    args = argparse.Namespace(
        action="auto-approve",
        run_id=run["id"],
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store.get_needs_review_findings.return_value = []  # 빈 목록
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 0, f"Expected exit code 0 but got {result}"
        mock_store.approve_finding.assert_not_called()


def test_audit_review_partial_approval_failure() -> None:
    """비정상: 일부 findings 승인이 실패하면 exit 3."""
    run = _mock_run()
    findings = [
        _mock_finding(run["id"], "tags"),
        _mock_finding(run["id"], "weights"),
    ]

    args = argparse.Namespace(
        action="auto-approve",
        run_id=run["id"],
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store.get_needs_review_findings.return_value = findings

        # 첫 번째 호출은 성공, 두 번째는 실패
        mock_store.approve_finding.side_effect = [
            None,
            ValueError("동시성 충돌"),
        ]
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 3, f"Expected exit code 3 but got {result}"
        assert mock_store.approve_finding.call_count == 2  # 계속 진행해야 함


def test_audit_review_invalid_run_id() -> None:
    """비정상: invalid run-id 문자열("not-a-uuid")은 UUID 파싱에서 실패하여 exit 1."""
    args = argparse.Namespace(
        action="auto-approve",
        run_id="not-a-uuid",  # 유효하지 않은 UUID
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials"):
        result = main_audit_review(args)

        assert result == 1, f"Expected exit code 1 but got {result}"


def test_audit_review_runtime_error_mixed_with_success() -> None:
    """비정상: approve_finding이 RuntimeError를 던지는 finding이 있어도 루프가 계속되고 exit 3."""
    run = _mock_run()
    findings = [
        _mock_finding(run["id"], "tags"),
        _mock_finding(run["id"], "weights"),
        _mock_finding(run["id"], "tags"),
    ]

    args = argparse.Namespace(
        action="auto-approve",
        run_id=run["id"],
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store.get_needs_review_findings.return_value = findings

        # 첫 번째: 성공, 두 번째: RuntimeError, 세 번째: 성공
        mock_store.approve_finding.side_effect = [
            None,
            RuntimeError("DB 연결 오류"),
            None,
        ]
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 3, f"Expected exit code 3 but got {result}"
        # 루프가 계속되었으므로 모든 findings에 대해 approve_finding이 호출됨
        assert mock_store.approve_finding.call_count == 3
        # 실패는 1건, 성공은 2건
        assert len([f for f in findings]) == 3  # 모든 finding 처리 검증
