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


@dataclass(frozen=True)
class ApprovedFontFileCandidate:
    """사람이 승인한 legal download finding과 그 원본 증거의 결합."""

    url: str
    source_kind: str
    request_url: str
    evidence_id: UUID
    run_id: UUID


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

    def approved_font_file_candidates(
        self,
        font_id: UUID,
        provider: str,
        provider_record_id: str,
    ) -> list[ApprovedFontFileCandidate]: ...

    def scheduled_run_status(
        self, run_id: UUID, *, kind: str, artifact_sha256: str
    ) -> str | None: ...

    def start_scheduled_run(
        self,
        run_id: UUID,
        *,
        kind: str,
        target_count: int,
        artifact_sha256: str,
        started_at: datetime,
    ) -> None: ...

    def previous_observations(
        self,
        font_id: UUID,
        normalized_url: str,
        *,
        before: datetime,
    ) -> list[Mapping[str, object]]: ...


class InMemoryAuditStore:
    """테스트와 dry-run 검증에 쓰는 append-only 저장소."""

    def __init__(self, *, fail_on_write: bool = False) -> None:
        self.fail_on_write = fail_on_write
        self.write_calls = 0
        self._snapshots: dict[tuple[str, ...], UUID] = {}
        self._snapshot_drafts: dict[UUID, tuple[UUID, SnapshotDraft]] = {}
        self._observations: dict[tuple[UUID, str, str], UUID] = {}
        self._observation_rows: dict[tuple[UUID, str, str], dict[str, object]] = {}
        self._findings: dict[tuple[UUID, UUID, str], UUID] = {}
        self._finding_ids: set[UUID] = set()
        self._finding_drafts: dict[UUID, FindingDraft] = {}
        self._finding_runs: dict[UUID, UUID] = {}
        self._finding_status: dict[UUID, str] = {}
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
        self._finding_status[finding_id] = "applied"

    def approve_finding(self, finding_id: UUID) -> None:
        """테스트 저장소에서도 DB와 같은 approved 상태만 후보로 연다."""
        if finding_id not in self._finding_ids:
            raise ValueError("unknown finding")
        self._finding_status[finding_id] = "approved"

    def finding_draft(self, finding_id: UUID) -> FindingDraft:
        """테스트용: 저장된 finding이 같은 run 안에서 바뀌지 않았는지 읽는다."""
        return self._finding_drafts[finding_id]

    def snapshot_draft(self, snapshot_id: UUID) -> tuple[UUID, SnapshotDraft]:
        """테스트용: 저장된 snapshot과 run 결합을 확인한다."""
        return self._snapshot_drafts[snapshot_id]

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
        snapshot_id = self._snapshots.setdefault(key, uuid4())
        self._snapshot_drafts.setdefault(snapshot_id, (run_id, snapshot))
        return snapshot_id

    def save_observation(self, run_id: UUID, observation: Mapping[str, object]) -> UUID:
        self._write()
        font_id = observation.get("font_id")
        normalized_url = observation.get("normalized_url")
        if not isinstance(font_id, str) or not isinstance(normalized_url, str):
            raise ValueError("observation requires font_id and normalized_url")
        key = (run_id, font_id, normalized_url)
        observation_id = self._observations.setdefault(key, uuid4())
        self._observation_rows.setdefault(key, {**dict(observation), "run_id": str(run_id)})
        return observation_id

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
        self._finding_runs[finding_id] = run_id
        self._finding_status[finding_id] = "proposed"
        return finding_id

    def complete_run(self, run_id: UUID, report: Mapping[str, object]) -> None:
        self._write()
        self._runs[run_id] = {**self._runs[run_id], "status": "completed", "report": dict(report)}

    def approved_font_file_candidates(
        self,
        font_id: UUID,
        provider: str,
        provider_record_id: str,
    ) -> list[ApprovedFontFileCandidate]:
        candidates: list[ApprovedFontFileCandidate] = []
        for finding_id, finding in self._finding_drafts.items():
            if (
                self._finding_status.get(finding_id) != "approved"
                or finding.font_id != font_id
                or finding.field_name != "download_url"
                or not isinstance(finding.proposed_value, str)
                or finding.evidence_id is None
            ):
                continue
            stored = self._snapshot_drafts.get(finding.evidence_id)
            if stored is None:
                continue
            snapshot_run, snapshot = stored
            finding_run = self._finding_runs[finding_id]
            if (
                snapshot_run != finding_run
                or snapshot.font_id != font_id
                or snapshot.provider != provider
                or snapshot.provider_record_id != provider_record_id
                or snapshot.document_kind != "download"
                or snapshot.source_kind not in {"official", "public"}
                or snapshot.extracted.get("download_url") != finding.proposed_value
            ):
                continue
            candidates.append(
                ApprovedFontFileCandidate(
                    url=finding.proposed_value,
                    source_kind=snapshot.source_kind,
                    request_url=snapshot.request_url,
                    evidence_id=finding.evidence_id,
                    run_id=finding_run,
                )
            )
        candidates.sort(
            key=lambda item: ({"official": 0, "public": 1}[item.source_kind], item.url)
        )
        return candidates

    def scheduled_run_status(
        self, run_id: UUID, *, kind: str, artifact_sha256: str
    ) -> str | None:
        row = self._runs.get(run_id)
        if row and (
            row.get("stage") != "scheduled"
            or row.get("kind") != kind
            or row.get("baseline_sha256") != artifact_sha256
        ):
            return "mismatch"
        status = row.get("status") if row else None
        return status if isinstance(status, str) else None

    def start_scheduled_run(
        self,
        run_id: UUID,
        *,
        kind: str,
        target_count: int,
        artifact_sha256: str,
        started_at: datetime,
    ) -> None:
        self._write()
        self._runs.setdefault(
            run_id,
            {
                "stage": "scheduled",
                "kind": kind,
                "target_count": target_count,
                "baseline_sha256": artifact_sha256,
                "started_at": started_at.isoformat(),
                "status": "running",
            },
        )

    def previous_observations(
        self,
        font_id: UUID,
        normalized_url: str,
        *,
        before: datetime,
    ) -> list[Mapping[str, object]]:
        rows: list[Mapping[str, object]] = []
        for (_, stored_font_id, stored_url), row in self._observation_rows.items():
            if stored_font_id != str(font_id) or stored_url != normalized_url:
                continue
            observed_at = row.get("observed_at")
            if not isinstance(observed_at, str):
                continue
            try:
                observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if observed < before:
                rows.append(row)
        return rows


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

    def approved_font_file_candidates(
        self,
        font_id: UUID,
        provider: str,
        provider_record_id: str,
    ) -> list[ApprovedFontFileCandidate]:
        """approved legal finding과 같은 run/font의 공식 증거만 결합한다."""
        findings = (
            self._schema.table("font_audit_findings")
            .select("run_id,font_id,proposed_value,evidence_id,status")
            .eq("font_id", str(font_id))
            .eq("field_name", "download_url")
            .eq("status", "approved")
            .execute()
            .data
        )
        if not isinstance(findings, list) or not all(
            isinstance(item, Mapping) for item in findings
        ):
            raise RuntimeError("승인 download finding 조회 결과가 올바르지 않습니다")
        candidates: list[ApprovedFontFileCandidate] = []
        for finding in findings:
            run_text = finding.get("run_id")
            evidence_text = finding.get("evidence_id")
            proposed = finding.get("proposed_value")
            if (
                finding.get("status") != "approved"
                or finding.get("font_id") != str(font_id)
                or not all(
                    isinstance(value, str)
                    for value in (run_text, evidence_text, proposed)
                )
            ):
                continue
            snapshots = (
                self._schema.table("font_source_snapshots")
                .select(
                    "id,run_id,font_id,provider,provider_record_id,source_kind,"
                    "document_kind,request_url,extracted"
                )
                .eq("id", evidence_text)
                .eq("run_id", run_text)
                .eq("font_id", str(font_id))
                .eq("provider", provider)
                .eq("provider_record_id", provider_record_id)
                .limit(1)
                .execute()
                .data
            )
            if not isinstance(snapshots, list) or len(snapshots) != 1:
                continue
            snapshot = snapshots[0]
            if not isinstance(snapshot, Mapping):
                continue
            extracted = snapshot.get("extracted")
            source_kind = snapshot.get("source_kind")
            request_url = snapshot.get("request_url")
            if (
                snapshot.get("id") != evidence_text
                or snapshot.get("run_id") != run_text
                or snapshot.get("font_id") != str(font_id)
                or snapshot.get("provider") != provider
                or snapshot.get("provider_record_id") != provider_record_id
                or source_kind not in {"official", "public"}
                or snapshot.get("document_kind") != "download"
                or not isinstance(extracted, Mapping)
                or extracted.get("download_url") != proposed
                or not isinstance(request_url, str)
            ):
                continue
            try:
                candidates.append(
                    ApprovedFontFileCandidate(
                        url=proposed,
                        source_kind=str(source_kind),
                        request_url=request_url,
                        evidence_id=UUID(evidence_text),
                        run_id=UUID(run_text),
                    )
                )
            except ValueError:
                continue
        candidates.sort(
            key=lambda item: ({"official": 0, "public": 1}[item.source_kind], item.url)
        )
        return candidates

    def scheduled_run_status(
        self, run_id: UUID, *, kind: str, artifact_sha256: str
    ) -> str | None:
        data = (
            self._schema.table("font_audit_runs")
            .select("status,stage,parser_version,baseline_sha256")
            .eq("id", str(run_id))
            .limit(1)
            .execute()
            .data
        )
        if not isinstance(data, list) or not data:
            return None
        row = data[0]
        if not isinstance(row, Mapping) or (
            row.get("stage") != "scheduled"
            or row.get("parser_version") != f"scheduled-{kind}-v1"
            or row.get("baseline_sha256") != artifact_sha256
        ):
            return "mismatch"
        value = row.get("status")
        return value if isinstance(value, str) else None

    def start_scheduled_run(
        self,
        run_id: UUID,
        *,
        kind: str,
        target_count: int,
        artifact_sha256: str,
        started_at: datetime,
    ) -> None:
        self._one(
            "font_audit_runs",
            {
                "id": str(run_id),
                "stage": "scheduled",
                "target_environment": "dev",
                "target_count": target_count,
                "parser_version": f"scheduled-{kind}-v1",
                "baseline_sha256": artifact_sha256,
                "dry_run": False,
                "started_at": started_at.isoformat(),
            },
        )

    def previous_observations(
        self,
        font_id: UUID,
        normalized_url: str,
        *,
        before: datetime,
    ) -> list[Mapping[str, object]]:
        data = (
            self._schema.table("font_link_observations")
            .select("run_id,observed_at,http_status,content_sha256,error_kind")
            .eq("font_id", str(font_id))
            .eq("normalized_url", normalized_url)
            .lt("observed_at", before.isoformat())
            .order("observed_at")
            .execute()
            .data
        )
        if not isinstance(data, list) or not all(isinstance(row, Mapping) for row in data):
            raise RuntimeError("이전 예약 관찰 조회 결과가 올바르지 않습니다")
        return data


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
