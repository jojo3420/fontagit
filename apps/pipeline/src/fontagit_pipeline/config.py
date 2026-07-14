"""환경 설정 로드."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """파이프라인 설정.

    pydantic-settings를 사용하여 .env 파일에서 환경변수를 로드한다.
    """

    google_fonts_api_key: str
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    github_token: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("google_fonts_api_key")
    @classmethod
    def validate_api_key_not_empty(cls, v: str) -> str:
        """API 키는 공백만으로 이루어져 있을 수 없다."""
        if not v.strip():
            raise ValueError("google_fonts_api_key는 비워둘 수 없습니다")
        return v


def load_settings() -> Settings:
    """환경변수와 .env 파일로부터 설정을 로드한다.

    Returns:
        로드된 설정 인스턴스.

    Raises:
        ValidationError: google_fonts_api_key가 없을 경우.
    """
    return Settings()  # type: ignore[call-arg]
