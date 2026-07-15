"""Models 모듈 TDD 테스트."""

import pytest
from pydantic import ValidationError

from fontagit_pipeline.models import GoogleFontRaw, FontRecord, OutputDocument


class TestGoogleFontRaw:
    """GoogleFontRaw 모델 테스트."""

    def test_create_google_font_raw(self) -> None:
        """GoogleFontRaw 인스턴스 생성."""
        raw = GoogleFontRaw(
            family="Roboto",
            variants=["regular", "bold"],
            subsets=["latin", "latin-ext"],
            version="3.0",
            lastModified="2024-01-01",
            files={"regular": "roboto-regular.ttf"},
            category="sans-serif",
        )
        assert raw.family == "Roboto"
        assert raw.variants == ["regular", "bold"]
        assert raw.subsets == ["latin", "latin-ext"]
        assert raw.version == "3.0"
        assert raw.lastModified == "2024-01-01"
        assert raw.files == {"regular": "roboto-regular.ttf"}
        assert raw.category == "sans-serif"
        assert raw.menu is None

    def test_google_font_raw_with_menu(self) -> None:
        """menu가 있는 GoogleFontRaw 인스턴스 생성."""
        raw = GoogleFontRaw(
            family="Noto Sans",
            variants=["400"],
            subsets=["latin"],
            version="1.0",
            lastModified="2024-01-01",
            files={"400": "noto-sans-400.ttf"},
            category="sans-serif",
            menu="Noto Sans",
        )
        assert raw.menu == "Noto Sans"


