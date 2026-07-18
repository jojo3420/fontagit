"""폰트 감사 실행의 append-only 저장 경계.

이 모듈은 감사 테이블만 다룬다. ``fonts`` 공개값을 바꾸는 권한은 없으며,
그 변경은 이후 manifest RPC 한 곳에서만 수행한다.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4


@dataclass(frozen=True)
class SnapshotDraft:
    """원문 보관 여부와 무관하게 남기는 구조화된 증거."""

    font_id: UUID
    provider: str
    provider_record_id: str
    source_kind: str
    document_kind: str
    request_url: str
    final_url: str
    extracted: Mapping[str, object]
    evidence_locations: Mapping[str, object]
    normalized_sha256: str
    raw_text: str | None = None
    http_status: int | None = None
    extraction_rule_id: str | None = None
    parser_version: str = "audit-runner-v1"
    collected_at: datetime | None = None

    @property
    def raw_sha256(self) -> str:
        return hashlib.sha256((self.raw_text or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FindingDraft:
    """자동 적용하지 않는 검수 후보 한 건."""

    font_id: UUID
    field_name: str
    before_value: object | None
    proposed_value: object | None
    evidence_id: UUID | None
    confidence: str
    review_reason: str
    auto_applicable: bool = False


class AuditStore(Protocol):
    """DB와 dry-run 저장소가 공유하는 작은 감사 저장 계약."""

    def start_run(
        self,
        *,
        stage: str,
        target_count: int,
        baseline_sha256: str,
        dry_run: bool,
    ) -> UUID: ...

    def save_snapshot(self, run_id: UUID, snapshot: SnapshotDraft) -> UUID: ...

    def save_observation(self, run_id: UUID, observation: Mapping[str, object]) -> UUID: ...

    def save_finding(self, run_id: UUID, finding: FindingDraft) -> UUID: ...

    def complete_run(self, run_id: UUID, report: Mapping[str, object]) -> None: ...


class InMemoryAuditStore:
    """테스트와 dry-run 검증에 쓰는 append-only 저장소."""

    def __init__(self, *, fail_on_write: bool = False) -> None:
        self.fail_on_write = fail_on_write
        self.write_calls = 0
        self._snapshots: dict[tuple[str, ...], UUID] = {}
        self._findings: dict[tuple[UUID, str], tuple[UUID, str]] = {}
        self._finding_ids: set[UUID] = set()
        self._applied: set[UUID] = set()
        self._runs: dict[UUID, dict[str, object]] = {}

    @property
    def finding_count(self) -> int:
        return len(self._finding_ids)

    def mark_applied(self, finding_id: UUID) -> None:
        """테스트에서 적용 완료된 finding을 불변 상태로 전환한다."""
        if finding_id not in self._finding_ids:
            raise ValueError("unknown finding")
        self._applied.add(finding_id)

    def _write(self) -> None:
        self.write_calls += 1
        if self.fail_on_write:
            raise AssertionError("dry-run must not write through AuditStore")

    def start_run(
        self,
        *,
        stage: str,
        target_count: int,
        baseline_sha256: str,
        dry_run: bool,
    ) -> UUID:
        self._write()
        run_id = uuid4()
        self._runs[run_id] = {
            "stage": stage,
            "target_count": target_count,
            "baseline_sha256": baseline_sha256,
            "dry_run": dry_run,
            "status": "running",
        }
        return run_id

    def save_snapshot(self, run_id: UUID, snapshot: SnapshotDraft) -> UUID:
        self._write()
        key = (
            str(snapshot.font_id),
            snapshot.provider,
            snapshot.provider_record_id,
            snapshot.document_kind,
            snapshot.normalized_sha256,
        )
        return self._snapshots.setdefault(key, uuid4())

    def save_observation(self, run_id: UUID, observation: Mapping[str, object]) -> UUID:
        self._write()
        return uuid4()

    def save_finding(self, run_id: UUID, finding: FindingDraft) -> UUID:
        self._write()
        key = (finding.font_id, finding.field_name)
        serialized = _canonical_value(finding.proposed_value)
        existing = self._findings.get(key)
        if existing is not None and existing[0] not in self._applied and existing[1] == serialized:
            return existing[0]
        finding_id = uuid4()
        self._findings[key] = (finding_id, serialized)
        self._finding_ids.add(finding_id)
        return finding_id

    def complete_run(self, run_id: UUID, report: Mapping[str, object]) -> None:
        self._write()
        self._runs[run_id] = {**self._runs[run_id], "status": "completed", "report": dict(report)}


class SupabaseAuditStore:
    """dev service-role 전용 감사 테이블 저장소.

    이 클래스는 prod 설정을 받지 않는다. 호출자는 dev URL과 dev service key만
    전달할 수 있고, 공개 ``fonts`` 테이블에는 어떤 요청도 보내지 않는다.
    """

    def __init__(self, client: Any) -> None:
        self._schema = client.schema("fontagit")

    @classmethod
    def from_dev_credentials(cls, url: str, secret_key: str) -> "SupabaseAuditStore":
        if not url.strip() or not secret_key.strip():
            raise ValueError("dev 감사 저장에는 URL과 service key가 필요합니다")
        from supabase import create_client

        return cls(create_client(url, secret_key))

    def _one(self, table: str, payload: Mapping[str, object]) -> Mapping[str, object]:
        response = self._schema.table(table).insert(dict(payload)).execute()
        data = response.data
        if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], Mapping):
            raise RuntimeError("감사 저장 응답이 올바르지 않습니다")
        return data[0]

    def start_run(
        self,
        *,
        stage: str,
        target_count: int,
        baseline_sha256: str,
        dry_run: bool,
    ) -> UUID:
        row = self._one(
            "font_audit_runs",
            {
                "stage": stage,
                "target_environment": "dev",
                "target_count": target_count,
                "parser_version": "audit-runner-v1",
                "baseline_sha256": baseline_sha256,
                "dry_run": dry_run,
            },
        )
        return _row_uuid(row)

    def save_snapshot(self, run_id: UUID, snapshot: SnapshotDraft) -> UUID:
        existing = (
            self._schema.table("font_source_snapshots")
            .select("id")
            .eq("font_id", str(snapshot.font_id))
            .eq("provider", snapshot.provider)
            .eq("provider_record_id", snapshot.provider_record_id)
            .eq("document_kind", snapshot.document_kind)
            .eq("normalized_sha256", snapshot.normalized_sha256)
            .execute()
        )
        if isinstance(existing.data, list) and existing.data:
            row = existing.data[0]
            if isinstance(row, Mapping):
                return _row_uuid(row)

        row = self._one(
            "font_source_snapshots",
            {
                "run_id": str(run_id),
                "font_id": str(snapshot.font_id),
                "provider": snapshot.provider,
                "provider_record_id": snapshot.provider_record_id,
                "source_kind": snapshot.source_kind,
                "document_kind": snapshot.document_kind,
                "request_url": snapshot.request_url,
                "final_url": snapshot.final_url,
                "http_status": snapshot.http_status,
                "raw_text": snapshot.raw_text,
                "raw_sha256": snapshot.raw_sha256,
                "normalized_sha256": snapshot.normalized_sha256,
                "extracted": dict(snapshot.extracted),
                "evidence_locations": dict(snapshot.evidence_locations),
                "extraction_rule_id": snapshot.extraction_rule_id,
                "parser_version": snapshot.parser_version,
                "collected_at": (snapshot.collected_at or datetime.now(UTC)).isoformat(),
            },
        )
        return _row_uuid(row)

    def save_observation(self, run_id: UUID, observation: Mapping[str, object]) -> UUID:
        return _row_uuid(self._one("font_link_observations", {"run_id": str(run_id), **observation}))

    def save_finding(self, run_id: UUID, finding: FindingDraft) -> UUID:
        existing = (
            self._schema.table("font_audit_findings")
            .select("id,status,proposed_value")
            .eq("font_id", str(finding.font_id))
            .eq("field_name", finding.field_name)
            .order("reviewed_at", desc=True)
            .limit(1)
            .execute()
        )
        if isinstance(existing.data, list) and existing.data and isinstance(existing.data[0], Mapping):
            row = existing.data[0]
            if row.get("status") != "applied" and _canonical_value(row.get("proposed_value")) == _canonical_value(finding.proposed_value):
                return _row_uuid(row)

        row = self._one(
            "font_audit_findings",
            {
                "run_id": str(run_id),
                "font_id": str(finding.font_id),
                "field_name": finding.field_name,
                "before_value": finding.before_value,
                "proposed_value": finding.proposed_value,
                "evidence_id": str(finding.evidence_id) if finding.evidence_id else None,
                "confidence": finding.confidence,
                "auto_applicable": finding.auto_applicable,
                "review_reason": finding.review_reason,
            },
        )
        return _row_uuid(row)

    def complete_run(self, run_id: UUID, report: Mapping[str, object]) -> None:
        self._schema.table("font_audit_runs").update(
            {
                "status": "completed",
                "success_count": _report_count(report, "success_count"),
                "verified_count": _report_count(report, "verified_count"),
                "review_count": _report_count(report, "needs_review_count"),
                "broken_count": _report_count(report, "broken_count"),
                "finished_at": datetime.now(UTC).isoformat(),
            }
        ).eq("id", str(run_id)).execute()


def _canonical_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _report_count(report: Mapping[str, object], key: str) -> int:
    """DB 집계에는 JSON 객체가 아닌 정수만 허용한다."""
    value = report.get(key)
    if isinstance(value, int) and value >= 0:
        return value
    raise ValueError(f"invalid audit report count: {key}")


def _row_uuid(row: Mapping[str, object]) -> UUID:
    value = row.get("id")
    if not isinstance(value, str):
        raise RuntimeError("감사 저장 응답에 id가 없습니다")
    return UUID(value)
