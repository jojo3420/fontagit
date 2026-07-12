"""CLI 진입점 및 파이프라인 오케스트레이션."""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import ValidationError

from fontagit_pipeline.client import fetch_webfonts
from fontagit_pipeline.config import load_settings
from fontagit_pipeline.models import GoogleFontRaw, OutputDocument
from fontagit_pipeline.transform import build_records
from fontagit_pipeline.writer import write_output

logger = logging.getLogger(__name__)
_OUTPUT_PATH = Path("output") / "tier-a.json"
_SOURCE = "google-fonts-webfonts-api"


def build_document(
    fonts: list[GoogleFontRaw], generated_at: str, latin_limit: int = 100
) -> OutputDocument:
    """폰트 원형 목록을 OutputDocument로 변환한다.

    Args:
        fonts: 구글폰트 API에서 받은 원형 폰트 목록.
        generated_at: 생성 타임스탐프(ISO 8601).
        latin_limit: 라틴 폰트 선택 제한(기본값 100).

    Returns:
        변환된 OutputDocument 인스턴스.
    """
    records = build_records(fonts, latin_limit)
    return OutputDocument(
        generated_at=generated_at,
        source=_SOURCE,
        record_count=len(records),
        fonts=records,
    )


def main() -> int:
    """파이프라인 메인 진입점.

    환경설정을 로드하고, 구글폰트 API를 조회한 후, 결과를 JSON으로 저장한다.

    Returns:
        0: 성공
        2: API 키 누락 (ValidationError)
        3: 네트워크 오류 (httpx.HTTPError)
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        settings = load_settings()
    except ValidationError:
        logger.error("GOOGLE_FONTS_API_KEY가 없습니다. apps/pipeline/.env를 확인하세요.")
        return 2

    try:
        fonts = fetch_webfonts(settings.google_fonts_api_key)
    except httpx.HTTPError as exc:
        logger.error("webfonts 조회 실패: %s", exc)
        return 3

    generated_at = datetime.now(timezone.utc).isoformat()
    doc = build_document(fonts, generated_at)
    write_output(doc, _OUTPUT_PATH)
    logger.info("저장 완료: %s (%d개)", _OUTPUT_PATH, doc.record_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
