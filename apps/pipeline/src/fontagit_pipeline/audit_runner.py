"""법적 근거 수집 파일럿의 결정론적 선택과 dry-run 산출물."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import sys
import tempfile
import unicodedata
from collections import defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fontagit_pipeline.audit_http import FetchError, FetchResult, classify_download, fetch_public_url
from fontagit_pipeline.audit_license import classify_license
from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot, extract_noonnu_font
from fontagit_pipeline.audit_policy import RegistryEntry, SourceRegistry
from fontagit_pipeline.audit_store import (
    ApprovedFontFileCandidate,
    AuditStore,
    FindingDraft,
    InMemoryAuditStore,
    SnapshotDraft,
    SupabaseAuditStore,
)

if TYPE_CHECKING:
    from fontagit_pipeline.audit_metadata import FontFileMetadata

_REPORTED_SLUGS = ("흰꼬리수리", "횡성한우체")
_DOCUMENT_FIELDS = {
    "homepage": "foundry_url",
    "download": "download_url",
    "license": "license_source_url",
}
_REQUIRED_LEGAL_ROLES = ("download", "license")
_SCHEDULED_KINDS = {"download", "license"}
_SCHEDULED_ERROR_KINDS = {"blocked", "timeout", "network", "oversize"}
_SCHEDULED_ROOT_FIELDS = {
    "schema_version",
    "run_id",
    "kind",
    "generated_at",
    "target_count",
    "observations",
    "errors",
}
_SCHEDULED_OBSERVATION_FIELDS = {
    "font_id",
    "normalized_url",
    "observed_at",
    "http_status",
    "final_url",
    "content_sha256",
    "error_kind",
}
_MAX_SCHEDULED_ARTIFACT_BYTES = 8 * 1024 * 1024


class AuditInputError(ValueError):
    """파일럿 입력이 감사 가능한 상태가 아닐 때 발생한다."""


class AuditGateError(RuntimeError):
    """검수 대기 또는 과도한 재확인 비율이 남았을 때 발생한다."""


@dataclass(frozen=True)
class ScheduledObservation:
    """예약 실행에서 외부로 내보낼 수 있는 최소 관찰값."""

    font_id: UUID
    normalized_url: str
    observed_at: datetime
    http_status: int | None
    final_url: str | None
    content_sha256: str | None
    error_kind: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "font_id": str(self.font_id),
            "normalized_url": self.normalized_url,
            "observed_at": _utc_text(self.observed_at),
            "http_status": self.http_status,
            "final_url": self.final_url,
            "content_sha256": self.content_sha256,
            "error_kind": self.error_kind,
        }


@dataclass(frozen=True)
class ScheduledArtifact:
    """원문-헤더-자격증명을 담지 않는 예약 감사 산출물."""

    schema_version: int
    run_id: UUID
    kind: str
    generated_at: datetime
    target_count: int
    observations: tuple[ScheduledObservation, ...]
    errors: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "run_id": str(self.run_id),
            "kind": self.kind,
            "generated_at": _utc_text(self.generated_at),
            "target_count": self.target_count,
            "observations": [item.as_dict() for item in self.observations],
            "errors": list(self.errors),
        }

    @property
    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.as_dict())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


@dataclass(frozen=True)
class ScheduledImportResult:
    """공개 폰트 값을 적용하지 않는 import 결과."""

    status: str
    applied_count: int
    observation_count: int
    finding_count: int


@dataclass(frozen=True)
class ScheduledTarget:
    """공개 prod에서 읽은 폰트 ID와 검사 URL."""

    font_id: UUID
    url: str


@dataclass(frozen=True)
class FontTarget:
    """안정 출처키와 URL 역할을 분리한 한 폰트의 감사 입력."""

    font_id: UUID
    slug: str
    name_ko: str | None
    source_tier: str
    provider: str
    provider_record_id: str
    reference_url: str
    name_en: str | None = None
    foundry: str | None = None
    foundry_url: str | None = None
    download_url: str | None = None
    download_source_kind: str | None = None
    download_status: str = "pending"
    download_evidence_id: str | None = None
    license_source_url: str | None = None
    category_ko: str | None = None
    tags: tuple[str, ...] = ()
    weights: tuple[int, ...] = ()
    variants: tuple[str, ...] = ()
    subsets: tuple[str, ...] = ()
    script_status: str = "pending"
    script_checked_at: str | None = None
    script_evidence_id: str | None = None
    candidates: tuple["CandidateUrl", ...] = ()


@dataclass(frozen=True)
class CandidateUrl:
    """문서 역할과 일치 여부를 확인할 수 있는 URL 후보.

    후보의 ``source`` 표시는 우선순위 힌트일 뿐이다. official/public은
    반드시 승인 레지스트리의 도메인-제작사-역할과 다시 일치해야 한다.
    """

    url: str
    document_role: str
    source: str
    name_ko: str | None
    maker: str | None
    meaningful_cta: bool = False
    observations: tuple[Mapping[str, object], ...] = ()
    dry_run_status: str | None = None


AuditFetcher = Callable[..., FetchResult]


@dataclass(frozen=True)
class AuditReport:
    """실행 결과와 검수 게이트에 필요한 집계."""

    run_id: UUID
    stage: str
    dry_run: bool
    targets: list[FontTarget]
    snapshot_ids: list[UUID]
    finding_ids: list[UUID]
    verified_count: int = 0
    needs_review_count: int = 0
    broken_count: int = 0
    pending_count: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def target_count(self) -> int:
        return len(self.targets)

    @property
    def success_count(self) -> int:
        return self.target_count - len(self.errors)

    def assert_safe(self) -> None:
        if self.target_count == 0:
            raise AuditGateError("target count must be greater than zero")
        if self.pending_count:
            raise AuditGateError("pending remains")
        if self.target_count and self.needs_review_count / self.target_count > 0.10:
            raise AuditGateError("pilot review ratio exceeds 10%")

    def as_dict(self) -> dict[str, object]:
        domains: dict[str, int] = {}
        for target in self.targets:
            domain = (urlparse(target.reference_url).hostname or "unknown").lower()
            domains[domain] = domains.get(domain, 0) + 1
        return {
            "schema_version": 1,
            "run_id": str(self.run_id),
            "stage": self.stage,
            "dry_run": self.dry_run,
            "targets": [
                {
                    **asdict(target),
                    "font_id": str(target.font_id),
                }
                for target in self.targets
            ],
            "target_count": self.target_count,
            "success_count": self.success_count,
            "verified_count": self.verified_count,
            "needs_review_count": self.needs_review_count,
            "broken_count": self.broken_count,
            "pending_count": self.pending_count,
            "errors": self.errors,
            "snapshot_ids": [str(item) for item in self.snapshot_ids],
            "finding_ids": [str(item) for item in self.finding_ids],
            "domains": dict(sorted(domains.items())),
        }


def select_pilot(
    fonts: Sequence[FontTarget], size: int = 50, *, require_slugs: Sequence[str] = ()
) -> list[FontTarget]:
    """신고 폰트를 고정 포함한 층화 50종 표본을 안정적으로 고른다."""
    if size < len(_REPORTED_SLUGS):
        raise AuditInputError("pilot size must include both reported fonts")
    if len({font.font_id for font in fonts}) != len(fonts):
        raise AuditInputError("font target id is duplicated")
    if len({font.slug for font in fonts}) != len(fonts):
        raise AuditInputError("font target slug is duplicated")
    provider_keys = {(font.provider, font.provider_record_id) for font in fonts}
    if len(provider_keys) != len(fonts):
        raise AuditInputError("font target provider stable key is duplicated")

    if len(set(require_slugs)) != len(require_slugs):
        raise AuditInputError("required slug is duplicated")
    requested = [*_REPORTED_SLUGS, *require_slugs]
    required = [_exactly_one_slug(fonts, slug) for slug in requested]
    required = list(dict.fromkeys(required))
    if len(required) > size:
        raise AuditInputError("required fonts exceed pilot size")

    remaining = [font for font in fonts if font not in required]
    selected = required + _round_robin_strata(remaining, size - len(required))
    if len(selected) != size:
        raise AuditInputError("not enough font targets for requested pilot size")
    return selected


def _resolve_dev_font_ids(
    selected: Sequence[FontTarget],
    store: AuditStore,
) -> list[FontTarget]:
    """prod font_id를 dev font_id로 변환한다 (SupabaseAuditStore인 경우만).

    dry-run (InMemoryAuditStore)이면 변환 없이 원본 반환.
    SupabaseAuditStore면 각 target마다 store.resolve_font_id()로 dev UUID를 조회해
    font_id 필드만 치환한 새 FontTarget 반환.
    """
    if isinstance(store, InMemoryAuditStore):
        # dry-run: 변환 없음
        return list(selected)

    if not isinstance(store, SupabaseAuditStore):
        # 예상 밖의 store 타입: 그대로 반환
        return list(selected)

    resolved: list[FontTarget] = []
    for target in selected:
        dev_font_id = store.resolve_font_id(
            slug=target.slug,
            name_ko=target.name_ko,
            name_en=target.name_en,
            source_tier=target.source_tier,
        )
        if dev_font_id is None:
            raise ValueError(
                f"Cannot resolve font ID for {target.slug} "
                f"(name_ko={target.name_ko}, source_tier={target.source_tier}): "
                f"0 or multiple matches in dev fonts"
            )
        resolved.append(replace(target, font_id=dev_font_id))

    return resolved


def run_legal_audit(
    targets: Sequence[FontTarget],
    store: AuditStore,
    registry: SourceRegistry | Mapping[str, object],
    rules: Mapping[str, object],
    *,
    dry_run: bool = False,
    fetcher: AuditFetcher = fetch_public_url,
) -> AuditReport:
    """승인된 후보만 안전하게 수집하고 검수 finding을 append-only로 기록한다."""
    if not targets:
        raise AuditInputError("audit requires at least one target")
    source_registry = registry if isinstance(registry, SourceRegistry) else SourceRegistry.model_validate(registry)
    _validate_license_rules(rules)
    baseline_sha256 = _baseline_sha256(targets)
    run_id = _dry_run_id(targets) if dry_run else store.start_run(
        stage="legal", target_count=len(targets), baseline_sha256=baseline_sha256, dry_run=False
    )
    snapshot_ids: list[UUID] = []
    finding_ids: list[UUID] = []
    counts = {"verified": 0, "needs_review": 0, "broken": 0, "pending": 0}
    errors: list[str] = []

    for target in targets:
        try:
            result = _audit_target(
                target,
                run_id,
                store,
                source_registry,
                rules,
                dry_run=dry_run,
                fetcher=fetcher,
            )
        except (FetchError, UnicodeError, ValueError) as exc:
            counts["needs_review"] += 1
            errors.append(f"{target.slug}: {type(exc).__name__}")
            continue
        snapshot_ids.extend(result.snapshot_ids)
        finding_ids.extend(result.finding_ids)
        counts[result.status] += 1

    report = AuditReport(
        run_id=run_id,
        stage="legal",
        dry_run=dry_run,
        targets=list(targets),
        snapshot_ids=snapshot_ids,
        finding_ids=finding_ids,
        verified_count=counts["verified"],
        needs_review_count=counts["needs_review"],
        broken_count=counts["broken"],
        pending_count=counts["pending"],
        errors=errors,
    )
    if not dry_run:
        store.complete_run(run_id, report.as_dict())
    return report


def run_metadata_audit(
    targets: Sequence[FontTarget],
    store: AuditStore,
    registry: SourceRegistry | Mapping[str, object],
    *,
    dry_run: bool = False,
    fetcher: AuditFetcher = fetch_public_url,
    font_fetcher: AuditFetcher | None = None,
) -> AuditReport:
    """공식 파일 또는 같은 눈누 snapshot의 파일만 구조화해 감사한다."""
    from fontagit_pipeline.audit_metadata import compare_metadata

    if not targets:
        raise AuditInputError("metadata audit requires at least one target")
    source_registry = (
        registry if isinstance(registry, SourceRegistry) else SourceRegistry.model_validate(registry)
    )
    effective_font_fetcher = font_fetcher
    if effective_font_fetcher is None:
        effective_font_fetcher = (
            (lambda url: fetch_public_url(url, max_body_bytes=32 * 1024 * 1024))
            if fetcher is fetch_public_url
            else fetcher
        )
    baseline_sha256 = _baseline_sha256(targets)
    run_id = (
        uuid5(NAMESPACE_URL, f"fontagit:metadata:{baseline_sha256}")
        if dry_run
        else store.start_run(
            stage="metadata",
            target_count=len(targets),
            baseline_sha256=baseline_sha256,
            dry_run=False,
        )
    )
    snapshot_ids: list[UUID] = []
    finding_ids: list[UUID] = []
    verified = 0
    needs_review = 0
    errors: list[str] = []
    for target in targets:
        if dry_run:
            finding = FindingDraft(
                font_id=target.font_id,
                field_name="script_status",
                before_value=target.script_status,
                proposed_value="needs_review",
                evidence_id=None,
                confidence="unverified",
                review_reason="dry-run does not download font files",
            )
            finding_ids.append(_save_finding(store, run_id, finding, dry_run=True))
            needs_review += 1
            continue
        if not sys.platform.startswith("linux"):
            needs_review += 1
            errors.append(f"{target.slug}: unsupported_platform")
            finding = FindingDraft(
                font_id=target.font_id,
                field_name="script_status",
                before_value=target.script_status,
                proposed_value="needs_review",
                evidence_id=None,
                confidence="unverified",
                review_reason="metadata execution requires Linux isolation",
            )
            finding_ids.append(_save_finding(store, run_id, finding, dry_run=False))
            continue
        try:
            approved_files = store.approved_font_file_candidates(
                target.font_id,
                target.provider,
                target.provider_record_id,
            )
            evidence, metadata = _collect_metadata_evidence(
                target,
                source_registry,
                approved_files=approved_files,
                fetcher=fetcher,
                font_fetcher=effective_font_fetcher,
            )
            snapshot_id = _save_snapshot(store, run_id, evidence, dry_run=False)
            snapshot_ids.append(snapshot_id)
            findings = compare_metadata(target, evidence, metadata)
            script_auto = next(
                (
                    item.auto_applicable
                    for item in findings
                    if item.field_name == "script_status"
                ),
                False,
            )
            checked_at = evidence.collected_at or datetime.now(UTC)
            confidence = (
                evidence.source_kind
                if evidence.source_kind in {"official", "public"}
                else "reference"
            )
            findings.extend(
                (
                    FindingDraft(
                        font_id=target.font_id,
                        field_name="script_checked_at",
                        before_value=target.script_checked_at,
                        proposed_value=checked_at.isoformat(),
                        evidence_id=snapshot_id,
                        confidence=confidence,
                        review_reason="font file cmap checked",
                        auto_applicable=script_auto,
                    ),
                    FindingDraft(
                        font_id=target.font_id,
                        field_name="script_evidence_id",
                        before_value=target.script_evidence_id,
                        proposed_value=str(snapshot_id),
                        evidence_id=snapshot_id,
                        confidence=confidence,
                        review_reason="font file evidence bound",
                        auto_applicable=script_auto,
                    ),
                )
            )
            for finding in findings:
                saved = replace(finding, evidence_id=snapshot_id)
                finding_ids.append(_save_finding(store, run_id, saved, dry_run=False))
            status = next(
                (
                    item.proposed_value
                    for item in findings
                    if item.field_name == "script_status"
                ),
                "needs_review",
            )
            if status == "verified":
                verified += 1
            else:
                needs_review += 1
        except (FetchError, OSError, UnicodeError, ValueError) as exc:
            needs_review += 1
            errors.append(f"{target.slug}: {type(exc).__name__}")
            finding = FindingDraft(
                font_id=target.font_id,
                field_name="script_status",
                before_value=target.script_status,
                proposed_value="needs_review",
                evidence_id=None,
                confidence="unverified",
                review_reason=f"font metadata unavailable: {type(exc).__name__}",
            )
            finding_ids.append(_save_finding(store, run_id, finding, dry_run=False))
    report = AuditReport(
        run_id=run_id,
        stage="metadata",
        dry_run=dry_run,
        targets=list(targets),
        snapshot_ids=snapshot_ids,
        finding_ids=finding_ids,
        verified_count=verified,
        needs_review_count=needs_review,
        errors=errors,
    )
    if not dry_run:
        store.complete_run(run_id, report.as_dict())
    return report


def _collect_metadata_evidence(
    target: FontTarget,
    registry: SourceRegistry,
    *,
    approved_files: Sequence[ApprovedFontFileCandidate],
    fetcher: AuditFetcher,
    font_fetcher: AuditFetcher,
) -> tuple[SnapshotDraft, FontFileMetadata]:
    """승인 파일 또는 동일 눈누 상세의 @font-face 파일만 읽는다."""
    from fontagit_pipeline.audit_metadata import (
        MAX_FONT_FILE_BYTES,
        classify_scripts,
        inspect_font_metadata,
        merge_font_metadata,
    )

    source_kind: str
    source_page: str
    file_urls: list[str]
    partial_file = False
    if approved_files:
        approved_candidate = approved_files[0]
        source_kind = approved_candidate.source_kind
        source_page = approved_candidate.request_url
        file_urls = [approved_candidate.url]
    elif _is_noonnu_reference(target):
        page = fetcher(target.reference_url)
        parsed = _parse_candidate(
            page,
            CandidateUrl(
                url=target.reference_url,
                document_role="metadata",
                source="noonnu",
                name_ko=target.name_ko,
                maker=target.foundry,
            ),
        )
        if not _discovered_identity_matches(target, parsed) or parsed is None:
            raise AuditInputError("noonnu metadata identity does not match target")
        file_urls = list(dict.fromkeys(parsed.font_file_candidates))
        if not file_urls:
            raise AuditInputError("noonnu snapshot has no font file candidate")
        source_kind = "noonnu"
        source_page = target.reference_url
        unicode_blocks = sum(
            "unicode-range" in block.casefold() for block in parsed.font_face_css
        )
        partial_file = unicode_blocks > len(file_urls)
    else:
        # 기존 DB URL은 승인 finding이 아니므로 레지스트리의 제작사-역할이
        # 다시 일치할 때만 마지막 fallback으로 사용한다.
        existing: list[tuple[str, CandidateUrl]] = []
        for candidate in target.candidates:
            entry = _approved_registry_entry(candidate, registry, target)
            if (
                candidate.source == "existing"
                and candidate.document_role == "download"
                and entry is not None
                and _candidate_matches_target(candidate, target)
            ):
                existing.append((entry.source_kind, candidate))
        existing.sort(key=lambda item: ({"official": 0, "public": 1}[item[0]], item[1].url))
        if not existing:
            # discovery URL이나 역할 없는 legacy URL은 파일 후보로 승격하지 않는다.
            raise AuditInputError("approved font file candidate is missing")
        source_kind, existing_candidate = existing[0]
        source_page = existing_candidate.url
        file_urls = [existing_candidate.url]

    fetched_files: list[FetchResult] = []
    metadata_files: list[FontFileMetadata] = []
    for file_url in file_urls:
        query = parse_qs(urlparse(file_url).query, keep_blank_values=True)
        partial_file = partial_file or "text" in {key.casefold() for key in query}
        fetched = font_fetcher(file_url, max_bytes=MAX_FONT_FILE_BYTES)
        if fetched.status < 200 or fetched.status >= 300:
            raise AuditInputError("font file response is not successful")
        if not fetched.content or len(fetched.content) > MAX_FONT_FILE_BYTES:
            raise AuditInputError("font file response size is invalid")
        suffix = Path(urlparse(fetched.final_url).path).suffix.lower()
        if suffix not in {".ttf", ".otf", ".ttc", ".woff", ".woff2"}:
            suffix = ".font"
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", suffix=suffix, prefix="fontagit-audit-", delete=False
            ) as handle:
                handle.write(fetched.content)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)
            inspected = inspect_font_metadata(temporary_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        fetched_files.append(fetched)
        metadata_files.append(inspected)

    merged = merge_font_metadata(metadata_files, partial_file=partial_file)
    coverage = classify_scripts(merged.codepoints)
    extracted = {
        **merged.extracted(),
        "evidence_role": "font-file-script",
        "subsets": coverage.subsets,
        "script_status": coverage.status,
        "hangul_glyph_count": coverage.hangul_glyph_count,
        "common_hangul_count": coverage.common_hangul_count,
        "font_file_count": len(fetched_files),
        "font_file_urls": file_urls,
    }
    normalized_sha256 = hashlib.sha256(
        json.dumps(extracted, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    first = fetched_files[0]
    snapshot = SnapshotDraft(
        font_id=target.font_id,
        provider=target.provider,
        provider_record_id=target.provider_record_id,
        source_kind=source_kind,
        document_kind="metadata",
        request_url=source_page,
        final_url=first.final_url,
        http_status=first.status,
        raw_text=None,
        raw_sha256=merged.file_sha256,
        normalized_sha256=normalized_sha256,
        extracted=extracted,
        evidence_locations={
            "font_files": "approved download candidate"
            if source_kind in {"official", "public"}
            else "same noonnu snapshot @font-face",
        },
        extraction_rule_id="fonttools-cmap-v1",
        parser_version=merged.parser_version,
        collected_at=datetime.now(UTC),
    )
    return snapshot, merged


def load_bootstrap_targets(path: Path) -> list[FontTarget]:
    """완료된 안정 출처키 bootstrap 산출물만 파일럿 입력으로 허용한다."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditInputError("bootstrap artifact를 읽을 수 없습니다") from exc
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise AuditInputError("bootstrap artifact entries가 올바르지 않습니다")
    targets: list[FontTarget] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise AuditInputError("bootstrap entry가 올바르지 않습니다")
        before = entry.get("before")
        if not isinstance(before, Mapping):
            raise AuditInputError("bootstrap entry before가 올바르지 않습니다")
        current = entry.get("current")
        if not isinstance(current, Mapping):
            raise AuditInputError("bootstrap entry current가 올바르지 않습니다")
        if set(before) != set(current) or set(current) != {
            "slug",
            "name_ko",
            "name_en",
            "foundry",
            "source_tier",
            "official_url",
            "foundry_url",
            "download_url",
            "license_source_url",
            "category_ko",
            "tags",
            "weights",
            "variants",
            "subsets",
            "script_status",
            "script_checked_at",
            "script_evidence_id",
            "download_source_kind",
            "download_status",
            "download_evidence_id",
            "status",
            "updated_at",
        }:
            raise AuditInputError("bootstrap current 필드 계약이 올바르지 않습니다")
        values = current
        try:
            name_ko = _optional(values, "name_ko")
            foundry = _optional(values, "foundry")
            # bootstrap의 before.official_url은 이전 적재값이라는 증거다.
            # 역할을 알 수 없으므로 현재 URL이나 자동 적용 후보로 승격하지 않는다.
            legacy_url = _optional(before, "official_url")
            current_download = _optional(values, "download_url")
            download_source_kind = _optional(values, "download_source_kind")
            download_status = _required(values, "download_status")
            download_evidence_id = _optional(values, "download_evidence_id")
            current_download_is_verified = (
                current_download is not None
                and download_source_kind in {"official", "public"}
                and download_status == "verified"
                and download_evidence_id is not None
            )
            legacy_candidates = tuple(
                candidate
                for candidate in (
                    CandidateUrl(
                        url=legacy_url or "",
                        document_role="metadata",
                        source="existing-db",
                        name_ko=_optional(before, "name_ko"),
                        maker=_optional(before, "foundry"),
                    )
                    if legacy_url
                    else None,
                    CandidateUrl(
                        url=current_download or "",
                        document_role="download",
                        source="existing",
                        name_ko=name_ko,
                        maker=foundry,
                    )
                    if current_download_is_verified
                    else None,
                )
                if candidate is not None
            )
            targets.append(
                FontTarget(
                    font_id=UUID(_required(entry, "font_id")),
                    slug=_required(entry, "slug"),
                    name_ko=name_ko,
                    name_en=_optional(values, "name_en"),
                    source_tier=_required(values, "source_tier"),
                    provider=_required(entry, "provider"),
                    provider_record_id=_required(entry, "provider_record_id"),
                    reference_url=_required(entry, "source_url"),
                    foundry=foundry,
                    foundry_url=_optional(values, "foundry_url"),
                    download_url=current_download,
                    download_source_kind=download_source_kind,
                    download_status=download_status,
                    download_evidence_id=download_evidence_id,
                    license_source_url=_optional(values, "license_source_url"),
                    category_ko=_required(values, "category_ko"),
                    tags=_string_tuple(values.get("tags"), "tags"),
                    weights=_integer_tuple(values.get("weights"), "weights"),
                    variants=_string_tuple(values.get("variants"), "variants"),
                    subsets=_string_tuple(values.get("subsets"), "subsets"),
                    script_status=_required(values, "script_status"),
                    script_checked_at=_optional(values, "script_checked_at"),
                    script_evidence_id=_optional(values, "script_evidence_id"),
                    candidates=legacy_candidates,
                )
            )
        except (TypeError, ValueError) as exc:
            raise AuditInputError("bootstrap entry 필드가 올바르지 않습니다") from exc
    return targets


