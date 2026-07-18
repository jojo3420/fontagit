"""폰트 데이터 감사에서 공유하는 타입."""

from datetime import datetime
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, HttpUrl

AuditStage = Literal["bootstrap", "legal", "metadata", "scheduled"]
SourceKind = Literal["official", "public", "noonnu"]
RegistryKind = Literal["official", "public", "discovery"]
DocumentKind = Literal["download", "license", "metadata"]
DownloadStatus = Literal["pending", "verified", "needs_review", "broken"]
LicenseStatus = Literal["pending", "verified", "needs_review"]
PermissionValue = Literal["allowed", "conditional", "denied"]
ScriptStatus = Literal["pending", "verified", "needs_review"]


class AuditRun(BaseModel):
    """한 번의 감사 실행과 그 결과 집계."""

    id: UUID
    stage: AuditStage
    target_environment: Literal["dev", "prod-readonly"]
    target_count: int
    success_count: int = 0
    verified_count: int = 0
    review_count: int = 0
    broken_count: int = 0
    parser_version: str
    baseline_sha256: str
    manifest_sha256: str | None = None
    dry_run: bool = True
    status: Literal["running", "completed", "failed"] = "running"
    started_at: datetime
    finished_at: datetime | None = None


class SourceSnapshot(BaseModel):
    """출처 문서에서 수집한 변경 불가능한 근거."""

    id: UUID
    run_id: UUID
    font_id: UUID
    provider: str
    provider_record_id: str
    source_kind: SourceKind
    document_kind: DocumentKind
    request_url: HttpUrl
    final_url: HttpUrl
    http_status: int | None
    raw_text: str | None
    raw_sha256: str
    normalized_sha256: str
    extracted: dict[str, object]
    evidence_locations: dict[str, object]
    extraction_rule_id: str | None
    parser_version: str
    collected_at: datetime


class LinkObservation(BaseModel):
    """한 시점에 관찰한 링크 상태."""

    normalized_url: HttpUrl
    observed_at: datetime
    http_status: int | None
    final_url: HttpUrl | None
    content_sha256: str | None
    error_kind: Literal["blocked", "timeout", "network", "oversize"] | None


class Finding(BaseModel):
    """기존 값과 근거에서 나온 변경 제안."""

    id: UUID
    run_id: UUID
    font_id: UUID
    field_name: str
    before_value: object | None
    proposed_value: object | None
    evidence_id: UUID | None
    confidence: Literal["official", "public", "reference", "unverified"]
    auto_applicable: bool = False
    review_reason: str | None = None
    status: Literal["proposed", "approved", "rejected", "applied"] = "proposed"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class SourceKey(BaseModel):
    """환경이 달라도 유지되는 출처 레코드 식별자."""

    provider: str
    provider_record_id: str


class ManifestEntry(BaseModel):
    """한 폰트 행에 적용할 감사 변경."""

    source_key: SourceKey
    before: dict[str, object]
    after: dict[str, object]
    evidence_ids: list[UUID]
    expected_updated_at: datetime


class EvidenceBundle(BaseModel):
    """manifest를 검증하는 데 필요한 근거 묶음."""

    run: dict[str, object]
    snapshots: list[dict[str, object]]
    findings: list[dict[str, object]]


class FontAuditManifest(BaseModel):
    """검수된 감사 변경을 원자적으로 적용하기 위한 문서."""

    schema_version: Literal[1]
    run_id: UUID
    baseline_sha256: str
    generated_at: datetime
    evidence_bundle: EvidenceBundle
    entries: list[ManifestEntry]


Manifest: TypeAlias = FontAuditManifest
