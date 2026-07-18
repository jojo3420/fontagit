"""폰트 감사 실행의 append-only 저장 경계.

이 모듈은 감사 테이블만 다룬다. ``fonts`` 공개값을 바꾸는 권한은 없으며,
그 변경은 이후 manifest RPC 한 곳에서만 수행한다.
"""

from __future__ import annotations

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
    raw_sha256: str | None = None
    raw_text: str | None = None
    http_status: int | None = None
    extraction_rule_id: str | None = None
    parser_version: str = "audit-runner-v1"
    collected_at: datetime | None = None

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
        self._observations: dict[tuple[UUID, str, str], UUID] = {}
        self._findings: dict[tuple[UUID, UUID, str], UUID] = {}
        self._finding_ids: set[UUID] = set()
        self._finding_drafts: dict[UUID, FindingDraft] = {}
        self._applied: set[UUID] = set()
        self._runs: dict[UUID, dict[str, object]] = {}

    @property
    def finding_count(self) -> int:
        return len(self._finding_ids)

    @property
    def observation_count(self) -> int:
        return len(self._observations)

    def mark_applied(self, finding_id: UUID) -> None:
        """테스트에서 적용 완료된 finding을 불변 상태로 전환한다."""
        if finding_id not in self._finding_ids:
            raise ValueError("unknown finding")
        self._applied.add(finding_id)

    def finding_draft(self, finding_id: UUID) -> FindingDraft:
        """테스트용: 저장된 finding이 같은 run 안에서 바뀌지 않았는지 읽는다."""
        return self._finding_drafts[finding_id]

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
        if snapshot.raw_sha256 is None:
            raise ValueError("observed snapshot requires an explicit raw_sha256")
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
        font_id = observation.get("font_id")
        normalized_url = observation.get("normalized_url")
        if not isinstance(font_id, str) or not isinstance(normalized_url, str):
            raise ValueError("observation requires font_id and normalized_url")
        return self._observations.setdefault((run_id, font_id, normalized_url), uuid4())

    def save_finding(self, run_id: UUID, finding: FindingDraft) -> UUID:
        self._write()
        key = (run_id, finding.font_id, finding.field_name)
        existing = self._findings.get(key)
        if existing is not None:
            # DB의 unique(run_id, font_id, field_name)와 같다. 같은 실행의
            # applied finding은 물론 proposed finding도 변경하지 않는다.
            return existing
        finding_id = uuid4()
        self._findings[key] = finding_id
        self._finding_ids.add(finding_id)
        self._finding_drafts[finding_id] = finding
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

    def _insert_once(
        self,
        table: str,
        payload: Mapping[str, object],
        *,
        on_conflict: str,
        lookup: Mapping[str, object],
    ) -> Mapping[str, object]:
        """unique 충돌은 무시하고, 승자 row를 읽어 동일 ID를 반환한다."""
        response = (
            self._schema.table(table)
            .upsert(
                dict(payload),
                on_conflict=on_conflict,
                ignore_duplicates=True,
            )
            .execute()
        )
        data = response.data
        if isinstance(data, list) and data and isinstance(data[0], Mapping):
            return data[0]

        query = self._schema.table(table).select("id")
        for key, value in lookup.items():
            query = query.eq(key, value)
        existing = query.limit(1).execute().data
        if isinstance(existing, list) and existing and isinstance(existing[0], Mapping):
            return existing[0]
        raise RuntimeError("감사 원자 저장 결과를 확인할 수 없습니다")

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
        if snapshot.raw_sha256 is None:
            raise ValueError("observed snapshot requires an explicit raw_sha256")
        payload = {
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
        }
        row = self._insert_once(
            "font_source_snapshots",
            payload,
            on_conflict="font_id,provider,provider_record_id,document_kind,normalized_sha256",
            lookup={
                "font_id": str(snapshot.font_id),
                "provider": snapshot.provider,
                "provider_record_id": snapshot.provider_record_id,
                "document_kind": snapshot.document_kind,
                "normalized_sha256": snapshot.normalized_sha256,
            },
        )
        return _row_uuid(row)

    def save_observation(self, run_id: UUID, observation: Mapping[str, object]) -> UUID:
        font_id = observation.get("font_id")
        normalized_url = observation.get("normalized_url")
        if not isinstance(font_id, str) or not isinstance(normalized_url, str):
            raise ValueError("observation requires font_id and normalized_url")
        row = self._insert_once(
            "font_link_observations",
            {**observation, "run_id": str(run_id)},
            on_conflict="run_id,font_id,normalized_url",
            lookup={
                "run_id": str(run_id),
                "font_id": font_id,
                "normalized_url": normalized_url,
            },
        )
        return _row_uuid(row)

    def save_finding(self, run_id: UUID, finding: FindingDraft) -> UUID:
        payload = {
            "run_id": str(run_id),
            "font_id": str(finding.font_id),
            "field_name": finding.field_name,
            "before_value": finding.before_value,
            "proposed_value": finding.proposed_value,
            "evidence_id": str(finding.evidence_id) if finding.evidence_id else None,
            "confidence": finding.confidence,
            "auto_applicable": finding.auto_applicable,
            "review_reason": finding.review_reason,
        }
        row = self._insert_once(
            "font_audit_findings",
            payload,
            on_conflict="run_id,font_id,field_name",
            lookup={
                "run_id": str(run_id),
                "font_id": str(finding.font_id),
                "field_name": finding.field_name,
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
