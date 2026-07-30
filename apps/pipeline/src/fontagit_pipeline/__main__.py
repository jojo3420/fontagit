"""CLI 진입점 및 파이프라인 오케스트레이션."""

import argparse
import logging
import os
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from pydantic import ValidationError

from fontagit_pipeline.client import fetch_webfonts, WebfontsError
from fontagit_pipeline.config import load_settings
from fontagit_pipeline.korean_names import load_korean_names, KoreanNamesError
from fontagit_pipeline.licenses import fetch_license_map, LicenseFetchError
from fontagit_pipeline.models import GoogleFontRaw, KoreanNameEntry, OutputDocument
from fontagit_pipeline.noonnu_enrich import enrich_fonts, NoonnuEnrichError
from fontagit_pipeline.noonnu_import import import_noonnu_seeds, NoonnuImportError
from fontagit_pipeline.noonnu_seed import _USER_AGENT, collect_noonnu_seeds, NoonnuSeedError
from fontagit_pipeline.noonnu_url_scan import (
    IngestContext,
    ScanAbortedError,
    ScanLockError,
    ScanRecord,
    acquire_scan_lock,
    build_robots_checker,
    fetch_scan_html,
    fetch_scan_page,
    load_actionable_records,
    load_scan_targets,
    load_state_records,
    scan_targets,
    select_actionable,
    summarize,
)
from fontagit_pipeline.transform import build_records
from fontagit_pipeline.uploader import upload_tier_a_snapshot
from fontagit_pipeline.writer import write_output

if TYPE_CHECKING:
    from uuid import UUID

    from fontagit_pipeline.audit_manifest_preflight import PreflightReport
    from fontagit_pipeline.audit_store import ExcludedFontSource

logger = logging.getLogger(__name__)
_OUTPUT_PATH = Path("output") / "tier-a.json"
_SOURCE = "google-fonts-webfonts-api"
_BROKEN_RATIO_THRESHOLD = 0.10


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


