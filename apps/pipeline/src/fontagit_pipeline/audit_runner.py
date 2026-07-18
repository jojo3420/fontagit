"""법적 근거 수집 파일럿의 결정론적 선택과 dry-run 산출물."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
from collections import defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, UUID, uuid5

from fontagit_pipeline.audit_http import FetchError, FetchResult, classify_download, fetch_public_url
from fontagit_pipeline.audit_license import classify_license
from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot, extract_noonnu_font
from fontagit_pipeline.audit_policy import RegistryEntry, SourceRegistry
from fontagit_pipeline.audit_store import AuditStore, FindingDraft, SnapshotDraft

_REPORTED_SLUGS = ("흰꼬리수리", "횡성한우체")
_DOCUMENT_FIELDS = {
    "homepage": "foundry_url",
    "download": "download_url",
    "license": "license_source_url",
}


class AuditInputError(ValueError):
    """파일럿 입력이 감사 가능한 상태가 아닐 때 발생한다."""


class AuditGateError(RuntimeError):
    """검수 대기 또는 과도한 재확인 비율이 남았을 때 발생한다."""


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
    license_source_url: str | None = None
    candidates: tuple["CandidateUrl", ...] = ()


@dataclass(frozen=True)
class CandidateUrl:
    """문서 역할과 일치 여부를 확인할 수 있는 URL 후보.

    후보의 ``source`` 표시는 우선순위 힌트일 뿐이다. official/public은
    반드시 승인 레지스트리의 도메인·제작사·역할과 다시 일치해야 한다.
    """

    url: str
    document_role: str
    source: str
    name_ko: str | None
    maker: str | None
    meaningful_cta: bool = False


AuditFetcher = Callable[[str], FetchResult]


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
        try:
            targets.append(
                FontTarget(
                    font_id=UUID(_required(entry, "font_id")),
                    slug=_required(entry, "slug"),
                    name_ko=_optional(before, "name_ko"),
                    name_en=_optional(before, "name_en"),
                    source_tier=_required(before, "source_tier"),
                    provider=_required(entry, "provider"),
                    provider_record_id=_required(entry, "provider_record_id"),
                    reference_url=_required(entry, "source_url"),
                    foundry=_optional(before, "foundry"),
                )
            )
        except (TypeError, ValueError) as exc:
            raise AuditInputError("bootstrap entry 필드가 올바르지 않습니다") from exc
    return targets


def write_audit_artifacts(report: AuditReport, out: Path) -> str:
    """감사 보고서를 JSON·Markdown과 SHA-256으로 원자 저장한다."""
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
    discovery = [
        item for item in candidates if _candidate_priority(item, registry, target)[0] >= 4
    ]
    snapshot_ids: list[UUID] = []
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

    outcomes: list[str] = []
    for role, field_name in _DOCUMENT_FIELDS.items():
        candidate = _choose_candidate(target, role, registry)
        if candidate is None:
            continue
        priority, source_kind = _candidate_priority(candidate, registry, target)
        # 일반 discovery와 승인되지 않은 기존 DB URL은 요청하지 않는다.
        if priority >= 4 or source_kind not in {"official", "public", "noonnu"}:
            continue

        if dry_run:
            snapshot = _planned_snapshot(target, candidate, source_kind)
            snapshot_id = _save_snapshot(store, run_id, snapshot, dry_run=True)
            snapshot_ids.append(snapshot_id)
            if role in {"download", "license"}:
                outcomes.append("pending")
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
                        review_reason="dry-run candidate was not requested",
                    ),
                    dry_run=True,
                )
            )
            continue

        fetched = fetcher(candidate.url)
        parsed = _parse_candidate(fetched, candidate)
        extracted, evidence = _extracted_evidence(target, candidate, parsed)
        snapshot = _fetched_snapshot(
            target,
            candidate,
            fetched,
            source_kind,
            extracted,
            evidence,
        )
        snapshot_id = _save_snapshot(store, run_id, snapshot, dry_run)
        snapshot_ids.append(snapshot_id)
        if not dry_run:
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

        outcome = _candidate_outcome(candidate, fetched, parsed, registry, rules)
        if role in {"download", "license"}:
            outcomes.append(outcome)
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
    if _is_noonnu_url(target.reference_url):
        candidates.append(
            CandidateUrl(
                url=target.reference_url,
                document_role="homepage",
                source="noonnu",
                name_ko=target.name_ko,
                maker=target.foundry,
                meaningful_cta=True,
            )
        )
    unique: dict[tuple[str, str], CandidateUrl] = {}
    for candidate in candidates:
        unique.setdefault((candidate.document_role, candidate.url), candidate)
    return list(unique.values())


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
) -> tuple[dict[str, object], dict[str, object]]:
    extracted: dict[str, object] = {
        "candidate_role": candidate.document_role,
        "candidate_source": candidate.source,
        "name_ko": parsed.name_ko if parsed else candidate.name_ko,
        "maker": parsed.foundry if parsed else candidate.maker,
        "target_slug": target.slug,
    }
    evidence: dict[str, object] = {"candidate_url": "audit_runner.candidate"}
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
) -> SnapshotDraft:
    document_kind = "metadata" if candidate.document_role == "homepage" else candidate.document_role
    normalized_payload = {
        "request_url": candidate.url,
        "final_url": fetched.final_url,
        "document_role": candidate.document_role,
        "source_kind": source_kind,
        "extracted": extracted,
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
        extracted=dict(extracted),
        evidence_locations=dict(evidence),
        normalized_sha256=normalized,
        extraction_rule_id="candidate-priority-v2",
    )


def _planned_snapshot(
    target: FontTarget, candidate: CandidateUrl, source_kind: str
) -> SnapshotDraft:
    """dry-run의 후보 메타데이터다. URL을 요청하거나 원문을 보관하지 않는다."""
    document_kind = "metadata" if candidate.document_role == "homepage" else candidate.document_role
    extracted = {
        "candidate_role": candidate.document_role,
        "candidate_source": candidate.source,
        "name_ko": candidate.name_ko,
        "maker": candidate.maker,
        "target_slug": target.slug,
    }
    normalized = hashlib.sha256(
        json.dumps(extracted | {"url": candidate.url}, ensure_ascii=False, sort_keys=True).encode("utf-8")
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
        evidence_locations={"candidate_url": "audit_runner.dry_run"},
        normalized_sha256=normalized,
        extraction_rule_id="candidate-priority-dry-run-v1",
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
            return classify_download([observation])
        # URL 응답만으로는 대상 폰트 파일·문서 일치를 증명할 수 없다.
        return "needs_review"
    if candidate.document_role == "license":
        if candidate.source not in {"official", "public"} or not _parsed_identity_matches(parsed, candidate):
            return "needs_review"
        assert parsed is not None
        return classify_license(parsed, registry, rules).status
    return "needs_review"


def _parsed_identity_matches(parsed: NoonnuFontSnapshot | None, candidate: CandidateUrl) -> bool:
    return bool(
        parsed
        and _normalize_text(parsed.name_ko) == _normalize_text(candidate.name_ko)
        and _normalize_text(parsed.foundry) == _normalize_text(candidate.maker)
    )


def _target_status(outcomes: Sequence[str]) -> str:
    if not outcomes:
        return "pending"
    if "broken" in outcomes:
        return "broken"
    if "needs_review" in outcomes:
        return "needs_review"
    return "verified" if "verified" in outcomes else "pending"


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
        f"{run_id}:{finding.font_id}:{finding.field_name}:{json.dumps(finding.proposed_value, sort_keys=True)}",
    )


def _exactly_one_slug(fonts: Sequence[FontTarget], slug: str) -> FontTarget:
    matches = [font for font in fonts if font.slug == slug]
    if len(matches) != 1:
        raise AuditInputError(f"required slug must match exactly one font: {slug}")
    return matches[0]


def _choose_candidate(
    target: FontTarget,
    role: str,
    registry: SourceRegistry,
) -> CandidateUrl | None:
    """승인 제작사·공공기관·눈누 CTA·기존 주소 순으로 하나만 고른다."""
    candidates = [item for item in _all_candidates(target) if item.document_role == role]
    valid = [item for item in candidates if _candidate_matches_target(item, target)]
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
    entry = _approved_registry_entry(candidate, registry, target)
    if entry is not None and entry.source_kind == "official":
        return 0, "official"
    if entry is not None and entry.source_kind == "public":
        return 1, "public"
    if (
        candidate.source == "noonnu"
        and candidate.meaningful_cta
        and _is_noonnu_url(candidate.url)
        and _is_noonnu_reference(target)
    ):
        return 2, "noonnu"
    if candidate.source == "existing" and entry is not None:
        return 3, entry.source_kind
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
    value = row.get(key)
    return value if isinstance(value, str) and value.strip() else None


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
