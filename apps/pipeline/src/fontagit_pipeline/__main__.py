"""CLI 진입점 및 파이프라인 오케스트레이션."""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import ValidationError

from fontagit_pipeline.client import fetch_webfonts, WebfontsError
from fontagit_pipeline.config import load_settings
from fontagit_pipeline.licenses import fetch_license_map
from fontagit_pipeline.models import GoogleFontRaw, OutputDocument
from fontagit_pipeline.transform import build_records
from fontagit_pipeline.uploader import upload_records
from fontagit_pipeline.writer import write_output

logger = logging.getLogger(__name__)
_OUTPUT_PATH = Path("output") / "tier-a.json"
_SOURCE = "google-fonts-webfonts-api"


def build_document(
    fonts: list[GoogleFontRaw],
    license_map: dict[str, str],
    generated_at: str,
    latin_limit: int = 100,
) -> OutputDocument:
    """폰트 원형 목록을 OutputDocument로 변환한다."""
    records = build_records(fonts, license_map, latin_limit)
    return OutputDocument(
        generated_at=generated_at, source=_SOURCE,
        record_count=len(records), fonts=records,
    )


def main() -> int:
    """파이프라인 메인 진입점.

    환경설정을 로드하고, 구글폰트 API를 조회한 후, 결과를 JSON으로 저장한다.

    Returns:
        0: 성공
        2: API 키 누락 또는 유효성 검사 실패 (ValidationError)
        3: API 조회 실패, 데이터 검증 실패, 또는 파일 저장 실패
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        settings = load_settings()
    except ValidationError:
        logger.error("GOOGLE_FONTS_API_KEY가 없습니다. apps/pipeline/.env를 확인하세요.")
        return 2

    try:
        fonts = fetch_webfonts(settings.google_fonts_api_key)
    except WebfontsError as exc:
        logger.error("webfonts 데이터 검증 실패: %s", exc)
        return 3
    except httpx.HTTPError as exc:
        logger.error("webfonts 조회 실패: %s", exc.__class__.__name__)
        return 3

    license_map = fetch_license_map(settings.github_token)
    logger.info("라이선스 매핑 %d건", len(license_map))

    generated_at = datetime.now(timezone.utc).isoformat()
    doc = build_document(fonts, license_map, generated_at)

    # 빈 응답 처리: record_count가 0이면 기존 파일 보존
    if doc.record_count == 0:
        logger.error("변환된 폰트 레코드가 없습니다 (덮어쓰기 건너뜀).")
        return 3

    try:
        write_output(doc, _OUTPUT_PATH)
    except OSError as exc:
        logger.error("파일 저장 실패: %s", exc.__class__.__name__)
        return 3

    logger.info("저장 완료: %s (%d개)", _OUTPUT_PATH, doc.record_count)

    if settings.supabase_url and settings.supabase_secret_key:
        published = [r for r in doc.fonts if r.status == "published"]
        try:
            uploaded = upload_records(doc.fonts, settings.supabase_url, settings.supabase_secret_key)
        except Exception as exc:  # 외부 경계
            logger.error("Supabase 업로드 실패: %s", exc.__class__.__name__)
            return 3
        logger.info("업로드 %d개(공개 %d개)", uploaded, len(published))
    else:
        logger.info("Supabase 설정 없음 — 업로드 건너뜀(로컬 JSON만).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
