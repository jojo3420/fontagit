"""설정 로드 테스트."""

from argparse import Namespace

import pytest
from pydantic import ValidationError

from fontagit_pipeline.config import Settings, load_audit_settings
from fontagit_pipeline.__main__ import main_audit_policy_check


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


def test_audit_settings_do_not_require_google_key(monkeypatch, tmp_path):
    """감사 전용 설정은 Google Fonts API 키가 없어도 로드한다."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    assert load_audit_settings().supabase_url is None


def test_audit_policy_cli_loads_audit_settings(monkeypatch, tmp_path):
    """감사 정책 CLI는 Google 설정이 아닌 감사 설정을 초기화한다."""
    calls = 0

    def track_audit_settings_load():
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        "fontagit_pipeline.config.load_audit_settings",
        track_audit_settings_load,
    )

    result = main_audit_policy_check(Namespace(out=tmp_path / "policy.json"))

    assert result == 0
    assert calls == 1
