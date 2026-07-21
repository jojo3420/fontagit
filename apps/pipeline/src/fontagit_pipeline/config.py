"""환경 설정 로드."""

import base64
import binascii
import json
from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# pipeline은 자체 .env 없이 apps/web의 환경변수 파일을 SSoT로 공유한다.
# dev 쓰기와 prod 읽기를 한 실행에서 함께 쓰므로 두 파일을 모두 로드하며,
# 중복 키는 뒤 파일(.env.local=dev)이 우선한다.
_WEB_ENV_DIR = Path(__file__).resolve().parents[3] / "web"
_ENV_FILES = (_WEB_ENV_DIR / ".env.production", _WEB_ENV_DIR / ".env.local")


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

    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

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
    supabase_allowed_dev_origins: str | None = None
    supabase_audit_prod_allowlist: str | None = None
    supabase_prod_public_url: str | None = None
    supabase_prod_public_anon_key: str | None = None
    supabase_prod_public_allowlist: str | None = None

    model_config = SettingsConfigDict(env_file=_ENV_FILES, extra="ignore")

    def dev_write_credentials(self) -> tuple[str, str]:
        """감사 쓰기에만 쓰는 전용 dev 자격증명을 안전하게 반환한다.

        일반 ``SUPABASE_URL``/``SUPABASE_SECRET_KEY``는 공개 기준선 읽기와
        기존 명령 호환용일 뿐, 이 경계에서 fallback으로 사용하지 않는다.
        """
        url = _required_setting(self.supabase_dev_url, "SUPABASE_DEV_URL")
        key = _required_setting(self.supabase_dev_secret_key, "SUPABASE_DEV_SECRET_KEY")
        prod_url = _required_setting(self.supabase_prod_url, "SUPABASE_PROD_URL")
        dev_origin = _https_origin(url, "SUPABASE_DEV_URL")
        prod_origin = _https_origin(prod_url, "SUPABASE_PROD_URL")
        if dev_origin == prod_origin:
            raise ValueError("dev and prod Supabase origins must differ")

        dev_ref = _supabase_project_ref(dev_origin)
        if dev_ref is not None:
            approved = _allowlist_items(self.supabase_audit_dev_allowlist)
            if not approved or (dev_ref not in approved and dev_origin not in approved):
                raise ValueError(
                    "SUPABASE_AUDIT_DEV_ALLOWLIST must approve the managed dev URL or project ref"
                )
        else:
            allowed_origins = {
                _https_origin(item, "SUPABASE_ALLOWED_DEV_ORIGINS")
                for item in _allowlist_items(self.supabase_allowed_dev_origins)
            }
            if not allowed_origins or dev_origin not in allowed_origins:
                raise ValueError(
                    "SUPABASE_ALLOWED_DEV_ORIGINS must explicitly approve the self-hosted dev origin"
                )
        return url, key

    def prod_write_credentials(self) -> tuple[str, str]:
        """감사 쓰기에만 쓰는 전용 prod 자격증명을 안전하게 반환한다.

        일반 ``SUPABASE_PROD_URL``/``SUPABASE_PROD_SECRET_KEY``는 공개 기준선 읽기와
        기존 명령 호환용일 뿐, 이 경계에서 fallback으로 사용하지 않는다.
        """
        url = _required_setting(self.supabase_prod_url, "SUPABASE_PROD_URL")
        key = _required_setting(self.supabase_prod_secret_key, "SUPABASE_PROD_SECRET_KEY")
        origin = _https_origin(url, "SUPABASE_PROD_URL")
        prod_ref = _supabase_project_ref(origin)
        if prod_ref is not None:
            approved = _allowlist_items(self.supabase_audit_prod_allowlist)
            if not approved or (prod_ref not in approved and origin not in approved):
                raise ValueError(
                    "SUPABASE_AUDIT_PROD_ALLOWLIST must explicitly approve the self-hosted prod origin"
                )
        else:
            allowed_origins = {
                _https_origin(item, "SUPABASE_AUDIT_PROD_ALLOWLIST")
                for item in _allowlist_items(self.supabase_audit_prod_allowlist)
            }
            if not allowed_origins or origin not in allowed_origins:
                raise ValueError(
                    "SUPABASE_AUDIT_PROD_ALLOWLIST must explicitly approve the self-hosted prod origin"
                )
        return url, key

    def prod_public_read_credentials(self) -> tuple[str, str]:
        """예약 scan에만 쓰는 prod 공개 origin과 public key를 반환한다.

        일반 ``SUPABASE_URL``/``SUPABASE_ANON_KEY``로 fallback하지 않는다.
        legacy JWT는 서명을 검증하는 척하지 않고 role이 anon인지 형식만
        제한적으로 확인한다. 최종 인증은 Supabase가 수행한다.
        """
        url = _required_public_setting(self.supabase_prod_public_url)
        key = _required_public_setting(self.supabase_prod_public_anon_key)
        origin = _https_origin(url, "SUPABASE_PROD_PUBLIC_URL")
        approved = _allowlist_items(self.supabase_prod_public_allowlist)
        project_ref = _supabase_project_ref(origin)
        if project_ref is not None:
            if not approved or (project_ref not in approved and origin not in approved):
                raise ValueError("prod public Supabase origin is not approved")
        else:
            allowed_origins = {
                _https_origin(item, "SUPABASE_PROD_PUBLIC_ALLOWLIST") for item in approved
            }
            if not allowed_origins or origin not in allowed_origins:
                raise ValueError("prod public Supabase origin is not approved")
        _validate_public_anon_key(key)
        return origin, key


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
        raise ValueError(f"{name} is required for audit writes")
    return value.strip()


