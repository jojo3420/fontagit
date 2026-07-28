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
        <div class="noon-page-content">
            <a href="https://www.noto-fonts.com">Official Website</a>
        </div>
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
        <div class="noon-page-content">
            <a href="https://noonnu.cc/other-font">Internal Link</a>
            <a href="/font_page/999">Relative Link</a>
            <a href="https://example.com">External Link</a>
        </div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/111")
        assert result is not None
        name_ko, name_en, maker, official_url = result
        # 외부 링크만 선택되어야 함
        if official_url and official_url != "https://noonnu.cc/font_page/111":
            assert "example.com" in official_url

    def test_extract_official_url_ignores_footer_sns_links(self) -> None:
        """본문과 푸터가 분리된 실제 구조에서 본문 링크만 채택한다(#148 핵심 회귀)."""
        html = """
<html>
    <body>
        <h1>또박또박</h1>
        <div>Foundry: 네이버</div>
        <div class="noon-page-content max-w-9xl">
            <a href="/index?search=test">관련 폰트</a>
            <a href="https://clova.ai/handwriting/list.html">공식 홈페이지</a>
        </div>
        <div class="bg-gray-noon">
            <a href="https://forms.gle/abc123">문의하기</a>
            <a href="https://maily.so/noonnu">뉴스레터</a>
            <a href="https://www.instagram.com/noonnu_official/">인스타그램</a>
            <a href="https://www.facebook.com/projectnoonnu">페이스북</a>
        </div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/600")
        assert result is not None
        _, _, _, official_url = result
        assert official_url == "https://clova.ai/handwriting/list.html"
        assert official_url != "https://www.instagram.com/noonnu_official/"

    def test_extract_official_url_none_without_content_container(self) -> None:
        """본문 컨테이너가 없으면 페이지 전체로 폴백하지 않고 None을 반환한다."""
        html = """
<html>
    <body>
        <h1>테스트폰트</h1>
        <div>Foundry: Test Maker</div>
        <a href="https://clova.ai/handwriting/list.html">본문 밖 링크</a>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/601")
        assert result is not None
        _, _, _, official_url = result
        assert official_url is None

    def test_extract_official_url_none_when_only_noonnu_links_in_content(
        self,
    ) -> None:
        """본문에 눈누 자체 링크만 있으면 None을 반환한다."""
        html = """
<html>
    <body>
        <h1>테스트폰트</h1>
        <div>Foundry: Test Maker</div>
        <div class="noon-page-content">
            <a href="https://www.instagram.com/noonnu_official/">인스타그램</a>
            <a href="https://noonnu.cc/other-font">관련 폰트</a>
        </div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/602")
        assert result is not None
        _, _, _, official_url = result
        assert official_url is None

    def test_extract_official_url_accepts_non_whitelisted_tld(self) -> None:
        """제거된 TLD 화이트리스트에 없던 도메인(.ai 등)도 정상 선택된다."""
        html = """
<html>
    <body>
        <h1>테스트폰트</h1>
        <div>Foundry: Test Maker</div>
        <div class="noon-page-content">
            <a href="https://clova.ai/handwriting/list.html">공식 홈페이지</a>
        </div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/603")
        assert result is not None
        _, _, _, official_url = result
        assert official_url == "https://clova.ai/handwriting/list.html"

    def test_extract_official_url_blocks_uppercase_noonnu_domain(self) -> None:
        """대소문자 표기가 섞인 눈누 자체 링크도 차단 목록에 걸려야 한다(HIGH 회귀)."""
        html = """
<html>
    <body>
        <h1>테스트폰트</h1>
        <div>Foundry: Test Maker</div>
        <div class="noon-page-content">
            <a href="https://INSTAGRAM.COM/noonnu_official">인스타그램(대문자)</a>
            <a href="https://Instagram.Com/Noonnu_Official">인스타그램(혼합)</a>
        </div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/604")
        assert result is not None
        _, _, _, official_url = result
        assert official_url is None

    def test_extract_official_url_ignores_asset_link_with_query_string(
        self,
    ) -> None:
        """쿼리스트링이 붙은 에셋 URL(.png?v=1 등)도 제외되어야 한다(LOW 회귀)."""
        html = """
<html>
    <body>
        <h1>테스트폰트</h1>
        <div>Foundry: Test Maker</div>
        <div class="noon-page-content">
            <a href="https://cdn.example.com/logo.png?v=1">로고 이미지</a>
            <a href="https://cdn.example.com/style.css?hash=abc">스타일시트</a>
            <a href="https://clova.ai/handwriting/list.html">공식 홈페이지</a>
        </div>
    </body>
</html>
"""
        result = _extract_font_data(html, "https://noonnu.cc/font_page/605")
        assert result is not None
        _, _, _, official_url = result
        assert official_url == "https://clova.ai/handwriting/list.html"


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
