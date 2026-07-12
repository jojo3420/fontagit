"""build_document 함수 통합 테스트."""

from datetime import datetime, timezone

from fontagit_pipeline.__main__ import build_document
from fontagit_pipeline.models import GoogleFontRaw, OutputDocument


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
    doc = build_document(fonts, generated_at)

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
    doc = build_document(fonts, generated_at, latin_limit=50)

    # Assert
    assert doc.record_count <= 50
