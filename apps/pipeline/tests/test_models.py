"""Models 모듈 TDD 테스트."""



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
        """기본값을 사용한 FontRecord 인스턴스 생성 (name_ko 미지정 시 None)."""
        record = FontRecord(
            name_en="Roboto",
            category="sans-serif",
            subsets=["latin"],
            variants=["regular", "bold"],
            official_url="https://fonts.google.com/specimen/Roboto",
            aliases=["roboto-family"],
            version="3.0",
            last_modified="2024-01-01",
        )
        assert record.name_en == "Roboto"
        assert record.name_ko is None  # default
        assert record.tier == "A"  # default
        assert record.category == "sans-serif"
        assert record.license is None  # default
        assert record.license_verified is False  # default

    def test_create_font_record_with_all_fields(self) -> None:
        """모든 필드를 지정한 FontRecord 인스턴스 생성."""
        record = FontRecord(
            name_en="Noto Sans",
            name_ko="노토 산스",
            tier="B",
            category="sans-serif",
            subsets=["latin", "korean"],
            variants=["400", "700"],
            official_url="https://fonts.google.com/specimen/Noto+Sans",
            license="OFL",
            license_verified=True,
            aliases=["noto", "noto-sans"],
            version="1.0",
            last_modified="2024-02-01",
        )
        assert record.name_en == "Noto Sans"
        assert record.name_ko == "노토 산스"
        assert record.tier == "B"
        assert record.license == "OFL"
        assert record.license_verified is True


class TestOutputDocument:
    """OutputDocument 모델 테스트."""

    def test_create_output_document_with_defaults(self) -> None:
        """기본값을 사용한 OutputDocument 인스턴스 생성 (schema_version 미지정 시 1)."""
        fonts = [
            FontRecord(
                name_en="Roboto",
                category="sans-serif",
                subsets=["latin"],
                variants=["regular"],
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