class TestFontRecord:
    """FontRecord 모델 테스트."""

    def test_create_font_record_with_defaults(self) -> None:
        """기본값을 사용한 FontRecord 인스턴스 생성."""
        record = FontRecord(
            slug="roboto",
            name_en="Roboto",
            category_ko="산세리프",
            category_google="sans-serif",
            subsets=["latin"],
            variants=["regular", "bold"],
            weights=[400, 700],
            official_url="https://fonts.google.com/specimen/Roboto",
            aliases=["roboto-family"],
            version="3.0",
            last_modified="2024-01-01",
        )
        assert record.name_en == "Roboto"
        assert record.name_ko is None  # default
        assert record.slug == "roboto"
        assert record.source_tier == "A"  # default
        assert record.category_google == "sans-serif"
        assert record.category_ko == "산세리프"
        assert record.weights == [400, 700]
        assert record.is_commercial_free is False  # default
        assert record.license is None  # default
        assert record.license_type is None  # default
        assert record.license_verified is False  # default
        assert record.status == "draft"  # default

    def test_create_font_record_with_all_fields(self) -> None:
        """모든 필드를 지정한 FontRecord 인스턴스 생성."""
        record = FontRecord(
            slug="noto-sans",
            name_en="Noto Sans",
            name_ko="노토 산스",
            source_tier="B",
            category_ko="산세리프",
            category_google="sans-serif",
            subsets=["latin", "korean"],
            variants=["400", "700"],
            weights=[400, 700],
            official_url="https://fonts.google.com/specimen/Noto+Sans",
            is_commercial_free=True,
            license="OFL",
            license_type="OFL 1.1",
            license_verified=True,
            status="active",
            aliases=["noto", "noto-sans"],
            version="1.0",
            last_modified="2024-02-01",
        )
        assert record.name_en == "Noto Sans"
        assert record.name_ko == "노토 산스"
        assert record.slug == "noto-sans"
        assert record.source_tier == "B"
        assert record.category_google == "sans-serif"
        assert record.category_ko == "산세리프"
        assert record.weights == [400, 700]
        assert record.is_commercial_free is True
        assert record.license == "OFL"
        assert record.license_type == "OFL 1.1"
        assert record.license_verified is True
        assert record.status == "active"

    def test_font_record_forbids_license_without_verification(self) -> None:
        """라이선스는 license_verified=False일 때 설정할 수 없다."""
        with pytest.raises(ValidationError, match="라이선스는"):
            FontRecord(
                slug="noto-sans",
                name_en="Noto Sans",
                category_ko="산세리프",
                category_google="sans-serif",
                subsets=["latin"],
                variants=["400"],
                weights=[400],
                official_url="https://fonts.google.com/specimen/Noto+Sans",
                license="OFL",
                license_verified=False,
                aliases=["noto"],
                version="1.0",
                last_modified="2024-02-01",
            )

    def test_font_record_forbids_license_type_without_verification(self) -> None:
        """라이선스_타입은 license_verified=False일 때 설정할 수 없다."""
        with pytest.raises(ValidationError, match="라이선스는"):
            FontRecord(
                slug="noto-sans",
                name_en="Noto Sans",
                category_ko="산세리프",
                category_google="sans-serif",
                subsets=["latin"],
                variants=["400"],
                weights=[400],
                official_url="https://fonts.google.com/specimen/Noto+Sans",
                license_type="OFL 1.1",
                license_verified=False,
                aliases=["noto"],
                version="1.0",
                last_modified="2024-02-01",
            )

    def test_font_record_allows_verified_license_and_type(self) -> None:
        """라이선스와 라이선스_타입은 license_verified=True일 때 설정 가능하다."""
        record = FontRecord(
            slug="noto-sans",
            name_en="Noto Sans",
            category_ko="산세리프",
            category_google="sans-serif",
            subsets=["latin"],
            variants=["400"],
            weights=[400],
            official_url="https://fonts.google.com/specimen/Noto+Sans",
            license="OFL",
            license_type="OFL 1.1",
            license_verified=True,
            aliases=["noto"],
            version="1.0",
            last_modified="2024-02-01",
        )
        assert record.license == "OFL"
        assert record.license_type == "OFL 1.1"
        assert record.license_verified is True

    def test_font_record_allows_no_license_and_type(self) -> None:
        """라이선스/라이선스_타입이 모두 None일 때는 license_verified 값이 무관하게 허용된다."""
        record = FontRecord(
            slug="noto-sans",
            name_en="Noto Sans",
            category_ko="산세리프",
            category_google="sans-serif",
            subsets=["latin"],
            variants=["400"],
            weights=[400],
            official_url="https://fonts.google.com/specimen/Noto+Sans",
            license=None,
            license_type=None,
            license_verified=False,
            aliases=["noto"],
            version="1.0",
            last_modified="2024-02-01",
        )
        assert record.license is None
        assert record.license_type is None
        assert record.license_verified is False

    def test_font_record_forbids_published_without_verification(self) -> None:
        """status=published는 license_verified=False일 때 불가능하다."""
        with pytest.raises(ValidationError, match="published는"):
            FontRecord(
                slug="noto-sans",
                name_en="Noto Sans",
                category_ko="산세리프",
                category_google="sans-serif",
                subsets=["latin"],
                variants=["400"],
                weights=[400],
                official_url="https://fonts.google.com/specimen/Noto+Sans",
                license_type=None,
                license_verified=False,
                status="published",
                aliases=["noto"],
                version="1.0",
                last_modified="2024-02-01",
            )

    def test_font_record_forbids_published_without_license_type(self) -> None:
        """status=published는 license_type이 None일 때 불가능하다."""
        with pytest.raises(ValidationError, match="published는"):
            FontRecord(
                slug="noto-sans",
                name_en="Noto Sans",
                category_ko="산세리프",
                category_google="sans-serif",
                subsets=["latin"],
                variants=["400"],
                weights=[400],
                official_url="https://fonts.google.com/specimen/Noto+Sans",
                license_type=None,
                license_verified=True,
                status="published",
                aliases=["noto"],
                version="1.0",
                last_modified="2024-02-01",
            )

    def test_font_record_forbids_published_with_invalid_license_type(self) -> None:
        """status=published는 허가된 license_type(OFL/Apache-2.0/UFL) 외에는 불가능하다."""
        with pytest.raises(ValidationError, match="published는"):
            FontRecord(
                slug="noto-sans",
                name_en="Noto Sans",
                category_ko="산세리프",
                category_google="sans-serif",
                subsets=["latin"],
                variants=["400"],
                weights=[400],
                official_url="https://fonts.google.com/specimen/Noto+Sans",
                license_type="MIT",
                license_verified=True,
                status="published",
                aliases=["noto"],
                version="1.0",
                last_modified="2024-02-01",
            )

    def test_font_record_allows_published_with_valid_ofl(self) -> None:
        """status=published는 license_type=OFL + license_verified=True일 때 허용된다."""
        record = FontRecord(
            slug="noto-sans",
            name_en="Noto Sans",
            category_ko="산세리프",
            category_google="sans-serif",
            subsets=["latin"],
            variants=["400"],
            weights=[400],
            official_url="https://fonts.google.com/specimen/Noto+Sans",
            license_type="OFL",
            license_verified=True,
            status="published",
            aliases=["noto"],
            version="1.0",
            last_modified="2024-02-01",
        )
        assert record.status == "published"
        assert record.license_type == "OFL"
        assert record.license_verified is True

    def test_font_record_allows_published_with_valid_apache(self) -> None:
        """status=published는 license_type=Apache-2.0 + license_verified=True일 때 허용된다."""
        record = FontRecord(
            slug="roboto",
            name_en="Roboto",
            category_ko="산세리프",
            category_google="sans-serif",
            subsets=["latin"],
            variants=["400"],
            weights=[400],
            official_url="https://fonts.google.com/specimen/Roboto",
            license_type="Apache-2.0",
            license_verified=True,
            status="published",
            aliases=["roboto"],
            version="1.0",
            last_modified="2024-02-01",
        )
        assert record.status == "published"
        assert record.license_type == "Apache-2.0"
        assert record.license_verified is True

    def test_font_record_allows_published_with_valid_ufl(self) -> None:
        """status=published는 license_type=UFL + license_verified=True일 때 허용된다."""
        record = FontRecord(
            slug="ubuntu",
            name_en="Ubuntu",
            category_ko="산세리프",
            category_google="sans-serif",
            subsets=["latin"],
            variants=["400"],
            weights=[400],
            official_url="https://fonts.google.com/specimen/Ubuntu",
            license_type="UFL",
            license_verified=True,
            status="published",
            aliases=["ubuntu"],
            version="1.0",
            last_modified="2024-02-01",
        )
        assert record.status == "published"
        assert record.license_type == "UFL"
        assert record.license_verified is True


