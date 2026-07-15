"""build_document 함수 통합 테스트."""

from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from fontagit_pipeline.__main__ import build_document, main
from fontagit_pipeline.models import GoogleFontRaw, OutputDocument
from fontagit_pipeline.licenses import LicenseFetchError


def test_build_document_creates_output_document():
    """build_document는 fonts와 generated_at로부터 OutputDocument를 생성한다."""
    # Arrange
    fonts = [
        GoogleFontRaw(
            family="Noto Sans KR",
            variants=["regular", "700"],
            subsets=["korean", "latin"],
            version="v24.1.0",
            lastModified="2024-09-01",
            files={"regular": "http://example.com/font1.ttf", "700": "http://example.com/font1b.ttf"},
            category="sans-serif",
        ),
        GoogleFontRaw(
            family="Roboto",
            variants=["regular", "italic"],
            subsets=["latin"],
            version="v30.0.0",
            lastModified="2024-09-01",
            files={"regular": "http://example.com/font2.ttf", "italic": "http://example.com/font2i.ttf"},
            category="sans-serif",
        ),
    ]
    generated_at = datetime.now(timezone.utc).isoformat()

    # Act
    doc = build_document(fonts, {}, generated_at)

    # Assert
    assert isinstance(doc, OutputDocument)
    assert doc.generated_at == generated_at
    assert doc.source == "google-fonts-webfonts-api"
    assert doc.record_count == 2
    assert len(doc.fonts) == 2


def test_build_document_respects_latin_limit():
    """build_document는 latin_limit 파라미터를 존중한다."""
    # Arrange
    fonts = [
        GoogleFontRaw(
            family=f"Font{i}",
            variants=["regular"],
            subsets=["latin"],
            version="v1.0.0",
            lastModified="2024-09-01",
            files={"regular": f"http://example.com/font{i}.ttf"},
            category="sans-serif",
        )
        for i in range(150)
    ]
    generated_at = datetime.now(timezone.utc).isoformat()

    # Act
    doc = build_document(fonts, {}, generated_at, latin_limit=50)

    # Assert (latin_limit이 50이므로 정확히 50개여야 함)
    assert doc.record_count == 50
    assert len(doc.fonts) == 50


def test_build_document_passes_license_map():
    """build_document는 license_map을 전달받아 처리한다."""
    from fontagit_pipeline.models import GoogleFontRaw
    from fontagit_pipeline.__main__ import build_document

    raw = GoogleFontRaw(
        family="Jua", variants=["regular"], subsets=["korean"],
        version="v1", lastModified="2024-01-01", files={}, category="display",
    )
    doc = build_document([raw], {"jua": "OFL"}, "2026-07-14T00:00:00Z")
    assert doc.record_count == 1
    assert doc.fonts[0].status == "published"
    assert doc.fonts[0].category_ko == "장식"


def test_main_returns_3_on_empty_record_count(tmp_path):
    """record_count가 0일 때 main은 3을 반환하고 파일을 쓰지 않는다."""
    fonts_empty = []
    generated_at = datetime.now(timezone.utc).isoformat()
    doc = build_document(fonts_empty, {}, generated_at)

    # record_count가 0이면 main이 exit 3를 반환해야 함
    assert doc.record_count == 0

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            with patch("fontagit_pipeline.__main__.build_document") as mock_build:
                with patch("fontagit_pipeline.__main__.write_output") as mock_write:
                    mock_settings.return_value = MagicMock(
                        google_fonts_api_key="test_key"
                    )
                    mock_fetch.return_value = []
                    mock_build.return_value = doc

                    result = main()

                    # write_output이 호출되지 않아야 함
                    mock_write.assert_not_called()
                    # exit code는 3이어야 함
                    assert result == 3


def test_main_returns_3_on_webfonts_error(tmp_path):
    """WebfontsError 발생 시 main은 3을 반환한다."""
    from fontagit_pipeline.client import WebfontsError

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            mock_settings.return_value = MagicMock(
                google_fonts_api_key="test_key"
            )
            mock_fetch.side_effect = WebfontsError("테스트 에러")

            result = main()

            # exit code는 3이어야 함
            assert result == 3


def test_main_returns_3_on_write_error(tmp_path):
    """파일 저장 실패 시 main은 3을 반환한다."""
    fonts = [
        GoogleFontRaw(
            family="Roboto",
            variants=["regular"],
            subsets=["latin"],
            version="v30",
            lastModified="2024-09-01",
            files={"regular": "https://x/r.ttf"},
            category="sans-serif",
        )
    ]

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            with patch("fontagit_pipeline.__main__.write_output") as mock_write:
                mock_settings.return_value = MagicMock(
                    google_fonts_api_key="test_key"
                )
                mock_fetch.return_value = fonts
                mock_write.side_effect = OSError("디스크 오류")

                result = main()

                # exit code는 3이어야 함
                assert result == 3


def test_main_returns_3_on_license_fetch_error(tmp_path):
    """라이선스 조회 실패 시 main은 산출물 미생성 후 즉시 3을 반환한다."""
    fonts = [
        GoogleFontRaw(
            family="Roboto",
            variants=["regular"],
            subsets=["latin"],
            version="v30",
            lastModified="2024-09-01",
            files={"regular": "https://x/r.ttf"},
            category="sans-serif",
        )
    ]

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            with patch("fontagit_pipeline.__main__.fetch_license_map") as mock_license:
                with patch("fontagit_pipeline.__main__.write_output") as mock_write:
                    mock_settings.return_value = MagicMock(
                        google_fonts_api_key="test_key",
                        github_token="test_token",
                        supabase_url="https://test.supabase.co",
                        supabase_secret_key="test_secret_key",
                    )
                    mock_fetch.return_value = fonts
                    mock_license.side_effect = LicenseFetchError("네트워크 오류")

                    result = main()

                    # write_output은 호출되지 않음 (산출물 미생성)
                    mock_write.assert_not_called()
                    # exit code는 3이어야 함
                    assert result == 3


def test_main_returns_3_on_supabase_config_mismatch(tmp_path):
    """Supabase URL과 SECRET_KEY 중 하나만 있으면 main은 3을 반환한다."""
    fonts = [
        GoogleFontRaw(
            family="Roboto",
            variants=["regular"],
            subsets=["latin"],
            version="v30",
            lastModified="2024-09-01",
            files={"regular": "https://x/r.ttf"},
            category="sans-serif",
        )
    ]

    with patch("fontagit_pipeline.__main__.load_settings") as mock_settings:
        with patch("fontagit_pipeline.__main__.fetch_webfonts") as mock_fetch:
            with patch("fontagit_pipeline.__main__.fetch_license_map") as mock_license:
                with patch("fontagit_pipeline.__main__.write_output") as mock_write:
                    mock_settings.return_value = MagicMock(
                        google_fonts_api_key="test_key",
                        github_token="test_token",
                        supabase_url="https://test.supabase.co",
                        supabase_secret_key=None,
                    )
                    mock_fetch.return_value = fonts
                    mock_license.return_value = {}

                    result = main()

                    # write_output은 호출되어야 함 (JSON 저장)
                    mock_write.assert_called_once()
                    # exit code는 3이어야 함 (설정 불완전)
                    assert result == 3
