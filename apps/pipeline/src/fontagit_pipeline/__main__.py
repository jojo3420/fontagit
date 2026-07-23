"""CLI 진입점 및 파이프라인 오케스트레이션."""

import argparse
import logging
import os
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
    from typing import cast

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
        logger.info("감사 manifest 적용 완료: target=%s result=%s", args.target, response.data)
        return 0
    except (ManifestError, OSError, ValueError) as exc:
        logger.error("감사 manifest 적용 중단: %s", exc)
        return 3
    except Exception as exc:  # 외부 DB 경계
        logger.error("감사 manifest RPC 실패: %s", exc.__class__.__name__)
        return 3


def main_audit_manifest_build(args: argparse.Namespace) -> int:
    """approved findings를 조회하여 manifest 번들을 생성한다.

    - run_id로 기준 run을 조회
    - 해당 run의 approved findings 조회
    - 현재 font 스냅샷 조회
    - build_manifest로 번들 생성
    - write_manifest_bundle로 파일 저장

    build는 approve를 하지 않는다 — 이미 approved인 finding만 조회한다.
    """
    from uuid import UUID

    from fontagit_pipeline.audit_manifest import ManifestError, build_manifest, write_manifest_bundle
    from fontagit_pipeline.audit_store import SupabaseAuditStore
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

        # 3. 현재 font 스냅샷 조회
        current_rows = store.get_current_fonts_with_snapshots(run_id, target_store=target_store)
        logger.info("현재 font 스냅샷 조회: count=%d", len(current_rows))

        if target_store is not None:
            # 대상 DB 문맥 재바인딩: finding.font_id를 evidence가 붙은 대상 폰트로 치환
            evidence_to_font: dict[str, str] = {}
            for row in current_rows:
                row_snapshots = row.get("evidence_snapshots")
                if isinstance(row_snapshots, list):
                    for snap in row_snapshots:
                        evidence_to_font[str(snap.get("id"))] = str(row.get("id"))
            for finding in approved_findings:
                target_font_id = evidence_to_font.get(str(finding.get("evidence_id")))
                if target_font_id is None:
                    raise ManifestError(
                        f"finding evidence가 대상 현재행에 없습니다: {finding.get('id')}"
                    )
                finding["font_id"] = target_font_id

        # 4. manifest 번들 생성
        bundle = build_manifest(run, approved_findings, current_rows)
        logger.info(
            "manifest 번들 생성: forward_sha256=%s reverse_sha256=%s",
            bundle.forward_sha256[:8] + "...",
            bundle.reverse_sha256[:8] + "...",
        )

        # 5. 파일 저장
        paths = write_manifest_bundle(bundle, args.out)
        logger.info(
            "manifest 번들 저장: forward=%s reverse=%s",
            paths.forward,
            paths.reverse,
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

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
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
            logger.warning("승인 대상 findings가 없습니다: run_id=%s", run_id)
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

            try:
                if not isinstance(finding_id, str):
                    raise ValueError(f"invalid finding_id: {finding_id}")

                # values-evidence 대조 (tags/weights 전용)
                if field_name in {"tags", "weights"} and evidence_id and isinstance(evidence_id, str):
                    extracted = evidence_by_id.get(evidence_id)
                    if extracted:
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
    manifest_apply_parser.set_defaults(func=main_audit_manifest_apply)

    manifest_build_parser = manifest_subparsers.add_parser("build")
    manifest_build_parser.add_argument("--run-id", required=True, help="조회할 감사 run의 UUID")
    manifest_build_parser.add_argument("--target", choices=["dev", "prod"], default="dev", help="현재 상태 조회 대상")
    manifest_build_parser.add_argument("--out", type=Path, required=True, help="manifest 번들 저장 디렉터리")
    manifest_build_parser.set_defaults(func=main_audit_manifest_build)

    review_parser = subparsers.add_parser(
        "font-audit-review",
        help="metadata findings 무인 승인",
    )
    review_parser.add_argument(
        "action",
        choices=["auto-approve"],
        help="실행 액션",
    )
    review_parser.add_argument(
        "--run-id", required=True, help="조회할 감사 run의 UUID"
    )
    review_parser.set_defaults(func=main_audit_review)

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

    args = parser.parse_args()

    if hasattr(args, "func"):
        sys.exit(args.func(args))
    elif args.command == "tier-a" or not args.command:
        # tier-a 또는 명령어 없음 = 기본 파이프라인
        sys.exit(main())
    else:
        parser.print_help()
        sys.exit(1)