def main_noonnu_url_scan(args: argparse.Namespace) -> int:
    """눈누 공식 URL 전수 대조 진입점.

    종료 코드:
        0: 성공, 재시도 대상 없이 전부 처리됨.
        1: CLI 인자 검증 실패(음수 --limit, --state와 --out 경로 동일).
        2: --target 환경의 supabase_url/secret_key 설정 없음.
        3: 예상치 못한 오류.
        4: no_container 비율이 임계치를 넘어 구조 가정이 깨진 것으로 판단.
        5: robots.txt 거부 또는 회로차단기 발동으로 스캔 중단(부분 리포트 기록됨).
        6: 스캔은 끝까지 돌았지만 재시도 대상(retryable_error)이 남음.
        7: 다른 스캔이 실행 중이라 잠금을 얻지 못함.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    if args.limit < 0:
        logger.error("--limit은 음수일 수 없습니다: %d", args.limit)
        return 1
    if args.state == args.out:
        logger.error("--state와 --out은 같은 경로일 수 없습니다: %s", args.state)
        return 1

    try:
        with acquire_scan_lock(args.state):
            return _run_url_scan(args)
    except ScanLockError as exc:
        logger.error("잠금 획득 실패: %s", exc)
        return 7
    except Exception as exc:
        logger.error("예상치 못한 오류: %s", exc)
        return 3


def _run_url_scan(args: argparse.Namespace) -> int:
    """잠금을 쥔 상태에서 실제 스캔을 수행하고 리포트를 남긴다."""
    if args.store_findings and args.target != "dev":
        logger.error("--store-findings는 dev에서만 허용됩니다: %s", args.target)
        return 1
    if args.retry_failed and args.only_actionable is None:
        logger.error("--retry-failed는 --only-actionable과 함께 써야 합니다")
        return 1

    import json
    from typing import cast

    from supabase import create_client

    from fontagit_pipeline.config import load_audit_settings

    settings = load_audit_settings()
    if args.target == "prod":
        url, secret = settings.supabase_prod_url, settings.supabase_prod_secret_key
    else:
        url, secret = settings.supabase_dev_url, settings.supabase_dev_secret_key
    if not url or not secret:
        logger.error(
            "%s 환경의 supabase_%s_url 또는 supabase_%s_secret_key가 없습니다",
            args.target,
            args.target,
            args.target,
        )
        return 2
    client = create_client(url, secret)
    targets = load_scan_targets(client)
    if args.limit:
        targets = targets[: args.limit]
    logger.info("스캔 대상 %d종", len(targets))

    if args.only_actionable is not None:
        previous = load_actionable_records(
            args.only_actionable, retry_failed_only=args.retry_failed
        )
        wanted = {record.font_id for record in previous}
        targets = [target for target in targets if target.font_id in wanted]
        logger.info("재스캔 대상 %d종으로 좁혔습니다", len(targets))

    ingest: IngestContext | None = None
    run_id: UUID | None = None

    try:
        with httpx.Client(headers={"User-Agent": _USER_AGENT}) as http:
            robots_checker = build_robots_checker(http)

            if args.store_findings:
                import hashlib
                from uuid import uuid4

                from fontagit_pipeline.audit_store import SupabaseAuditStore

                store = SupabaseAuditStore.from_dev_credentials(url, secret)
                baseline_sha256 = hashlib.sha256(
                    json.dumps(
                        sorted(target.font_id for target in targets),
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()
                run_id = store.start_run(
                    stage="metadata",
                    target_count=len(targets),
                    baseline_sha256=baseline_sha256,
                    dry_run=False,
                )
                logger.info("감사 run 시작: %s (대상 %d종)", run_id, len(targets))
                ingest = IngestContext(
                    store=store,
                    run_id=run_id,
                    page_fetcher=lambda page_url: fetch_scan_page(http, page_url),
                )

            records = scan_targets(
                targets,
                fetcher=lambda url: fetch_scan_html(http, url),
                state_path=args.state,
                robots_checker=robots_checker,
                ingest=ingest,
            )
    except ScanAbortedError as exc:
        logger.error("스캔 중단: %s", exc)
        partial_records = load_state_records(args.state)
        partial_summary = summarize(partial_records)
        _write_scan_report(args.out, partial_summary, partial_records)
        logger.info("중단 시점까지 요약: %s", json.dumps(partial_summary, ensure_ascii=False))
        return 5

    summary = summarize(records)

    if ingest is not None and run_id is not None:
        from fontagit_pipeline.noonnu_url_ingest import build_finding_drafts

        actionable = select_actionable(records)
        expected_findings = sum(
            len(build_finding_drafts(record, uuid4())) for record in actionable
        )
        logger.info(
            "적재 완료: 대상 %d종, 예상 finding %d건",
            len(actionable),
            expected_findings,
        )
        # complete_run은 집계 4종을 정수로 요구한다(audit_store.py:530-533).
        raw_actions = summary["recommended_action"]
        action_counts = raw_actions if isinstance(raw_actions, Mapping) else {}
        total = int(cast(int, summary["total"]))
        error_count = int(cast(int, summary["error_count"]))
        ingest.store.complete_run(
            run_id,
            {
                "success_count": total - error_count,
                "verified_count": int(action_counts.get("auto_fix_safe", 0)),
                "needs_review_count": int(action_counts.get("manual_review", 0)),
                "broken_count": error_count,
                "summary": summary,
            },
        )

    _write_scan_report(args.out, summary, records)
    logger.info("요약: %s", json.dumps(summary, ensure_ascii=False))
    if not summary["structure_assumption_ok"]:
        logger.error(
            "no_container 비율 %.1f%%가 임계치를 넘었습니다. 정정을 진행하지 마세요.",
            cast(float, summary["no_container_ratio"]) * 100,
        )
        return 4
    if cast(int, summary["retryable_count"]) > 0:
        logger.warning(
            "재시도 대상 %d건이 남았습니다. 상태 파일에서 재실행하세요: %s",
            summary["retryable_count"],
            args.state,
        )
        return 6
    return 0


def _write_scan_report(
    out_path: Path, summary: dict[str, object], records: list[ScanRecord]
) -> None:
    """판정 리포트를 JSON으로 저장한다. 정상 종료-중단 두 경로에서 공유한다."""
    import json
    from dataclasses import asdict

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            {"summary": summary, "records": [asdict(record) for record in records]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


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
            findings = list_pending(schema)
            logger.info("검수 대기: %d건", len(findings))
            for finding in findings:
                logger.info(
                    "  - finding=%s font=%s field=%s",
                    finding.get("id"),
                    finding.get("font_id"),
                    finding.get("field_name"),
                )
            return 0

        elif action == "approve":
            if not args.finding_id or not args.reviewed_by:
                logger.error("approve는 --finding-id와 --reviewed-by가 필수입니다")
                return 1
            approve(
                schema,
                args.finding_id,
                reviewed_by=args.reviewed_by,
                note=args.note,
            )
            return 0

        elif action == "reject":
            if not args.finding_id or not args.reviewed_by or not args.note:
                logger.error(
                    "reject는 --finding-id, --reviewed-by, --note가 필수입니다"
                )
                return 1
            reject(
                schema,
                args.finding_id,
                reviewed_by=args.reviewed_by,
                note=args.note,
            )
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

    try:
        # Dev 스키마 접속
        dev_client = create_client(settings.supabase_url, settings.supabase_secret_key)
        dev_schema = dev_client.schema("fontagit")
        dry_run = not getattr(args, "confirm", False)
        total, written = publish_to_prod(
            dev_schema,
            settings.supabase_prod_url or "",
            settings.supabase_prod_secret_key or "",
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
    """prod 공개 또는 dev 서비스 기준선을 내보낸다."""
    from fontagit_pipeline.audit_bootstrap import (
        BootstrapError,
        calculate_baseline_content_sha256,
        fetch_dev_service_rows,
        fetch_prod_public_rows,
        write_prod_baseline,
    )
    from fontagit_pipeline.config import load_audit_settings

    if args.source not in ("prod-public", "dev-service"):
        logger.error("허용되지 않은 기준선 출처입니다: %s", args.source)
        return 2
    try:
        settings = load_audit_settings()
        if args.source == "prod-public":
            if not settings.supabase_url or not settings.supabase_anon_key:
                raise BootstrapError("SUPABASE_URL과 SUPABASE_ANON_KEY가 필요합니다")
            rows = fetch_prod_public_rows(settings.supabase_url, settings.supabase_anon_key)
            # prod 기준선: 고정 개수/tier 기대치 검증
            baseline_content_sha256 = calculate_baseline_content_sha256(rows)
            file_sha256 = write_prod_baseline(rows, args.out)
        else:  # dev-service
            dev_url, dev_secret = settings.dev_write_credentials()
            rows = fetch_dev_service_rows(dev_url, dev_secret)
            # dev 기준선: 구조 검증만 (개수/tier 기대치 없음)
            baseline_content_sha256 = calculate_baseline_content_sha256(
                rows, expected_record_count=None, expected_tier_counts=None
            )
            file_sha256 = write_prod_baseline(
                rows, args.out, expected_record_count=None, expected_tier_counts=None
            )
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


def _project_bootstrap_manifest(manifest: dict[str, object]) -> dict[str, object]:
    """bootstrap manifest를 RPC 계약 형식으로 투영한다 (신형 22필드 → 구형 7필드).

    Args:
        manifest: 신형 22필드 manifest dict (entries 필수)

    Returns:
        구형 7필드 RPC 계약 형식 dict

    Raises:
        ValueError: 필드 검증 실패 (before 결측, 필드 누락 등)
    """
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise ValueError("entries가 배열이 아닙니다")

    projected_entries = []
    for entry in entries:
        before = entry.get("before", {})
        if not isinstance(before, dict):
            raise ValueError("before가 dict가 아닙니다")

        # before 필드 검증 및 선별
        before_keys = ("foundry", "name_en", "name_ko", "official_url", "slug", "source_tier", "updated_at")
        projected_before = {}
        for key in before_keys:
            if key not in before:
                raise ValueError(f"before에 필수 키 '{key}'가 없습니다 (계약 위반)")
            projected_before[key] = before[key]

        projected_entry = {
            "font_id": entry.get("font_id"),
            "provider": entry.get("provider"),
            "provider_record_id": entry.get("provider_record_id"),
            "slug": entry.get("slug"),
            "source_url": entry.get("source_url"),
            "public_updates": entry.get("public_updates", {}),
            "before": projected_before,
        }
        projected_entries.append(projected_entry)

    # 투영 payload 구성
    projected_payload = {
        "schema_version": manifest.get("schema_version", 1),
        "matched": manifest.get("matched"),
        "unmatched": manifest.get("unmatched"),
        "conflicts": manifest.get("conflicts"),
        "review_rows": manifest.get("review_rows"),
        "entries": projected_entries,
    }

    return projected_payload


def main_audit_bootstrap_apply(args: argparse.Namespace) -> int:
    """bootstrap manifest를 RPC로 dev 또는 prod에 적용한다."""
    import hashlib
    import json
    import os

    from fontagit_pipeline.audit_store import SupabaseAuditStore
    from fontagit_pipeline.config import load_audit_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        # 1. 원본 파일 SHA256 검증
        manifest_bytes = args.manifest.read_bytes()
        file_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        if file_sha256 != args.confirm_hash:
            logger.error("bootstrap manifest SHA-256 불일치")
            return 3

        # 2. 원본 payload 로드
        manifest_dict = json.loads(manifest_bytes.decode("utf-8"))

        # 3. RPC 계약으로 투영
        projected_payload = _project_bootstrap_manifest(manifest_dict)

        # 4. 투영 payload SHA256 계산
        projected_text = json.dumps(projected_payload, sort_keys=True, ensure_ascii=False)
        projected_sha256 = hashlib.sha256(projected_text.encode("utf-8")).hexdigest()

        logger.info("bootstrap manifest 투영: file_sha=%s projected_sha=%s", file_sha256, projected_sha256)

        # 6. 대상 환경 RPC 호출
        settings = load_audit_settings()
        if args.target == "prod":
            if os.environ.get("FONTAGIT_PROD_MANIFEST_ENABLED") != "true":
                logger.error("prod bootstrap 적용은 FONTAGIT_PROD_MANIFEST_ENABLED=true 필수")
                return 3
            if not settings.supabase_prod_url or not settings.supabase_prod_secret_key:
                logger.error("prod credentials 미설정")
                return 3
            url, secret = settings.supabase_prod_url, settings.supabase_prod_secret_key
        else:
            url, secret = settings.dev_write_credentials()

        store = SupabaseAuditStore.from_dev_credentials(url, secret)

        result = store._schema.rpc(
            "apply_font_source_bootstrap",
            {
                "p_manifest_text": projected_text,
                "p_expected_sha256": projected_sha256,
                "p_schema_version": 1,
            },
        ).execute()

        if isinstance(result.data, int) and result.data > 0:
            logger.info("bootstrap manifest 적용 완료: %d건", result.data)
            return 0
        else:
            logger.error("bootstrap manifest RPC 실패: %s", result.data)
            return 3

    except (ValueError, OSError) as exc:
        logger.error("bootstrap manifest 적용 실패 (입력): %s", exc)
        return 3
    except Exception as exc:
        logger.error("bootstrap manifest 적용 실패 (DB): %s", exc)
        return 3


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


def main_audit_run(args: argparse.Namespace) -> int:
    """법적-메타데이터 감사 파일럿과 보고서를 만든다."""
    from fontagit_pipeline.audit_license import _load_rules
    from fontagit_pipeline.audit_policy import load_source_registry
    from fontagit_pipeline.audit_runner import (
        AuditGateError,
        _resolve_dev_font_ids,
        load_bootstrap_targets,
        run_legal_audit,
        run_metadata_audit,
        select_pilot,
        write_audit_artifacts,
    )
    from fontagit_pipeline.audit_store import InMemoryAuditStore, SupabaseAuditStore

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        targets = load_bootstrap_targets(args.bootstrap)
        # metadata 감사는 눈누 파일 cmap 검사 기반이라 Tier A는 파일 후보가 없음
        if args.stage == "metadata":
            targets = [t for t in targets if t.source_tier == "B"]
        selected = select_pilot(targets, size=args.limit, require_slugs=args.require_slug)
        registry = load_source_registry()
        if args.stage == "metadata" and not args.dry_run and not sys.platform.startswith("linux"):
            raise AuditGateError("metadata execution requires Linux isolation")
        if args.dry_run:
            dry_store = InMemoryAuditStore()
            if args.stage == "metadata":
                report = run_metadata_audit(selected, dry_store, registry, dry_run=True)
            else:
                rules = _load_rules(Path(__file__).with_name("data") / "license_rules.json")
                report = run_legal_audit(selected, dry_store, registry, rules, dry_run=True)
        else:
            from fontagit_pipeline.config import load_audit_settings

            settings = load_audit_settings()
            dev_url, dev_secret_key = settings.dev_write_credentials()
            dev_store = SupabaseAuditStore.from_dev_credentials(
                dev_url, dev_secret_key
            )
            selected = _resolve_dev_font_ids(selected, dev_store)
            if args.stage == "metadata":
                report = run_metadata_audit(selected, dev_store, registry)
            else:
                rules = _load_rules(Path(__file__).with_name("data") / "license_rules.json")
                report = run_legal_audit(selected, dev_store, registry, rules)
        digest = write_audit_artifacts(report, args.out)
        report.assert_safe()
    except (AuditGateError, OSError, ValueError) as exc:
        logger.error("감사 파일럿 중단: %s", exc)
        return 3

    logger.info("감사 파일럿 보고서 저장: %s (sha256=%s)", args.out, digest)
    return 0


def main_audit_scan(args: argparse.Namespace) -> int:
    """공개 prod RLS와 안전한 HTTP 경계만 사용해 예약 관찰을 만든다."""
    from fontagit_pipeline.audit_runner import (
        AuditGateError,
        load_prod_public_scheduled_targets,
        scan_scheduled_targets,
        write_scheduled_artifact,
    )
    from fontagit_pipeline.config import load_audit_settings

    if args.source != "prod-public":
        logger.error("허용되지 않은 예약 감사 출처입니다")
        return 2
    try:
        settings = load_audit_settings()
        public_url, public_key = settings.prod_public_read_credentials()
        from supabase import create_client

        public_schema = create_client(public_url, public_key).schema("fontagit")
        targets = load_prod_public_scheduled_targets(public_schema, args.kind)
        artifact = scan_scheduled_targets(args.kind, targets)
        digest = write_scheduled_artifact(artifact, args.out)
    except (AuditGateError, OSError, ValueError) as exc:
        logger.error("예약 감사 scan 중단: %s", exc)
        return 3
    except Exception as exc:  # 공개 API/외부 HTTP 경계
        logger.error("예약 감사 scan 실패: %s", exc.__class__.__name__)
        return 3
    logger.info(
        "예약 감사 artifact 저장: kind=%s targets=%d sha256=%s",
        args.kind,
        artifact.target_count,
        digest,
    )
    return 0


def main_audit_import(args: argparse.Namespace) -> int:
    """고정 artifact를 검증해 dev append-only 감사 테이블에만 넣는다."""
    from fontagit_pipeline.audit_runner import (
        AuditGateError,
        import_observations,
        read_regular_file_once,
    )
    from fontagit_pipeline.audit_store import SupabaseAuditStore
    from fontagit_pipeline.config import load_audit_settings

    try:
        artifact_bytes = read_regular_file_once(args.artifact, max_bytes=8 * 1024 * 1024)
        sha_bytes = read_regular_file_once(args.sha256, max_bytes=128)
        expected_sha256 = sha_bytes.decode("ascii")
        settings = load_audit_settings()
        dev_url, dev_key = settings.dev_write_credentials()
        store = SupabaseAuditStore.from_dev_credentials(dev_url, dev_key)
        result = import_observations(artifact_bytes, expected_sha256, store)
    except (AuditGateError, OSError, UnicodeError, ValueError) as exc:
        logger.error("예약 감사 import 중단: %s", exc)
        return 3
    except Exception as exc:  # dev DB 경계; 자격증명은 기록하지 않는다.
        logger.error("예약 감사 import 실패: %s", exc.__class__.__name__)
        return 3
    logger.info(
        "예약 감사 import 완료: status=%s observations=%d findings=%d applied=%d",
        result.status,
        result.observation_count,
        result.finding_count,
        result.applied_count,
    )
    return 0


def main_audit_manifest_apply(args: argparse.Namespace) -> int:
    """검증된 manifest 하나만 전용 RPC로 적용한다.

    prod는 파일 SHA 전체 일치와 대화형 yes를 모두 통과해야만 네트워크 경계를
    넘는다. 이 함수는 이번 작업에서 호출하지 않는다.
    """
    import hashlib

    from fontagit_pipeline.audit_manifest import ManifestError, verify_manifest_bytes
    from fontagit_pipeline.config import load_audit_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        manifest_bytes = args.manifest.read_bytes()
        expected_hash = args.sha256.read_text(encoding="ascii")
        manifest = verify_manifest_bytes(manifest_bytes, expected_hash)
        digest = hashlib.sha256(manifest_bytes).hexdigest()
        if args.confirm_hash != digest:
            raise ManifestError("--confirm-hash must exactly match the full manifest SHA-256")
        settings = load_audit_settings()
        if args.target == "prod":
            if os.environ.get("FONTAGIT_PROD_MANIFEST_ENABLED") != "true":
                raise ManifestError("prod manifest requires FONTAGIT_PROD_MANIFEST_ENABLED=true")
            approval_id = args.approval_id or os.environ.get("FONTAGIT_PROD_APPROVAL_ID")
            if not approval_id or not approval_id.strip():
                raise ManifestError("prod manifest requires --approval-id or FONTAGIT_PROD_APPROVAL_ID")
            if args.approved_hash != digest:
                raise ManifestError("--approved-hash must exactly match the full manifest SHA-256")
            if input("prod manifest를 적용합니다. 계속하려면 yes 입력: ").strip() != "yes":
                logger.info("사용자 취소")
                return 1
            if not settings.supabase_prod_url or not settings.supabase_prod_secret_key:
                raise ValueError("SUPABASE_PROD_URL과 SUPABASE_PROD_SECRET_KEY가 필요합니다")
            url, secret = settings.supabase_prod_url, settings.supabase_prod_secret_key
        else:
            url, secret = settings.dev_write_credentials()

        if not getattr(args, "skip_preflight", False):
            from fontagit_pipeline.audit_manifest_preflight import run_preflight

            preflight_report = run_preflight(manifest, url=url, secret_key=secret)
            _log_preflight_report(preflight_report)
            if not preflight_report.is_clean:
                logger.error(
                    "preflight에서 어긋남을 발견해 적용을 중단합니다 (--skip-preflight로 건너뛸 수 있음)"
                )
                return 2

        from supabase import create_client

        rpc_payload = {
            "p_manifest_text": manifest_bytes.decode("utf-8"),
            "p_expected_sha256": digest,
            "p_schema_version": int(manifest.schema_version),
        }
        response = create_client(url, secret).schema("fontagit").rpc(
            "apply_font_audit_manifest",
            rpc_payload,
        ).execute()
        # apply_font_audit_manifest RPC는 갱신 행 수(integer)를 반환한다
        logger.info(
            "감사 manifest 적용 완료: target=%s updated_rows=%s",
            args.target,
            response.data,
        )
        return 0
    except (ManifestError, OSError, ValueError) as exc:
        logger.error("감사 manifest 적용 중단: %s", exc)
        return 3
    except Exception as exc:  # 외부 DB 경계
        logger.error("감사 manifest RPC 실패: %s", exc.__class__.__name__)
        return 3


def main_audit_manifest_preflight(args: argparse.Namespace) -> int:
    """apply 전 manifest와 DB를 필드 단위로 대조하는 읽기 전용 게이트.

    - manifest/sha256을 검증 로드한다
    - 대상 env(dev/prod)의 findings/snapshots를 조회해 RPC(0025 수정 이후 기준)와
      동일한 의미론으로 대조한다
    - 어긋남이 있으면 (id, 필드, manifest값, DB값) 목록과 필드별 집계를 로깅하고
      exit code 1을 반환한다. DB에 없는 id는 오류가 아니라 신규 insert 예정이다.
    """
    from fontagit_pipeline.audit_manifest import ManifestError, verify_manifest_file
    from fontagit_pipeline.audit_manifest_preflight import run_preflight
    from fontagit_pipeline.config import load_audit_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        manifest = verify_manifest_file(args.manifest, args.sha256)
        settings = load_audit_settings()
        if args.target == "prod":
            if not settings.supabase_prod_url or not settings.supabase_prod_secret_key:
                logger.error("prod credentials 미설정")
                return 2
            url, secret = settings.supabase_prod_url, settings.supabase_prod_secret_key
        else:
            url, secret = settings.dev_write_credentials()

        report = run_preflight(manifest, url=url, secret_key=secret)
    except (ManifestError, OSError, ValueError) as exc:
        logger.error("preflight 준비 중단: %s", exc)
        return 2
    except Exception as exc:  # 외부 DB 경계
        logger.error("preflight 조회 실패: %s", exc.__class__.__name__)
        return 3

    _log_preflight_report(report)
    return 0 if report.is_clean else 1


_PREFLIGHT_LOG_VALUE_LIMIT = 200


def _truncated_repr(value: object, limit: int = _PREFLIGHT_LOG_VALUE_LIMIT) -> str:
    """raw_text 등 큰 값이 로그를 비대화시키지 않도록 repr 출력을 제한 길이로 자른다."""
    text = repr(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}...(총 {len(text)}자)"


def _log_preflight_report(report: "PreflightReport") -> None:
    """preflight 결과의 어긋남 목록과 필드별 집계를 로깅한다."""
    logger.info(
        "preflight 결과: 어긋남=%d 신규 finding=%d 신규 snapshot=%d",
        len(report.mismatches),
        len(report.new_finding_ids),
        len(report.new_snapshot_ids),
    )
    for mismatch in report.mismatches:
        logger.error(
            "불일치: entity=%s id=%s field=%s manifest=%s db=%s",
            mismatch.entity,
            mismatch.entity_id,
            mismatch.field_name,
            _truncated_repr(mismatch.manifest_value),
            _truncated_repr(mismatch.db_value),
        )
    if report.mismatches:
        logger.error("필드별 집계: %s", report.field_summary())


def _write_excluded_fonts_sidecar(
    out_dir: Path, run_id: "UUID", excluded_fonts: list["ExcludedFontSource"]
) -> Path:
    """대상 DB에 없어 제외된 폰트 목록을 manifest와 별도인 사이드카 파일로 저장한다.

    manifest forward/reverse JSON의 체크섬 계산과는 무관한 파일이다.
    제외 0건이어도 파일을 생성해, "누락 검사가 실행됐다"는 감사 신호를 남긴다.
    """
    import json

    payload = {
        "run_id": str(run_id),
        "excluded_count": len(excluded_fonts),
        "excluded": [
            {
                "provider": f.provider,
                "provider_record_id": f.provider_record_id,
                "dev_font_id": f.dev_font_id,
                "evidence_ids": list(f.evidence_ids),
            }
            for f in excluded_fonts
        ],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "excluded.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def main_audit_manifest_build(args: argparse.Namespace) -> int:
    """approved findings를 조회하여 manifest 번들을 생성한다.

    - run_id로 기준 run을 조회
    - 해당 run의 approved findings 조회
    - 현재 font 스냅샷 조회
    - build_manifest로 번들 생성
    - write_manifest_bundle로 파일 저장 (또는 --chunk-size로 청크 분할)

    build는 approve를 하지 않는다 — 이미 approved인 finding만 조회한다.
    """
    from uuid import UUID

    from fontagit_pipeline.audit_manifest import (
        ManifestError,
        build_manifest,
        split_manifest_into_chunks,
        write_chunked_manifest_bundles,
        write_manifest_bundle,
    )
    from fontagit_pipeline.audit_store import ExcludedFontSource, SupabaseAuditStore
    from fontagit_pipeline.config import load_audit_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        run_id = UUID(args.run_id)
        settings = load_audit_settings()
        dev_url, dev_secret = settings.dev_write_credentials()
        store = SupabaseAuditStore.from_dev_credentials(dev_url, dev_secret)

        # target_store 초기화 (prod 대상 시)
        target_store: SupabaseAuditStore | None = None
        target = getattr(args, "target", "dev")
        if target == "prod":
            if not settings.supabase_prod_url or not settings.supabase_prod_secret_key:
                logger.error("prod credentials 미설정")
                return 3
            target_store = SupabaseAuditStore.from_dev_credentials(
                settings.supabase_prod_url, settings.supabase_prod_secret_key
            )
            logger.info("manifest build target: prod")
        else:
            logger.info("manifest build target: dev")

        # 1. run 조회
        run = store.get_run(run_id)
        logger.info("감사 run 조회: run_id=%s", run_id)

        # 2. approved findings 조회
        approved_findings = store.get_approved_findings(run_id)
        if not approved_findings:
            logger.error("승인된 findings가 없습니다: run_id=%s", run_id)
            return 1
        logger.info("승인된 findings 조회: count=%d", len(approved_findings))

        # 3. 현재 font 스냅샷 조회 (대상 DB에 없는 폰트는 excluded_fonts로 별도 보고됨)
        excluded_fonts: list[ExcludedFontSource] = []
        current_rows = store.get_current_fonts_with_snapshots(
            run_id, target_store=target_store, excluded_out=excluded_fonts
        )
        logger.info("현재 font 스냅샷 조회: count=%d", len(current_rows))
        if excluded_fonts:
            logger.warning(
                "대상 DB에 없어 제외된 폰트: count=%d keys=%s",
                len(excluded_fonts),
                "; ".join(
                    f"({f.provider}, {f.provider_record_id})" for f in excluded_fonts
                ),
            )

        if target_store is not None:
            # 대상 DB 문맥 재바인딩: finding.font_id를 evidence가 붙은 대상 폰트로 치환
            excluded_evidence_ids = {
                evidence_id for f in excluded_fonts for evidence_id in f.evidence_ids
            }
            evidence_to_font: dict[str, str] = {}
            for row in current_rows:
                row_snapshots = row.get("evidence_snapshots")
                if isinstance(row_snapshots, list):
                    for snap in row_snapshots:
                        evidence_to_font[str(snap.get("id"))] = str(row.get("id"))

            findings_for_manifest: list[dict[str, object]] = []
            skipped_finding_count = 0
            for finding in approved_findings:
                evidence_id = str(finding.get("evidence_id"))
                if evidence_id in excluded_evidence_ids:
                    skipped_finding_count += 1
                    continue
                target_font_id = evidence_to_font.get(evidence_id)
                if target_font_id is None:
                    raise ManifestError(
                        f"finding evidence가 대상 현재행에 없습니다: {finding.get('id')}"
                    )
                finding["font_id"] = target_font_id
                findings_for_manifest.append(finding)

            if skipped_finding_count:
                logger.warning(
                    "대상 DB에 없는 폰트의 finding %d건을 manifest에서 제외합니다",
                    skipped_finding_count,
                )
            approved_findings = findings_for_manifest

        # 4. manifest 번들 생성
        bundle = build_manifest(run, approved_findings, current_rows)
        logger.info(
            "manifest 번들 생성: forward_sha256=%s reverse_sha256=%s",
            bundle.forward_sha256[:8] + "...",
            bundle.reverse_sha256[:8] + "...",
        )

        # 5. 파일 저장 (청크 분할 여부)
        chunk_size = getattr(args, "chunk_size", 0)
        if chunk_size > 0:
            chunks = split_manifest_into_chunks(bundle, chunk_size)
            logger.info(
                "manifest 청크 분할: chunk_size=%d total_chunks=%d",
                chunk_size,
                len(chunks),
            )
            index = write_chunked_manifest_bundles(chunks, args.out)
            logger.info(
                "청크 manifest 저장: chunk_count=%d total_entries=%d out=%s",
                index.get("total_chunks"),
                index.get("total_entries"),
                args.out,
            )
        else:
            paths = write_manifest_bundle(bundle, args.out)
            logger.info(
                "manifest 번들 저장: forward=%s reverse=%s",
                paths.forward,
                paths.reverse,
            )

        if target_store is not None:
            sidecar_path = _write_excluded_fonts_sidecar(
                args.out, run_id, excluded_fonts
            )
            logger.info(
                "제외 폰트 사이드카 저장: count=%d out=%s",
                len(excluded_fonts),
                sidecar_path,
            )

        return 0
    except ValueError as exc:
        logger.error("입력값 오류: %s", exc)
        return 1
    except (ManifestError, OSError) as exc:
        logger.error("manifest 생성 중단: %s", exc)
        return 2
    except Exception as exc:  # 외부 DB 경계
        logger.error("manifest 생성 실패: %s", exc.__class__.__name__)
        return 3


def _summarize_findings_by_field(findings: list[dict[str, object]]) -> dict[str, int]:
    """findings를 field_name으로 그룹화하여 개수 반환."""
    summary: dict[str, int] = {}
    for finding in findings:
        field_name = finding.get("field_name")
        if isinstance(field_name, str):
            summary[field_name] = summary.get(field_name, 0) + 1
    return summary


def main_audit_review(args: argparse.Namespace) -> int:
    """font-audit-review 서브커맨드 진입점: action으로 auto-approve/approve를 분기한다.

    - auto-approve: metadata findings을 무인 승인(evidence-values 대조 필수, 기존 동작 유지)
    - approve: 사람이 검수를 마친 findings를 --field로 지정한 필드(기본 전체)만 배치 승인
      (main_audit_review_approve로 위임)
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.action == "approve":
        return main_audit_review_approve(args)

    return _main_audit_review_auto_approve(args)


