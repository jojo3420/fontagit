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
from fontagit_pipeline.noonnu_enrich import enrich_fonts, NoonnuEnrichError
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


def main_noonnu_enrich(args: argparse.Namespace) -> int:
    """눈누 Tier B 라이선스 제안 적재 진입점."""
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
        auto, proposed, skipped = enrich_fonts(
            supabase_url=settings.supabase_url,
            secret_key=settings.supabase_secret_key,
            limit=args.limit,
            only_slug=args.slug,
        )
        logger.info(
            "enrich 완료: 자동발행 %d개, 검수대기 %d개, 스킵 %d개",
            auto,
            proposed,
            skipped,
        )
        return 0
    except NoonnuEnrichError as exc:
        logger.error("enrich 실패: %s", exc)
        return 3
    except Exception as exc:
        logger.error("예상치 못한 오류: %s", exc)
        return 3


def main_noonnu_review(args: argparse.Namespace) -> int:
    """눈누 라이선스 제안 검수 진입점."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    from supabase import create_client

    from .noonnu_review import (
        approve,
        list_pending,
        reject,
        sample_auto_published,
        unpublish,
    )

    try:
        settings = load_settings()
    except ValidationError:
        logger.error(
            "Supabase 설정이 없습니다. apps/pipeline/.env를 확인하세요."
        )
        return 2

    if not settings.supabase_url or not settings.supabase_secret_key:
        logger.error("Supabase URL 및 secret key가 필요합니다.")
        return 2

    try:
        client = create_client(settings.supabase_url, settings.supabase_secret_key)
        schema = client.schema("fontagit")

        action = args.action

        if action == "list":
            proposals = list_pending(schema)
            logger.info("검수 대기: %d건", len(proposals))
            for p in proposals:
                logger.info(
                    "  - %s (%s): %s",
                    p.get("slug"),
                    p.get("proposed_license_type"),
                    p.get("source_url"),
                )
            return 0

        elif action == "approve":
            approve(schema, args.slug, note=args.note)
            return 0

        elif action == "reject":
            if not args.note:
                logger.error("--note는 필수입니다")
                return 1
            reject(schema, args.slug, note=args.note)
            return 0

        elif action == "audit-sample":
            pct = getattr(args, "pct", 5)
            samples = sample_auto_published(schema, pct=pct)
            logger.info("표본 감시: %d건 (전체의 %d%%)", len(samples), pct)
            for s in samples:
                logger.info(
                    "  - %s (%s): %s",
                    s.get("slug"),
                    s.get("name_ko"),
                    s.get("official_url"),
                )
            return 0

        elif action == "unpublish":
            if not args.note:
                logger.error("--note는 필수입니다")
                return 1
            unpublish(schema, args.slug, note=args.note)
            return 0

        else:
            logger.error("미지원 액션: %s", action)
            return 1

    except Exception as exc:
        logger.error("검수 실패: %s", exc)
        return 3


def main_noonnu_publish(args: argparse.Namespace) -> int:
    """prod 폰트 발행 명령 진입점."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    from supabase import create_client

    from .noonnu_publish import publish_to_prod

    try:
        settings = load_settings()
    except ValidationError:
        logger.error(
            "설정 로드 실패: apps/pipeline/.env를 확인하세요."
        )
        return 2

    # dev 접속 설정
    if not settings.supabase_url or not settings.supabase_secret_key:
        logger.error("Dev Supabase 설정이 필요합니다.")
        return 2

    # prod 접속 설정 (필수)
    if not settings.supabase_prod_url or not settings.supabase_prod_secret_key:
        logger.error(
            "Prod Supabase 설정이 필요합니다 "
            "(SUPABASE_PROD_URL, SUPABASE_PROD_SECRET_KEY)."
        )
        return 2

    try:
        # Dev 스키마 접속
        dev_client = create_client(settings.supabase_url, settings.supabase_secret_key)
        dev_schema = dev_client.schema("fontagit")

        # prod 환경 오염 방지: dev URL로 prod 쓰기 금지
        if settings.supabase_prod_url == settings.supabase_url:
            logger.error(
                "prod URL이 dev URL과 동일합니다. 설정을 확인하세요."
            )
            return 2

        # dry_run 여부 결정
        dry_run = not getattr(args, "confirm", False)

        if not dry_run:
            # 실제 쓰기를 위한 대화형 확인
            total_rows, _ = publish_to_prod(
                dev_schema,
                settings.supabase_prod_url,
                settings.supabase_prod_secret_key,
                dry_run=True,
            )
            confirm_input = input(
                f"prod에 {total_rows}건 발행합니다. 계속하려면 'yes' 입력: "
            )
            if confirm_input.strip() != "yes":
                logger.info("사용자 취소")
                return 1

        # 실행
        total, written = publish_to_prod(
            dev_schema,
            settings.supabase_prod_url,
            settings.supabase_prod_secret_key,
            dry_run=dry_run,
        )
        logger.info("완료: 대상 %d개, 쓰기 %d개", total, written)
        return 0

    except Exception as exc:
        logger.error("발행 실패: %s", exc)
        return 3


