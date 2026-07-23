"""승인된 폰트 감사 변경을 결정론적 manifest로 고정한다."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


_HASH = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_FIELDS = frozenset(
    {
        "foundry",
        "foundry_url",
        "download_url",
        "license_source_url",
        "license_summary",
        "download_source_kind",
        "license_source_kind",
        "download_evidence_id",
        "license_evidence_id",
        "download_status",
        "license_status",
        "download_checked_at",
        "license_checked_at",
        "allow_commercial",
        "allow_font_sale",
        "allow_embedding",
        "allow_redistribute",
        "allow_modify",
        "attribution_requirement",
        "is_commercial_free",
        "license_verified",
        "name_en",
        "name_ko",
        "category_ko",
        "tags",
        "weights",
        "variants",
        "subsets",
        "script_status",
        "script_checked_at",
        "script_evidence_id",
    }
)
_TEXT_FIELDS = frozenset(
    {
        "foundry",
        "foundry_url",
        "download_url",
        "license_source_url",
        "license_summary",
        "name_en",
        "name_ko",
        "category_ko",
    }
)
_SOURCE_KIND_FIELDS = frozenset({"download_source_kind", "license_source_kind"})
_EVIDENCE_FIELDS = frozenset(
    {"download_evidence_id", "license_evidence_id", "script_evidence_id"}
)
_DATETIME_FIELDS = frozenset(
    {"download_checked_at", "license_checked_at", "script_checked_at"}
)
_PERMISSION_FIELDS = frozenset(
    {
        "allow_commercial",
        "allow_font_sale",
        "allow_embedding",
        "allow_redistribute",
        "allow_modify",
    }
)
_TEXT_ARRAY_FIELDS = frozenset({"tags", "variants", "subsets"})
_METADATA_FIELDS = frozenset(
    {
        "foundry",
        "foundry_url",
        "name_en",
        "name_ko",
        "category_ko",
        "tags",
        "weights",
        "variants",
    }
)
_SCRIPT_FIELDS = frozenset(
    {"subsets", "script_status", "script_checked_at", "script_evidence_id"}
)
_RUN_KEYS = frozenset(
    {
        "id", "stage", "target_environment", "target_count", "success_count",
        "verified_count", "review_count", "broken_count", "parser_version",
        "baseline_sha256", "manifest_sha256", "dry_run", "status", "started_at",
        "finished_at",
    }
)
_SNAPSHOT_KEYS = frozenset(
    {
        "id", "run_id", "provider", "provider_record_id", "source_kind",
        "document_kind", "request_url", "final_url", "http_status", "raw_text",
        "raw_sha256", "normalized_sha256", "extracted", "evidence_locations",
        "extraction_rule_id", "parser_version", "collected_at", "source_key",
    }
)
_FINDING_KEYS = frozenset(
    {
        "id", "run_id", "field_name", "before_value", "proposed_value",
        "evidence_id", "confidence", "auto_applicable", "review_reason", "status",
        "reviewed_by", "reviewed_at", "source_key",
    }
)


class ManifestError(ValueError):
    """manifest가 안전하게 생성-검증될 수 없을 때 발생한다."""


def _evidence_role_is_valid(
    field_name: str, snapshot: Mapping[str, object], confidence: object
) -> bool:
    if field_name.startswith("download_"):
        required_document = "download"
    elif field_name.startswith("license_") or field_name in {
        "allow_commercial",
        "allow_font_sale",
        "allow_embedding",
        "allow_redistribute",
        "allow_modify",
        "attribution_requirement",
        "is_commercial_free",
        "license_verified",
    }:
        required_document = "license"
    elif field_name in _SCRIPT_FIELDS:
        source_kind = snapshot.get("source_kind")
        extracted = snapshot.get("extracted")
        if (
            source_kind == "noonnu"
            and snapshot.get("document_kind") == "metadata"
            and isinstance(extracted, Mapping)
            and extracted.get("evidence_role") == "font-file-script"
        ):
            return confidence == "reference"
        required_document = "metadata"
    elif field_name in _METADATA_FIELDS:
        required_document = "metadata"
    else:
        return False
    source_kind = snapshot.get("source_kind")
    return (
        source_kind in {"official", "public"}
        and snapshot.get("document_kind") == required_document
        and confidence == source_kind
    )


class SourceKey(BaseModel):
    """환경 간에 유지되는 제공자 레코드 키."""

    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1)
    provider_record_id: str = Field(min_length=1)


class ManifestCurrent(BaseModel):
    """변경하지 않고 대상 일치 여부만 확인하는 공개 현재값."""

    model_config = ConfigDict(extra="forbid")
    slug: str
    name_en: str | None
    name_ko: str | None
    foundry: str | None
    source_tier: str | None = None
    official_url: str
    status: str


class ManifestEntry(BaseModel):
    """한 폰트의 변경 전후 값과 근거."""

    model_config = ConfigDict(extra="forbid")
    source_key: SourceKey
    current: ManifestCurrent
    before: dict[str, object]
    after: dict[str, object]
    evidence_ids: list[UUID]
    finding_ids: list[UUID]
    expected_updated_at: datetime

    @model_validator(mode="after")
    def validate_change_contract(self) -> ManifestEntry:
        if not self.before or set(self.before) != set(self.after):
            raise ValueError("before and after must contain the same non-empty fields")
        for field_name, value in self.before.items():
            if field_name not in _ALLOWED_FIELDS:
                raise ValueError(f"field {field_name} is not allowed")
            _validated_value(field_name, value)
            _validated_value(field_name, self.after[field_name])
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("finding_ids must be unique")
        if not self.evidence_ids or not self.finding_ids:
            raise ValueError("entries require evidence_ids and finding_ids")
        return self


class EvidenceBundle(BaseModel):
    """동일 UUID로 이식할 실행-스냅샷-finding."""

    model_config = ConfigDict(extra="forbid")
    run: dict[str, object]
    snapshots: list[dict[str, object]]
    findings: list[dict[str, object]]


class FontAuditManifest(BaseModel):
    """DB에서 한 트랜잭션으로 적용할 감사 문서."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    run_id: UUID
    baseline_sha256: str
    generated_at: datetime
    rollback_mode: bool = False
    evidence_bundle: EvidenceBundle
    entries: list[ManifestEntry] = Field(min_length=1, max_length=1240)

    @model_validator(mode="after")
    def validate_evidence_contract(self) -> FontAuditManifest:
        run = self.evidence_bundle.run
        if set(run) != _RUN_KEYS:
            raise ValueError("run has unknown or missing keys")
        if _uuid(run.get("id"), "run.id") != self.run_id:
            raise ValueError("run.id does not match manifest run_id")
        if run.get("baseline_sha256") != self.baseline_sha256:
            raise ValueError("run baseline_sha256 does not match manifest")
        if not isinstance(run.get("target_count"), int) or isinstance(run.get("target_count"), bool):
            raise ValueError("run target_count must be an integer")
        parser_version = run.get("parser_version")
        if not isinstance(parser_version, str) or not parser_version.strip():
            raise ValueError("run parser_version must be text")

        entries_by_key: dict[tuple[str, str], ManifestEntry] = {}
        for entry in self.entries:
            key = (entry.source_key.provider, entry.source_key.provider_record_id)
            if key in entries_by_key:
                raise ValueError("source_key is duplicated")
            entries_by_key[key] = entry

        snapshots: dict[UUID, dict[str, object]] = {}
        globally_used_ids = {self.run_id}
        for snapshot in self.evidence_bundle.snapshots:
            if set(snapshot) != _SNAPSHOT_KEYS:
                raise ValueError("snapshot has unknown or missing keys")
            snapshot_id = _uuid(snapshot.get("id"), "snapshot.id")
            if snapshot_id in globally_used_ids:
                raise ValueError("run, snapshot, and finding UUIDs must be globally unique")
            globally_used_ids.add(snapshot_id)
            source_key = SourceKey.model_validate(snapshot.get("source_key"))
            if (snapshot.get("provider"), snapshot.get("provider_record_id")) != (
                source_key.provider,
                source_key.provider_record_id,
            ) or (source_key.provider, source_key.provider_record_id) not in entries_by_key:
                raise ValueError("snapshot source key is not an entry source key")
            for hash_name in ("raw_sha256", "normalized_sha256"):
                if not isinstance(snapshot.get(hash_name), str) or _HASH.fullmatch(str(snapshot[hash_name])) is None:
                    raise ValueError(f"snapshot {hash_name} must be SHA-256")
            snapshots[snapshot_id] = snapshot

        findings: dict[UUID, dict[str, object]] = {}
        for finding in self.evidence_bundle.findings:
            if set(finding) != _FINDING_KEYS:
                raise ValueError("finding has unknown or missing keys")
            finding_id = _uuid(finding.get("id"), "finding.id")
            if finding_id in globally_used_ids:
                raise ValueError("run, snapshot, and finding UUIDs must be globally unique")
            globally_used_ids.add(finding_id)
            if _uuid(finding.get("run_id"), "finding.run_id") != self.run_id:
                raise ValueError("finding run_id does not match manifest")
            if finding.get("status") != "approved":
                raise ValueError("manifest finding must be approved")
            reviewed_by = finding.get("reviewed_by")
            if not isinstance(reviewed_by, str) or not reviewed_by.strip():
                raise ValueError("finding reviewed_by must be non-empty text")
            _datetime(finding.get("reviewed_at"), "finding.reviewed_at")
            source_key = SourceKey.model_validate(finding.get("source_key"))
            entry_for_finding = entries_by_key.get(
                (source_key.provider, source_key.provider_record_id)
            )
            if entry_for_finding is None:
                raise ValueError("finding source key is not an entry source key")
            evidence_id = _uuid(finding.get("evidence_id"), "finding.evidence_id")
            snapshot_for_finding = snapshots.get(evidence_id)
            if (
                snapshot_for_finding is None
                or snapshot_for_finding.get("source_key") != source_key.model_dump(mode="json")
            ):
                raise ValueError("finding evidence does not belong to its source key")
            field_name = finding.get("field_name")
            if not isinstance(field_name, str) or field_name not in entry_for_finding.before:
                raise ValueError("finding does not exactly authorize entry field")
            expected_before = (
                entry_for_finding.after[field_name]
                if self.rollback_mode
                else entry_for_finding.before[field_name]
            )
            expected_after = (
                entry_for_finding.before[field_name]
                if self.rollback_mode
                else entry_for_finding.after[field_name]
            )
            if (
                finding.get("before_value") != expected_before
                or finding.get("proposed_value") != expected_after
            ):
                raise ValueError("finding does not exactly authorize entry field")
            if not _evidence_role_is_valid(
                field_name, snapshot_for_finding, finding.get("confidence")
            ):
                raise ValueError("finding evidence document/source kind is not approved")
            findings[finding_id] = finding

        entry_evidence_ids = {item for entry in self.entries for item in entry.evidence_ids}
        entry_finding_ids = {item for entry in self.entries for item in entry.finding_ids}
        if entry_evidence_ids != set(snapshots) or entry_finding_ids != set(findings):
            raise ValueError("entries must reference every and only bundled evidence")
        for entry in self.entries:
            referenced_evidence_ids = {
                _uuid(findings[item]["evidence_id"], "finding.evidence_id")
                for item in entry.finding_ids
            }
            if set(entry.evidence_ids) != referenced_evidence_ids:
                raise ValueError("entry evidence_ids must exactly match finding evidence")
            authorized_fields = {str(findings[item]["field_name"]) for item in entry.finding_ids}
            derived_fields = (
                {"license_verified"}
                if "license_status" in authorized_fields
                and "license_verified" in entry.after
                else set()
            )
            if set(entry.after) != authorized_fields | derived_fields:
                raise ValueError("every changed field requires an approved finding")
            for finding_id in entry.finding_ids:
                finding = findings[finding_id]
                if (
                    finding["source_key"] != entry.source_key.model_dump(mode="json")
                    or _uuid(finding["evidence_id"], "finding.evidence_id") not in entry.evidence_ids
                ):
                    raise ValueError("entry finding is not bound to its evidence")
        return self