def _main_audit_review_auto_approve(args: argparse.Namespace) -> int:
    """metadata findings을 무인 승인한다.

    - run_id로 기준 run을 조회
    - 해당 run의 needs_review metadata findings을 조회
    - 각 finding을 전건 auto-approve
    - 결과를 요약하여 로깅

    실패한 findings는 continue하고, 최종 결과를 기반으로 exit code 결정.

    Exit codes:
    - 0: 승인 성공 또는 대상 findings 없음
    - 1: 입력값 오류 (invalid run-id 등)
    - 3: 개별 finding 승인 실패 또는 DB 오류
    """
    from uuid import UUID

    from fontagit_pipeline.audit_store import SupabaseAuditStore
    from fontagit_pipeline.config import load_audit_settings

    try:
        if args.action != "auto-approve":
            raise ValueError(f"지원하지 않는 action: {args.action}")

        run_id = UUID(args.run_id)
        reviewed_by = "auto"
        settings = load_audit_settings()
        dev_url, dev_secret = settings.dev_write_credentials()
        store = SupabaseAuditStore.from_dev_credentials(dev_url, dev_secret)

        # 1. run 조회 및 stage 검증
        run = store.get_run(run_id)
        run_stage = run.get("stage")
        logger.info("감사 run 조회: run_id=%s stage=%s", run_id, run_stage)

        if run_stage != "metadata":
            logger.error("run stage는 metadata여야 합니다: stage=%s", run_stage)
            return 1

        # run status 검증: completed 상태 확인
        run_status = run.get("status")
        if run_status != "completed":
            logger.error("run status는 completed여야 합니다: status=%s", run_status)
            return 1

        # broken ratio 검증: 10% 초과 금지
        from typing import cast

        broken_count = cast(int, run.get("broken_count")) or 0
        target_count = cast(int, run.get("target_count")) or 0
        if target_count and broken_count / target_count > _BROKEN_RATIO_THRESHOLD:
            logger.error(
                "broken ratio 10%% 초과: broken=%d target=%d ratio=%.1f%%",
                broken_count,
                target_count,
                100 * broken_count / target_count,
            )
            return 1

        # 2. proposed findings 조회 (tags/weights만)
        proposed_findings = store.get_proposed_findings(run_id)
        if not proposed_findings:
            logger.info(
                "승인 완료: approved=0 failed=0 total=0 (승인 대상 없음) run_id=%s", run_id
            )
            return 0
        logger.info("승인 대상 findings 조회: count=%d", len(proposed_findings))

        # 2.5. 증거 스냅샷 조회 (values-evidence 대조용)
        from fontagit_pipeline.audit_metadata import derive_proposed_value

        evidence_ids: set[str] = set()
        for finding in proposed_findings:
            evidence_id = finding.get("evidence_id")
            if isinstance(evidence_id, str):
                evidence_ids.add(evidence_id)

        evidence_by_id: dict[str, dict[str, object]] = {}
        chunk_size = 100
        evidence_ids_list = list(evidence_ids)

        for i in range(0, len(evidence_ids_list), chunk_size):
            chunk = evidence_ids_list[i : i + chunk_size]
            snapshots_result = (
                store._schema.table("font_source_snapshots")
                .select("id, extracted")
                .in_("id", chunk)
                .execute()
            )
            snapshots_data = snapshots_result.data
            if not isinstance(snapshots_data, list):
                raise RuntimeError("font_source_snapshots 조회 결과가 올바르지 않습니다")

            for snapshot in snapshots_data:
                snapshot_id = snapshot.get("id")
                extracted = snapshot.get("extracted")
                if isinstance(snapshot_id, str) and isinstance(extracted, dict):
                    evidence_by_id[snapshot_id] = extracted

        # 3. 각 finding 승인 (개별 실패는 수집)
        approved_count = 0
        failed_findings: list[dict[str, object]] = []

        for finding in proposed_findings:
            finding_id = finding.get("id")
            field_name = finding.get("field_name")
            evidence_id = finding.get("evidence_id")
            proposed_value = finding.get("proposed_value")
            auto_applicable = finding.get("auto_applicable", False)  # 기존 DB 레코드에 값이 없으면 fail-closed로 사람 검수 유지

            try:
                if not isinstance(finding_id, str):
                    raise ValueError(f"invalid finding_id: {finding_id}")

                # 자동 승인 필드 필터 (auto_applicable=True만 처리). foundry_url/license_source_url은
                # legal 필드가 아닌 링크-표기 등급이라 스펙상 자동 게이트 대상이다(이슈 #133).
                if field_name not in {
                    "tags",
                    "weights",
                    "foundry",
                    "foundry_url",
                    "download_url",
                    "download_source_kind",
                    "license_source_url",
                }:
                    continue
                if not auto_applicable:
                    # auto_applicable=False는 needs_review 유지 (자동 승인 불가)
                    continue

                # values-evidence 대조 (자동 승인 대상 필드). evidence_id가 없거나
                # 매칭되는 스냅샷을 찾지 못하면 fail-closed로 승인을 건너뛴다
                # (검증 불가를 검증 통과로 취급하지 않는다).
                if not isinstance(evidence_id, str) or not evidence_id:
                    raise ValueError(f"missing evidence_id for auto-approvable field: field={field_name}")
                extracted = evidence_by_id.get(evidence_id)
                if not extracted:
                    raise ValueError(
                        f"evidence snapshot not found: field={field_name} evidence_id={evidence_id}"
                    )
                expected = derive_proposed_value(field_name, extracted)
                if expected != proposed_value:
                    raise ValueError(
                        f"evidence mismatch: field={field_name} expected={expected} proposed={proposed_value}"
                    )

                store.approve_finding(UUID(finding_id), reviewed_by=reviewed_by)
                approved_count += 1
            except Exception as exc:  # DB 호출 경계: APIError, RuntimeError, ValueError 등
                logger.warning(
                    "finding 승인 실패: id=%s field=%s type=%s reason=%s",
                    finding_id,
                    field_name,
                    exc.__class__.__name__,
                    exc,
                )
                failed_findings.append(finding)

        # 4. 요약 로깅
        summary = _summarize_findings_by_field(proposed_findings)
        logger.info(
            "승인 완료: approved=%d failed=%d total=%d field_distribution=%s",
            approved_count,
            len(failed_findings),
            len(proposed_findings),
            summary,
        )

        # 5. exit code 결정
        if failed_findings:
            logger.error("일부 findings 승인 실패: 수동 검수 필요")
            return 3

        return 0

    except ValueError as exc:
        logger.error("입력값 오류: %s", exc)
        return 1
    except Exception as exc:  # settings 로드 또는 상위 DB 경계 오류
        logger.error("metadata 승인 실패: %s", exc)
        return 3


