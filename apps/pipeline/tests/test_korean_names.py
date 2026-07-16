"""한글 이름 매핑 로더 테스트."""

import unicodedata

import pytest

from fontagit_pipeline.korean_names import (
    KoreanNamesError,
    load_korean_names,
    validate_coverage,
)


def test_load_korean_names_returns_38_nfc_normalized_entries():
    """38개 항목 로드 후 모든 문자열이 NFC 정규화됨을 확인한다."""
    mapping = load_korean_names()
    assert len(mapping) == 38
    entry = mapping["noto-sans-kr"]
    assert entry.name_ko == "본고딕"
    assert entry.sources  # 근거 URL 1개 이상
    # NFC 보장: 모든 문자열이 NFC와 동일
    for slug, e in mapping.items():
        for s in ([e.name_ko] if e.name_ko else []) + e.aliases:
            assert s == unicodedata.normalize("NFC", s), f"{slug}: NFD 혼입"


def test_validate_coverage_fails_on_missing_and_surplus():
    """매핑과 published 폰트 집합의 불일치를 감지한다."""
    mapping = load_korean_names()
    published = set(mapping.keys())
    validate_coverage(mapping, published)  # 일치 → 통과

    with pytest.raises(KoreanNamesError, match="누락"):
        validate_coverage(mapping, published | {"new-korean-font"})

    with pytest.raises(KoreanNamesError, match="잉여"):
        validate_coverage(mapping, published - {"noto-sans-kr"})