@dataclass(frozen=True)
class ManifestBundle:
    forward: FontAuditManifest
    reverse: FontAuditManifest
    forward_sha256: str
    reverse_sha256: str


@dataclass(frozen=True)
class ManifestPaths:
    forward: Path
    forward_sha256: Path
    reverse: Path
    reverse_sha256: Path


def _plain(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    raise ManifestError("manifest input must be a mapping or Pydantic model")


def _mapping(value: object, label: str) -> dict[str, object]:
    plain = _plain(value)
    if not isinstance(plain, dict):
        raise ManifestError(f"{label} must be an object")
    return plain


def _uuid(value: object, label: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ManifestError(f"{label} must be a UUID") from exc


def _datetime(value: object, label: str) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"{label} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise ManifestError(f"{label} must include timezone")
    return parsed


def _canonical_bytes(value: BaseModel | Mapping[str, object]) -> bytes:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else dict(value)
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, separators=(",", ": "))
        + "\n"
    ).encode("utf-8")


def _digest(value: FontAuditManifest) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _validated_value(field_name: str, value: object) -> object:
    if field_name in _TEXT_FIELDS:
        if value is not None and not isinstance(value, str):
            raise ManifestError(f"field {field_name} requires text or null")
    elif field_name in _SOURCE_KIND_FIELDS:
        if value is not None and value not in {"official", "public"}:
            raise ManifestError(f"field {field_name} has invalid source kind")
    elif field_name in _EVIDENCE_FIELDS:
        if value is not None:
            _uuid(value, field_name)
            return str(value)
    elif field_name == "download_status":
        if value not in {"pending", "verified", "needs_review", "broken"}:
            raise ManifestError("field download_status has invalid status")
    elif field_name == "license_status":
        if value not in {"pending", "verified", "needs_review"}:
            raise ManifestError("field license_status has invalid status")
    elif field_name == "script_status":
        if value not in {"pending", "verified", "needs_review"}:
            raise ManifestError("field script_status has invalid status")
    elif field_name in _DATETIME_FIELDS:
        if value is not None:
            return _datetime(value, field_name).isoformat()
    elif field_name in _PERMISSION_FIELDS:
        if value is not None and value not in {"allowed", "conditional", "denied"}:
            raise ManifestError(f"field {field_name} has invalid permission")
    elif field_name == "attribution_requirement":
        if value is not None and value not in {"required", "recommended", "not_required"}:
            raise ManifestError("field attribution_requirement has invalid value")
    elif field_name in {"is_commercial_free", "license_verified"}:
        if not isinstance(value, bool):
            raise ManifestError(f"field {field_name} requires boolean")
    elif field_name in _TEXT_ARRAY_FIELDS:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ManifestError(f"field {field_name} requires a text array")
    elif field_name == "weights":
        if not isinstance(value, list) or not all(
            isinstance(item, int) and not isinstance(item, bool) for item in value
        ):
            raise ManifestError("field weights requires an integer array")
    return value


