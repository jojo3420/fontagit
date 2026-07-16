import json
import logging

import pytest

from fontagit_pipeline.models import GoogleFontRaw
from fontagit_pipeline.transform import (
    build_aliases,
    build_official_url,
    normalize_variants,
    filter_korean,
    select_latin_top,
    merge_dedup,
    to_record,
    build_records,
    map_category_ko,
    build_slug,
    extract_weights,
)


def test_normalize_variants_maps_regular_and_italic():
    assert normalize_variants(["regular", "italic", "700", "700italic"]) == [
        "400",
        "400 italic",
        "700",
        "700 italic",
    ]


def test_normalize_variants_handles_all_italic_weights():
    """모든 italic 가중치 (100italic, 300italic, 500italic, 900italic 등)를 정규화한다."""
    variants = ["100", "100italic", "300italic", "500italic", "900italic"]
    result = normalize_variants(variants)
    assert "100" in result
    assert "100 italic" in result
    assert "300 italic" in result
    assert "500 italic" in result
    assert "900 italic" in result
    assert result == ["100", "100 italic", "300 italic", "500 italic", "900 italic"]


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


@pytest.fixture
def license_map() -> dict[str, str]:
    """라이선스 맵 테스트 픽스처(정규화 디렉토리명 키)."""
    return {
        "notosanskr": "OFL",
        "roboto": "Apache-2.0",
    }


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


def test_merge_dedup_removes_duplicates_within_korean():
    """한국어 리스트 내의 중복도 제거한다."""
    korean_dup = [
        GoogleFontRaw(
            family="Noto Sans KR",
            variants=["regular"],
            subsets=["korean"],
            version="v1",
            lastModified="2024-01-01",
            files={"regular": "https://x/noto1.ttf"},
            category="sans-serif",
        ),
        GoogleFontRaw(
            family="Noto Sans KR",  # 중복
            variants=["regular"],
            subsets=["korean"],
            version="v1",
            lastModified="2024-01-01",
            files={"regular": "https://x/noto1.ttf"},
            category="sans-serif",
        ),
    ]
    latin = [
        GoogleFontRaw(
            family="Roboto",
            variants=["regular"],
            subsets=["latin"],
            version="v1",
            lastModified="2024-01-01",
            files={"regular": "https://x/roboto.ttf"},
            category="sans-serif",
        ),
    ]
    result = merge_dedup(korean_dup, latin)
    families = [font.family for font in result]
    # 중복된 "Noto Sans KR"은 한 번만 나타나야 함
    assert families == ["Noto Sans KR", "Roboto"]
    assert len(families) == len(set(families))


def test_to_record_uses_build_official_url_and_normalize_variants(webfonts_sample, license_map):
    raw = webfonts_sample[1]
    rec = to_record(raw, license_map)
    assert rec.official_url == "https://fonts.google.com/specimen/Roboto"
    assert rec.variants == ["400", "700"]


def test_build_records_merges_dedup_and_converts(webfonts_sample, license_map):
    records = build_records(webfonts_sample, license_map, latin_limit=100)
    families = [rec.name_en for rec in records]
    assert families == ["Noto Sans KR", "Roboto"]
    assert len(families) == len(set(families))
    for rec in records:
        assert rec.license is None
        assert rec.license_verified is True
        assert rec.status == "published"


def test_build_records_skips_non_ascii_family_with_warning(caplog, license_map):
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
    records = build_records(fonts, license_map, latin_limit=100)
    families = [rec.name_en for rec in records]
    assert "Noto Sans KR" in families
    assert "나눔고딕" not in families
    assert len(records) == 1
    assert any("나눔고딕" in record.message for record in caplog.records if record.levelno == logging.WARNING)


def test_map_category_ko():
    assert map_category_ko("sans-serif") == "고딕"
    assert map_category_ko("serif") == "명조"
    assert map_category_ko("handwriting") == "손글씨"
    assert map_category_ko("display") == "장식"
    assert map_category_ko("monospace") == "고딕"


def test_build_slug():
    assert build_slug("Noto Sans KR") == "noto-sans-kr"
    assert build_slug("IBM Plex Sans") == "ibm-plex-sans"


def test_extract_weights():
    assert extract_weights(["400", "400 italic", "700"]) == [400, 700]
    assert extract_weights(["300", "300 italic", "100"]) == [100, 300]


def test_to_record_published_for_ofl():
    raw = GoogleFontRaw(
        family="Noto Sans KR", variants=["regular", "700"], subsets=["korean", "latin"],
        version="v1", lastModified="2024-01-01", files={}, category="sans-serif",
    )
    rec = to_record(raw, {"notosanskr": "OFL"})
    assert rec.slug == "noto-sans-kr"
    assert rec.category_ko == "고딕"
    assert rec.weights == [400, 700]
    assert rec.license_type == "OFL"
    assert rec.is_commercial_free is True
    assert rec.license_verified is True
    assert rec.status == "published"


def test_to_record_draft_for_unknown_license():
    raw = GoogleFontRaw(
        family="Mystery Font", variants=["regular"], subsets=["latin"],
        version="v1", lastModified="2024-01-01", files={}, category="serif",
    )
    rec = to_record(raw, {})
    assert rec.license_type is None
    assert rec.license_verified is False
    assert rec.status == "draft"
    assert rec.is_commercial_free is False


def test_build_aliases_with_korean_name():
    """name_ko가 제공되면 한글 이름과 공백 제거 버전을 추가한다."""
    result = build_aliases("Noto Sans KR", name_ko="노토 산스 KR")
    assert "Noto Sans KR" in result
    assert "noto sans kr" in result
    assert "notosanskr" in result
    assert "noto sans kr ttf" in result
    assert "노토 산스 KR" in result
    assert "노토산스KR" in result
    # 중복 제거 확인 (name_ko 자체와 공백 제거 버전만)
    assert len(result) == 6


def test_build_aliases_with_extra_aliases():
    """extra_aliases가 제공되면 기본 별칭에 추가한다."""
    result = build_aliases("Roboto", extra_aliases=["로보토"])
    assert "Roboto" in result
    assert "roboto" in result
    assert "roboto ttf" in result
    assert "로보토" in result
    assert len(result) == 4


def test_to_record_uses_korean_names_mapping():
    """korean_names 매핑이 제공되면 name_ko와 aliases를 설정한다."""
    from fontagit_pipeline.models import KoreanNameEntry

    korean_names = {
        "noto-sans-kr": KoreanNameEntry(
            name_ko="노토 산스 KR",
            aliases=["노토산스KR", "노토산스"],
            sources=["curated"],
        ),
    }
    raw = GoogleFontRaw(
        family="Noto Sans KR",
        variants=["regular", "700"],
        subsets=["korean", "latin"],
        version="v1",
        lastModified="2024-01-01",
        files={},
        category="sans-serif",
    )
    rec = to_record(raw, {"notosanskr": "OFL"}, korean_names=korean_names)
    assert rec.name_ko == "노토 산스 KR"
    assert "노토 산스 KR" in rec.aliases
    assert "노토산스KR" in rec.aliases
    assert "노토산스" in rec.aliases