def main_audit_review_approve(args: argparse.Namespace) -> int:
    """사람이 검수를 마친 proposed findings를 필드 단위로 배치 승인한다.

    - run_id의 status='proposed' findings 중 --field로 지정한 field_name(생략 시
      MANUAL_APPROVABLE_FIELDS 전체)만 조회한다. legal 필드(allow_commercial 등)는
      MANUAL_APPROVABLE_FIELDS에 없으므로 --field로 지정해도 입력값 오류로 거부한다
      (이슈 #128 - legal 필드는 이 CLI에서는 별도 사람 게이트 절차 대상이라 이번 범위가
      아니다. 다만 기존 noonnu-review approve는 필드 화이트리스트가 없어 legal finding도
      승인 가능하다 - 선행 존재하는 별도 경로이며 이번 범위 밖이다).
    - run.status가 completed가 아니면 거부한다(아직 findings가 insert 중일 수 있는
      running run이나 실패한 run의 findings를 승인하지 못하게 막는 최소 게이트).
    - auto-approve와 달리 evidence-values 재대조는 하지 않는다: 이 경로는 사람이 이미
      findings 내용을 확인하고 승인을 지시한 상태를 전제로 한다.
    - --dry-run이면 조회만 하고 승인/건너뜀 집계 없이 대상 건수와 필드별 분포만 로깅한다.
    - 조회 필터를 신뢰하지 않고 각 finding에서 field_name을 다시 확인한다. 이 재확인이
      걸리면 쿼리 필터가 뚫렸다는 보안 이벤트이므로 건별 WARNING을 남기고 exit code를
      0이 아닌 값으로 바꾼다.

    Exit codes:
    - 0: 승인 성공(0건 포함) 또는 dry-run
    - 1: 입력값 오류 (invalid run-id, 허용되지 않은 --field, run status != completed 등)
    - 2: 방어선(field_name 재확인)에서 legal 필드 유입이 1건 이상 감지됨
    - 3: 일부 finding 승인 실패 또는 DB 오류
    """
    from uuid import UUID

    from fontagit_pipeline.audit_store import MANUAL_APPROVABLE_FIELDS, SupabaseAuditStore
    from fontagit_pipeline.config import load_audit_settings

    try:
        run_id = UUID(args.run_id)
        reviewed_by = args.reviewed_by
        if not reviewed_by or not str(reviewed_by).strip():
            raise ValueError("approve는 --reviewed-by가 필수입니다")

        requested_fields = args.field if args.field else sorted(MANUAL_APPROVABLE_FIELDS)
        disallowed_fields = [f for f in requested_fields if f not in MANUAL_APPROVABLE_FIELDS]
        if disallowed_fields:
            raise ValueError(f"승인 대상이 아닌 --field: {disallowed_fields}")

        settings = load_audit_settings()
        dev_url, dev_secret = settings.dev_write_credentials()
        store = SupabaseAuditStore.from_dev_credentials(dev_url, dev_secret)

        # run 게이트: completed가 아닌 run(진행 중이라 findings가 계속 insert되거나,
        # 실패한 run)의 findings는 사람 승인 경로에서도 막는다 (MEDIUM 리뷰 지적).
        run = store.get_run(run_id)
        run_status = run.get("status")
        if run_status != "completed":
            logger.error("run status는 completed여야 합니다: status=%s", run_status)
            return 1

        auto_applicable_only = not getattr(args, "include_manual_review", False)
        proposed_findings = store.get_proposed_findings_by_fields(
            run_id, requested_fields, auto_applicable_only=auto_applicable_only
        )
        logger.info(
            "배치 승인 대상 조회: run_id=%s fields=%s auto_applicable_only=%s count=%d",
            run_id,
            requested_fields,
            auto_applicable_only,
            len(proposed_findings),
        )

        if args.dry_run:
            field_distribution = _summarize_findings_by_field(proposed_findings)
            logger.info(
                "dry-run: 승인 대상 %d건 field_distribution=%s (실제 승인 없음)",
                len(proposed_findings),
                field_distribution,
            )
            return 0

        approved_count = 0
        skipped_count = 0
        defense_triggered_count = 0
        failed_findings: list[dict[str, object]] = []

        for finding in proposed_findings:
            finding_id = finding.get("id")
            field_name = finding.get("field_name")
            status = finding.get("status")

            # 이중 방어: 조회 필터를 신뢰하지 않고 각 finding에서 다시 확인한다
            # (legal 필드가 어떤 경로로든 섞여 들어오면 여기서 건너뛴다). field_name 쪽
            # 방어선이 걸리는 것은 "쿼리 필터가 뚫렸다"는 보안 이벤트이므로 건별
            # WARNING을 남기고 별도로 집계한다. status 불일치(동시성)는 보안 이벤트가
            # 아니므로 기존처럼 skipped_count에만 반영한다.
            if field_name not in MANUAL_APPROVABLE_FIELDS:
                logger.warning(
                    "방어선 발동: 승인 대상이 아닌 field가 조회 결과에 섞여 있음 id=%s field=%s",
                    finding_id,
                    field_name,
                )
                defense_triggered_count += 1
                skipped_count += 1
                continue
            if status != "proposed":
                skipped_count += 1
                continue

            try:
                if not isinstance(finding_id, str):
                    raise ValueError(f"invalid finding_id: {finding_id}")
                store.approve_finding(UUID(finding_id), reviewed_by=reviewed_by)
                approved_count += 1
            except Exception as exc:  # DB 호출 경계: APIError, RuntimeError, ValueError 등
                logger.warning(
                    "finding 승인 실패: id=%s field=%s type=%s reason=%s",
                    finding_id,
                    field_name,
                    exc.__class__.__name__,
                    exc,
                )
                failed_findings.append(finding)

        logger.info(
            "승인=%d 건너뜀=%d 실패=%d (run_id=%s)",
            approved_count,
            skipped_count,
            len(failed_findings),
            run_id,
        )

        if failed_findings:
            logger.error("일부 findings 승인 실패: 수동 재확인 필요")
            return 3

        if defense_triggered_count:
            logger.error(
                "방어선 발동 %d건: 쿼리 필터 유입 경로 점검 필요 (run_id=%s)",
                defense_triggered_count,
                run_id,
            )
            return 2

        return 0

    except ValueError as exc:
        logger.error("입력값 오류: %s", exc)
        return 1
    except Exception as exc:  # settings 로드 또는 상위 DB 경계 오류
        logger.error("배치 승인 실패: %s", exc)
        return 3


