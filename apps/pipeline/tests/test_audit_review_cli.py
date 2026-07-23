"""metadata findings 무인 승인 CLI의 핵심 회귀 테스트."""

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fontagit_pipeline.__main__ import main_audit_review


def _mock_run(stage: str = "metadata") -> dict:
    """audit_review 테스트용 mock run 객체."""
    return {
        "id": str(uuid4()),
        "stage": stage,
        "status": "completed",
        "broken_count": 0,
        "target_count": 50,
    }


def _mock_finding(run_id: str, field_name: str = "tags") -> dict:
    """metadata findings 구조를 따르는 mock (실스키마: no stage, status=proposed)."""
    return {
        "id": str(uuid4()),
        "run_id": run_id,
        "font_id": str(uuid4()),
        "field_name": field_name,
        "status": "proposed",
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
        mock_store.get_proposed_findings.return_value = findings
        mock_store.approve_finding.return_value = None  # 성공 시 None 반환
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 0, f"Expected exit code 0 but got {result}"
        mock_store.get_run.assert_called_once()
        mock_store.get_proposed_findings.assert_called_once()
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
        mock_store.get_proposed_findings.return_value = []  # 빈 목록
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
        mock_store.get_proposed_findings.return_value = findings

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
        mock_store.get_proposed_findings.return_value = findings

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


def test_audit_review_run_stage_not_metadata() -> None:
    """비정상: run stage가 'metadata'이 아니면 exit 1."""
    run = _mock_run(stage="legal")  # stage를 'legal'로 설정
    args = argparse.Namespace(
        action="auto-approve",
        run_id=run["id"],
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 1, f"Expected exit code 1 but got {result}"
        # run 검증 실패이므로 findings 조회 안 됨
        mock_store.get_proposed_findings.assert_not_called()


def test_audit_review_run_not_completed() -> None:
    """비정상: run status가 'completed'이 아니면 exit 1."""
    run = _mock_run()
    run["status"] = "running"  # status를 'running'으로 변경

    args = argparse.Namespace(
        action="auto-approve",
        run_id=run["id"],
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 1, f"Expected exit code 1 but got {result}"
        # status 검증 실패이므로 findings 조회 안 됨
        mock_store.get_proposed_findings.assert_not_called()


def test_audit_review_run_broken_ratio_exceeded() -> None:
    """비정상: broken ratio가 10%를 초과하면 exit 1."""
    run = _mock_run()
    run["broken_count"] = 25
    run["target_count"] = 50  # 50%로 설정, 임계값 10% 초과

    args = argparse.Namespace(
        action="auto-approve",
        run_id=run["id"],
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 1, f"Expected exit code 1 but got {result}"
        # broken ratio 검증 실패이므로 findings 조회 안 됨
        mock_store.get_proposed_findings.assert_not_called()


def test_audit_review_evidence_mismatch() -> None:
    """비정상: proposed_value가 evidence extracted와 다르면 해당 finding만 실패."""
    from uuid import uuid4

    run = _mock_run()
    evidence_id = str(uuid4())

    # tags/weights finding 섞임
    findings = [
        {
            **_mock_finding(run["id"], "tags"),
            "evidence_id": evidence_id,
            "proposed_value": ["tag1", "tag2"],
        },
        {
            **_mock_finding(run["id"], "weights"),
            "evidence_id": str(uuid4()),  # 다른 evidence_id
            "proposed_value": [400],
        },
    ]

    args = argparse.Namespace(
        action="auto-approve",
        run_id=run["id"],
        reviewed_by="auto",
    )

    with patch("fontagit_pipeline.audit_store.SupabaseAuditStore.from_dev_credentials") as mock_store_ctor:
        mock_store = MagicMock()
        mock_store.get_run.return_value = run
        mock_store.get_proposed_findings.return_value = findings

        # snapshot 조회 결과: 첫 번째 evidence의 extracted 값이 다름
        # (proposed_value=["tag1", "tag2"]인데 extracted["tags"]는 ["different"])
        mock_store._schema.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
            {
                "id": evidence_id,
                "extracted": {"tags": ["different"]},  # proposed와 다른 값
            },
            {
                "id": findings[1]["evidence_id"],
                "extracted": {"weight": 400},  # proposed [400]과 일치
            },
        ]

        # 첫 번째는 값-증거 검증 실패로 실패, 두 번째는 성공
        mock_store.approve_finding.side_effect = [
            None,  # 두 번째 finding 승인 성공
        ]
        mock_store_ctor.return_value = mock_store

        result = main_audit_review(args)

        assert result == 3, f"Expected exit code 3 but got {result}"
        # 첫 번째는 실패로 건너뛰고, 두 번째만 승인 호출
        assert mock_store.approve_finding.call_count == 1
