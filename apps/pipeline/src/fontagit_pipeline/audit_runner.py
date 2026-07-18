"""법적 근거 수집 파일럿의 결정론적 선택과 dry-run 산출물."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, UUID, uuid5

from fontagit_pipeline.audit_policy import SourceRegistry
from fontagit_pipeline.audit_store import AuditStore, FindingDraft, SnapshotDraft

_REPORTED_NAMES = ("흰꼬리수리", "횡성한우체")


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
    if size < len(_REPORTED_NAMES):
        raise AuditInputError("pilot size must include both reported fonts")
    if len({font.font_id for font in fonts}) != len(fonts):
        raise AuditInputError("font target id is duplicated")

    requested = set(require_slugs)
    required = [
        font
        for name in _REPORTED_NAMES
        for font in fonts
        if font.name_ko == name
    ]
    if len(required) != len(_REPORTED_NAMES):
        raise AuditInputError("reported font is missing from pilot input")
    required.extend(font for font in fonts if font.slug in requested and font not in required)
    if len(required) > size:
        raise AuditInputError("required fonts exceed pilot size")

    remaining = [font for font in fonts if font not in required]
    remaining.sort(key=_pilot_sort_key)
    selected = required + remaining[: size - len(required)]
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
) -> AuditReport:
    """외부 요청 없이 수집 가능한 사실만 append-only로 기록한다.

    일반 검색이나 눈누 참고 URL은 discovery finding으로만 남기며, 자동 요청,
    자동 승인, 공개 폰트 변경은 하지 않는다.
    """
    source_registry = registry if isinstance(registry, SourceRegistry) else SourceRegistry.model_validate(registry)
    baseline_sha256 = _baseline_sha256(targets)
    run_id = _dry_run_id(targets) if dry_run else store.start_run(
        stage="legal", target_count=len(targets), baseline_sha256=baseline_sha256, dry_run=False
    )
    snapshot_ids: list[UUID] = []
    finding_ids: list[UUID] = []
    pending_count = 0

    for target in targets:
        source_kind = source_registry.classify(target.reference_url)
        snapshot = _reference_snapshot(target, source_kind)
        snapshot_id = _snapshot_id(snapshot) if dry_run else store.save_snapshot(run_id, snapshot)
        snapshot_ids.append(snapshot_id)
        finding = FindingDraft(
            font_id=target.font_id,
            field_name="source_discovery",
            before_value=None,
            proposed_value={"reference_url": target.reference_url, "source_kind": source_kind},
            evidence_id=snapshot_id,
            confidence="reference" if source_kind == "discovery" else source_kind,
            review_reason="reference source requires verified document retrieval",
        )
        finding_id = _finding_id(finding) if dry_run else store.save_finding(run_id, finding)
        finding_ids.append(finding_id)
        pending_count += 1

    report = AuditReport(
        run_id=run_id,
        stage="legal",
        dry_run=dry_run,
        targets=list(targets),
        snapshot_ids=snapshot_ids,
        finding_ids=finding_ids,
        pending_count=pending_count,
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


def _reference_snapshot(target: FontTarget, source_kind: str) -> SnapshotDraft:
    kind = source_kind if source_kind in {"official", "public"} else "noonnu"
    extracted = {
        "name_ko": target.name_ko,
        "name_en": target.name_en,
        "foundry": target.foundry,
        "foundry_url": target.foundry_url,
        "download_url": target.download_url,
        "license_source_url": target.license_source_url,
    }
    normalized = hashlib.sha256(
        json.dumps(extracted, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return SnapshotDraft(
        font_id=target.font_id,
        provider=target.provider,
        provider_record_id=target.provider_record_id,
        source_kind=kind,
        document_kind="metadata",
        request_url=target.reference_url,
        final_url=target.reference_url,
        extracted=extracted,
        evidence_locations={"reference_url": "bootstrap.source_url"},
        normalized_sha256=normalized,
        extraction_rule_id="bootstrap-reference-v1",
    )


def _pilot_sort_key(target: FontTarget) -> tuple[int, str, str, str]:
    tier_rank = {"A": 0, "B": 1}.get(target.source_tier, 2)
    domain = (urlparse(target.foundry_url or target.reference_url).hostname or "").casefold()
    return tier_rank, (target.foundry or "").casefold(), domain, target.slug.casefold()


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


def _finding_id(finding: FindingDraft) -> UUID:
    return uuid5(NAMESPACE_URL, f"{finding.font_id}:{finding.field_name}:{json.dumps(finding.proposed_value, sort_keys=True)}")


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
