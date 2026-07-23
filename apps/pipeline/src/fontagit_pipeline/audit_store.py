"""폰트 감사 실행의 append-only 저장 경계.

이 모듈은 감사 테이블만 다룬다. ``fonts`` 공개값을 바꾸는 권한은 없으며,
그 변경은 이후 manifest RPC 한 곳에서만 수행한다.
"""

from __future__ import annotations

import unicodedata
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

    def approve_finding(
        self, finding_id: UUID, *, reviewed_by: str
    ) -> None:
        """명시적 검증 후 metadata tags/weights finding을 approved로 상태 전이.

        Args:
            finding_id: 승인할 finding UUID
            reviewed_by: 검수자 식별자

        Raises:
            ValueError: finding 미존재, field 불허, status 불일치, 동시성 실패, reviewed_by 비어있음
        """
        # 검증 0: reviewed_by 필수
        if not reviewed_by or not str(reviewed_by).strip():
            raise ValueError("reviewed_by는 필수 입력입니다")

        # SELECT: finding 검색
        query = self._schema.table("font_audit_findings").select("id", "field_name", "status").eq("id", str(finding_id)).limit(1)
        response = query.execute()
        data = response.data

        # 검증 1: 존재 여부
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"존재하지 않는 finding: {finding_id}")

        row = data[0]
        if not isinstance(row, Mapping):
            raise ValueError(f"invalid finding row: {finding_id}")

        field_name = row.get("field_name")
        current_status = row.get("status")

        # 검증 2: field_name (tags, weights만 승인 가능)
        if field_name not in {"tags", "weights"}:
            raise ValueError(f"field '{field_name}' 는 승인 대상이 아닙니다")

        # 검증 3: 현재 상태 (proposed만)
        if current_status != "proposed":
            raise ValueError(f"status={current_status}인 경우 승인 불가 (proposed만 가능)")

        # UPDATE: 조건부 승인 (id+status+field_name 조합)
        update_response = (
            self._schema.table("font_audit_findings")
            .update(
                {
                    "status": "approved",
                    "reviewed_by": reviewed_by,
                    "reviewed_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", str(finding_id))
            .eq("status", "proposed")
            .eq("field_name", field_name)
            .execute()
        )

        update_data = update_response.data
        if not isinstance(update_data, list) or len(update_data) == 0:
            raise ValueError(f"finding 승인 실패 (동시성 충돌): {finding_id}")

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

    def resolve_font_id(
        self,
        slug: str,
        name_ko: str | None,
        name_en: str | None,
        source_tier: str,
    ) -> UUID | None:
        """dev fonts 테이블에서 prod font_id를 dev font_id로 변환한다.

        복합키 (slug + NFC정규화(name_ko) + source_tier)로 dev fonts를 조회.
        name_ko가 None이면 name_en으로 보조매칭.
        정확히 1개 매칭 → UUID 반환. 0개 또는 2개+ → None 반환.
        """
        query = self._schema.table("fonts").select("id, name_ko, name_en").eq("slug", slug).eq("source_tier", source_tier)

        data = query.execute().data
        if not isinstance(data, list):
            return None

        candidates: list[UUID] = []
        for row in data:
            if not isinstance(row, Mapping):
                continue
            row_id = row.get("id")
            row_name_ko = row.get("name_ko")
            if not isinstance(row_id, str):
                continue

            # name_ko 비교 (NFC 정규화 적용)
            if name_ko is not None and isinstance(row_name_ko, str):
                normalized_target = unicodedata.normalize("NFC", name_ko)
                normalized_row = unicodedata.normalize("NFC", row_name_ko)
                if normalized_target == normalized_row:
                    try:
                        candidates.append(UUID(row_id))
                    except ValueError:
                        continue
            # name_ko가 None이면 name_en으로 보조매칭
            elif name_ko is None and name_en is not None:
                row_name_en = row.get("name_en")
                if name_en == row_name_en:
                    try:
                        candidates.append(UUID(row_id))
                    except ValueError:
                        continue

        # 정확히 1개만 반환
        if len(candidates) == 1:
            return candidates[0]
        return None



    def get_run(self, run_id: UUID) -> dict[str, object]:
        """font_audit_runs 테이블에서 run_id로 레코드 조회.
        
        Args:
            run_id: 조회할 감사 run의 UUID
            
        Returns:
            audit run 레코드를 포함한 dict
            
        Raises:
            ValueError: run을 찾을 수 없는 경우
        """
        result = (
            self._schema.table("font_audit_runs")
            .select("*")
            .eq("id", str(run_id))
            .execute()
        )
        data = result.data
        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(f"Run {run_id} not found")
        return data[0]

    def get_approved_findings(self, run_id: UUID) -> list[dict[str, object]]:
        """font_audit_findings 테이블에서 승인 기록 findings 조회 (페이지네이션).

        applied는 approved+반영 마커라 다른 타깃(build --target prod) 재조립을 위해 포함하고,
        번들 계약(승인 기록)에 맞춰 status를 approved로 정규화해 돌려준다.

        Args:
            run_id: 조회할 감사 run의 UUID

        Returns:
            approved 상태의 finding 레코드 리스트

        Raises:
            RuntimeError: 부분 조회 실패(1,000행 제한 초과 가능성)
        """
        all_findings: list[dict[str, object]] = []
        page_size = 1000
        offset = 0

        while True:
            result = (
                self._schema.table("font_audit_findings")
                .select("*")
                .eq("run_id", str(run_id))
                .in_("status", ["approved", "applied"])
                .order("id", desc=False)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            data = result.data
            if not isinstance(data, list):
                raise RuntimeError("approved findings 조회 결과가 올바르지 않습니다")

            for row in data:
                if row.get("status") == "applied":
                    row["status"] = "approved"
            all_findings.extend(data)

            if len(data) < page_size:
                break

            offset += page_size

        return all_findings

    def get_proposed_findings(self, run_id: UUID) -> list[dict[str, object]]:
        """font_audit_findings 테이블에서 proposed 상태의 tags/weights findings 조회 (페이지네이션).

        Args:
            run_id: 조회할 감사 run의 UUID

        Returns:
            proposed 상태이고 field_name이 tags 또는 weights인 finding 레코드 리스트

        Raises:
            RuntimeError: 부분 조회 실패(1,000행 제한 초과 가능성)
        """
        all_findings: list[dict[str, object]] = []
        page_size = 1000
        offset = 0

        while True:
            result = (
                self._schema.table("font_audit_findings")
                .select("*")
                .eq("run_id", str(run_id))
                .eq("status", "proposed")
                .in_("field_name", ["tags", "weights"])
                .order("id", desc=False)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            data = result.data
            if not isinstance(data, list):
                raise RuntimeError("proposed findings 조회 결과가 올바르지 않습니다")

            all_findings.extend(data)

            if len(data) < page_size:
                break

            offset += page_size

        return all_findings

    def get_current_fonts_with_snapshots(
        self, run_id: UUID, target_store: "SupabaseAuditStore | None" = None
    ) -> list[dict[str, object]]:
        """현재 run의 approved findings 증거 스냅샷과 폰트를 조회 (evidence_id 기준).

        스냅샷은 (font_id, provider, provider_record_id, document_kind, normalized_sha256) on-conflict
        중복 제거되어 과거 run의 기존 행이 재사용됨. finding.evidence_id가 가리키는 행들을 직접 조회하여
        current rows를 구성한다. 이를 통해 타 run 귀속 스냅샷도 포함되며, 스냅샷 결측 오류를 사전 감지.

        현재 상태 단언은 적용 대상 DB를 기준으로 한다. target_store가 지정되면 fonts와 font_sources는
        그곳에서 조회하며, 감사 증거 스냅샷은 항상 self(dev)에서 조회한다.

        Args:
            run_id: 조회할 감사 run의 UUID
            target_store: fonts/font_sources를 조회할 대상 스토어 (None이면 self 사용)

        Returns:
            font_source_snapshots가 포함된 font 레코드 리스트

        Raises:
            RuntimeError: evidence_id 결측, evidence 스냅샷 결측, fonts 결측, source_key 중복
        """
        # 1. approved findings 조회 (evidence_id 기준)
        approved_findings = self.get_approved_findings(run_id)
        if not approved_findings:
            return []

        # evidence_ids와 font_ids 추출
        evidence_ids: set[str] = set()
        font_ids: set[str] = set()

        for finding in approved_findings:
            evidence_id = finding.get("evidence_id")
            if evidence_id is None:
                raise RuntimeError(f"finding {finding.get('id')} has no evidence_id (계약 위반)")
            if isinstance(evidence_id, str):
                evidence_ids.add(evidence_id)

            font_id = finding.get("font_id")
            if isinstance(font_id, str):
                font_ids.add(font_id)

        if not evidence_ids or not font_ids:
            return []

        # 2. snapshots를 id in-list 청크 조회 (100단위, 502 대응)
        all_snapshots: list[dict[str, object]] = []
        chunk_size = 100
        evidence_ids_list = list(evidence_ids)

        for i in range(0, len(evidence_ids_list), chunk_size):
            chunk = evidence_ids_list[i : i + chunk_size]
            snapshots_result = (
                self._schema.table("font_source_snapshots")
                .select("*")
                .in_("id", chunk)
                .execute()
            )
            snapshots_data = snapshots_result.data
            if not isinstance(snapshots_data, list):
                raise RuntimeError("font_source_snapshots 조회 결과가 올바르지 않습니다")

            all_snapshots.extend(snapshots_data)

        # 결측 검증
        if len(all_snapshots) != len(evidence_ids):
            raise RuntimeError(
                f"evidence 스냅샷 결측: 예상 {len(evidence_ids)}, 조회 {len(all_snapshots)}"
            )

        # 3. (provider, provider_record_id) 유일성 검증
        source_keys_seen: dict[tuple[str, str], bool] = {}

        for snapshot in all_snapshots:
            provider = snapshot.get("provider")
            provider_record_id = snapshot.get("provider_record_id")
            if provider and provider_record_id:
                key = (str(provider), str(provider_record_id))
                if key in source_keys_seen:
                    raise RuntimeError(
                        f"중복된 source_key ({provider}, {provider_record_id})"
                    )
                source_keys_seen[key] = True

        # 4. fonts를 id in-list 청크 조회 (target_store가 있으면 그곳에서, 없으면 self에서)
        fonts_by_id: dict[str, dict[str, object]] = {}
        query_store = target_store if target_store is not None else self
        font_ids_list = list(font_ids)

        if target_store is not None:
            # 스냅샷을 (provider, provider_record_id) 그룹으로 묶어서 font_sources 조회
            source_groups: dict[tuple[str, str], list[dict[str, object]]] = {}
            for snapshot in all_snapshots:
                provider = snapshot.get("provider")
                provider_record_id = snapshot.get("provider_record_id")
                if provider and provider_record_id:
                    key = (str(provider), str(provider_record_id))
                    source_groups.setdefault(key, []).append(snapshot)

            # 각 (provider, provider_record_id)를 target_store의 font_sources에서 조회
            target_font_ids: set[str] = set()
            source_key_to_target_font_id: dict[tuple[str, str], str] = {}
            for (provider, provider_record_id), snapshots in source_groups.items():
                source_result = (
                    target_store._schema.table("font_sources")
                    .select("*")
                    .eq("provider", provider)
                    .eq("provider_record_id", provider_record_id)
                    .execute()
                )
                source_data = source_result.data
                if not isinstance(source_data, list):
                    raise RuntimeError("font_sources 조회 결과가 올바르지 않습니다")

                if len(source_data) != 1:
                    raise RuntimeError(
                        f"font_sources 매칭 실패: provider={provider} provider_record_id={provider_record_id} "
                        f"조회 결과 {len(source_data)}건 (예상 1건)"
                    )

                source_row = source_data[0]
                font_id = source_row.get("font_id")
                if font_id is not None:
                    target_font_ids.add(str(font_id))
                    source_key_to_target_font_id[(provider, provider_record_id)] = str(font_id)

            # target_store에서 fonts를 id in-list 청크 조회
            target_font_ids_list = list(target_font_ids)
            for i in range(0, len(target_font_ids_list), chunk_size):
                chunk = target_font_ids_list[i : i + chunk_size]
                fonts_result = (
                    target_store._schema.table("fonts")
                    .select("*")
                    .in_("id", chunk)
                    .execute()
                )
                fonts_data = fonts_result.data
                if not isinstance(fonts_data, list):
                    raise RuntimeError("fonts 조회 결과가 올바르지 않습니다")

                for font in fonts_data:
                    font_id = font.get("id")
                    if font_id is not None:
                        fonts_by_id[font_id] = font

            # fonts 결측 검증
            if len(fonts_by_id) != len(target_font_ids):
                raise RuntimeError(
                    f"fonts 결측: 예상 {len(target_font_ids)}, 조회 {len(fonts_by_id)}"
                )
        else:
            # 기존 로직: self에서 조회
            for i in range(0, len(font_ids_list), chunk_size):
                chunk = font_ids_list[i : i + chunk_size]
                fonts_result = (
                    self._schema.table("fonts")
                    .select("*")
                    .in_("id", chunk)
                    .execute()
                )
                fonts_data = fonts_result.data
                if not isinstance(fonts_data, list):
                    raise RuntimeError("fonts 조회 결과가 올바르지 않습니다")

                for font in fonts_data:
                    font_id = font.get("id")
                    if font_id is not None:
                        fonts_by_id[font_id] = font

            # fonts 결측 검증
            if len(fonts_by_id) != len(font_ids):
                raise RuntimeError(
                    f"fonts 결측: 예상 {len(font_ids)}, 조회 {len(fonts_by_id)}"
                )

        # 5. snapshots를 fonts에 매핑하고 source_key 파생
        snapshots_by_font: dict[object, list[dict[str, object]]] = {}

        if target_store is not None:
            # target_store 사용: source_key_to_target_font_id 매핑을 통해 스냅샷 매핑
            for snapshot in all_snapshots:
                provider = snapshot.get("provider")
                provider_record_id = snapshot.get("provider_record_id")
                if provider and provider_record_id:
                    key = (str(provider), str(provider_record_id))
                    if key in source_key_to_target_font_id:
                        target_font_id = source_key_to_target_font_id[key]
                        if target_font_id in fonts_by_id:
                            # 대상 DB 문맥으로 재바인딩(export 시 pop되며 source_key가 신원)
                            snapshot["font_id"] = target_font_id
                            snapshot["source_key"] = {
                                "provider": provider,
                                "provider_record_id": provider_record_id,
                            }

                            if "source_key" not in fonts_by_id[target_font_id]:
                                fonts_by_id[target_font_id]["source_key"] = snapshot["source_key"]

                            snapshots_by_font.setdefault(target_font_id, []).append(snapshot)
        else:
            # 기존 로직: dev 폰트 ID로 직접 매핑
            for snapshot in all_snapshots:
                font_id = snapshot.get("font_id")
                if font_id in fonts_by_id:
                    provider = snapshot.get("provider")
                    provider_record_id = snapshot.get("provider_record_id")
                    snapshot["source_key"] = {
                        "provider": provider,
                        "provider_record_id": provider_record_id,
                    }

                    if "source_key" not in fonts_by_id[font_id]:
                        fonts_by_id[font_id]["source_key"] = snapshot["source_key"]

                    snapshots_by_font.setdefault(font_id, []).append(snapshot)

        for font_id, font_row in fonts_by_id.items():
            font_row["evidence_snapshots"] = snapshots_by_font.get(font_id, [])

        return list(fonts_by_id.values())


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
