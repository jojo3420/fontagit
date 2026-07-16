from unittest.mock import call, patch, MagicMock

import pytest

from fontagit_pipeline.models import FontRecord
from fontagit_pipeline.uploader import (
    build_font_row,
    build_alias_rows,
    normalize_alias,
    upload_tier_a_snapshot,
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


def test_upload_records_calls_rpc_per_font():
    """upload_records가 RPC upsert_font를 폰트당 1회 호출한다."""
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        mock_schema = mock_client.schema.return_value

        n = upload_records([_rec()], "https://x.supabase.co", "sb_secret")

        assert n == 1
        mock_client.schema.assert_called_once_with("fontagit")
        mock_schema.rpc.assert_called_once()
        name, payload = mock_schema.rpc.call_args.args
        assert name == "upsert_font"
        assert payload["p_font"]["slug"] == "noto-sans-kr"
        assert "id" not in payload["p_font"]
        assert payload["p_aliases"][0]["alias_norm"] == "notosanskr"
        assert "font_id" not in payload["p_aliases"][0]
        mock_schema.rpc.return_value.execute.assert_called_once()


def test_upload_records_raises_on_rpc_failure():
    """RPC 실패 시 예외가 전파된다."""
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        mock_schema = mock_client.schema.return_value
        mock_schema.rpc.return_value.execute.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            upload_records([_rec()], "https://x.supabase.co", "sb_secret")


def test_normalize_alias_converts_nfd_to_nfc():
    import unicodedata

    nfd = unicodedata.normalize("NFD", "본 고딕")  # 자모 분리형
    assert normalize_alias(nfd) == "본고딕"
    assert normalize_alias(nfd) == normalize_alias("본 고딕")  # NFC/NFD 입력 동치


def _snapshot_records(count: int = 100) -> list[FontRecord]:
    return [
        _rec().model_copy(
            update={
                "slug": f"font-{i:03d}",
                "name_en": f"Font {i:03d}",
                "aliases": [f"Font {i:03d}"],
            }
        )
        for i in range(count)
    ]


def test_upload_tier_a_snapshot_syncs_only_after_all_upserts():
    records = _snapshot_records()
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        schema = mock_create.return_value.schema.return_value
        schema.rpc.return_value.execute.return_value.data = 1

        result = upload_tier_a_snapshot(records, "https://x.supabase.co", "sb_secret")

        assert result == (100, 1)
        names = [rpc_call.args[0] for rpc_call in schema.rpc.call_args_list]
        assert names == ["upsert_font"] * 100 + ["sync_tier_a_fonts"]
        assert schema.rpc.call_args_list[-1] == call(
            "sync_tier_a_fonts",
            {"p_active_slugs": [f"font-{i:03d}" for i in range(100)]},
        )


def test_upload_tier_a_snapshot_skips_sync_after_upsert_failure():
    records = _snapshot_records()
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        schema = mock_create.return_value.schema.return_value
        schema.rpc.return_value.execute.side_effect = [None, RuntimeError("boom")]

        with pytest.raises(RuntimeError, match="boom"):
            upload_tier_a_snapshot(records, "https://x.supabase.co", "sb_secret")

        names = [rpc_call.args[0] for rpc_call in schema.rpc.call_args_list]
        assert names == ["upsert_font", "upsert_font"]


def test_upload_tier_a_snapshot_rejects_fewer_than_100_before_connecting():
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        with pytest.raises(ValueError, match="100종 미만"):
            upload_tier_a_snapshot(
                _snapshot_records(99), "https://x.supabase.co", "sb_secret"
            )

        mock_create.assert_not_called()