def main_audit_policy_check(args: argparse.Namespace) -> int:
    """사람 승인 전 수집 정책 점검 문서를 만든다."""
    from fontagit_pipeline.audit_policy import write_policy_check
    from fontagit_pipeline.config import load_audit_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        load_audit_settings()
        policy = write_policy_check(args.out)
    except (OSError, ValueError) as exc:
        logger.error("감사 정책 파일 생성 실패: %s", exc)
        return 3

    logger.info(
        "정책 점검 파일 생성: %s (robots=%s, terms=%s, crawl=%s, raw=%s)",
        args.out,
        policy.robots_sha256,
        policy.terms_sha256,
        policy.crawl_allowed,
        policy.raw_retention_allowed,
    )
    return 0


def main_audit_export_baseline(args: argparse.Namespace) -> int:
    """공개 anon API만 사용해 prod 기준선을 내보낸다."""
    from fontagit_pipeline.audit_bootstrap import (
        BootstrapError,
        calculate_baseline_content_sha256,
        fetch_prod_public_rows,
        write_prod_baseline,
    )
    from fontagit_pipeline.config import load_audit_settings

    if args.source != "prod-public":
        logger.error("허용되지 않은 기준선 출처입니다: %s", args.source)
        return 2
    try:
        settings = load_audit_settings()
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise BootstrapError("SUPABASE_URL과 SUPABASE_ANON_KEY가 필요합니다")
        rows = fetch_prod_public_rows(settings.supabase_url, settings.supabase_anon_key)
        baseline_content_sha256 = calculate_baseline_content_sha256(rows)
        file_sha256 = write_prod_baseline(rows, args.out)
    except (BootstrapError, OSError, httpx.HTTPError) as exc:
        logger.error("prod 공개 기준선 내보내기 실패: %s", exc)
        return 3

    logger.info(
        "prod 공개 기준선 저장: %s (%d개, baseline_content_sha256=%s, file_sha256=%s)",
        args.out,
        len(rows),
        baseline_content_sha256,
        file_sha256,
    )
    return 0


