"""환경 설정 로드."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """파이프라인 설정.

    pydantic-settings를 사용하여 .env 파일에서 환경변수를 로드한다.
    """

    google_fonts_api_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def load_settings() -> Settings:
    """환경변수와 .env 파일로부터 설정을 로드한다.

    Returns:
        로드된 설정 인스턴스.

    Raises:
        ValidationError: google_fonts_api_key가 없을 경우.
    """
    return Settings()  # type: ignore[call-arg]
