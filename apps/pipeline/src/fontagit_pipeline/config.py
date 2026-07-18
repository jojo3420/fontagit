"""환경 설정 로드."""

import hmac
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """파이프라인 설정.

    pydantic-settings를 사용하여 .env 파일에서 환경변수를 로드한다.
    """

    google_fonts_api_key: str
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    supabase_prod_url: str | None = None
    supabase_prod_secret_key: str | None = None
    github_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("google_fonts_api_key")
    @classmethod
    def validate_api_key_not_empty(cls, v: str) -> str:
        """API 키는 공백만으로 이루어져 있을 수 없다."""
        if not v.strip():
            raise ValueError("google_fonts_api_key는 비워둘 수 없습니다")
        return v


class AuditSettings(BaseSettings):
    """Google Fonts API 키와 분리된 감사 전용 설정."""

    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_secret_key: str | None = None
    supabase_prod_url: str | None = None
    supabase_prod_secret_key: str | None = None
    supabase_dev_url: str | None = None
    supabase_dev_secret_key: str | None = None
    supabase_audit_dev_allowlist: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def dev_write_credentials(self) -> tuple[str, str]:
        """감사 쓰기에만 쓰는 전용 dev 자격증명을 안전하게 반환한다.

        일반 ``SUPABASE_URL``/``SUPABASE_SECRET_KEY``는 공개 기준선 읽기와
        기존 명령 호환용일 뿐, 이 경계에서 fallback으로 사용하지 않는다.
        """
        url = _required_setting(self.supabase_dev_url, "SUPABASE_DEV_URL")
        key = _required_setting(self.supabase_dev_secret_key, "SUPABASE_DEV_SECRET_KEY")
        dev_ref = _supabase_project_ref(url)
        if dev_ref is None:
            raise ValueError("SUPABASE_DEV_URL must be a valid Supabase project URL")

        approved = {
            item.strip().rstrip("/")
            for item in (self.supabase_audit_dev_allowlist or "").split(",")
            if item.strip()
        }
        if not approved or (url.rstrip("/") not in approved and dev_ref not in approved):
            raise ValueError("SUPABASE_AUDIT_DEV_ALLOWLIST must approve the dev URL or project ref")

        if self.supabase_prod_url:
            prod_ref = _supabase_project_ref(self.supabase_prod_url)
            if prod_ref is None:
                raise ValueError("SUPABASE_PROD_URL must be a valid Supabase project URL")
            if url.rstrip("/") == self.supabase_prod_url.rstrip("/") or dev_ref == prod_ref:
                raise ValueError("dev and prod Supabase project refs must differ")
        if self.supabase_prod_secret_key and hmac.compare_digest(key, self.supabase_prod_secret_key):
            raise ValueError("dev and prod service keys must differ")
        return url, key


def load_settings() -> Settings:
    """환경변수와 .env 파일로부터 설정을 로드한다.

    Returns:
        로드된 설정 인스턴스.

    Raises:
        ValidationError: google_fonts_api_key가 없을 경우.
    """
    return Settings()  # type: ignore[call-arg]


def load_audit_settings() -> AuditSettings:
    """감사 명령용 선택 설정을 로드한다."""
    return AuditSettings()


def _required_setting(value: str | None, name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{name} is required for dev audit writes")
    return value.strip()


def _supabase_project_ref(url: str) -> str | None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    suffix = ".supabase.co"
    if parsed.scheme != "https" or not hostname.endswith(suffix):
        return None
    ref = hostname.removesuffix(suffix)
    return ref if ref and "." not in ref else None
