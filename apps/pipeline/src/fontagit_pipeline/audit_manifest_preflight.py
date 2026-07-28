"""apply_font_audit_manifest RPC 실행 전, manifest와 DB를 필드 단위로 대조하는 읽기 전용 preflight.

RPC(0025 수정 이후 기준)와 동일한 비교 의미론을 로컬에서 재현한다:
- jsonb 필드(before_value/proposed_value/extracted/evidence_locations)는
  SQL NULL과 jsonb 'null'을 같은 값으로 취급한다.
- finding.font_id/snapshot.font_id는 source_key(provider, provider_record_id)로
  font_sources를 조회해 정확히 1행이 나와야 하며, 0행/2행+은 오류로 보고한다.
- DB에 없는 id는 오류가 아니라 신규 insert 예정으로 분류한다.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

import httpx

from fontagit_pipeline.audit_manifest import FontAuditManifest

logger = logging.getLogger(__name__)

# prod(ollidam) 게이트웨이가 UUID 100개 in-list(약 3.7KB URL)를 502로 거부한다
# (audit_store.py get_current_fonts_with_snapshots와 동일 제약) - 40개로 제한한다.
_ID_CHUNK_SIZE = 40
_PAGE_SIZE = 1000

_SQL_NULL_LABEL = "<SQL NULL>"
_JSONB_NULL_LABEL = "<jsonb null>"

EntityKind = Literal["finding", "snapshot"]

_FINDING_DIRECT_FIELDS: tuple[str, ...] = (
    "run_id",
    "field_name",
    "evidence_id",
    "confidence",
    "auto_applicable",
    "review_reason",
    "reviewed_by",
)
_FINDING_JSONB_NULL_FIELDS: tuple[str, ...] = ("before_value", "proposed_value")
_FINDING_SELECT = (
    "id,run_id,font_id,field_name,before_value,proposed_value,evidence_id,"
    "confidence,auto_applicable,review_reason,status,reviewed_by,reviewed_at"
)

_SNAPSHOT_DIRECT_FIELDS: tuple[str, ...] = (
    "provider",
    "provider_record_id",
    "source_kind",
    "document_kind",
    "request_url",
    "final_url",
    "http_status",
    "raw_text",
    "raw_sha256",
    "normalized_sha256",
    "extraction_rule_id",
    "parser_version",
)
_SNAPSHOT_JSONB_NULL_FIELDS: tuple[str, ...] = ("extracted", "evidence_locations")
_SNAPSHOT_SELECT = (
    "id,run_id,font_id,provider,provider_record_id,source_kind,document_kind,"
    "request_url,final_url,http_status,raw_text,raw_sha256,normalized_sha256,"
    "extracted,evidence_locations,extraction_rule_id,parser_version,collected_at"
)

_APPROVED_STATUSES = frozenset({"approved", "applied"})


@dataclass(frozen=True)
class FieldMismatch:
    """manifest와 DB가 어긋난 필드 하나."""

    entity: EntityKind
    entity_id: UUID
    field_name: str
    manifest_value: object
    db_value: object


@dataclass(frozen=True)
class PreflightReport:
    """apply 전 findings/snapshots 필드 단위 대조 결과."""

    mismatches: tuple[FieldMismatch, ...]
    new_finding_ids: frozenset[UUID]
    new_snapshot_ids: frozenset[UUID]

    @property
    def is_clean(self) -> bool:
        """어긋난 필드가 하나도 없으면 True."""
        return not self.mismatches

    def field_summary(self) -> dict[str, int]:
        """필드별 어긋남 개수 집계."""
        summary: dict[str, int] = {}
        for mismatch in self.mismatches:
            summary[mismatch.field_name] = summary.get(mismatch.field_name, 0) + 1
        return summary


def run_preflight(
    manifest: FontAuditManifest,
    *,
    url: str,
    secret_key: str,
    client: httpx.Client | None = None,
) -> PreflightReport:
    """manifest의 findings/snapshots를 대상 DB와 필드 단위로 대조한다 (읽기 전용).

    Args:
        manifest: 검증을 통과한 forward manifest (또는 청크).
        url: 대상 Supabase 프로젝트 URL.
        secret_key: 대상 프로젝트의 service-role secret key.
        client: 테스트용으로 주입할 httpx.Client. 생략 시 내부에서 생성-종료한다.

    Returns:
        어긋난 필드 목록과 신규 insert 예정 id 집합을 담은 PreflightReport.
    """
    owns_client = client is None
    http_client = client or httpx.Client(timeout=60.0)
    base_url = url.rstrip("/") + "/rest/v1"
    headers = _headers(secret_key)
    try:
        by_source_key = _resolve_font_sources(http_client, base_url, headers)

        findings = manifest.evidence_bundle.findings
        snapshots = manifest.evidence_bundle.snapshots
        finding_ids = [UUID(str(finding["id"])) for finding in findings]
        snapshot_ids = [UUID(str(snapshot["id"])) for snapshot in snapshots]

        db_findings = {
            UUID(str(row["id"])): row
            for row in _fetch_by_ids(
                http_client, base_url, headers, "font_audit_findings", finding_ids, _FINDING_SELECT
            )
        }
        db_snapshots = {
            UUID(str(row["id"])): row
            for row in _fetch_by_ids(
                http_client, base_url, headers, "font_source_snapshots", snapshot_ids, _SNAPSHOT_SELECT
            )
        }

        # jsonb 필드는 PostgREST가 SQL NULL과 jsonb 'null'을 구분해 반환하지 않으므로
        # is.null 보조 질의로 SQL NULL인 id만 별도 확인해 표시 라벨링에 쓴다.
        finding_null_ids = {
            field_name: _fetch_sql_null_ids(
                http_client, base_url, headers, "font_audit_findings", finding_ids, field_name
            )
            for field_name in _FINDING_JSONB_NULL_FIELDS
        }
        snapshot_null_ids = {
            field_name: _fetch_sql_null_ids(
                http_client, base_url, headers, "font_source_snapshots", snapshot_ids, field_name
            )
            for field_name in _SNAPSHOT_JSONB_NULL_FIELDS
        }

        mismatches: list[FieldMismatch] = []
        new_finding_ids: set[UUID] = set()
        new_snapshot_ids: set[UUID] = set()

        for finding in findings:
            finding_id = UUID(str(finding["id"]))
            db_row = db_findings.get(finding_id)
            if db_row is None:
                # 신규 insert 예정이어도 source_key→font_sources 해석(정확히 1행)은 항상 검증한다.
                # 여기서 생략하면 apply RPC가 entries 단계에서 실패할 오류를 preflight가 놓친다.
                _, resolution_mismatch = _check_source_key_resolution(
                    "finding", finding_id, finding.get("source_key"), by_source_key
                )
                if resolution_mismatch is not None:
                    mismatches.append(resolution_mismatch)
                new_finding_ids.add(finding_id)
                continue
            mismatches.extend(
                _compare_finding(finding_id, finding, db_row, by_source_key, finding_null_ids)
            )

        for snapshot in snapshots:
            snapshot_id = UUID(str(snapshot["id"]))
            db_row = db_snapshots.get(snapshot_id)
            if db_row is None:
                _, resolution_mismatch = _check_source_key_resolution(
                    "snapshot", snapshot_id, snapshot.get("source_key"), by_source_key
                )
                if resolution_mismatch is not None:
                    mismatches.append(resolution_mismatch)
                new_snapshot_ids.add(snapshot_id)
                continue
            mismatches.extend(
                _compare_snapshot(snapshot_id, snapshot, db_row, by_source_key, snapshot_null_ids)
            )

        return PreflightReport(
            mismatches=tuple(mismatches),
            new_finding_ids=frozenset(new_finding_ids),
            new_snapshot_ids=frozenset(new_snapshot_ids),
        )
    finally:
        if owns_client:
            http_client.close()


def _headers(secret_key: str) -> dict[str, str]:
    return {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
        "Accept-Profile": "fontagit",
    }


def _fetch_all(
    client: httpx.Client,
    base_url: str,
    headers: Mapping[str, str],
    path: str,
    params: Mapping[str, str],
) -> list[dict[str, object]]:
    """PostgREST 응답을 offset 페이지네이션으로 전량 조회한다."""
    rows: list[dict[str, object]] = []
    offset = 0
    while True:
        page_params = {**params, "limit": str(_PAGE_SIZE), "offset": str(offset)}
        response = client.get(f"{base_url}/{path}", params=page_params, headers=headers)
        response.raise_for_status()
        batch = response.json()
        if not isinstance(batch, list):
            raise RuntimeError(f"{path} 조회 응답이 배열이 아닙니다")
        rows.extend(batch)
        if len(batch) < _PAGE_SIZE:
            return rows
        offset += _PAGE_SIZE


def _fetch_by_ids(
    client: httpx.Client,
    base_url: str,
    headers: Mapping[str, str],
    path: str,
    ids: Sequence[UUID],
    select: str,
) -> list[dict[str, object]]:
    """id in-list를 청크 단위로 조회한다 (prod 게이트웨이 502 방지)."""
    rows: list[dict[str, object]] = []
    id_strings = [str(item) for item in ids]
    for offset in range(0, len(id_strings), _ID_CHUNK_SIZE):
        chunk = id_strings[offset : offset + _ID_CHUNK_SIZE]
        rows.extend(
            _fetch_all(
                client,
                base_url,
                headers,
                path,
                {"id": f"in.({','.join(chunk)})", "select": select},
            )
        )
    return rows


def _fetch_sql_null_ids(
    client: httpx.Client,
    base_url: str,
    headers: Mapping[str, str],
    path: str,
    ids: Sequence[UUID],
    field_name: str,
) -> frozenset[UUID]:
    """id 목록 중 field_name이 SQL NULL인 id만 골라낸다 (jsonb 'null'과 구분용)."""
    id_strings = [str(item) for item in ids]
    null_ids: set[UUID] = set()
    for offset in range(0, len(id_strings), _ID_CHUNK_SIZE):
        chunk = id_strings[offset : offset + _ID_CHUNK_SIZE]
        rows = _fetch_all(
            client,
            base_url,
            headers,
            path,
            {"id": f"in.({','.join(chunk)})", field_name: "is.null", "select": "id"},
        )
        for row in rows:
            row_id = row.get("id")
            if isinstance(row_id, str):
                null_ids.add(UUID(row_id))
    return frozenset(null_ids)


def _resolve_font_sources(
    client: httpx.Client, base_url: str, headers: Mapping[str, str]
) -> dict[tuple[str, str], list[str]]:
    """font_sources 전체를 (provider, provider_record_id)로 그룹화한다."""
    rows = _fetch_all(
        client,
        base_url,
        headers,
        "font_sources",
        {"select": "font_id,provider,provider_record_id"},
    )
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in rows:
        provider = row.get("provider")
        provider_record_id = row.get("provider_record_id")
        font_id = row.get("font_id")
        if (
            isinstance(provider, str)
            and isinstance(provider_record_id, str)
            and isinstance(font_id, str)
        ):
            grouped[(provider, provider_record_id)].append(font_id)
    return grouped


def _resolve_font_id(
    source_key: Mapping[str, object], by_source_key: Mapping[tuple[str, str], list[str]]
) -> tuple[str | None, int]:
    """source_key로 font_sources를 조회해 (font_id, 매칭 행 수)를 반환한다."""
    key = (str(source_key.get("provider")), str(source_key.get("provider_record_id")))
    candidates = by_source_key.get(key, [])
    if len(candidates) == 1:
        return candidates[0], 1
    return None, len(candidates)


def _normalize_jsonb(value: object) -> str | None:
    """jsonb 값을 비교용 정규 문자열로 만든다. None은 SQL NULL과 jsonb null을 구분하지 않는다."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _display_jsonb(value: object, is_sql_null: bool) -> object:
    """불일치 보고에서 None의 근원(SQL NULL/jsonb null)을 밝힌다."""
    if value is None:
        return _SQL_NULL_LABEL if is_sql_null else _JSONB_NULL_LABEL
    return value


