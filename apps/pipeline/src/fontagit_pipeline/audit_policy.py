"""승인된 출처와 수집 보관 범위를 검증한다."""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, HttpUrl, field_validator, model_validator

from fontagit_pipeline.audit_models import RegistryKind

_DATA_DIR = Path(__file__).with_name("data")
_DEFAULT_REGISTRY_PATH = _DATA_DIR / "source_registry.json"

PolicyDecision = Literal["allowed", "denied", "unknown"]
CollectionMode = Literal["structured-only", "raw-retention"]


class RegistryEntry(BaseModel):
    """제작사 또는 공공 출처 한 곳의 승인 정보."""

    maker: str | None = None
    domain: str | None = None
    roles: list[str] | None = None
    source_kind: RegistryKind = "discovery"
    approved_by: str | None = None
    approved_at: datetime | None = None
    evidence_snapshot_id: str | None = None

    @field_validator("approved_at", mode="before")
    @classmethod
    def blank_approval_time_is_missing(cls, value: object) -> object:
        """빈 승인 시각을 검증 가능한 미입력 상태로 바꾼다."""
        return None if value == "" else value

    @model_validator(mode="after")
    def require_approval_evidence(self) -> "RegistryEntry":
        """공식·공공 출처에는 빈칸 없는 승인 근거가 필요하다."""
        if self.source_kind not in {"official", "public"}:
            return self

        required = (
            self.maker,
            self.domain,
            self.roles,
            self.approved_by,
            self.approved_at,
            self.evidence_snapshot_id,
        )
        if not all(required):
            raise ValueError("official/public registry entry requires approval evidence")
        return self


class SourceRegistry(BaseModel):
    """사람이 승인한 출처와 discovery 후보 목록."""

    version: Literal[1]
    entries: list[RegistryEntry]

    def classify(self, url: str) -> RegistryKind:
        """URL을 승인 정보에 따라 분류하고, 모르면 discovery로 둔다."""
        hostname = (urlparse(url).hostname or "").lower().rstrip(".")
        for entry in self.entries:
            domain = (entry.domain or "").lower().rstrip(".")
            if not domain or not (hostname == domain or hostname.endswith(f".{domain}")):
                continue
            if entry.source_kind in {"official", "public"}:
                return entry.source_kind
            return "discovery"
        return "discovery"


class CollectionPolicy(BaseModel):
    """robots와 이용 조건을 사람이 승인한 결과."""

    version: Literal[1]
    source: str
    robots_url: HttpUrl | None
    terms_url: HttpUrl | None
    checked_at: datetime | None
    crawl_allowed: PolicyDecision = "unknown"
    raw_retention_allowed: PolicyDecision = "unknown"
    robots_sha256: str | None
    terms_sha256: str | None
    approved_by: str | None
    approved_at: datetime | None

    @property
    def has_human_approval(self) -> bool:
        """승인자와 승인 시각이 모두 있는지 반환한다."""
        return bool(self.approved_by and self.approved_at)

    @property
    def has_complete_evidence(self) -> bool:
        """robots·이용 조건 원문과 SHA-256이 모두 기록됐는지 반환한다."""
        return bool(
            self.checked_at
            and self.robots_url
            and self.terms_url
            and _is_sha256(self.robots_sha256)
            and _is_sha256(self.terms_sha256)
        )


def _is_sha256(value: str | None) -> bool:
    """문자열이 64자리 16진수 SHA-256인지 확인한다."""
    if value is None or len(value) != 64:
        return False
    return all(character in "0123456789abcdefABCDEF" for character in value)


def load_source_registry(path: str | Path = _DEFAULT_REGISTRY_PATH) -> SourceRegistry:
    """JSON 출처 레지스트리를 읽고 승인 근거를 검증한다."""
    registry_path = Path(path)
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"source registry를 읽을 수 없습니다: {registry_path}") from exc
    return SourceRegistry.model_validate(payload)


def load_collection_policy(path: str | Path) -> CollectionPolicy:
    """수집 정책 JSON을 읽는다."""
    policy_path = Path(path)
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"collection policy를 읽을 수 없습니다: {policy_path}") from exc
    return CollectionPolicy.model_validate(payload)


def assert_collection_allowed(
    policy_path: str | Path | None = None,
    *,
    retain_raw_text: bool = False,
) -> CollectionMode:
    """수집·원문 보관 정책을 확인하고 허용된 저장 모드를 반환한다."""
    policy = load_collection_policy(policy_path) if policy_path is not None else None
    if policy is not None and policy.crawl_allowed == "denied":
        raise ValueError("collection is denied by approved policy")

    raw_allowed = bool(
        policy is not None
        and policy.has_human_approval
        and policy.has_complete_evidence
        and policy.crawl_allowed == "allowed"
        and policy.raw_retention_allowed == "allowed"
    )
    if retain_raw_text and not raw_allowed:
        raise ValueError("raw_text retention requires an approved collection policy")
    return "raw-retention" if retain_raw_text else "structured-only"


def write_policy_check(path: str | Path) -> CollectionPolicy:
    """사람 검수 전 unknown 상태의 정책 JSON을 만든다."""
    policy = CollectionPolicy(
        version=1,
        source="noonnu",
        robots_url=HttpUrl("https://noonnu.cc/robots.txt"),
        terms_url=None,
        checked_at=None,
        crawl_allowed="unknown",
        raw_retention_allowed="unknown",
        robots_sha256=None,
        terms_sha256=None,
        approved_by=None,
        approved_at=None,
    )
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(policy.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return policy
