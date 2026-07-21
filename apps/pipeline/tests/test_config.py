"""설정 로드 테스트."""

import pytest
from pydantic import ValidationError

from fontagit_pipeline.config import AuditSettings, Settings, load_audit_settings


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


def test_audit_settings_require_separate_managed_dev_origin_without_prod_secret(monkeypatch, tmp_path):
    """managed dev는 승인 ref와 prod URL만으로 안전하게 쓸 수 있다."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOOGLE_FONTS_API_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://prod-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "general-key-must-not-be-used")

    # 공개 기준선 읽기에는 일반 URL이 남아도, dev 쓰기에는 쓰면 안 된다.
    assert load_audit_settings().supabase_url == "https://prod-ref.supabase.co"
    with pytest.raises(ValueError, match="SUPABASE_DEV"):
        AuditSettings(_env_file=None).dev_write_credentials()

    with pytest.raises(ValueError, match="SUPABASE_PROD"):
        AuditSettings(
            supabase_dev_url="https://dev-ref.supabase.co",
            supabase_dev_secret_key="dev-key",
            supabase_audit_dev_allowlist="dev-ref",
            _env_file=None,
        ).dev_write_credentials()

    monkeypatch.setenv("SUPABASE_DEV_URL", "https://prod-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_DEV_SECRET_KEY", "dev-key")
    monkeypatch.setenv("SUPABASE_PROD_URL", "https://prod-ref.supabase.co")
    monkeypatch.delenv("SUPABASE_PROD_SECRET_KEY", raising=False)
    monkeypatch.setenv("SUPABASE_AUDIT_DEV_ALLOWLIST", "prod-ref,dev-ref")
    with pytest.raises(ValueError, match="origins must differ"):
        AuditSettings(_env_file=None).dev_write_credentials()

    monkeypatch.setenv("SUPABASE_DEV_URL", "https://prod-ref.supabase.co.")
    with pytest.raises(ValueError, match="origins must differ"):
        AuditSettings(_env_file=None).dev_write_credentials()

    monkeypatch.setenv("SUPABASE_DEV_URL", "https://dev-ref.supabase.co")
    monkeypatch.setenv("SUPABASE_DEV_SECRET_KEY", "dev-key")
    assert AuditSettings(_env_file=None).dev_write_credentials() == (
        "https://dev-ref.supabase.co",
        "dev-key",
    )


def test_audit_settings_accepts_explicit_self_hosted_dev_origin() -> None:
    """자체 호스팅 dev는 별도 origin allowlist가 있어야만 허용한다."""
    settings = AuditSettings(
        supabase_dev_url="https://10.0.0.7:8443",
        supabase_dev_secret_key="dev-key",
        supabase_prod_url="https://supabase.example.com",
    )
    with pytest.raises(ValueError, match="SUPABASE_ALLOWED_DEV_ORIGINS"):
        settings.dev_write_credentials()

    assert AuditSettings(
        supabase_dev_url="https://10.0.0.7:8443/",
        supabase_dev_secret_key="dev-key",
        supabase_prod_url="https://supabase.example.com:443",
        supabase_allowed_dev_origins="https://10.0.0.7:8443",
    ).dev_write_credentials() == ("https://10.0.0.7:8443/", "dev-key")


def test_prod_write_credentials_requires_settings() -> None:
    """prod 쓰기는 SUPABASE_PROD_URL과 SUPABASE_PROD_SECRET_KEY가 필수다."""
    with pytest.raises(ValueError, match="SUPABASE_PROD"):
        AuditSettings(_env_file=None).prod_write_credentials()

    with pytest.raises(ValueError, match="SUPABASE_PROD_SECRET_KEY"):
        AuditSettings(
            supabase_prod_url="https://prod.supabase.co",
            _env_file=None,
        ).prod_write_credentials()


def test_prod_write_credentials_requires_allowlist() -> None:
    """managed prod는 allowlist 승인이 필수다."""
    with pytest.raises(ValueError, match="SUPABASE_AUDIT_PROD_ALLOWLIST"):
        AuditSettings(
            supabase_prod_url="https://prod-ref.supabase.co",
            supabase_prod_secret_key="prod-key",
            _env_file=None,
        ).prod_write_credentials()


def test_prod_write_credentials_accepts_approved() -> None:
    """allowlist에서 승인된 managed prod URL은 자격증명을 반환한다."""
    assert AuditSettings(
        supabase_prod_url="https://prod-ref.supabase.co",
        supabase_prod_secret_key="prod-key",
        supabase_audit_prod_allowlist="prod-ref",
        _env_file=None,
    ).prod_write_credentials() == ("https://prod-ref.supabase.co", "prod-key")