def _source_key(row: Mapping[str, object]) -> SourceKey:
    value = row.get("source_key")
    if not isinstance(value, Mapping):
        raise ManifestError("current row source_key is required")
    try:
        return SourceKey.model_validate(value)
    except ValidationError as exc:
        raise ManifestError("current row source_key is invalid") from exc


def _current(row: Mapping[str, object]) -> ManifestCurrent:
    try:
        return ManifestCurrent.model_validate(
            {
                "slug": row.get("slug"),
                "name_en": row.get("name_en"),
                "name_ko": row.get("name_ko"),
                "foundry": row.get("foundry"),
                "source_tier": row.get("source_tier"),
                "official_url": row.get("official_url"),
                "status": row.get("status"),
            }
        )
    except ValidationError as exc:
        raise ManifestError("current row identity precondition is invalid") from exc


def _snapshot_for_export(snapshot: Mapping[str, object], source_key: SourceKey) -> dict[str, object]:
    exported = dict(snapshot)
    exported.pop("font_id", None)
    retain_raw = exported.pop("raw_retention_allowed", False)
    if retain_raw is not True:
        exported["raw_text"] = None
    exported["source_key"] = source_key.model_dump(mode="json")
    return exported


def _finding_for_export(finding: Mapping[str, object], source_key: SourceKey) -> dict[str, object]:
    exported = dict(finding)
    exported.pop("font_id", None)
    exported["source_key"] = source_key.model_dump(mode="json")
    return exported


