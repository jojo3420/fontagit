"""FontAgit 데이터 모델."""

from pydantic import BaseModel


class GoogleFontRaw(BaseModel):
    """Google Fonts API의 원본 폰트 데이터."""

    family: str
    variants: list[str]
    subsets: list[str]
    version: str
    lastModified: str
    files: dict[str, str]
    category: str
    menu: str | None = None


class FontRecord(BaseModel):
    """처리된 폰트 레코드."""

    name_en: str
    name_ko: str | None = None
    tier: str = "A"
    category: str
    subsets: list[str]
    variants: list[str]
    official_url: str
    license: str | None = None
    license_verified: bool = False
    aliases: list[str]
    version: str
    last_modified: str


class OutputDocument(BaseModel):
    """최종 출력 문서."""

    schema_version: int = 1
    generated_at: str
    source: str = "google-fonts-webfonts-api"
    record_count: int
    fonts: list[FontRecord]