def _required_public_setting(value: str | None) -> str:
    if not value or not value.strip():
        raise ValueError("dedicated prod public audit setting is required")
    return value.strip()


def _allowlist_items(value: str | None) -> set[str]:
    return {item.strip().rstrip("/") for item in (value or "").split(",") if item.strip()}


def _https_origin(url: str, setting_name: str) -> str:
    """비밀키를 보낼 Supabase HTTPS origin을 정규화한다."""
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError(f"{setting_name} must be a valid HTTPS origin")
    try:
        port = parsed.port or 443
    except ValueError as exc:
        raise ValueError(f"{setting_name} must be a valid HTTPS origin") from exc
    host = f"[{hostname}]" if ":" in hostname else hostname
    return f"https://{host}" if port == 443 else f"https://{host}:{port}"


def _supabase_project_ref(origin: str) -> str | None:
    hostname = (urlparse(origin).hostname or "").rstrip(".").lower()
    suffix = ".supabase.co"
    if not hostname.endswith(suffix):
        return None
    ref = hostname.removesuffix(suffix)
    return ref if ref and "." not in ref else None


def _validate_public_anon_key(key: str) -> None:
    """공개 publishable key 또는 role=anon인 제한된 legacy JWT만 허용한다."""
    if len(key) > 4096 or not key.isascii():
        raise ValueError("prod public anon key format is invalid")
    if key.startswith("sb_secret_"):
        raise ValueError("prod public anon key format is invalid")
    if key.startswith("sb_publishable_"):
        suffix = key.removeprefix("sb_publishable_")
        if suffix and len(suffix) <= 512 and all(
            char.isalnum() or char in "-_" for char in suffix
        ):
            return
        raise ValueError("prod public anon key format is invalid")

    segments = key.split(".")
    if len(segments) != 3 or any(not segment for segment in segments):
        raise ValueError("prod public anon key format is invalid")
    encoded_payload = segments[1]
    if len(encoded_payload) > 2732:
        raise ValueError("prod public anon key format is invalid")
    try:
        padding = "=" * (-len(encoded_payload) % 4)
        payload_bytes = base64.b64decode(
            encoded_payload + padding, altchars=b"-_", validate=True
        )
        if len(payload_bytes) > 2048:
            raise ValueError
        claims = json.loads(payload_bytes, object_pairs_hook=_closed_claims)
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("prod public anon key format is invalid") from exc
    allowed_claims = {"iss", "ref", "role", "iat", "exp", "sub", "aud"}
    if not isinstance(claims, dict) or not set(claims) <= allowed_claims:
        raise ValueError("prod public anon key format is invalid")
    if claims.get("role") != "anon":
        raise ValueError("prod public anon key format is invalid")


def _closed_claims(pairs: list[tuple[str, object]]) -> dict[str, object]:
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate JWT claim")
    return dict(pairs)
