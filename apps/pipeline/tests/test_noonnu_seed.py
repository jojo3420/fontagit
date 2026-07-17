"""눈누 시드 수집 테스트."""

from fontagit_pipeline.noonnu_seed import (
    _extract_font_data,
    _parse_robots_policy,
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
        """JSON-LD에서 정제된 폰트명과 제작사를 파싱한다."""
        html = """
<html>
    <head>
        <meta property="og:title" content="나눔고딕 | 눈누 - 상업용 무료 한글 폰트">
        <script type="application/ld+json">
          {
            "@type": "SoftwareApplication",
            "name": "나눔고딕",
            "applicationCategory": "Font",
            "creator": {"@type": "Organization", "name": "네이버"}
          }
        </script>
    </head>
    <body>
        <a href="https://www.noto-fonts.com">Official Website</a>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/123")
        assert result is not None
        name_ko, name_en, maker, official_url = result
        assert name_ko == "나눔고딕"
        assert maker == "네이버"
        assert official_url is not None
        assert "noto-fonts.com" in official_url

    def test_extract_with_minimal_data(self) -> None:
        """화면의 제작 라벨을 JSON-LD 대체 경로로 파싱한다."""
        html = """
<html>
    <body>
        <h1>다른폰트 | 눈누</h1>
        <div><span>제작</span><span>폰트제작사</span></div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/456")
        assert result is not None
        name_ko, name_en, maker, official_url = result
        assert name_ko == "다른폰트"
        assert maker == "폰트제작사"

    def test_extract_without_required_fields(self) -> None:
        """제작사가 없으면 성공 레코드로 세지 않는다."""
        html = """
<html>
    <body>
        <div>Just some content</div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/789")
        assert result is None


def test_robots_policy_blocks_disallowed_paths() -> None:
    """robots.txt에서 막은 경로는 수집하지 않는다."""
    policy = _parse_robots_policy(
        "User-agent: *\nDisallow: /private\nAllow: /font_page/\n"
    )

    assert policy.can_fetch("FontAgitSeedBot", "https://noonnu.cc/font_page/1")
    assert not policy.can_fetch("FontAgitSeedBot", "https://noonnu.cc/private/1")