def _timestamptz_equal(manifest_value: object, db_value: object) -> bool:
    """표기가 달라도(Z/+00:00, 마이크로초 자릿수) 같은 시각이면 동일 취급한다."""
    try:
        manifest_dt = datetime.fromisoformat(str(manifest_value))
        db_dt = datetime.fromisoformat(str(db_value))
    except ValueError:
        return manifest_value == db_value
    return manifest_dt == db_dt


def _check_source_key_resolution(
    entity: EntityKind,
    entity_id: UUID,
    source_key: object,
    by_source_key: Mapping[tuple[str, str], list[str]],
) -> tuple[str | None, FieldMismatch | None]:
    """source_key→font_sources 해석 결과를 반환한다 (DB 존재 여부와 무관하게 항상 필요한 검증).

    apply RPC는 entries 단계에서 이 해석이 정확히 1행이어야 성공한다
    ('stable source key must resolve exactly one font'). DB에 아직 없는
    신규 finding/snapshot이라도 생략하면 안 되는 이유가 여기에 있다.
    """
    if not isinstance(source_key, Mapping):
        raise ValueError(f"{entity} {entity_id}: source_key가 없습니다")
    resolved_font_id, row_count = _resolve_font_id(source_key, by_source_key)
    if row_count != 1:
        return None, FieldMismatch(
            entity=entity,
            entity_id=entity_id,
            field_name="font_id",
            manifest_value=dict(source_key),
            db_value=f"font_sources 매칭 {row_count}행 (정확히 1행이어야 함)",
        )
    return resolved_font_id, None