def build_manifest(
    run: object,
    approved_findings: Sequence[object],
    current_rows: Sequence[Mapping[str, object]],
) -> ManifestBundle:
    """현재값과 승인 finding을 정방향-역방향 manifest로 고정한다."""
    run_data = _mapping(run, "run")
    run_id = _uuid(run_data.get("id"), "run.id")
    baseline_sha256 = run_data.get("baseline_sha256")
    if not isinstance(baseline_sha256, str) or _HASH.fullmatch(baseline_sha256) is None:
        raise ManifestError("run baseline_sha256 must be lowercase SHA-256")
    generated_at = _datetime(
        run_data.get("finished_at") or run_data.get("started_at"), "run.generated_at"
    )

    rows_by_id: dict[UUID, Mapping[str, object]] = {}
    source_keys: set[tuple[str, str]] = set()
    snapshots_by_id: dict[UUID, tuple[Mapping[str, object], SourceKey]] = {}
    globally_used_ids = {run_id}
    for row in current_rows:
        font_id = _uuid(row.get("id"), "current row id")
        if font_id in rows_by_id:
            raise ManifestError("current row id is duplicated")
        key = _source_key(row)
        key_tuple = (key.provider, key.provider_record_id)
        if key_tuple in source_keys:
            raise ManifestError("current row source_key is duplicated")
        source_keys.add(key_tuple)
        rows_by_id[font_id] = row
        raw_snapshots = row.get("evidence_snapshots", [])
        if not isinstance(raw_snapshots, list):
            raise ManifestError("evidence_snapshots must be an array")
        for raw_snapshot in raw_snapshots:
            snapshot = _mapping(raw_snapshot, "snapshot")
            snapshot_id = _uuid(snapshot.get("id"), "snapshot.id")
            if snapshot_id in globally_used_ids:
                raise ManifestError("run, snapshot, and finding UUIDs must be globally unique")
            globally_used_ids.add(snapshot_id)
            if _uuid(snapshot.get("font_id"), "snapshot.font_id") != font_id:
                raise ManifestError("snapshot font_id does not match current row")
            if (
                snapshot.get("provider") != key.provider
                or snapshot.get("provider_record_id") != key.provider_record_id
            ):
                raise ManifestError("snapshot provider does not match current source key")
            snapshots_by_id[snapshot_id] = (snapshot, key)

    grouped: dict[UUID, list[dict[str, object]]] = defaultdict(list)
    for raw_finding in approved_findings:
        finding = _mapping(raw_finding, "finding")
        if finding.get("status") != "approved":
            raise ManifestError("only approved findings may enter a manifest")
        reviewed_by = finding.get("reviewed_by")
        if not isinstance(reviewed_by, str) or not reviewed_by.strip():
            raise ManifestError("approved finding reviewed_by must be non-empty text")
        if finding.get("reviewed_at") is None:
            raise ManifestError("approved finding requires reviewed_at")
        _datetime(finding.get("reviewed_at"), "finding.reviewed_at")
        if _uuid(finding.get("run_id"), "finding.run_id") != run_id:
            raise ManifestError("finding run_id does not match run")
        field_name = finding.get("field_name")
        if not isinstance(field_name, str) or field_name not in _ALLOWED_FIELDS:
            raise ManifestError(f"finding field is not allowed: {field_name}")
        font_id = _uuid(finding.get("font_id"), "finding.font_id")
        if font_id not in rows_by_id:
            raise ManifestError("finding font has no current row")
        evidence_id = _uuid(finding.get("evidence_id"), "finding.evidence_id")
        if evidence_id not in snapshots_by_id:
            raise ManifestError("finding evidence snapshot is missing")
        finding_id = _uuid(finding.get("id"), "finding.id")
        if finding_id in globally_used_ids:
            raise ManifestError("run, snapshot, and finding UUIDs must be globally unique")
        globally_used_ids.add(finding_id)
        grouped[font_id].append(finding)

    if not grouped:
        raise ManifestError("manifest requires at least one approved finding")

    entries: list[ManifestEntry] = []
    exported_snapshots: dict[UUID, dict[str, object]] = {}
    exported_findings: dict[UUID, dict[str, object]] = {}
    for font_id, findings in grouped.items():
        row = rows_by_id[font_id]
        key = _source_key(row)
        before: dict[str, object] = {}
        after: dict[str, object] = {}
        evidence_ids: set[UUID] = set()
        finding_ids: set[UUID] = set()
        for finding in sorted(findings, key=lambda item: str(item["field_name"])):
            field_name = str(finding["field_name"])
            if field_name in after:
                raise ManifestError(f"finding field is duplicated: {field_name}")
            current_value = row.get(field_name)
            if current_value != finding.get("before_value"):
                raise ManifestError(f"finding before value is stale: {field_name}")
            before[field_name] = _validated_value(field_name, current_value)
            after[field_name] = _validated_value(field_name, finding.get("proposed_value"))
            evidence_id = _uuid(finding.get("evidence_id"), "finding.evidence_id")
            evidence_ids.add(evidence_id)
            evidence_snapshot, snapshot_key = snapshots_by_id[evidence_id]
            if snapshot_key != key:
                raise ManifestError("finding evidence belongs to another source key")
            if not _evidence_role_is_valid(
                field_name, evidence_snapshot, finding.get("confidence")
            ):
                raise ManifestError("finding evidence document/source kind is not approved")
            exported_snapshots[evidence_id] = _snapshot_for_export(evidence_snapshot, key)
            finding_id = _uuid(finding.get("id"), "finding.id")
            finding_ids.add(finding_id)
            exported_findings[finding_id] = _finding_for_export(finding, key)

        if "license_status" in after:
            desired = after["license_status"]
            if desired in {"verified", "needs_review"}:
                expected_verified = desired == "verified"
                if "license_verified" in after and after["license_verified"] != expected_verified:
                    raise ManifestError("license_status conflicts with license_verified")
                if "license_verified" not in after:
                    before["license_verified"] = _validated_value(
                        "license_verified", row.get("license_verified")
                    )
                    after["license_verified"] = expected_verified

        entries.append(
            ManifestEntry(
                source_key=key,
                current=_current(row),
                before=before,
                after=after,
                evidence_ids=sorted(evidence_ids, key=str),
                finding_ids=sorted(finding_ids, key=str),
                expected_updated_at=_datetime(row.get("updated_at"), "current updated_at"),
            )
        )

    entries.sort(key=lambda item: (item.source_key.provider, item.source_key.provider_record_id))
    evidence = EvidenceBundle(
        run={**run_data, "id": str(run_id)},
        snapshots=[exported_snapshots[key] for key in sorted(exported_snapshots, key=str)],
        findings=[exported_findings[key] for key in sorted(exported_findings, key=str)],
    )
    forward = FontAuditManifest(
        run_id=run_id,
        baseline_sha256=baseline_sha256,
        generated_at=generated_at,
        rollback_mode=False,
        evidence_bundle=evidence,
        entries=entries,
    )
    reverse = FontAuditManifest(
        run_id=run_id,
        baseline_sha256=baseline_sha256,
        generated_at=generated_at,
        rollback_mode=True,
        evidence_bundle=evidence,
        entries=[
            entry.model_copy(update={"before": entry.after, "after": entry.before})
            for entry in entries
        ],
    )
    return ManifestBundle(
        forward=forward,
        reverse=reverse,
        forward_sha256=_digest(forward),
        reverse_sha256=_digest(reverse),
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
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


def write_manifest_bundle(bundle: ManifestBundle, out: Path) -> ManifestPaths:
    """정-역 manifest와 sidecar SHA-256을 원자적으로 저장한다."""
    paths = ManifestPaths(
        forward=out / "forward.json",
        forward_sha256=out / "forward.sha256",
        reverse=out / "reverse.json",
        reverse_sha256=out / "reverse.sha256",
    )
    _atomic_write(paths.forward, _canonical_bytes(bundle.forward))
    _atomic_write(paths.forward_sha256, f"{bundle.forward_sha256}\n".encode("ascii"))
    _atomic_write(paths.reverse, _canonical_bytes(bundle.reverse))
    _atomic_write(paths.reverse_sha256, f"{bundle.reverse_sha256}\n".encode("ascii"))
    return paths


def verify_manifest_bytes(content: bytes, expected: str) -> FontAuditManifest:
    """한 번 읽은 본문을 해시 확인한 뒤 파싱한다."""
    expected = expected.strip()
    if _HASH.fullmatch(expected) is None:
        raise ManifestError("manifest SHA-256 형식이 올바르지 않습니다")
    if hashlib.sha256(content).hexdigest() != expected:
        raise ManifestError("manifest SHA-256이 일치하지 않습니다")
    if b"\r" in content:
        raise ManifestError("manifest는 UTF-8 LF 줄바꿈이어야 합니다")
    try:
        payload = json.loads(content.decode("utf-8"))
        manifest = FontAuditManifest.model_validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ManifestError("manifest JSON이 올바르지 않습니다") from exc
    if _canonical_bytes(manifest) != content:
        raise ManifestError("manifest JSON이 canonical 형식이 아닙니다")
    return manifest


def verify_manifest_file(path: Path, sha256_path: Path) -> FontAuditManifest:
    """파일을 읽고 동일 바이트 검증 함수에 전달한다."""
    try:
        content = path.read_bytes()
        expected = sha256_path.read_text(encoding="ascii")
    except OSError as exc:
        raise ManifestError("manifest 또는 SHA-256 파일을 읽을 수 없습니다") from exc
    return verify_manifest_bytes(content, expected)
