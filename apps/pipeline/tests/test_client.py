"""webfonts API 클라이언트 TDD 테스트."""

import httpx
import pytest

from fontagit_pipeline.client import fetch_webfonts, mask_key, WebfontsError


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
    with pytest.raises(WebfontsError):
        fetch_webfonts("SECRET123", client=client, retries=0)


def test_fetch_webfonts_logs_no_api_key_on_500_error(caplog):
    """500 오류 시 로그에 API 키가 포함되지 않는다."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(WebfontsError):
        fetch_webfonts("SECRET123", client=client, retries=0)

    # 모든 로그 레코드에서 SECRET123이 나타나지 않아야 함
    for record in caplog.records:
        assert "SECRET123" not in record.message


def test_fetch_webfonts_rejects_non_dict_response():
    """응답 본문이 dict가 아니면 WebfontsError를 발생시킨다."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])  # list instead of dict

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(WebfontsError, match="응답 본문은 dict여야"):
        fetch_webfonts("SECRET123", client=client)


def test_fetch_webfonts_rejects_missing_items():
    """items 필드가 없으면 WebfontsError를 발생시킨다."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})  # missing "items"

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(WebfontsError, match='응답에 "items" 필드가'):
        fetch_webfonts("SECRET123", client=client)


def test_fetch_webfonts_rejects_non_list_items():
    """items이 list가 아니면 WebfontsError를 발생시킨다."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": {}})  # dict instead of list

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(WebfontsError, match='"items"은 list여야'):
        fetch_webfonts("SECRET123", client=client)


def test_fetch_webfonts_does_not_retry_404():
    """404는 재시도하지 않고 즉시 WebfontsError를 발생시킨다."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(WebfontsError, match="HTTP 404"):
        fetch_webfonts("SECRET123", client=client, retries=2)

    # 정확히 1회만 호출되어야 함 (재시도 없음)
    assert call_count == 1
