"""구글폰트 webfonts API 클라이언트."""

import json
import logging
import re

import httpx

from fontagit_pipeline.models import GoogleFontRaw

logger = logging.getLogger(__name__)

_API_URL = "https://www.googleapis.com/webfonts/v1/webfonts"
_KEY_RE = re.compile(r"key=[^&]+")


class WebfontsError(Exception):
    """webfonts API 데이터 검증 또는 파싱 오류."""

    pass


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

    Raises:
        WebfontsError: JSON 파싱, 응답 형식 검증, 또는 아이템 검증 실패.
        httpx.HTTPError: HTTP 오류.
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

                # JSON 파싱
                try:
                    body = resp.json()
                except json.JSONDecodeError as exc:
                    raise WebfontsError("응답 JSON 파싱 실패") from exc

                # 응답 형식 검증
                if not isinstance(body, dict):
                    raise WebfontsError(f"응답 본문은 dict여야 합니다 (got {type(body).__name__})")

                if "items" not in body:
                    raise WebfontsError('응답에 "items" 필드가 없습니다')

                items = body["items"]
                if not isinstance(items, list):
                    raise WebfontsError(f'"items"은 list여야 합니다 (got {type(items).__name__})')

                # 아이템 검증
                try:
                    return [GoogleFontRaw(**it) for it in items]
                except Exception as exc:
                    raise WebfontsError(f"아이템 검증 실패: {exc}") from exc

            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                # 4xx 클라이언트 오류 (429 제외)는 재시도하지 않음
                if isinstance(exc, httpx.HTTPStatusError):
                    status = exc.response.status_code
                    if 400 <= status < 500 and status != 429:
                        # 요청 URL 마스킹하여 로그
                        masked_url = mask_key(str(exc.request.url))
                        logger.warning(
                            "요청 실패(재시도 안함, 상태 %d): %s",
                            status,
                            masked_url,
                        )
                        raise WebfontsError(f"HTTP {status} 오류") from exc
                    else:
                        logger.warning(
                            "요청 실패(시도 %d/%d): %s",
                            attempt + 1,
                            retries + 1,
                            exc.__class__.__name__,
                        )
                        last_exc = exc
                else:
                    logger.warning(
                        "요청 실패(시도 %d/%d): %s",
                        attempt + 1,
                        retries + 1,
                        exc.__class__.__name__,
                    )
                    last_exc = exc
            except WebfontsError as exc:
                # 검증 오류는 즉시 전파 (재시도 안함)
                logger.warning("데이터 검증 실패: %s", exc)
                raise

        assert last_exc is not None
        raise WebfontsError(f"최대 재시도 초과 ({retries + 1}회)") from last_exc
    finally:
        if owns_client:
            client.close()
