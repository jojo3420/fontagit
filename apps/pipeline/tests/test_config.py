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


def test_settings_optional_supabase(monkeypatch):
    """Supabase 설정은 선택사항이다."""
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GOOGLE_FONTS_API_KEY", "valid_key")

    settings = Settings(_env_file=None)
    assert settings.supabase_url is None
    assert settings.supabase_secret_key is None
    assert settings.github_token is None


def test_settings_supabase_absent_ok(monkeypatch):
    """Supabase 없이도 설정을 로드할 수 있다."""
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GOOGLE_FONTS_API_KEY", "required_key")

    settings = Settings(_env_file=None)
    assert settings.google_fonts_api_key == "required_key"
    assert settings.supabase_url is None
    assert settings.supabase_secret_key is None
    assert settings.github_token is None