def _compare_font_id(
    entity: EntityKind,
    entity_id: UUID,
    source_key: object,
    db_font_id: object,
    by_source_key: Mapping[tuple[str, str], list[str]],
) -> FieldMismatch | None:
    resolved_font_id, resolution_mismatch = _check_source_key_resolution(
        entity, entity_id, source_key, by_source_key
    )
    if resolution_mismatch is not None:
        return resolution_mismatch
    if resolved_font_id != db_font_id:
        return FieldMismatch(
            entity=entity,
            entity_id=entity_id,
            field_name="font_id",
            manifest_value=resolved_font_id,
            db_value=db_font_id,
        )
    return None


def _compare_finding(
    finding_id: UUID,
    finding: Mapping[str, object],
    db_row: Mapping[str, object],
    by_source_key: Mapping[tuple[str, str], list[str]],
    null_ids: Mapping[str, frozenset[UUID]],
) -> list[FieldMismatch]:
    """finding 한 건을 RPC 비교 의미론대로 DB 행과 대조한다."""
    mismatches: list[FieldMismatch] = []

    font_id_mismatch = _compare_font_id(
        "finding", finding_id, finding.get("source_key"), db_row.get("font_id"), by_source_key
    )
    if font_id_mismatch is not None:
        mismatches.append(font_id_mismatch)

    for field_name in _FINDING_DIRECT_FIELDS:
        if finding.get(field_name) != db_row.get(field_name):
            mismatches.append(
                FieldMismatch(
                    entity="finding",
                    entity_id=finding_id,
                    field_name=field_name,
                    manifest_value=finding.get(field_name),
                    db_value=db_row.get(field_name),
                )
            )

    for field_name in _FINDING_JSONB_NULL_FIELDS:
        db_value = db_row.get(field_name)
        if _normalize_jsonb(finding.get(field_name)) != _normalize_jsonb(db_value):
            mismatches.append(
                FieldMismatch(
                    entity="finding",
                    entity_id=finding_id,
                    field_name=field_name,
                    manifest_value=finding.get(field_name),
                    db_value=_display_jsonb(db_value, finding_id in null_ids[field_name]),
                )
            )

    db_status = db_row.get("status")
    if db_status not in _APPROVED_STATUSES:
        mismatches.append(
            FieldMismatch(
                entity="finding",
                entity_id=finding_id,
                field_name="status",
                manifest_value="approved 또는 applied",
                db_value=db_status,
            )
        )

    if not _timestamptz_equal(finding.get("reviewed_at"), db_row.get("reviewed_at")):
        mismatches.append(
            FieldMismatch(
                entity="finding",
                entity_id=finding_id,
                field_name="reviewed_at",
                manifest_value=finding.get("reviewed_at"),
                db_value=db_row.get("reviewed_at"),
            )
        )

    return mismatches


