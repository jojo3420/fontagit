import json
import logging

import pytest

from fontagit_pipeline.models import GoogleFontRaw, FontRecord
from fontagit_pipeline.transform import (
    build_aliases,
    build_official_url,
    normalize_variants,
    filter_korean,
    select_latin_top,
    merge_dedup,
    to_record,
    build_records,
)


def test_normalize_variants_maps_regular_and_italic():
    assert normalize_variants(["regular", "italic", "700", "700italic"]) == [
        "400",
        "400 italic",
        "700",
        "700 italic",
    ]


def test_build_official_url_replaces_spaces_with_plus():
    assert (
        build_official_url("Noto Sans KR")
        == "https://fonts.google.com/specimen/Noto+Sans+KR"
    )


def test_build_official_url_rejects_non_ascii():
    with pytest.raises(ValueError):
        build_official_url("나눔고딕")


def test_build_aliases_dedupes_exact_strings_keeping_order():
    assert build_aliases("Noto Sans KR") == [
        "Noto Sans KR",
        "noto sans kr",
        "notosanskr",
        "noto sans kr ttf",
    ]


@pytest.fixture
def webfonts_sample() -> list[GoogleFontRaw]:
    """load webfonts_sample.json and convert to GoogleFontRaw."""
    import pathlib
    fixture_path = pathlib.Path(__file__).parent / "fixtures" / "webfonts_sample.json"
    with open(fixture_path) as f:
        data = json.load(f)
    return [GoogleFontRaw(**item) for item in data]


def test_filter_korean_keeps_fonts_with_korean_subset_in_order(webfonts_sample):
    result = filter_korean(webfonts_sample)
    families = [font.family for font in result]
    assert "Noto Sans KR" in families
    assert families == ["Noto Sans KR"]


def test_select_latin_top_keeps_latin_fonts_up_to_limit(webfonts_sample):
    result = select_latin_top(webfonts_sample, limit=100)
    families = [font.family for font in result]
    assert "Roboto" in families
    assert len(families) <= 100


def test_merge_dedup_korean_first_then_latin_not_in_korean(webfonts_sample):
    korean = filter_korean(webfonts_sample)
    latin = select_latin_top(webfonts_sample, limit=100)
    result = merge_dedup(korean, latin)
    families = [font.family for font in result]
    assert families == ["Noto Sans KR", "Roboto"]
    assert len(families) == len(set(families))


def test_to_record_creates_record_with_license_none_and_verified_false(webfonts_sample):
    raw = webfonts_sample[0]
    rec = to_record(raw)
    assert rec.name_en == "Noto Sans KR"
    assert rec.license is None
    assert rec.license_verified is False


def test_to_record_uses_build_official_url_and_normalize_variants(webfonts_sample):
    raw = webfonts_sample[1]
    rec = to_record(raw)
    assert rec.official_url == "https://fonts.google.com/specimen/Roboto"
    assert rec.variants == ["400", "700"]


def test_build_records_merges_dedup_and_converts(webfonts_sample):
    records = build_records(webfonts_sample, latin_limit=100)
    families = [rec.name_en for rec in records]
    assert families == ["Noto Sans KR", "Roboto"]
    assert len(families) == len(set(families))
    for rec in records:
        assert rec.license is None
        assert rec.license_verified is False


def test_build_records_skips_non_ascii_family_with_warning(caplog):
    """비ASCII family는 build_official_url의 ValueError에 의해 건너뛰고 로그한다."""
    caplog.set_level(logging.WARNING)
    fonts = [
        GoogleFontRaw(
            family="Noto Sans KR",
            variants=["regular", "700"],
            subsets=["korean", "latin"],
            version="v1.0",
            lastModified="2024-09-01",
            files={"regular": "https://x/noto.ttf", "700": "https://x/noto700.ttf"},
            category="sans-serif",
        ),
        GoogleFontRaw(
            family="나눔고딕",
            variants=["regular", "700"],
            subsets=["korean"],
            version="v1.0",
            lastModified="2024-09-01",
            files={"regular": "https://x/nanum.ttf", "700": "https://x/nanum700.ttf"},
            category="sans-serif",
        ),
    ]
    records = build_records(fonts, latin_limit=100)
    families = [rec.name_en for rec in records]
    assert "Noto Sans KR" in families
    assert "나눔고딕" not in families
    assert len(records) == 1
    assert any("나눔고딕" in record.message for record in caplog.records if record.levelno == logging.WARNING)
