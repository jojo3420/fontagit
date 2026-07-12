"""webfonts API 클라이언트 TDD 테스트."""

import httpx
import pytest

from fontagit_pipeline.client import fetch_webfonts, mask_key


def test_mask_key_hides_api_key():
    """mask_key는 URL의 API 키를 마스킹한다."""
    url = "https://www.googleapis.com/webfonts/v1/webfonts?key=SECRET123&sort=popularity"
    assert "SECRET123" not in mask_key(url)
    assert "key=***" in mask_key(url)


def test_fetch_webfonts_parses_items():
    """fetch_webfonts는 API 응답의 items를 파싱한다."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "family": "Roboto",
                        "variants": ["regular"],
                        "subsets": ["latin"],
                        "version": "v30",
                        "lastModified": "2024-09-01",
                        "files": {"regular": "https://x/r.ttf"},
                        "category": "sans-serif",
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fonts = fetch_webfonts("SECRET123", client=client)
    assert [f.family for f in fonts] == ["Roboto"]


def test_fetch_webfonts_raises_on_http_error():
    """fetch_webfonts는 HTTP 오류 후 재시도 제한을 초과하면 예외를 전파한다."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_webfonts("SECRET123", client=client, retries=0)