def _compare_snapshot(
    snapshot_id: UUID,
    snapshot: Mapping[str, object],
    db_row: Mapping[str, object],
    by_source_key: Mapping[tuple[str, str], list[str]],
    null_ids: Mapping[str, frozenset[UUID]],
) -> list[FieldMismatch]:
    """snapshot 한 건을 RPC 비교 의미론대로 DB 행과 대조한다."""
    mismatches: list[FieldMismatch] = []

    font_id_mismatch = _compare_font_id(
        "snapshot", snapshot_id, snapshot.get("source_key"), db_row.get("font_id"), by_source_key
    )
    if font_id_mismatch is not None:
        mismatches.append(font_id_mismatch)

    for field_name in _SNAPSHOT_DIRECT_FIELDS:
        if snapshot.get(field_name) != db_row.get(field_name):
            mismatches.append(
                FieldMismatch(
                    entity="snapshot",
                    entity_id=snapshot_id,
                    field_name=field_name,
                    manifest_value=snapshot.get(field_name),
                    db_value=db_row.get(field_name),
                )
            )

    for field_name in _SNAPSHOT_JSONB_NULL_FIELDS:
        db_value = db_row.get(field_name)
        if _normalize_jsonb(snapshot.get(field_name)) != _normalize_jsonb(db_value):
            mismatches.append(
                FieldMismatch(
                    entity="snapshot",
                    entity_id=snapshot_id,
                    field_name=field_name,
                    manifest_value=snapshot.get(field_name),
                    db_value=_display_jsonb(db_value, snapshot_id in null_ids[field_name]),
                )
            )

    if not _timestamptz_equal(snapshot.get("collected_at"), db_row.get("collected_at")):
        mismatches.append(
            FieldMismatch(
                entity="snapshot",
                entity_id=snapshot_id,
                field_name="collected_at",
                manifest_value=snapshot.get("collected_at"),
                db_value=db_row.get("collected_at"),
            )
        )

    return mismatches