def main_audit_bootstrap(args: argparse.Namespace) -> int:
    """고정 snapshot만 비교해 안정 출처키 manifest를 생성한다."""
    from fontagit_pipeline.audit_bootstrap import (
        BootstrapError,
        build_bootstrap_manifest,
        load_prod_baseline,
        load_snapshot_records,
        write_bootstrap_manifest,
    )

    try:
        prod_rows = load_prod_baseline(args.prod_snapshot)
        tier_a = load_snapshot_records(Path("output") / "tier-a.json", "fonts")
        tier_b = load_snapshot_records(
            Path("output") / "tier-b-noonnu-seed.json", "records"
        )
        result = build_bootstrap_manifest(prod_rows, tier_a, tier_b)
        total = result.matched + result.unmatched + result.conflicts
        if total != len(prod_rows):
            raise BootstrapError("bootstrap 결과 수가 prod 기준선과 일치하지 않습니다")
        file_sha256 = write_bootstrap_manifest(result, args.out)
    except (BootstrapError, OSError) as exc:
        logger.error("안정 출처키 bootstrap 실패: %s", exc)
        return 3

    logger.info(
        "bootstrap 저장: %s (연결=%d, 미연결=%d, 충돌=%d, sha256=%s)",
        args.out,
        result.matched,
        result.unmatched,
        result.conflicts,
        file_sha256,
    )
    return 0


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

    # noonnu-enrich 명령
    enrich_parser = subparsers.add_parser(
        "noonnu-enrich",
        help="눈누 Tier B 라이선스 제안 적재",
    )
    enrich_parser.add_argument(
        "--limit", type=int, default=None, help="처리할 최대 폰트 수"
    )
    enrich_parser.add_argument(
        "--slug", type=str, default=None, help="특정 슬러그만 처리"
    )
    enrich_parser.set_defaults(func=main_noonnu_enrich)

    # noonnu-review 명령
    review_parser = subparsers.add_parser(
        "noonnu-review",
        help="눈누 라이선스 제안 검수",
    )
    review_parser.add_argument(
        "action",
        choices=["list", "approve", "reject", "audit-sample", "unpublish"],
        help="실행 액션",
    )
    review_parser.add_argument(
        "--slug", type=str, default=None, help="폰트 슬러그(approve/reject/unpublish에서 필수)"
    )
    review_parser.add_argument(
        "--note", type=str, default=None, help="검수자 코멘트(approve에서 선택, reject/unpublish에서 필수)"
    )
    review_parser.add_argument(
        "--pct", type=int, default=5, help="표본 백분율(audit-sample, 기본값 5)"
    )
    review_parser.set_defaults(func=main_noonnu_review)

    # noonnu-publish 명령
    publish_parser = subparsers.add_parser(
        "noonnu-publish",
        help="눈누 Tier B prod 발행 (dev→prod 동기화, 기본 dry-run)",
    )
    publish_parser.add_argument(
        "--confirm",
        action="store_true",
        help="실제 prod 쓰기 활성화 (이중 확인 필수)",
    )
    publish_parser.set_defaults(func=main_noonnu_publish)

    # 감사 수집 정책 확인 명령
    policy_parser = subparsers.add_parser(
        "font-audit-policy-check",
        help="robots와 이용 조건 승인 전 정책 파일 생성",
    )
    policy_parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="정책 점검 JSON 출력 경로",
    )
    policy_parser.set_defaults(func=main_audit_policy_check)

    baseline_parser = subparsers.add_parser(
        "font-audit-export-baseline",
        help="prod 공개 API를 읽기 전용으로 조회해 기준선 JSON 생성",
    )
    baseline_parser.add_argument(
        "--source",
        choices=["prod-public"],
        required=True,
        help="읽기 전용 공개 prod 출처",
    )
    baseline_parser.add_argument(
        "--out", type=Path, required=True, help="기준선 JSON 출력 경로"
    )
    baseline_parser.set_defaults(func=main_audit_export_baseline)

    bootstrap_parser = subparsers.add_parser(
        "font-audit-bootstrap",
        help="고정 prod·Tier A·Tier B snapshot으로 안정 출처키 manifest 생성",
    )
    bootstrap_parser.add_argument(
        "--prod-snapshot", type=Path, required=True, help="prod 공개 기준선 JSON 경로"
    )
    bootstrap_parser.add_argument(
        "--out", type=Path, required=True, help="bootstrap JSON 출력 경로"
    )
    bootstrap_parser.set_defaults(func=main_audit_bootstrap)

    args = parser.parse_args()

    if hasattr(args, "func"):
        sys.exit(args.func(args))
    elif args.command == "tier-a" or not args.command:
        # tier-a 또는 명령어 없음 = 기본 파이프라인
        sys.exit(main())
    else:
        parser.print_help()
        sys.exit(1)