def main_audit_crawl_all(args: argparse.Namespace) -> int:
    """전수 배치 크롤링을 실행하고 체크포인트로 재개를 지원한다."""
    from fontagit_pipeline.audit_license import _load_rules
    from fontagit_pipeline.audit_policy import load_source_registry
    from fontagit_pipeline.audit_runner import (
        AuditGateError,
        _resolve_dev_font_ids,
        load_bootstrap_targets,
        run_batch_crawl,
        write_audit_artifacts,
    )
    from fontagit_pipeline.audit_store import InMemoryAuditStore, SupabaseAuditStore

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        targets = load_bootstrap_targets(args.bootstrap)

        # Tier B 필터: source_tier == "B"만 선택
        tier_b_targets = [t for t in targets if t.source_tier == "B"]
        if not tier_b_targets:
            logger.warning("Tier B 대상 없음")
            return 1

        logger.info("전수 크롤링 시작: Tier B %d종, batch_size=%d", len(tier_b_targets), args.batch_size)

        registry = load_source_registry()
        checkpoint_path = Path(args.checkpoint) if args.checkpoint else None

        if args.dry_run:
            dry_store = InMemoryAuditStore()
            rules = _load_rules(Path(__file__).with_name("data") / "license_rules.json")
            report = run_batch_crawl(
                tier_b_targets,
                dry_store,
                registry,
                rules,
                batch_size=args.batch_size,
                checkpoint_path=checkpoint_path,
                dry_run=True,
            )
        else:
            from fontagit_pipeline.config import load_audit_settings

            settings = load_audit_settings()
            dev_url, dev_secret_key = settings.dev_write_credentials()
            dev_store = SupabaseAuditStore.from_dev_credentials(
                dev_url, dev_secret_key
            )
            tier_b_targets = _resolve_dev_font_ids(tier_b_targets, dev_store)
            rules = _load_rules(Path(__file__).with_name("data") / "license_rules.json")
            report = run_batch_crawl(
                tier_b_targets,
                dev_store,
                registry,
                rules,
                batch_size=args.batch_size,
                checkpoint_path=checkpoint_path,
                dry_run=False,
            )

        # 최종 결과 저장
        digest = write_audit_artifacts(report, args.out)
        logger.info(
            "전수 크롤링 완료: verified=%d, needs_review=%d, pending=%d, broken=%d, "
            "errors=%d, sha256=%s",
            report.verified_count,
            report.needs_review_count,
            report.pending_count,
            report.broken_count,
            len(report.errors),
            digest,
        )
        return 0
    except (AuditGateError, OSError, ValueError) as exc:
        logger.error("전수 크롤링 중단: %s", exc)
        return 3


