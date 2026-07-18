"""눈누 draft 안전 RPC 경계 테스트."""

import json
from pathlib import Path

import pytest

from fontagit_pipeline import noonnu_import as ni


def test_rpc_failure_never_falls_back_to_direct_fonts_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker
) -> None:
    """안전 RPC가 실패하면 slug 기반 직접 update/insert 대신 전체 중단한다."""
    seed_path = tmp_path / "seed.json"
    seed_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-07-18T00:00:00Z",
                "record_count": 1,
                "records": [
                    {
                        "name_ko": "테스트체",
                        "name_en": "Test Font",
                        "maker": "테스트 제작사",
                        "official_url": "https://maker.example/font",
                        "source_page": "https://noonnu.cc/font_page/9999",
                        "collected_at": "2026-07-18T00:00:00Z",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    schema = mocker.MagicMock()
    schema.rpc.return_value.execute.side_effect = RuntimeError("RPC unavailable")
    client = mocker.MagicMock()
    client.schema.return_value = schema
    monkeypatch.setattr(ni, "create_client", lambda *_: client)

    with pytest.raises(ni.NoonnuImportError, match="upsert_noonnu_draft"):
        ni.import_noonnu_seeds(seed_path, "https://dev.example", "dev-key")

    schema.table.assert_not_called()
