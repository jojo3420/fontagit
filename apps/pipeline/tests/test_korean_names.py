"""한글 이름 매핑 로더 테스트."""

import pytest
from pathlib import Path

from fontagit_pipeline.korean_names import (
    load_korean_names,
    validate_coverage,
    KoreanNamesError,
)


class TestLoadKoreanNames:
    """load_korean_names 함수 테스트."""

    def test_load_korean_names_returns_38_nfc_normalized_entries(self):
        """매핑 JSON을 로드하면 38개의 정규화된 항목을 반환한다."""
        mapping = load_korean_names()

        assert len(mapping) == 38
        assert "noto-sans-kr" in mapping

        entry = mapping["noto-sans-kr"]
        assert entry.name_ko == "본고딕"
        assert entry.sources is not None and len(entry.sources) > 0

    def test_validate_coverage_raises_on_missing_name_ko(self):
        """name_ko가 None인 항목이 있으면 KoreanNamesError를 발생시킨다."""
        mapping = load_korean_names()

        with pytest.raises(KoreanNamesError) as exc_info:
            validate_coverage(mapping)

        assert "name_ko is None" in str(exc_info.value)
