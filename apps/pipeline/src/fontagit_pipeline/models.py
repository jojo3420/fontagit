"""FontAgit 데이터 모델."""

from pydantic import BaseModel, model_validator


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

    slug: str
    name_en: str
    name_ko: str | None = None
    source_tier: str = "A"
    category_ko: str
    category_google: str
    subsets: list[str]
    variants: list[str]
    weights: list[int]
    official_url: str
    is_commercial_free: bool = False
    license: str | None = None
    license_type: str | None = None
    license_verified: bool = False
    status: str = "draft"
    aliases: list[str]
    version: str
    last_modified: str

    @model_validator(mode="after")
    def validate_license_requires_verification(self) -> "FontRecord":
        """라이선스와 라이선스_타입은 verified가 True일 때만 설정 가능하다."""
        if (
            (self.license is not None or self.license_type is not None)
            and not self.license_verified
        ):
            raise ValueError(
                "라이선스는 license_verified=True일 때만 설정할 수 있습니다"
            )
        if self.status == "published" and (
            not self.license_verified
            or self.license_type not in ("OFL", "Apache-2.0", "UFL")
        ):
            raise ValueError(
                "published는 검증된 라이선스(OFL/Apache-2.0/UFL)만 가능합니다"
            )
        return self


class OutputDocument(BaseModel):
    """최종 출력 문서."""

    schema_version: int = 1
    generated_at: str
    source: str = "google-fonts-webfonts-api"
    record_count: int
    fonts: list[FontRecord]
