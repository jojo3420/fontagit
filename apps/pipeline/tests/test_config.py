"""설정 로드 테스트."""

import pytest
from pydantic import ValidationError

from fontagit_pipeline.config import Settings


def test_settings_rejects_blank_api_key(monkeypatch):
    """API 키가 비어있거나 공백만으로 이루어져 있으면 거부한다."""
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)

    # 공백만 있는 경우
    monkeypatch.setenv("GOOGLE_FONTS_API_KEY", "   ")

    with pytest.raises(ValidationError, match="비워둘 수 없습니다"):
        Settings()


def test_settings_accepts_valid_api_key(monkeypatch):
    """유효한 API 키는 수용한다."""
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_FONTS_API_KEY", "valid_key_12345")

    settings = Settings()
    assert settings.google_fonts_api_key == "valid_key_12345"
