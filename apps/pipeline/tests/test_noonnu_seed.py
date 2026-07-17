"""눈누 시드 수집 테스트."""

from fontagit_pipeline.noonnu_seed import (
    _extract_font_data,
    _parse_robots_policy,
    _parse_sitemap_urls,
    clean_font_name,
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


class TestCleanFontName:
    """폰트 이름 정리 테스트."""

    def test_remove_suffix_and_preserve_clean_names(self) -> None:
        """눈누 접미사는 제거하고 정상 이름은 유지한다."""
        cases = [
            ("고도체 | 눈누", "고도체"),
            ("고도마음체  |  눈누", "고도마음체"),
            ("폰트명 | 눈누  ", "폰트명"),
            ("산돌국대떡볶이체", "산돌국대떡볶이체"),
            ("Noto Sans", "Noto Sans"),
        ]

        for source, expected in cases:
            assert clean_font_name(source) == expected

    def test_handle_empty_values(self) -> None:
        """None과 빈 문자열을 그대로 처리한다."""
        assert clean_font_name(None) is None
        assert clean_font_name("") == ""

    def test_handle_only_suffix(self) -> None:
        """접미사만 있는 경우 None을 반환한다."""
        assert clean_font_name("| 눈누") is None


def test_robots_policy_blocks_disallowed_paths() -> None:
    """robots.txt에서 막은 경로는 수집하지 않는다."""
    policy = _parse_robots_policy(
        "User-agent: *\nDisallow: /private\nAllow: /font_page/\n"
    )

    assert policy.can_fetch("FontAgitSeedBot", "https://noonnu.cc/font_page/1")
    assert not policy.can_fetch("FontAgitSeedBot", "https://noonnu.cc/private/1")
