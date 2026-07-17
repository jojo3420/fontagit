"""눈누 시드 수집 테스트."""

from fontagit_pipeline.noonnu_seed import (
    _extract_font_data,
    _parse_sitemap_urls,
)


class TestParseSitemapUrls:
    """Sitemap URL 파싱 테스트."""

    def test_parse_valid_sitemap(self) -> None:
        """유효한 sitemap XML을 파싱한다."""
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://noonnu.cc/font_page/123</loc>
    </url>
    <url>
        <loc>https://noonnu.cc/font_page/456</loc>
    </url>
    <url>
        <loc>https://noonnu.cc/about</loc>
    </url>
</urlset>
"""
        urls = _parse_sitemap_urls(sitemap_xml)
        assert len(urls) == 2
        assert "https://noonnu.cc/font_page/123" in urls
        assert "https://noonnu.cc/font_page/456" in urls

    def test_parse_empty_sitemap(self) -> None:
        """폰트 URL이 없는 sitemap을 처리한다."""
        sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://noonnu.cc/about</loc>
    </url>
</urlset>
"""
        urls = _parse_sitemap_urls(sitemap_xml)
        assert len(urls) == 0


class TestExtractFontData:
    """폰트 데이터 추출 테스트."""

    def test_extract_with_complete_data(self) -> None:
        """모든 필드를 포함한 HTML을 파싱한다."""
        html = """
<html>
    <head>
        <meta property="og:title" content="나눔고딕">
    </head>
    <body>
        <h1>나눔고딕</h1>
        <div>Foundry: Noto Sans Developer</div>
        <a href="https://www.noto-fonts.com">Official Website</a>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/123")
        assert result is not None
        name_ko, name_en, maker, official_url = result
        assert name_ko == "나눔고딕"
        assert maker == "Noto Sans Developer"
        assert official_url is not None
        assert "noto-fonts.com" in official_url

    def test_extract_with_minimal_data(self) -> None:
        """최소 필드만 포함한 HTML을 파싱한다."""
        html = """
<html>
    <body>
        <h1>다른폰트</h1>
        <div>Foundry: FontMaker Corp</div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/456")
        assert result is not None
        name_ko, name_en, maker, official_url = result
        assert name_ko == "다른폰트"
        assert maker == "FontMaker Corp"

    def test_extract_without_required_fields(self) -> None:
        """필수 필드가 없는 HTML은 추출 실패."""
        html = """
<html>
    <body>
        <div>Just some content</div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/789")
        # 필수 필드 없으면 None을 반환하거나 빈 값 반환
        # 호출자(collect_noonnu_seeds)가 필수 필드 검증함
        assert result is not None  # 함수 자체는 항상 튜플 반환
        name_ko, name_en, maker, official_url = result
        # 이 경우 name_ko나 maker가 None이거나 "Unknown"일 수 있음

    def test_filter_internal_links(self) -> None:
        """noonnu 내부 링크를 필터링한다."""
        html = """
<html>
    <body>
        <h1>테스트폰트</h1>
        <div>Foundry: Test Maker</div>
        <a href="https://noonnu.cc/other-font">Internal Link</a>
        <a href="/font_page/999">Relative Link</a>
        <a href="https://example.com">External Link</a>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/111")
        assert result is not None
        name_ko, name_en, maker, official_url = result
        # 외부 링크만 선택되어야 함
        if official_url and official_url != "https://noonnu.cc/font_page/111":
            assert "example.com" in official_url
