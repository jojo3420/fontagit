"""근거가 정확히 일치할 때만 라이선스 권한을 확정한다."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot


Permission = Literal["allowed", "conditional", "denied"]
Attribution = Literal["required", "recommended", "not_required"]
LicenseStatus = Literal["verified", "needs_review"]
_PERMISSION_FIELDS = (
    "allow_commercial",
    "allow_modify",
    "allow_redistribute",
    "allow_embedding",
    "allow_font_sale",
    "attribution_requirement",
)


class LicenseDecision(BaseModel):
    """공개 화면에 전달할 라이선스 판정과 증거 위치."""

    status: LicenseStatus = "needs_review"
    auto_applicable: bool = False
    allow_commercial: Permission | None = None
    allow_modify: Permission | None = None
    allow_redistribute: Permission | None = None
    allow_embedding: Permission | None = None
    allow_font_sale: Permission | None = None
    attribution_requirement: Attribution | None = None
    restrictions: list[str] = Field(default_factory=list)
    evidence_locations: dict[str, str] = Field(default_factory=dict)
    source_url: str
    summary: str


def classify_license(
    snapshot: NoonnuFontSnapshot,
    registry: object,
    rules: Mapping[str, object] | str | Path,
) -> LicenseDecision:
    """표준·제작사 템플릿·사람 승인이 정확히 맞을 때만 verified를 반환한다."""
    payload = _load_rules(rules)
    if snapshot.extractor != "deterministic":
        return _needs_review(snapshot)

    reviewed = _reviewed_permissions(snapshot)
    if reviewed is not None:
        return _verified(snapshot, reviewed, [], "human_review")

    fingerprint = _fingerprint(snapshot.license_text)
    standard = _matching_standard(snapshot, payload, fingerprint)
    if standard is not None:
        return _verified(
            snapshot,
            _permission_values(standard.get("permissions")),
            _restrictions(standard.get("restrictions")),
            "license_text",
        )

    template = _matching_template(snapshot, registry, payload, fingerprint)
    if template is not None:
        return _verified(
            snapshot,
            _permission_values(template.get("permissions")),
            _restrictions(template.get("restrictions")),
            "license_text",
        )
    return _needs_review(snapshot)


def _load_rules(rules: Mapping[str, object] | str | Path) -> Mapping[str, object]:
    if isinstance(rules, Mapping):
        return rules
    try:
        payload = json.loads(Path(rules).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"license rules를 읽을 수 없습니다: {rules}") from exc
    if not isinstance(payload, dict):
        raise ValueError("license rules must be a JSON object")
    return payload


def _fingerprint(text: str | None) -> str | None:
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _matching_standard(
    snapshot: NoonnuFontSnapshot,
    rules: Mapping[str, object],
    fingerprint: str | None,
) -> Mapping[str, object] | None:
    if fingerprint is None or not snapshot.license_id or not snapshot.license_version:
        return None
    entries = rules.get("standard_licenses")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        if (
            entry.get("id") == snapshot.license_id
            and entry.get("version") == snapshot.license_version
            and entry.get("fingerprint") == fingerprint
        ):
            return entry
    return None


def _matching_template(
    snapshot: NoonnuFontSnapshot,
    registry: object,
    rules: Mapping[str, object],
    fingerprint: str | None,
) -> Mapping[str, object] | None:
    if fingerprint is None or not snapshot.template_selector or not snapshot.template_version:
        return None
    if not _is_approved_source(snapshot.source_url, registry):
        return None
    hostname = (urlparse(snapshot.source_url).hostname or "").lower().rstrip(".")
    entries = rules.get("maker_templates")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        domain = entry.get("domain")
        if not isinstance(domain, str):
            continue
        normalized_domain = domain.lower().rstrip(".")
        if hostname != normalized_domain and not hostname.endswith(f".{normalized_domain}"):
            continue
        if (
            entry.get("selector") == snapshot.template_selector
            and entry.get("template_version") == snapshot.template_version
            and entry.get("fingerprint") == fingerprint
        ):
            return entry
    return None


def _is_approved_source(source_url: str, registry: object) -> bool:
    classifier = getattr(registry, "classify", None)
    if callable(classifier):
        return classifier(source_url) in {"official", "public"}
    if not isinstance(registry, Mapping):
        return False
    hostname = (urlparse(source_url).hostname or "").lower().rstrip(".")
    entries = registry.get("entries")
    if not isinstance(entries, list):
        return False
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        domain = entry.get("domain")
        if not isinstance(domain, str):
            continue
        normalized_domain = domain.lower().rstrip(".")
        if hostname == normalized_domain or hostname.endswith(f".{normalized_domain}"):
            return entry.get("source_kind") in {"official", "public"}
    return False


def _reviewed_permissions(snapshot: NoonnuFontSnapshot) -> dict[str, str | None] | None:
    if (
        snapshot.finding_status != "approved"
        or not snapshot.reviewed_by
        or not snapshot.reviewed_at
    ):
        return None
    return _permission_values(snapshot.reviewed_permissions)


def _permission_values(value: object) -> dict[str, str | None]:
    if not isinstance(value, Mapping):
        return {field: None for field in _PERMISSION_FIELDS}
    result: dict[str, str | None] = {}
    for field in _PERMISSION_FIELDS:
        item = value.get(field)
        if field == "attribution_requirement":
            result[field] = item if item in {"required", "recommended", "not_required"} else None
        else:
            result[field] = item if item in {"allowed", "conditional", "denied"} else None
    return result


def _restrictions(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _verified(
    snapshot: NoonnuFontSnapshot,
    permissions: Mapping[str, str | None],
    restrictions: list[str],
    evidence_key: str,
) -> LicenseDecision:
    location = snapshot.evidence_locations.get(evidence_key, evidence_key)
    evidence = {field: location for field in _PERMISSION_FIELDS if permissions.get(field) is not None}
    return LicenseDecision(
        status="verified",
        auto_applicable=True,
        allow_commercial=permissions.get("allow_commercial"),  # type: ignore[arg-type]
        allow_modify=permissions.get("allow_modify"),  # type: ignore[arg-type]
        allow_redistribute=permissions.get("allow_redistribute"),  # type: ignore[arg-type]
        allow_embedding=permissions.get("allow_embedding"),  # type: ignore[arg-type]
        allow_font_sale=permissions.get("allow_font_sale"),  # type: ignore[arg-type]
        attribution_requirement=permissions.get("attribution_requirement"),  # type: ignore[arg-type]
        restrictions=restrictions,
        evidence_locations=evidence,
        source_url=snapshot.source_url,
        summary=_summary(permissions, restrictions),
    )


def _needs_review(snapshot: NoonnuFontSnapshot) -> LicenseDecision:
    return LicenseDecision(
        source_url=snapshot.source_url,
        summary="라이선스 재확인 필요. 원문 링크를 확인하세요.",
    )


def _summary(permissions: Mapping[str, str | None], restrictions: list[str]) -> str:
    labels = {
        "allow_commercial": "상업적 이용",
        "allow_modify": "수정",
        "allow_redistribute": "재배포",
        "allow_embedding": "임베딩",
        "allow_font_sale": "폰트 판매",
        "attribution_requirement": "출처 표기",
    }
    values = {
        "allowed": "허용",
        "conditional": "조건부 허용",
        "denied": "금지",
        "required": "필수",
        "recommended": "권장",
        "not_required": "불필요",
    }
    parts = []
    for field in _PERMISSION_FIELDS:
        permission = permissions.get(field)
        display = values.get(permission, "미확인") if permission is not None else "미확인"
        parts.append(f"{labels[field]}: {display}")
    if restrictions:
        parts.append(f"제한: {'; '.join(restrictions)}")
    return " · ".join(parts)
