from fontagit_pipeline.models import FontRecord
from fontagit_pipeline.uploader import build_font_row, build_alias_rows, normalize_alias


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
    rows = build_alias_rows("fid-1", ["Noto Sans", "noto sans"])  # 정규화 동일
    assert len(rows) == 1
    assert rows[0]["font_id"] == "fid-1"
    assert rows[0]["alias_norm"] == "notosans"