def main_audit_tier_a_meta(args: argparse.Namespace) -> int:
    """Tier A 공식 메타데이터(권리사/specimen URL)를 수집한다."""
    import json
    from hashlib import sha256
    from uuid import uuid4

    from fontagit_pipeline.config import load_audit_settings
    from fontagit_pipeline.audit_policy import load_source_registry
    from fontagit_pipeline.tier_a_meta import (
        TierATarget,
        collect_tier_a_meta,
        load_brand_normalization,
    )

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    report = {
        "dry_run": args.dry_run,
        "limit": args.limit,
        "results": None,
        "errors": [],
    }

    try:
        # 정규화 테이블 로드
        normalization = load_brand_normalization()

        # 출처 레지스트리 로드
        registry = load_source_registry()

        # dev DB에서 Tier A 대상 조회
        settings = load_audit_settings()
        dev_url, dev_secret_key = settings.dev_write_credentials()
        from supabase import create_client

        dev_client = create_client(dev_url, dev_secret_key)
        dev_schema = dev_client.schema("fontagit")

        # published + source_tier='A' 폰트 조회
        query = (
            dev_schema.table("fonts")
            .select("id,slug,name_en,download_source_kind,license_source_kind")
            .eq("status", "published")
            .eq("source_tier", "A")
            .order("id")
        )
        if args.limit > 0:
            query = query.limit(args.limit)
        response = query.execute()

        if not isinstance(response.data, list):
            raise ValueError("dev fonts query returned invalid data")

        targets: list[TierATarget] = []
        for row in response.data:
            font_id = row.get("id")
            name_en = row.get("name_en")
            if not all([font_id, name_en]):
                logger.warning("skipping invalid font row: %s", row)
                continue
            slug = row.get("slug")
            download_source_kind = row.get("download_source_kind")
            license_source_kind = row.get("license_source_kind")
            # Tier A는 google-fonts 출처이고, 대부분 OFL 라이선스 사용
            # (apache, ufl도 있지만 메타데이터에서 판별 가능)
            targets.append(
                TierATarget(
                    font_id=font_id,
                    name_en=name_en,
                    license_type="OFL",  # google-fonts 기본값
                    slug=slug if isinstance(slug, str) else None,
                    noonnu_foundry=None,  # dev에서는 눈누 매핑 미제공
                    download_source_kind=(
                        download_source_kind if isinstance(download_source_kind, str) else None
                    ),
                    license_source_kind=(
                        license_source_kind if isinstance(license_source_kind, str) else None
                    ),
                )
            )

        logger.info("Tier A 대상 조회 완료: %d건", len(targets))

        if args.dry_run:
            # dry-run: 메모리 저장소 + 가상 run_id
            from fontagit_pipeline.audit_store import InMemoryAuditStore

            store = InMemoryAuditStore()
            run_id = uuid4()
            # run 생성 (dry-run이므로 저장 없음)
            result = collect_tier_a_meta(
                run_id,
                targets,
                store,
                registry,
                normalization,
                dry_run=True,
            )
            report["results"] = result
            report["target_count"] = len(targets)
            report["findings"] = result.get("findings", [])
            report["errors"] = result.get("errors", [])
            logger.info("Tier A 메타 dry-run 완료: %s", result)
        else:
            # 실제 저장: SupabaseAuditStore + run 생성
            from fontagit_pipeline.audit_store import SupabaseAuditStore

            store = SupabaseAuditStore.from_dev_credentials(dev_url, dev_secret_key)

            # baseline_sha256 계산 (타겟 목록의 해시)
            targets_json = json.dumps(
                [t.model_dump(mode="json") for t in targets],
                ensure_ascii=False,
                sort_keys=True,
            )
            baseline_sha256 = sha256(targets_json.encode()).hexdigest()

            # run 생성
            run_id = store.start_run(
                stage="scheduled",
                target_count=len(targets),
                baseline_sha256=baseline_sha256,
                dry_run=False,
            )

            result = collect_tier_a_meta(
                run_id,
                targets,
                store,
                registry,
                normalization,
                dry_run=False,
            )

            # run 완료
            store.complete_run(run_id, result)

            report["results"] = result
            report["target_count"] = len(targets)
            report["run_id"] = str(run_id)
            report["findings"] = result.get("findings", [])
            report["errors"] = result.get("errors", [])
            logger.info("Tier A 메타 저장 완료: run_id=%s, %s", run_id, result)

        # 보고서 저장
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info("Tier A 메타 보고서 저장: %s", args.out)
        return 0

    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Tier A 메타 수집 중단: %s", exc)
        report["errors"].append(str(exc))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return 1


