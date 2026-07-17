"""CLI 진입점 및 파이프라인 오케스트레이션."""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import ValidationError

from fontagit_pipeline.client import fetch_webfonts, WebfontsError
from fontagit_pipeline.config import load_settings
from fontagit_pipeline.korean_names import load_korean_names, KoreanNamesError
from fontagit_pipeline.licenses import fetch_license_map, LicenseFetchError
from fontagit_pipeline.models import GoogleFontRaw, KoreanNameEntry, OutputDocument
from fontagit_pipeline.noonnu_import import import_noonnu_seeds, NoonnuImportError
from fontagit_pipeline.noonnu_seed import collect_noonnu_seeds, NoonnuSeedError
from fontagit_pipeline.transform import build_records
from fontagit_pipeline.uploader import upload_tier_a_snapshot
from fontagit_pipeline.writer import write_output

logger = logging.getLogger(__name__)
_OUTPUT_PATH = Path("output") / "tier-a.json"
_SOURCE = "google-fonts-webfonts-api"


def build_document(
    fonts: list[GoogleFontRaw],
    license_map: dict[str, str],
    generated_at: str,
    latin_limit: int = 100,
    korean_names: dict[str, KoreanNameEntry] | None = None,
    strict: bool = False,
) -> OutputDocument:
    """폰트 원형 목록을 OutputDocument로 변환한다."""
    records = build_records(fonts, license_map, latin_limit, korean_names=korean_names, strict=strict)
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
    # httpx INFO 로그가 API 키 포함 URL을 평문 노출하므로 억제
    logging.getLogger("httpx").setLevel(logging.WARNING)

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

    try:
        license_map = fetch_license_map(settings.github_token)
    except LicenseFetchError:
        logger.error("라이선스 조회 실패 — 데이터 무결성 위해 중단(산출물 미생성)")
        return 3
    logger.info("라이선스 매핑 %d건", len(license_map))

    try:
        korean_names = load_korean_names()
        logger.info("한글 매핑 %d건 로드", len(korean_names))
    except KoreanNamesError as exc:
        logger.error("한글 매핑 로드 실패: %s", exc)
        return 3

    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        doc = build_document(fonts, license_map, generated_at, korean_names=korean_names, strict=True)
    except ValueError as exc:
        logger.error("폰트 변환 실패: %s", exc)
        return 3
    except KoreanNamesError as exc:
        logger.error("한글 매핑 검증 실패: %s", exc)
        return 3

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

    has_url = bool(settings.supabase_url)
    has_key = bool(settings.supabase_secret_key)
    if has_url != has_key:
        logger.error("Supabase 설정 불완전(URL/SECRET_KEY 중 하나만 존재) — 업로드 중단")
        return 3
    if has_url and has_key:
        assert settings.supabase_url is not None
        assert settings.supabase_secret_key is not None
        published = [r for r in doc.fonts if r.status == "published"]
        try:
            uploaded, drafted = upload_tier_a_snapshot(
                doc.fonts, settings.supabase_url, settings.supabase_secret_key
            )
        except Exception as exc:  # 외부 경계
            logger.error("Supabase 업로드 실패: %s", exc.__class__.__name__)
            return 3
        logger.info(
            "업로드 %d개(공개 %d개, stale draft %d개)",
            uploaded,
            len(published),
            drafted,
        )
    else:
        logger.info("Supabase 설정 없음 — 업로드 건너뜀(로컬 JSON만).")
    return 0


def main_noonnu_seed(args: argparse.Namespace) -> int:
    """눈누 Tier B 시드 수집 진입점."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        output = collect_noonnu_seeds(batch_size=args.limit)
        logger.info("수집 완료: %d개", output.record_count)
        return 0
    except NoonnuSeedError as exc:
        logger.error("수집 실패: %s", exc)
        return 3
    except Exception as exc:
        logger.error("예상치 못한 오류: %s", exc)
        return 3


def main_noonnu_import(args: argparse.Namespace) -> int:
    """눈누 Tier B draft 임포트 진입점."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        settings = load_settings()
    except ValidationError:
        logger.error(
            "Supabase 설정이 없습니다. apps/pipeline/.env를 확인하세요."
        )
        return 2

    try:
        upserted, skipped = import_noonnu_seeds(
            supabase_url=settings.supabase_url,
            supabase_secret_key=settings.supabase_secret_key,
        )
        logger.info(
            "임포트 완료: %d개 삽입/업데이트, %d개 스킵",
            upserted,
            skipped,
        )
        return 0
    except NoonnuImportError as exc:
        logger.error("임포트 실패: %s", exc)
        return 3
    except Exception as exc:
        logger.error("예상치 못한 오류: %s", exc)
        return 3


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FontAgit 파이프라인",
        prog="fontagit-pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", help="명령어")

    # tier-a 명령 (기본 명령)
    tier_a_parser = subparsers.add_parser(
        "tier-a",
        help="Tier A (Google Fonts) 처리 및 업로드",
    )

    # noonnu-seed 명령
    seed_parser = subparsers.add_parser(
        "noonnu-seed",
        help="눈누 Tier B 시드 수집",
    )
    seed_parser.add_argument(
        "--limit", type=int, default=30, help="수집할 폰트 페이지 최대 수"
    )
    seed_parser.set_defaults(func=main_noonnu_seed)

    # noonnu-import 명령
    import_parser = subparsers.add_parser(
        "noonnu-import",
        help="눈누 Tier B draft 임포트",
    )
    import_parser.set_defaults(func=main_noonnu_import)

    args = parser.parse_args()

    if hasattr(args, "func"):
        sys.exit(args.func(args))
    elif args.command == "tier-a" or not args.command:
        # tier-a 또는 명령어 없음 = 기본 파이프라인
        sys.exit(main())
    else:
        parser.print_help()
        sys.exit(1)
