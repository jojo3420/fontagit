"""눈누 finding 검수 경계의 핵심 회귀 테스트."""

import pytest

from fontagit_pipeline import noonnu_review as nr


def _finding_schema(mocker, *, status: str = "proposed"):
    tables = {
        "font_audit_findings": mocker.MagicMock(),
        "fonts": mocker.MagicMock(),
        "license_proposals": mocker.MagicMock(),
    }
    schema = mocker.MagicMock()
    schema.table.side_effect = tables.__getitem__
    finding_id = "30000000-0000-0000-0000-000000000008"
    finding = tables["font_audit_findings"]
    finding.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "id": finding_id,
        "status": status,
    }
    finding.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": finding_id}
    ]
    return schema, tables, finding_id


def test_approve_updates_only_the_exact_proposed_finding(mocker) -> None:
    """승인은 지정한 finding 하나의 검수 메타데이터만 바꾼다."""
    schema, tables, finding_id = _finding_schema(mocker)

    nr.approve(schema, finding_id, reviewed_by="operator@example.com")

    finding = tables["font_audit_findings"]
    payload = finding.update.call_args.args[0]
    assert payload["status"] == "approved"
    assert payload["reviewed_by"] == "operator@example.com"
    assert payload["reviewed_at"]
    finding.update.return_value.eq.assert_called_once_with("id", finding_id)
    finding.update.return_value.eq.return_value.eq.assert_called_once_with(
        "status", "proposed"
    )
    tables["fonts"].update.assert_not_called()
    tables["license_proposals"].update.assert_not_called()


def test_approve_rejects_applied_finding_without_writing(mocker) -> None:
    """이미 적용된 finding은 다시 승인하지 않는다."""
    schema, tables, finding_id = _finding_schema(mocker, status="applied")

    with pytest.raises(ValueError, match="proposed"):
        nr.approve(schema, finding_id, reviewed_by="operator@example.com")

    tables["font_audit_findings"].update.assert_not_called()


def test_approve_requires_reviewer_identity(mocker) -> None:
    """검수자 식별자 없이는 승인할 수 없다."""
    schema, tables, finding_id = _finding_schema(mocker)

    with pytest.raises(ValueError, match="reviewed_by"):
        nr.approve(schema, finding_id, reviewed_by="  ")

    tables["font_audit_findings"].select.assert_not_called()