def main_audit_kogl_preview(args: argparse.Namespace) -> int:
    """KOGL 후보 폰트 조회 및 유형 판별 미리보기 (preview 전용, DB 쓰기 없음)."""
    import json

    from fontagit_pipeline.audit_kogl import detect_kogl_type
    from fontagit_pipeline.config import load_audit_settings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    try:
        # 1. 설정 로드
        settings = load_audit_settings()
        dev_url, dev_secret_key = settings.dev_write_credentials()

        # 2. Supabase 클라이언트 생성
        from supabase import create_client

        dev_client = create_client(dev_url, dev_secret_key)
        dev_schema = dev_client.schema("fontagit")

        # 3. 라이선스 스냅샷 조회 (metadata 문서 종류, 1,000행 제한 회피용 페이지네이션)
        from typing import cast

        logger.info("라이선스 스냅샷 조회 (metadata)...")
        snapshots_data: list[dict[str, object]] = []
        page_size = 1000
        offset = 0
        while True:
            page_response = (
                dev_schema.table("font_source_snapshots")
                .select("font_id,extracted")
                .eq("document_kind", "metadata")
                .order("collected_at", desc=True)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not isinstance(page_response.data, list):
                raise ValueError("snapshots query returned invalid data")
            snapshots_data.extend(cast(list[dict[str, object]], page_response.data))
            if len(page_response.data) < page_size:
                break
            offset += page_size

        # 4. font_id별 스냅샷 선택 (collected_at이 전부 NULL이라 정렬이 무의미하므로
        #    license_text 본문을 보유한 스냅샷을 우선 채택)
        def _has_license_text(snap: dict[str, object]) -> bool:
            extracted = snap.get("extracted")
            return isinstance(extracted, dict) and isinstance(extracted.get("license_text"), str)

        latest_snapshots: dict[str, dict] = {}
        for snap in snapshots_data:
            font_id = snap.get("font_id")
            if not font_id:
                continue
            if font_id not in latest_snapshots:
                latest_snapshots[font_id] = snap
            elif _has_license_text(snap) and not _has_license_text(latest_snapshots[font_id]):
                latest_snapshots[font_id] = snap

        logger.info("라이선스 스냅샷: %d건 (폰트별 1건, 본문 보유 우선)", len(latest_snapshots))

        # 5. 각 스냅샷의 license_text로 detect_kogl_type 실행
        results: dict[str, object] = {
            "source": "font_source_snapshots (metadata, latest per font_id)",
            "query_count": len(latest_snapshots),
            "by_type": {1: [], 2: [], 3: [], 4: []},
            "undetected": [],
            "extraction_errors": [],
            "summary": {},
        }

        for font_id, snapshot in latest_snapshots.items():
            extracted = snapshot.get("extracted")

            # 타입 검증: extracted 필드가 dict인지 확인
            if not isinstance(extracted, dict):
                results["extraction_errors"].append(
                    {
                        "font_id": font_id,
                        "slug": "unknown",
                        "reason": f"extracted is {type(extracted).__name__}, not dict",
                    }
                )
                continue

            license_text = extracted.get("license_text")

            # license_text가 없거나 None이면 skip (정상 데이터, 오류 아님)
            if license_text is None:
                continue

            # 타입 검증: license_text 필드가 str인지 확인 (기대 범위 외)
            if not isinstance(license_text, str):
                slug = extracted.get("target_slug", "unknown")
                results["extraction_errors"].append(
                    {
                        "font_id": font_id,
                        "slug": slug,
                        "reason": f"license_text is {type(license_text).__name__}, not str",
                    }
                )
                continue

            # '공공누리' 포함 여부 확인
            if "공공누리" not in license_text:
                continue

            detection = detect_kogl_type(license_text)
            slug = extracted.get("target_slug", "unknown")
            font_entry = {
                "font_id": font_id,
                "slug": slug,
                "detection_reason": detection.reason,
            }

            if detection.kogl_type is not None:
                results["by_type"][detection.kogl_type].append(font_entry)
            else:
                results["undetected"].append(
                    {**font_entry, "undetected_reason": detection.reason}
                )

        # 7. 요약 집계
        summary = {}
        for kogl_type in (1, 2, 3, 4):
            summary[f"type_{kogl_type}"] = len(results["by_type"][kogl_type])
        summary["undetected"] = len(results["undetected"])
        summary["total_detected"] = sum(len(v) for v in results["by_type"].values())
        summary["extraction_errors"] = len(results["extraction_errors"])
        summary["total_with_kogl_text"] = summary["total_detected"] + summary["undetected"]
        # target_slug 추출 실패 카운트 ("unknown" fallback)
        slug_extraction_failures = sum(1 for items in results["by_type"].values() for e in items if e.get("slug") == "unknown") + sum(1 for e in results["undetected"] if e.get("slug") == "unknown")
        summary["slug_extraction_failures"] = slug_extraction_failures
        results["summary"] = summary

        # 8. JSON 저장
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        logger.info(
            "KOGL preview 완료: type_1=%d type_2=%d type_3=%d type_4=%d undetected=%d extraction_errors=%d (출력=%s)",
            summary["type_1"],
            summary["type_2"],
            summary["type_3"],
            summary["type_4"],
            summary["undetected"],
            summary["extraction_errors"],
            args.out,
        )
        return 0

    except Exception as exc:
        logger.error("KOGL preview 실패: %s (%s)", exc.__class__.__name__, exc)
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

    # noonnu-url-scan 명령
    url_scan_parser = subparsers.add_parser(
        "noonnu-url-scan",
        help="눈누 Tier B 공식 URL 전수 대조 (읽기 전용)",
    )
    url_scan_parser.add_argument(
        "--target", choices=["dev", "prod"], required=True, help="대상 환경"
    )
    url_scan_parser.add_argument(
        "--state", type=Path, required=True, help="진행 상태 JSONL 경로 (재개용)"
    )
    url_scan_parser.add_argument(
        "--out", type=Path, required=True, help="판정 리포트 JSON 저장 경로"
    )
    url_scan_parser.add_argument(
        "--limit", type=int, default=0, help="대상 상한 (0=전체)"
    )
    url_scan_parser.add_argument(
        "--store-findings",
        action="store_true",
        help="판정을 감사 저장소에 run/snapshot/finding으로 적재한다",
    )
    url_scan_parser.add_argument(
        "--only-actionable",
        type=Path,
        default=None,
        help="이전 스캔 상태 JSONL 경로. keep이 아닌 대상만 재스캔한다",
    )
    url_scan_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="--only-actionable 상태 파일에서 error가 있는 건만 다시 시도한다",
    )
    url_scan_parser.set_defaults(func=main_noonnu_url_scan)

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
        "--slug", type=str, default=None, help="폰트 슬러그(unpublish legacy 명령용)"
    )
    review_parser.add_argument(
        "--finding-id", type=str, default=None, help="승인/반려할 감사 finding ID"
    )
    review_parser.add_argument(
        "--reviewed-by", type=str, default=None, help="검수자 식별자(승인/반려 필수)"
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
        help="[deprecated] 대상 수 dry-run만 제공; 적용은 font-audit-manifest apply",
    )
    publish_parser.add_argument(
        "--confirm",
        action="store_true",
        help="[deprecated] 항상 차단됨; font-audit-manifest apply 사용",
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
        choices=["prod-public", "dev-service"],
        required=True,
        help="기준선 출처: prod-public=prod 공개 API, dev-service=dev published 한정",
    )
    baseline_parser.add_argument(
        "--out", type=Path, required=True, help="기준선 JSON 출력 경로"
    )
    baseline_parser.set_defaults(func=main_audit_export_baseline)

    bootstrap_parser = subparsers.add_parser(
        "font-audit-bootstrap",
        help="고정 prod-Tier A-Tier B snapshot으로 안정 출처키 manifest 생성",
    )
    bootstrap_parser.add_argument(
        "--prod-snapshot", type=Path, required=True, help="prod 공개 기준선 JSON 경로"
    )
    bootstrap_parser.add_argument(
        "--out", type=Path, required=True, help="bootstrap JSON 출력 경로"
    )
    bootstrap_parser.set_defaults(func=main_audit_bootstrap)

    bootstrap_apply_parser = subparsers.add_parser(
        "font-audit-bootstrap-apply",
        help="bootstrap manifest를 적용",
    )
    bootstrap_apply_parser.add_argument(
        "--manifest", type=Path, required=True, help="bootstrap-manifest.json 경로"
    )
    bootstrap_apply_parser.add_argument(
        "--target", choices=["dev", "prod"], required=True, help="대상 환경"
    )
    bootstrap_apply_parser.add_argument(
        "--confirm-hash", required=True, help="manifest SHA-256 확인"
    )
    bootstrap_apply_parser.set_defaults(func=main_audit_bootstrap_apply)

    audit_run_parser = subparsers.add_parser(
        "font-audit-run",
        help="50종 법적-메타데이터 감사 실행 (기본 dev 저장, --dry-run은 파일만 생성)",
    )
    audit_run_parser.add_argument("--stage", choices=["legal", "metadata"], required=True)
    audit_run_parser.add_argument("--limit", type=int, default=50)
    audit_run_parser.add_argument(
        "--require-slug", action="append", default=[], help="파일럿에 반드시 포함할 slug"
    )
    audit_run_parser.add_argument("--out", type=Path, required=True)
    audit_run_parser.add_argument(
        "--bootstrap",
        type=Path,
        default=Path("output") / "audit" / "bootstrap-manifest.json",
        help="검증된 안정 출처키 bootstrap artifact 경로",
    )
    audit_run_parser.add_argument(
        "--dry-run", action="store_true", help="DB 자격증명-DB 쓰기 없이 파일 산출물만 생성"
    )
    audit_run_parser.set_defaults(func=main_audit_run)

    audit_scan_parser = subparsers.add_parser(
        "font-audit-scan",
        help="공개 prod 링크를 읽기 전용 검사해 검증 가능한 artifact 생성",
    )
    audit_scan_parser.add_argument("--kind", choices=["download", "license"], required=True)
    audit_scan_parser.add_argument("--source", choices=["prod-public"], required=True)
    audit_scan_parser.add_argument("--out", type=Path, required=True)
    audit_scan_parser.set_defaults(func=main_audit_scan)

    audit_import_parser = subparsers.add_parser(
        "font-audit-import",
        help="검증된 예약 artifact를 dev 감사 테이블에만 import",
    )
    audit_import_parser.add_argument("--artifact", type=Path, required=True)
    audit_import_parser.add_argument("--sha256", type=Path, required=True)
    audit_import_parser.set_defaults(func=main_audit_import)

    manifest_parser = subparsers.add_parser(
        "font-audit-manifest",
        help="검증된 감사 manifest 적용",
    )
    manifest_subparsers = manifest_parser.add_subparsers(dest="manifest_action", required=True)
    manifest_apply_parser = manifest_subparsers.add_parser("apply")
    manifest_apply_parser.add_argument("--manifest", type=Path, required=True)
    manifest_apply_parser.add_argument("--sha256", type=Path, required=True)
    manifest_apply_parser.add_argument("--target", choices=["dev", "prod"], required=True)
    manifest_apply_parser.add_argument("--confirm-hash", required=True)
    manifest_apply_parser.add_argument("--approved-hash")
    manifest_apply_parser.add_argument("--approval-id")
    manifest_apply_parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="적용 전 자동 실행되는 preflight 대조를 건너뛴다 (기본은 실행)",
    )
    manifest_apply_parser.set_defaults(func=main_audit_manifest_apply)

    manifest_preflight_parser = manifest_subparsers.add_parser(
        "preflight",
        help="manifest와 DB를 필드 단위로 대조하는 읽기 전용 사전 점검",
    )
    manifest_preflight_parser.add_argument("--manifest", type=Path, required=True)
    manifest_preflight_parser.add_argument("--sha256", type=Path, required=True)
    manifest_preflight_parser.add_argument("--target", choices=["dev", "prod"], required=True)
    manifest_preflight_parser.set_defaults(func=main_audit_manifest_preflight)

    manifest_build_parser = manifest_subparsers.add_parser("build")
    manifest_build_parser.add_argument("--run-id", required=True, help="조회할 감사 run의 UUID")
    manifest_build_parser.add_argument("--target", choices=["dev", "prod"], default="dev", help="현재 상태 조회 대상")
    manifest_build_parser.add_argument("--out", type=Path, required=True, help="manifest 번들 저장 디렉터리")
    manifest_build_parser.add_argument("--chunk-size", type=int, default=0, help="청크 분할 크기 (0=분할 안함, 기본값)")
    manifest_build_parser.set_defaults(func=main_audit_manifest_build)

    review_parser = subparsers.add_parser(
        "font-audit-review",
        help="metadata findings 무인 승인 또는 사람 검수 findings 배치 승인",
    )
    # action별로 인자를 완전히 분리한다(HIGH 리뷰 지적 - 공유 플래그에서는 auto-approve에
    # --dry-run/--field/--reviewed-by를 줘도 argparse가 통과시키고 auto-approve 경로가
    # 이를 조용히 무시해 "미리보기인 줄 알았는데 실제 승인됨" 사고가 난다). 이제
    # auto-approve 서브파서에는 approve 전용 플래그 자체가 존재하지 않으므로 그런
    # 인자를 주면 argparse가 "unrecognized arguments"로 즉시 거부한다.
    review_subparsers = review_parser.add_subparsers(dest="action", required=True)

    review_auto_approve_parser = review_subparsers.add_parser(
        "auto-approve", help="metadata findings 무인 승인(evidence-values 대조 필수)"
    )
    review_auto_approve_parser.add_argument(
        "--run-id", required=True, help="조회할 감사 run의 UUID"
    )
    review_auto_approve_parser.set_defaults(func=main_audit_review)

    review_approve_parser = review_subparsers.add_parser(
        "approve", help="사람이 검수를 마친 findings를 필드 단위로 배치 승인"
    )
    review_approve_parser.add_argument(
        "--run-id", required=True, help="조회할 감사 run의 UUID"
    )
    review_approve_parser.add_argument(
        "--reviewed-by", type=str, default=None, help="검수자 식별자(필수)"
    )
    review_approve_parser.add_argument(
        "--field",
        action="append",
        default=None,
        help="승인 대상 field_name(반복 가능, 생략 시 MANUAL_APPROVABLE_FIELDS 전체)",
    )
    review_approve_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="승인 없이 대상 건수와 필드별 분포만 로깅",
    )
    review_approve_parser.add_argument(
        "--include-manual-review",
        action="store_true",
        help="auto_applicable=false인 finding까지 승인 대상에 포함(사람이 개별 검토한 뒤에만 사용)",
    )
    review_approve_parser.set_defaults(func=main_audit_review)

    crawl_all_parser = subparsers.add_parser(
        "font-audit-crawl-all",
        help="전수 Tier B 폰트 배치 크롤링 (체크포인트 재개 지원)",
    )
    crawl_all_parser.add_argument("--stage", choices=["legal"], default="legal", help="감사 단계 (기본값 legal)")
    crawl_all_parser.add_argument("--batch-size", type=int, default=100, help="배치 크기 (기본값 100)")
    crawl_all_parser.add_argument("--out", type=Path, required=True, help="결과 저장 경로")
    crawl_all_parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("output") / "audit" / "crawl-all-progress.json",
        help="체크포인트 파일 경로 (기본값 output/audit/crawl-all-progress.json)",
    )
    crawl_all_parser.add_argument(
        "--bootstrap",
        type=Path,
        default=Path("output") / "audit" / "bootstrap-manifest.json",
        help="bootstrap artifact 경로",
    )
    crawl_all_parser.add_argument("--dry-run", action="store_true", help="dry-run 모드")
    crawl_all_parser.set_defaults(func=main_audit_crawl_all)

    tier_a_meta_parser = subparsers.add_parser(
        "font-audit-tier-a-meta",
        help="Tier A 공식 메타데이터 수집 (권리사 판정+specimen URL fallback)",
    )
    tier_a_meta_parser.add_argument("--limit", type=int, default=50, help="수집 대상 한도 (기본값 50)")
    tier_a_meta_parser.add_argument("--dry-run", action="store_true", help="DB 쓰기 없이 메모리만 사용")
    tier_a_meta_parser.add_argument("--out", type=Path, required=True, help="결과 보고서 JSON 경로")
    tier_a_meta_parser.set_defaults(func=main_audit_tier_a_meta)

    kogl_preview_parser = subparsers.add_parser(
        "font-audit-kogl-preview",
        help="KOGL 후보 폰트 조회 및 유형 판별 미리보기 (preview 전용, DB 쓰기 없음)",
    )
    kogl_preview_parser.add_argument(
        "--out", type=Path, required=True, help="KOGL 판별 결과 JSON 경로"
    )
    kogl_preview_parser.set_defaults(func=main_audit_kogl_preview)

    args = parser.parse_args()

    if hasattr(args, "func"):
        sys.exit(args.func(args))
    elif args.command == "tier-a" or not args.command:
        # tier-a 또는 명령어 없음 = 기본 파이프라인
        sys.exit(main())
    else:
        parser.print_help()
        sys.exit(1)