def build_scheduled_artifact(
    kind: str,
    observations: Sequence[ScheduledObservation],
    *,
    run_id: UUID | None = None,
    generated_at: datetime | None = None,
    errors: Sequence[str] = (),
) -> ScheduledArtifact:
    """완전히 처리된 1회 scan만 canonical artifact로 고정한다."""
    if kind not in _SCHEDULED_KINDS:
        raise AuditGateError("scheduled artifact kind is invalid")
    if not observations:
        raise AuditGateError("empty artifact")
    if errors:
        raise AuditGateError("scheduled scan contains unprocessed errors")
    keys = {(item.font_id, item.normalized_url) for item in observations}
    if len(keys) != len(observations):
        raise AuditGateError("scheduled artifact observation is duplicated")
    for observation in observations:
        _validate_scheduled_observation(observation)
    created = generated_at or datetime.now(UTC)
    _require_aware_utc(created, "generated_at")
    return ScheduledArtifact(
        schema_version=1,
        run_id=run_id or uuid4(),
        kind=kind,
        generated_at=created.astimezone(UTC),
        target_count=len(observations),
        observations=tuple(observations),
        errors=(),
    )


def scan_scheduled_targets(
    kind: str,
    targets: Sequence[ScheduledTarget],
    *,
    fetcher: AuditFetcher = fetch_public_url,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ScheduledArtifact:
    """외부 URL을 기존 SSRF 방어 경계로만 읽어 예약 artifact를 만든다."""
    if not targets:
        raise AuditGateError("scheduled scan target count is zero")
    observations: list[ScheduledObservation] = []
    errors: list[str] = []
    for target in targets:
        try:
            fetched = fetcher(target.url)
        except FetchError as exc:
            errors.append(f"{target.font_id}:{exc.__class__.__name__}")
            continue
        observations.append(
            ScheduledObservation(
                font_id=target.font_id,
                normalized_url=target.url,
                observed_at=now(),
                http_status=fetched.status,
                final_url=fetched.final_url,
                content_sha256=fetched.content_sha256,
            )
        )
    if len(observations) != len(targets):
        raise AuditGateError(
            f"scheduled scan did not process every target ({len(errors)} errors)"
        )
    return build_scheduled_artifact(kind, observations)


def load_prod_public_scheduled_targets(schema: Any, kind: str) -> list[ScheduledTarget]:
    """anon client의 공개 RLS 조회로 검사할 URL 목록을 exact-count 로드한다."""
    if kind not in _SCHEDULED_KINDS:
        raise AuditGateError("scheduled scan kind is invalid")
    column = "download_url" if kind == "download" else "license_source_url"
    rows: list[Mapping[str, object]] = []
    offset = 0
    page_size = 1000
    exact_total: int | None = None
    while True:
        response = (
            schema.table("fonts")
            .select(f"id,{column}", count="exact")
            .eq("status", "published")
            .not_.is_(column, "null")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        page = response.data
        count = response.count
        if not isinstance(page, list) or not all(isinstance(row, Mapping) for row in page):
            raise AuditGateError("prod public scheduled target response is invalid")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise AuditGateError("prod public scheduled target exact count is missing")
        if exact_total is None:
            exact_total = count
        elif exact_total != count:
            raise AuditGateError("prod public scheduled target count changed during scan")
        rows.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
    if exact_total != len(rows) or not rows:
        raise AuditGateError("prod public scheduled target count is zero or incomplete")
    targets: list[ScheduledTarget] = []
    for row in rows:
        font_id = row.get("id")
        url = row.get(column)
        if not isinstance(font_id, str) or not isinstance(url, str) or not url.strip():
            raise AuditGateError("prod public scheduled target schema is invalid")
        _validate_public_http_url(url, column)
        targets.append(ScheduledTarget(font_id=UUID(font_id), url=url))
    if len({(item.font_id, item.url) for item in targets}) != len(targets):
        raise AuditGateError("prod public scheduled target is duplicated")
    return targets


def write_scheduled_artifact(artifact: ScheduledArtifact, out: Path) -> str:
    """검증된 artifact와 SHA sidecar만 원자적으로 저장한다."""
    content = artifact.canonical_bytes
    digest = hashlib.sha256(content).hexdigest()
    _atomic_write(out / "observations.json", content)
    _atomic_write(out / "observations.sha256", f"{digest}\n".encode("ascii"))
    return digest


def read_regular_file_once(path: Path, *, max_bytes: int) -> bytes:
    """symlink을 따르지 않고 같은 열린 파일 설명자에서 한 번만 읽는다."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise AuditGateError("scheduled artifact file is not a safe regular file") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size < 1 or before.st_size > max_bytes:
            raise AuditGateError("scheduled artifact file size is invalid")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        if (
            len(content) > max_bytes
            or before.st_dev != after.st_dev
            or before.st_ino != after.st_ino
            or before.st_size != after.st_size
            or len(content) != after.st_size
        ):
            raise AuditGateError("scheduled artifact file changed while reading")
        return content
    finally:
        os.close(descriptor)


def parse_scheduled_artifact(payload_bytes: bytes, expected_sha256: str) -> ScheduledArtifact:
    """해시를 먼저 확인한 뒤 closed schema와 canonical bytes를 검증한다."""
    if not payload_bytes or len(payload_bytes) > _MAX_SCHEDULED_ARTIFACT_BYTES:
        raise AuditGateError("scheduled artifact size is invalid")
    expected = expected_sha256.strip()
    if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
        raise AuditGateError("scheduled artifact SHA-256 is invalid")
    actual = hashlib.sha256(payload_bytes).hexdigest()
    if not hmac.compare_digest(actual, expected):
        raise AuditGateError("scheduled artifact SHA-256 mismatch")
    try:
        payload = json.loads(payload_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuditGateError("scheduled artifact schema is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != _SCHEDULED_ROOT_FIELDS:
        raise AuditGateError("scheduled artifact schema is not closed")
    if payload.get("schema_version") != 1:
        raise AuditGateError("scheduled artifact schema_version is invalid")
    kind = payload.get("kind")
    raw_observations = payload.get("observations")
    raw_errors = payload.get("errors")
    target_count = payload.get("target_count")
    if (
        kind not in _SCHEDULED_KINDS
        or not isinstance(raw_observations, list)
        or not raw_observations
        or not isinstance(raw_errors, list)
        or raw_errors
        or isinstance(target_count, bool)
        or not isinstance(target_count, int)
        or target_count != len(raw_observations)
    ):
        raise AuditGateError("scheduled artifact schema is invalid")
    try:
        artifact = ScheduledArtifact(
            schema_version=1,
            run_id=UUID(_strict_string(payload, "run_id")),
            kind=kind,
            generated_at=_parse_utc(_strict_string(payload, "generated_at"), "generated_at"),
            target_count=target_count,
            observations=tuple(_parse_scheduled_observation(item) for item in raw_observations),
            errors=(),
        )
    except (TypeError, ValueError) as exc:
        raise AuditGateError("scheduled artifact schema is invalid") from exc
    if len({(item.font_id, item.normalized_url) for item in artifact.observations}) != target_count:
        raise AuditGateError("scheduled artifact observation is duplicated")
    if artifact.canonical_bytes != payload_bytes:
        raise AuditGateError("scheduled artifact bytes are not canonical")
    return artifact


def import_observations(
    payload_bytes: bytes,
    expected_sha256: str,
    store: AuditStore,
) -> ScheduledImportResult:
    """검증한 예약 관찰을 dev 감사 테이블에만 append한다."""
    artifact = parse_scheduled_artifact(payload_bytes, expected_sha256)
    existing_status = store.scheduled_run_status(
        artifact.run_id, kind=artifact.kind, artifact_sha256=artifact.sha256
    )
    if existing_status == "completed":
        return ScheduledImportResult("already_imported", 0, 0, 0)
    if existing_status not in {None, "running"}:
        raise AuditGateError("scheduled run_id is not importable")
    if existing_status is None:
        store.start_scheduled_run(
            artifact.run_id,
            kind=artifact.kind,
            target_count=artifact.target_count,
            artifact_sha256=artifact.sha256,
            started_at=artifact.generated_at,
        )

    statuses: list[str] = []
    finding_count = 0
    for observation in artifact.observations:
        history = store.previous_observations(
            observation.font_id, observation.normalized_url, before=observation.observed_at
        )
        evidence_id: UUID | None = None
        if artifact.kind == "license" and observation.content_sha256 is not None:
            evidence_id = store.save_snapshot(
                artifact.run_id,
                SnapshotDraft(
                    font_id=observation.font_id,
                    provider="scheduled-audit",
                    provider_record_id=str(observation.font_id),
                    source_kind="public",
                    document_kind="license",
                    request_url=observation.normalized_url,
                    final_url=observation.final_url or observation.normalized_url,
                    http_status=observation.http_status,
                    raw_text=None,
                    raw_sha256=observation.content_sha256,
                    normalized_sha256=observation.content_sha256,
                    extracted={"content_sha256": observation.content_sha256},
                    evidence_locations={"source": "scheduled-artifact"},
                    extraction_rule_id="scheduled-license-hash-v1",
                    collected_at=observation.observed_at,
                ),
            )
        store.save_observation(
            artifact.run_id,
            {
                **observation.as_dict(),
                "snapshot_id": str(evidence_id) if evidence_id else None,
            },
        )
        status = _scheduled_status(artifact.kind, observation, history)
        statuses.append(status)
        if status in {"needs_review", "broken"}:
            store.save_finding(
                artifact.run_id,
                FindingDraft(
                    font_id=observation.font_id,
                    field_name=("download_status" if artifact.kind == "download" else "license_status"),
                    before_value=None,
                    proposed_value=status,
                    evidence_id=evidence_id,
                    confidence="unverified",
                    review_reason=(
                        "scheduled_download_observation"
                        if artifact.kind == "download"
                        else "scheduled_license_hash_changed"
                    ),
                    auto_applicable=False,
                ),
            )
            finding_count += 1
    final_status = "broken" if "broken" in statuses else (
        "needs_review" if "needs_review" in statuses else "verified"
    )
    store.complete_run(
        artifact.run_id,
        {
            "success_count": artifact.target_count,
            "verified_count": sum(item == "verified" for item in statuses),
            "needs_review_count": sum(item == "needs_review" for item in statuses),
            "broken_count": sum(item == "broken" for item in statuses),
        },
    )
    return ScheduledImportResult(final_status, 0, artifact.target_count, finding_count)


def _scheduled_status(
    kind: str,
    observation: ScheduledObservation,
    history: Sequence[Mapping[str, object]],
) -> str:
    current = observation.as_dict()
    current["run_id"] = "current"
    if kind == "download":
        if observation.http_status in {404, 410}:
            return classify_download([*history, current])
        return "verified" if observation.http_status is not None and 200 <= observation.http_status < 400 else "needs_review"
    previous_hashes = {
        value
        for row in history
        if isinstance((value := row.get("content_sha256")), str)
    }
    if observation.http_status is None or not (200 <= observation.http_status < 400):
        return "needs_review"
    if observation.content_sha256 is None:
        return "needs_review"
    return "needs_review" if previous_hashes and observation.content_sha256 not in previous_hashes else "verified"


def _parse_scheduled_observation(value: object) -> ScheduledObservation:
    if not isinstance(value, dict) or set(value) != _SCHEDULED_OBSERVATION_FIELDS:
        raise AuditGateError("scheduled observation schema is not closed")
    status = value.get("http_status")
    if isinstance(status, bool) or (status is not None and not isinstance(status, int)):
        raise AuditGateError("scheduled observation http_status is invalid")
    final_url = value.get("final_url")
    digest = value.get("content_sha256")
    error_kind = value.get("error_kind")
    if final_url is not None and not isinstance(final_url, str):
        raise AuditGateError("scheduled observation final_url is invalid")
    if digest is not None and not isinstance(digest, str):
        raise AuditGateError("scheduled observation content_sha256 is invalid")
    if error_kind is not None and not isinstance(error_kind, str):
        raise AuditGateError("scheduled observation error_kind is invalid")
    observation = ScheduledObservation(
        font_id=UUID(_strict_string(value, "font_id")),
        normalized_url=_strict_string(value, "normalized_url"),
        observed_at=_parse_utc(_strict_string(value, "observed_at"), "observed_at"),
        http_status=status,
        final_url=final_url,
        content_sha256=digest,
        error_kind=error_kind,
    )
    _validate_scheduled_observation(observation)
    return observation


def _validate_scheduled_observation(observation: ScheduledObservation) -> None:
    _validate_public_http_url(observation.normalized_url, "normalized_url")
    if observation.final_url is not None:
        _validate_public_http_url(observation.final_url, "final_url")
    _require_aware_utc(observation.observed_at, "observed_at")
    if observation.http_status is not None and not 100 <= observation.http_status <= 599:
        raise AuditGateError("scheduled observation http_status is invalid")
    if observation.content_sha256 is not None and (
        len(observation.content_sha256) != 64
        or any(char not in "0123456789abcdef" for char in observation.content_sha256)
    ):
        raise AuditGateError("scheduled observation content_sha256 is invalid")
    if observation.error_kind not in {None, *_SCHEDULED_ERROR_KINDS}:
        raise AuditGateError("scheduled observation error_kind is invalid")
    if observation.error_kind is not None:
        raise AuditGateError("scheduled artifact contains an unprocessed error")


def _validate_public_http_url(value: str, field_name: str) -> None:
    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError as exc:
        raise AuditGateError(f"scheduled observation {field_name} is invalid") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or port is not None and not 1 <= port <= 65535
    ):
        raise AuditGateError(f"scheduled observation {field_name} is invalid")


def _parse_utc(value: str, field_name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuditGateError(f"scheduled artifact {field_name} is invalid") from exc
    _require_aware_utc(parsed, field_name)
    return parsed.astimezone(UTC)


def _require_aware_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise AuditGateError(f"scheduled artifact {field_name} must include timezone")


def _utc_text(value: datetime) -> str:
    _require_aware_utc(value, "timestamp")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _strict_string(value: Mapping[str, object], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise AuditGateError(f"scheduled artifact {key} is invalid")
    return item


def _canonical_json(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_audit_artifacts(report: AuditReport, out: Path) -> str:
    """감사 보고서를 JSON-Markdown과 SHA-256으로 원자 저장한다."""
    payload = report.as_dict()
    content = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    digest = hashlib.sha256(content).hexdigest()
    _atomic_write(out.with_suffix(".json"), content)
    _atomic_write(out.with_suffix(".json.sha256"), f"{digest}\n".encode("ascii"))
    lines = [
        "# Font audit dry-run",
        "",
        f"- 대상: {report.target_count}",
        f"- verified: {report.verified_count}",
        f"- needs_review: {report.needs_review_count}",
        f"- broken: {report.broken_count}",
        f"- pending: {report.pending_count}",
        f"- JSON SHA-256: {digest}",
    ]
    _atomic_write(out.with_suffix(".md"), ("\n".join(lines) + "\n").encode("utf-8"))
    return digest


def write_dry_run_artifacts(report: AuditReport, out: Path) -> str:
    """하위 호환용 dry-run 산출물 저장 별칭."""
    return write_audit_artifacts(report, out)


@dataclass(frozen=True)
class _TargetResult:
    status: str
    snapshot_ids: list[UUID]
    finding_ids: list[UUID]


def _audit_target(
    target: FontTarget,
    run_id: UUID,
    store: AuditStore,
    registry: SourceRegistry,
    rules: Mapping[str, object],
    *,
    dry_run: bool,
    fetcher: AuditFetcher,
) -> _TargetResult:
    candidates = _all_candidates(target)
    reference_result = _discover_noonnu_cta(
        target,
        candidates,
        run_id,
        store,
        registry,
        dry_run=dry_run,
        fetcher=fetcher,
    )
    effective_target = reference_result.target
    candidates.extend(reference_result.candidates)
    discovery = [
        item for item in candidates if _candidate_priority(item, registry, effective_target)[0] >= 4
    ]
    snapshot_ids: list[UUID] = list(reference_result.snapshot_ids)
    finding_ids: list[UUID] = []

    if discovery:
        finding = FindingDraft(
            font_id=target.font_id,
            field_name="source_discovery",
            before_value=None,
            proposed_value=[
                {"url": item.url, "role": item.document_role, "source": item.source}
                for item in sorted(discovery, key=lambda item: (item.document_role, item.url))
            ],
            evidence_id=None,
            confidence="unverified",
            review_reason="unapproved discovery candidate; request and approval are blocked",
        )
        finding_ids.append(_save_finding(store, run_id, finding, dry_run))

    outcomes = {role: "pending" for role in _REQUIRED_LEGAL_ROLES}
    for role, field_name in _DOCUMENT_FIELDS.items():
        candidate = _choose_candidate(candidates, effective_target, role, registry)
        if candidate is None:
            continue
        priority, source_kind = _candidate_priority(candidate, registry, effective_target)
        # 일반 discovery와 승인되지 않은 기존 DB URL은 요청하지 않는다.
        if priority >= 4 or source_kind not in {"official", "public", "noonnu"}:
            continue

        if dry_run:
            snapshot = _planned_snapshot(target, candidate, source_kind)
            snapshot_id = _save_snapshot(store, run_id, snapshot, dry_run=True)
            snapshot_ids.append(snapshot_id)
            outcome = candidate.dry_run_status or "pending"
            if outcome not in {"verified", "needs_review", "broken", "pending"}:
                raise AuditInputError("invalid dry-run fixture status")
            if role in {"download", "license"}:
                outcomes[role] = outcome
            finding_ids.append(
                _save_finding(
                    store,
                    run_id,
                    FindingDraft(
                        font_id=target.font_id,
                        field_name=field_name,
                        before_value=getattr(target, field_name),
                        proposed_value=candidate.url,
                        evidence_id=snapshot_id,
                        confidence="reference" if source_kind == "noonnu" else source_kind,
                        review_reason=f"dry-run fixture status: {outcome}",
                    ),
                    dry_run=True,
                )
            )
            continue

        fetched = fetcher(candidate.url)
        raw_sha256 = hashlib.sha256(fetched.content).hexdigest()
        parsed = _parse_candidate(fetched, candidate)
        extracted, evidence = _extracted_evidence(
            target, candidate, parsed, raw_sha256=raw_sha256
        )
        snapshot = _fetched_snapshot(
            target,
            candidate,
            fetched,
            source_kind,
            extracted,
            evidence,
            raw_sha256=raw_sha256,
        )
        snapshot_id = _save_snapshot(store, run_id, snapshot, dry_run)
        snapshot_ids.append(snapshot_id)
        if not dry_run:
            _save_link_observation(store, run_id, target, snapshot_id, fetched)

        outcome = _candidate_outcome(candidate, fetched, parsed, registry, rules)
        if role in {"download", "license"}:
            outcomes[role] = outcome
        finding = FindingDraft(
            font_id=target.font_id,
            field_name=field_name,
            before_value=getattr(target, field_name),
            proposed_value=candidate.url,
            evidence_id=snapshot_id,
            confidence=source_kind if source_kind in {"official", "public"} else "reference",
            review_reason=f"{role} candidate status: {outcome}",
            auto_applicable=outcome == "verified" and source_kind in {"official", "public"},
        )
        finding_ids.append(_save_finding(store, run_id, finding, dry_run))

    status = _target_status(outcomes)
    return _TargetResult(status=status, snapshot_ids=snapshot_ids, finding_ids=finding_ids)


def _all_candidates(target: FontTarget) -> list[CandidateUrl]:
    candidates = list(target.candidates)
    existing = {
        "homepage": target.foundry_url,
        "download": target.download_url,
        "license": target.license_source_url,
    }
    for role, url in existing.items():
        if url:
            candidates.append(
                CandidateUrl(
                    url=url,
                    document_role=role,
                    source="existing",
                    name_ko=target.name_ko,
                    maker=target.foundry,
                )
            )
    unique: dict[tuple[str, str], CandidateUrl] = {}
    for candidate in candidates:
        unique.setdefault((candidate.document_role, candidate.url), candidate)
    return list(unique.values())


@dataclass(frozen=True)
class _DiscoveryResult:
    candidates: list[CandidateUrl]
    snapshot_ids: list[UUID]
    target: FontTarget


def _discover_noonnu_cta(
    target: FontTarget,
    candidates: Sequence[CandidateUrl],
    run_id: UUID,
    store: AuditStore,
    registry: SourceRegistry,
    *,
    dry_run: bool,
    fetcher: AuditFetcher,
) -> _DiscoveryResult:
    approved_download = any(
        item.document_role == "download"
        and _candidate_matches_target(item, target)
        and _candidate_priority(item, registry, target)[0] <= 1
        for item in candidates
    )
    if dry_run or approved_download or not _is_noonnu_reference(target):
        return _DiscoveryResult([], [], target)

    fetched = fetcher(target.reference_url)
    reference = CandidateUrl(
        url=target.reference_url,
        document_role="metadata",
        source="noonnu",
        name_ko=target.name_ko,
        maker=target.foundry,
    )
    raw_sha256 = hashlib.sha256(fetched.content).hexdigest()
    parsed = _parse_candidate(fetched, reference)
    extracted, evidence = _extracted_evidence(
        target, reference, parsed, raw_sha256=raw_sha256
    )
    snapshot = _fetched_snapshot(
        target,
        reference,
        fetched,
        "noonnu",
        extracted,
        evidence,
        raw_sha256=raw_sha256,
    )
    snapshot_id = _save_snapshot(store, run_id, snapshot, dry_run)
    if not dry_run:
        _save_link_observation(store, run_id, target, snapshot_id, fetched)
    if not _discovered_identity_matches(target, parsed):
        return _DiscoveryResult([], [snapshot_id], target)
    assert parsed is not None
    resolved_target = replace(target, foundry=parsed.foundry)
    return _DiscoveryResult(
        [
            CandidateUrl(
                url=url,
                document_role="download",
                source="noonnu",
                name_ko=parsed.name_ko,
                maker=parsed.foundry,
                meaningful_cta=True,
            )
            for url in parsed.download_candidates
        ],
        [snapshot_id],
        resolved_target,
    )


def _parse_candidate(
    fetched: FetchResult, candidate: CandidateUrl
) -> NoonnuFontSnapshot | None:
    if fetched.status < 200 or fetched.status >= 300:
        return None
    try:
        html = fetched.content.decode("utf-8")
        return extract_noonnu_font(html, candidate.url)
    except (UnicodeDecodeError, ValueError):
        return None


def _extracted_evidence(
    target: FontTarget,
    candidate: CandidateUrl,
    parsed: NoonnuFontSnapshot | None,
    *,
    raw_sha256: str | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    extracted: dict[str, object] = {
        "candidate_role": candidate.document_role,
        "candidate_source": candidate.source,
        "name_ko": parsed.name_ko if parsed else candidate.name_ko,
        "maker": parsed.foundry if parsed else candidate.maker,
        "target_slug": target.slug,
    }
    evidence: dict[str, object] = {"candidate_url": "audit_runner.candidate"}
    if raw_sha256 is not None:
        extracted["raw_sha256"] = raw_sha256
    if parsed:
        extracted.update(
            {
                "download_candidates": parsed.download_candidates,
                "license_text": parsed.license_text,
                "license_permissions": parsed.license_permissions,
            }
        )
        evidence.update(parsed.evidence_locations)
    return extracted, evidence


def _fetched_snapshot(
    target: FontTarget,
    candidate: CandidateUrl,
    fetched: FetchResult,
    source_kind: str,
    extracted: Mapping[str, object],
    evidence: Mapping[str, object],
    *,
    raw_sha256: str,
) -> SnapshotDraft:
    document_kind = "metadata" if candidate.document_role == "homepage" else candidate.document_role
    extracted_payload = {**extracted, "raw_sha256": raw_sha256}
    normalized_payload = {
        "request_url": candidate.url,
        "final_url": fetched.final_url,
        "document_role": candidate.document_role,
        "source_kind": source_kind,
        "extracted": extracted_payload,
        "evidence_locations": evidence,
    }
    normalized = hashlib.sha256(
        json.dumps(
            normalized_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return SnapshotDraft(
        font_id=target.font_id,
        provider=target.provider,
        provider_record_id=target.provider_record_id,
        source_kind=source_kind,
        document_kind=document_kind,
        request_url=candidate.url,
        final_url=fetched.final_url,
        http_status=fetched.status,
        extracted=extracted_payload,
        evidence_locations=dict(evidence),
        normalized_sha256=normalized,
        raw_sha256=raw_sha256,
        extraction_rule_id="candidate-priority-v2",
    )


def _planned_snapshot(
    target: FontTarget, candidate: CandidateUrl, source_kind: str
) -> SnapshotDraft:
    """네트워크 없는 dry-run에서 후보와 fixture 판정 근거를 안정적으로 남긴다."""
    document_kind = "metadata" if candidate.document_role == "homepage" else candidate.document_role
    extracted = {
        "candidate_role": candidate.document_role,
        "candidate_source": candidate.source,
        "name_ko": candidate.name_ko,
        "maker": candidate.maker,
        "target_slug": target.slug,
        "fixture_status": candidate.dry_run_status,
    }
    evidence = {"candidate_url": "audit_runner.dry_run_fixture"}
    normalized = hashlib.sha256(
        json.dumps(
            {
                "request_url": candidate.url,
                "final_url": candidate.url,
                "document_role": candidate.document_role,
                "source_kind": source_kind,
                "extracted": extracted,
                "evidence_locations": evidence,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return SnapshotDraft(
        font_id=target.font_id,
        provider=target.provider,
        provider_record_id=target.provider_record_id,
        source_kind=source_kind,
        document_kind=document_kind,
        request_url=candidate.url,
        final_url=candidate.url,
        extracted=extracted,
        evidence_locations=evidence,
        normalized_sha256=normalized,
        raw_sha256=None,
        extraction_rule_id="candidate-priority-dry-run-v2",
    )


def _candidate_outcome(
    candidate: CandidateUrl,
    fetched: FetchResult,
    parsed: NoonnuFontSnapshot | None,
    registry: SourceRegistry,
    rules: Mapping[str, object],
) -> str:
    if candidate.document_role == "download":
        observation = {
            "http_status": fetched.status,
            "run_id": "current",
            "observed_at": datetime.now(UTC).isoformat(),
        }
        if fetched.status in {404, 410}:
            return classify_download([*candidate.observations, observation])
        # URL 응답만으로는 대상 폰트 파일-문서 일치를 증명할 수 없다.
        return "verified" if _parsed_identity_matches(parsed, candidate) else "needs_review"
    if candidate.document_role == "license":
        if candidate.source not in {"official", "public"} or not _parsed_identity_matches(parsed, candidate):
            return "needs_review"
        assert parsed is not None
        return classify_license(parsed, registry, rules).status
    return "needs_review"


def _save_link_observation(
    store: AuditStore,
    run_id: UUID,
    target: FontTarget,
    snapshot_id: UUID,
    fetched: FetchResult,
) -> None:
    store.save_observation(
        run_id,
        {
            "font_id": str(target.font_id),
            "snapshot_id": str(snapshot_id),
            "normalized_url": fetched.final_url,
            "observed_at": datetime.now(UTC).isoformat(),
            "http_status": fetched.status,
            "final_url": fetched.final_url,
            "content_sha256": fetched.content_sha256,
            "error_kind": None,
        },
    )


def _parsed_identity_matches(parsed: NoonnuFontSnapshot | None, candidate: CandidateUrl) -> bool:
    return bool(
        parsed
        and _normalize_text(parsed.name_ko) == _normalize_text(candidate.name_ko)
        and _normalize_text(parsed.foundry) == _normalize_text(candidate.maker)
    )


def _target_status(outcomes: Mapping[str, str]) -> str:
    values = [outcomes[role] for role in _REQUIRED_LEGAL_ROLES]
    if "broken" in values:
        return "broken"
    if "needs_review" in values:
        return "needs_review"
    if "pending" in values:
        return "pending"
    return "verified" if all(value == "verified" for value in values) else "pending"


def _save_snapshot(
    store: AuditStore, run_id: UUID, snapshot: SnapshotDraft, dry_run: bool
) -> UUID:
    return _snapshot_id(snapshot) if dry_run else store.save_snapshot(run_id, snapshot)


def _save_finding(
    store: AuditStore, run_id: UUID, finding: FindingDraft, dry_run: bool
) -> UUID:
    return _finding_id(run_id, finding) if dry_run else store.save_finding(run_id, finding)


def _round_robin_strata(fonts: Sequence[FontTarget], count: int) -> list[FontTarget]:
    buckets_by_tier: dict[str, dict[tuple[str, str], deque[FontTarget]]] = defaultdict(dict)
    for font in sorted(fonts, key=lambda item: item.slug.casefold()):
        tier = font.source_tier.casefold()
        foundry = _normalize_text(font.foundry) or "~unknown"
        domain = (urlparse(font.foundry_url or font.reference_url).hostname or "").casefold()
        buckets_by_tier[tier].setdefault((foundry, domain), deque()).append(font)

    tiers = sorted(buckets_by_tier, key=lambda tier: ({"a": 0, "b": 1}.get(tier, 2), tier))
    bucket_orders = {tier: deque(sorted(buckets_by_tier[tier])) for tier in tiers}
    selected: list[FontTarget] = []
    while len(selected) < count and tiers:
        progress = False
        for tier in list(tiers):
            order = bucket_orders[tier]
            if not order:
                tiers.remove(tier)
                continue
            key = order.popleft()
            bucket = buckets_by_tier[tier][key]
            selected.append(bucket.popleft())
            progress = True
            if bucket:
                order.append(key)
            if len(selected) == count:
                break
        if not progress:
            break
    return selected


def _baseline_sha256(targets: Sequence[FontTarget]) -> str:
    values = [
        {"font_id": str(target.font_id), "provider": target.provider, "provider_record_id": target.provider_record_id}
        for target in sorted(targets, key=lambda item: str(item.font_id))
    ]
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _dry_run_id(targets: Sequence[FontTarget]) -> UUID:
    return uuid5(NAMESPACE_URL, f"fontagit:legal:{_baseline_sha256(targets)}")


def _snapshot_id(snapshot: SnapshotDraft) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        ":".join((str(snapshot.font_id), snapshot.provider, snapshot.provider_record_id, snapshot.document_kind, snapshot.normalized_sha256)),
    )


def _finding_id(run_id: UUID, finding: FindingDraft) -> UUID:
    return uuid5(
        NAMESPACE_URL,
        f"{run_id}:{finding.font_id}:{finding.field_name}",
    )


def _exactly_one_slug(fonts: Sequence[FontTarget], slug: str) -> FontTarget:
    matches = [font for font in fonts if font.slug == slug]
    if len(matches) != 1:
        raise AuditInputError(f"required slug must match exactly one font: {slug}")
    return matches[0]


def _choose_candidate(
    candidates: Sequence[CandidateUrl],
    target: FontTarget,
    role: str,
    registry: SourceRegistry,
) -> CandidateUrl | None:
    """승인 제작사-공공기관-눈누 CTA-기존 주소 순으로 하나만 고른다."""
    role_candidates = [item for item in candidates if item.document_role == role]
    valid = [item for item in role_candidates if _candidate_matches_target(item, target)]
    valid.sort(key=lambda item: _candidate_priority(item, registry, target))
    if not valid:
        return None
    selected = valid[0]
    return selected if _candidate_priority(selected, registry, target)[0] < 4 else None


def _candidate_priority(
    candidate: CandidateUrl,
    registry: SourceRegistry,
    target: FontTarget,
) -> tuple[int, str]:
    if candidate.source == "discovery":
        return 4, "discovery"
    entry = _approved_registry_entry(candidate, registry, target)
    if candidate.source == "existing" and entry is not None:
        return 3, entry.source_kind
    if entry is not None and entry.source_kind == "official":
        return 0, "official"
    if entry is not None and entry.source_kind == "public":
        return 1, "public"
    if (
        candidate.source == "noonnu"
        and candidate.meaningful_cta
        and _is_noonnu_reference(target)
    ):
        return 2, "noonnu"
    return 4, "discovery"


def _candidate_matches_target(candidate: CandidateUrl, target: FontTarget) -> bool:
    if candidate.document_role not in _DOCUMENT_FIELDS or not candidate.url.strip():
        return False
    if not target.name_ko or _normalize_text(candidate.name_ko) != _normalize_text(target.name_ko):
        return False
    return bool(
        target.foundry
        and _normalize_text(candidate.maker) == _normalize_text(target.foundry)
    )


def _approved_registry_entry(
    candidate: CandidateUrl, registry: SourceRegistry, target: FontTarget
) -> RegistryEntry | None:
    hostname = (urlparse(candidate.url).hostname or "").lower().rstrip(".")
    for entry in registry.entries:
        domain = (entry.domain or "").lower().rstrip(".")
        roles = {role.casefold() for role in entry.roles or []}
        if (
            domain
            and (hostname == domain or hostname.endswith(f".{domain}"))
            and _normalize_text(entry.maker) == _normalize_text(target.foundry)
            and _normalize_text(candidate.maker) == _normalize_text(target.foundry)
            and candidate.document_role.casefold() in roles
            and entry.source_kind in {"official", "public"}
        ):
            return entry
    return None


def _is_noonnu_reference(target: FontTarget) -> bool:
    return _is_noonnu_url(target.reference_url)


def _is_noonnu_url(url: str) -> bool:
    return (urlparse(url).hostname or "").lower().rstrip(".") == "noonnu.cc"


def _discovered_identity_matches(target: FontTarget, parsed: NoonnuFontSnapshot | None) -> bool:
    """눈누 이름-제작사가 DB 대상과 일치할 때만 외부 CTA를 후보로 남긴다."""
    if parsed is None or not target.name_ko:
        return False
    if _normalize_text(parsed.name_ko) != _normalize_text(target.name_ko):
        return False
    return not target.foundry or _normalize_text(parsed.foundry) == _normalize_text(target.foundry)


def _normalize_text(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(normalized.split())


def _validate_license_rules(rules: Mapping[str, object]) -> None:
    """라이선스 URL 후보도 Task 5의 승인 규칙 형식을 갖춘 입력에서만 다룬다."""
    if rules.get("version") != 1:
        raise AuditInputError("license rules version must be 1")
    for key in ("standard_licenses", "maker_templates"):
        value = rules.get(key, [])
        if not isinstance(value, list):
            raise AuditInputError(f"license rules {key} must be a list")


def _required(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(key)
    return value


def _optional(row: Mapping[str, object], key: str) -> str | None:
    if key not in row:
        raise ValueError(key)
    value = row[key]
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(key)
    return value


def _integer_tuple(value: object, field_name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in value
    ):
        raise ValueError(field_name)
    return tuple(value)


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(field_name)
    return tuple(value)


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