class TestOutputDocument:
    """OutputDocument 모델 테스트."""

    def test_create_output_document_with_defaults(self) -> None:
        """기본값을 사용한 OutputDocument 인스턴스 생성 (schema_version 미지정 시 1)."""
        fonts = [
            FontRecord(
                slug="roboto",
                name_en="Roboto",
                category_ko="산세리프",
                category_google="sans-serif",
                subsets=["latin"],
                variants=["regular"],
                weights=[400],
                official_url="https://fonts.google.com/specimen/Roboto",
                aliases=["roboto"],
                version="3.0",
                last_modified="2024-01-01",
            )
        ]
        doc = OutputDocument(
            generated_at="2024-01-15T10:00:00Z",
            record_count=1,
            fonts=fonts,
        )
        assert doc.schema_version == 1  # default
        assert doc.generated_at == "2024-01-15T10:00:00Z"
        assert doc.source == "google-fonts-webfonts-api"  # default
        assert doc.record_count == 1
        assert len(doc.fonts) == 1
        assert doc.fonts[0].name_en == "Roboto"

    def test_create_output_document_with_custom_source(self) -> None:
        """커스텀 source를 지정한 OutputDocument 인스턴스 생성."""
        fonts: list[FontRecord] = []
        doc = OutputDocument(
            schema_version=1,
            generated_at="2024-01-15T10:00:00Z",
            source="custom-source",
            record_count=0,
            fonts=fonts,
        )
        assert doc.source == "custom-source"
        assert doc.record_count == 0
