from unittest.mock import MagicMock

import pytest

from fontagit_pipeline.models import FontRecord
from fontagit_pipeline.uploader import (
    build_font_row,
    build_alias_rows,
    normalize_alias,
    upload_records,
)


def _rec():
    return FontRecord(
        slug="noto-sans-kr", name_en="Noto Sans KR", category_ko="고딕",
        category_google="sans-serif", subsets=["korean"], variants=["400"],
        weights=[400], official_url="https://x", aliases=["Noto Sans KR", "노토 산스"],
        version="v1", last_modified="2024-01-01",
        is_commercial_free=True, license_type="OFL", license_verified=True,
        status="published",
    )


def test_build_font_row():
    row = build_font_row(_rec())
    assert row["slug"] == "noto-sans-kr"
    assert row["status"] == "published"
    assert row["weights"] == [400]
    assert "id" not in row


def test_normalize_alias():
    assert normalize_alias("Noto Sans KR") == "notosanskr"
    assert normalize_alias("노토 산스") == "노토산스"


def test_build_alias_rows_dedup_norm():
    """정규화 후 중복인 별칭은 첫 원본만 유지."""
    rows = build_alias_rows(["Noto Sans", "noto sans"])  # 정규화 동일
    assert len(rows) == 1
    assert rows[0]["alias"] == "Noto Sans"  # 원본
    assert rows[0]["alias_norm"] == "notosans"
    assert "font_id" not in rows[0]


def test_build_alias_rows_empty_alias():
    """빈값/공백만인 별칭은 필터 제외."""
    rows = build_alias_rows(["  ", ""])  # 빈값/공백만
    assert len(rows) == 0


def test_upload_records_rpc(monkeypatch: pytest.MonkeyPatch):
    """upload_records가 RPC upsert_font를 폰트당 1회 호출한다."""
    mock_rpc = MagicMock()
    mock_execute = MagicMock()
    mock_rpc.execute.return_value = mock_execute

    mock_table = MagicMock()
    mock_table.rpc.return_value = mock_rpc

    mock_schema = MagicMock()
    mock_schema.return_value = mock_table

    mock_client = MagicMock()
    mock_client.schema.return_value = mock_table

    monkeypatch.setattr("fontagit_pipeline.uploader.create_client", lambda url, key: mock_client)

    records = [_rec(), _rec()]
    count = upload_records(records, "http://test", "test_key")

    assert count == 2
    assert mock_table.rpc.call_count == 2
    mock_table.rpc.assert_called_with(
        "upsert_font",
        {
            "p_font": build_font_row(_rec()),
            "p_aliases": build_alias_rows(_rec().aliases),
        },
    )
