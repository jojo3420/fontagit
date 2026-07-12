import pytest

from fontagit_pipeline.transform import (
    build_aliases,
    build_official_url,
    normalize_variants,
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


def test_build_aliases_dedupes_case_insensitively_keeping_order():
    assert build_aliases("Noto Sans KR") == [
        "Noto Sans KR",
        "noto sans kr",
        "notosanskr",
        "noto sans kr ttf",
    ]
