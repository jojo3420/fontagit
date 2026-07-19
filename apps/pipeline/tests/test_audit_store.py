"""승인 legal 근거를 metadata 입력으로 여는 저장소 계약."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

from fontagit_pipeline.audit_store import SupabaseAuditStore


def _query(data: list[dict[str, object]]) -> MagicMock:
    query = MagicMock()
    query.select.return_value = query
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
