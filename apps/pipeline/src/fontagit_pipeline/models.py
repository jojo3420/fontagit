"""FontAgit 데이터 모델."""

from typing import Literal

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
    status: Literal["draft", "published", "archived"] = "draft"
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


class KoreanNameEntry(BaseModel):
    """한글 이름-별칭 큐레이션 엔트리."""

    name_ko: str | None = None
    aliases: list[str] = []
    sources: list[str]

    @model_validator(mode="after")
    def validate_evidence(self) -> "KoreanNameEntry":
        """name_ko/aliases 존재 시 sources 필수, 빈 alias/공백 name_ko는 에러."""
        # (a) name_ko가 공백뿐이면 에러 (None으로 변환 아님)
        if self.name_ko is not None and not self.name_ko.strip():
            raise ValueError("name_ko는 공백만으로 구성될 수 없습니다")

        # (b) 빈 문자열 alias는 에러
        if any(not alias.strip() for alias in self.aliases):
            raise ValueError("aliases에 공백만 있는 항목이 있습니다")

        # (c) name_ko 또는 aliases가 있으면 sources 1개 이상 필수
        if (self.name_ko is not None or self.aliases) and not self.sources:
            raise ValueError(
                "name_ko 또는 aliases가 있으면 sources 1개 이상 필수입니다"
            )

        return self


class OutputDocument(BaseModel):
    """최종 출력 문서."""

    schema_version: int = 1
    generated_at: str
    source: str = "google-fonts-webfonts-api"
    record_count: int
    fonts: list[FontRecord]


class NoonnuSeedRecord(BaseModel):
    """눈누(noonnu.cc) 시드 수집 레코드."""

    name_ko: str
    name_en: str | None = None
    maker: str
    official_url: str
    source_page: str
    collected_at: str


class NoonnuSeedOutput(BaseModel):
    """눈누 시드 수집 결과 문서."""

    schema_version: int = 1
    generated_at: str
    source: str = "noonnu-cc"
    record_count: int
    records: list[NoonnuSeedRecord]
    skipped_count: int = 0
    skip_reasons: dict[str, int] = {}
