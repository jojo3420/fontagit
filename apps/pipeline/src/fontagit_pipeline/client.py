"""구글폰트 webfonts API 클라이언트."""

import logging
import re

import httpx

from fontagit_pipeline.models import GoogleFontRaw

logger = logging.getLogger(__name__)

_API_URL = "https://www.googleapis.com/webfonts/v1/webfonts"
_KEY_RE = re.compile(r"key=[^&]+")


def mask_key(url: str) -> str:
    """URL 안의 API 키를 마스킹한다(로그 노출 방지)."""
    return _KEY_RE.sub("key=***", url)


def fetch_webfonts(
    api_key: str,
    *,
    client: httpx.Client | None = None,
    sort: str = "popularity",
    timeout: float = 10.0,
    retries: int = 2,
) -> list[GoogleFontRaw]:
    """webfonts API를 조회해 원형 목록을 반환한다.

    타임아웃/HTTP 오류는 제한 재시도 후 예외를 전파한다. 로그에는 키를 마스킹한다.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    params = {"key": api_key, "sort": sort}
    try:
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = client.get(_API_URL, params=params)
                logger.info("webfonts 요청 %s", mask_key(str(resp.request.url)))
                resp.raise_for_status()
                items = resp.json().get("items", [])
                return [GoogleFontRaw(**it) for it in items]
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                logger.warning("요청 실패(시도 %d/%d): %s", attempt + 1, retries + 1, exc)
        assert last_exc is not None
        raise last_exc
    finally:
        if owns_client:
            client.close()
