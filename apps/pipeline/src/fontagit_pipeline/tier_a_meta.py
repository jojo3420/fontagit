"""Tier A(google-fonts) 공식 메타데이터 수집기.

METADATA.pb(designer/copyright)를 근거 자료로 권리사(foundry)를 판정하고,
구글폰트 specimen 페이지를 archive 등급 download_url fallback으로 제안한다.
링크 등급과 근거 자료 축은 별개다(스펙 0장).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Callable, Sequence
from urllib.parse import quote
from uuid import UUID

from pydantic import BaseModel

from fontagit_pipeline.audit_http import FetchResult, fetch_public_url
from fontagit_pipeline.audit_policy import (
    AUTO_APPLICABLE_SOURCE_KINDS,
    SourceRegistry,
    may_update_source_kind,
)
from fontagit_pipeline.audit_store import AuditStore, FindingDraft, SnapshotDraft
from fontagit_pipeline.licenses import _LICENSE_DIRS

logger = logging.getLogger(__name__)

_METADATA_URL = "https://raw.githubusercontent.com/google/fonts/main/{license_dir}/{family_dir}/METADATA.pb"
_DESIGNER_RE = re.compile(r'^designer:\s*"(?P<v>[^"]+)"', re.MULTILINE)
_COPYRIGHT_RE = re.compile(r'copyright:\s*"(?P<v>[^"]+)"')
_RIGHTS_HOLDER_RE = re.compile(
    r"Copyright\s*(?:\(c\)|©)?\s*[\d,\-\s]*(?:by\s+)?(?P<holder>[^.,()\"]+)", re.IGNORECASE
)


class TierAMeta(BaseModel):
    """METADATA.pb에서 추출한 메타데이터."""

    designer: str | None = None
    copyright: str | None = None


class BrandEntry(BaseModel):
    """정규화된 권리사(foundry) 한 건."""

    source_name: str
    display_name: str
    evidence_url: str
    status: str  # "approved" | "needs_review"


class BrandNormalization(BaseModel):
    """권리사 정규화 테이블."""

    entries: list[BrandEntry] = []

    def resolve(self, raw_name: str) -> BrandEntry | None:
        """정규화 테이블에서 권리사명을 찾는다. 대소문자 무시."""
        needle = raw_name.strip().casefold()
        for entry in self.entries:
            if entry.source_name.casefold() == needle:
                return entry
        return None


class FoundryResolution(BaseModel):
    """제작사(foundry) 판정 결과."""

    value: str | None
    status: str  # "auto" | "needs_review"
    reason: str


def parse_metadata_pb(text: str) -> TierAMeta:
    """METADATA.pb 텍스트에서 designer/copyright를 추출한다(프로토버프 의존 없이 라인 파싱)."""
    designer = _DESIGNER_RE.search(text)
    copyright_ = _COPYRIGHT_RE.search(text)
    return TierAMeta(
        designer=designer.group("v") if designer else None,
        copyright=copyright_.group("v") if copyright_ else None,
    )


def extract_rights_holder(copyright_text: str) -> str | None:
    """copyright 문자열에서 권리사 명칭을 추출한다. 실패 시 None(needs_review 경로)."""
    match = _RIGHTS_HOLDER_RE.search(copyright_text or "")
    if not match:
        return None
    holder = match.group("holder").strip().rstrip(".")
    return holder or None


def resolve_foundry(
    noonnu_foundry: str | None,
    rights_holder: str | None,
    normalization: BrandNormalization,
) -> FoundryResolution:
    """제작사 표기를 판정한다. 눈누 표기 == 정규화(approved)된 권리사일 때만 auto."""
    if not rights_holder:
        return FoundryResolution(value=noonnu_foundry, status="needs_review", reason="no_rights_holder")
    entry = normalization.resolve(rights_holder)
    display = entry.display_name if entry else rights_holder
    if entry and entry.status != "approved":
        return FoundryResolution(value=display, status="needs_review", reason="normalization_pending")
    if noonnu_foundry and noonnu_foundry.strip() == display:
        return FoundryResolution(value=display, status="auto", reason="matched")
    return FoundryResolution(value=display, status="needs_review", reason="mismatch_or_missing_noonnu")


def build_specimen_url(name_en: str) -> str:
    """구글폰트 specimen 페이지 URL(archive 등급 fallback)."""
    return f"https://fonts.google.com/specimen/{quote(name_en).replace('%20', '+')}"


def build_metadata_url(license_type: str, name_en: str) -> str:
    """license_type(OFL 등)과 영문명으로 google/fonts METADATA.pb URL을 만든다."""
    # _LICENSE_DIRS 역매핑: {"ofl": "OFL"} -> {"OFL": "ofl"}
    dirs = {label: d for d, label in _LICENSE_DIRS.items()}
    license_dir = dirs.get(license_type, "ofl")
    family_dir = name_en.replace(" ", "").lower()
    return _METADATA_URL.format(license_dir=license_dir, family_dir=family_dir)


def build_license_source_url(license_type: str, name_en: str) -> str:
    """google/fonts 레포 내 LICENSE 파일 URL."""
    dirs = {label: d for d, label in _LICENSE_DIRS.items()}
    license_dir = dirs.get(license_type, "ofl")
    family_dir = name_en.replace(" ", "").lower()
    return f"https://raw.githubusercontent.com/google/fonts/main/{license_dir}/{family_dir}/LICENSE.txt"


class TierATarget(BaseModel):
    """Tier A 수집 대상 폰트."""

    font_id: UUID
    name_en: str
    license_type: str
    slug: str | None = None  # 검수 리포트 표시용(DB 저장에는 미사용)
    noonnu_foundry: str | None = None
    download_source_kind: str | None = None
    license_source_kind: str | None = None


def _finding_detail(target: TierATarget, finding: FindingDraft) -> dict[str, object]:
    """검수용 리포트에 담을 finding 상세 레코드를 만든다."""
    return {
        "slug": target.slug,
        "name_en": target.name_en,
        "field_name": finding.field_name,
        "before_value": finding.before_value,
        "proposed_value": finding.proposed_value,
        "auto_applicable": finding.auto_applicable,
        "review_reason": finding.review_reason,
        # dry_run이면 스냅샷을 저장하지 않아 None(evidence 없음)이 그대로 드러난다.
        "evidence_id": str(finding.evidence_id) if finding.evidence_id else None,
    }


def collect_tier_a_meta(
    run_id: UUID,
    targets: Sequence[TierATarget],
    store: AuditStore,
    registry: SourceRegistry,
    normalization: BrandNormalization,
    *,
    dry_run: bool = False,
    fetcher: Callable[..., FetchResult] | None = None,
) -> dict[str, object]:
    """Tier A 폰트 대상별로 METADATA.pb fetch-파싱해 권리사 판정 및 URL 제안을 생성한다.

    Args:
        run_id: 감사 실행 ID
        targets: 수집 대상 폰트 시퀀스
        store: 감사 저장소 (AuditStore Protocol)
        registry: 출처 분류 레지스트리
        normalization: 권리사 정규화 테이블
        dry_run: True면 DB 쓰기 없이 메모리만 사용
        fetcher: fetch 함수(기본값: fetch_public_url)

    Returns:
        수집 결과 요약 dict (target_count, success_count, error_count, findings_created,
        findings: 검수용 finding 상세 배열, errors: 실패 대상 상세 배열)
    """
    if fetcher is None:
        fetcher = fetch_public_url

    success_count = 0
    error_count = 0
    findings_created = 0
    findings_detail: list[dict[str, object]] = []
    errors_detail: list[dict[str, object]] = []

    for target in targets:
        try:
            # METADATA.pb URL 구성
            metadata_url = build_metadata_url(target.license_type, target.name_en)

            # Fetch METADATA.pb
            result: FetchResult = fetcher(metadata_url, max_retries=1)

            if result.status != 200:
                logger.warning(
                    "metadata_pb_fetch_failed: font_id=%s, name=%s, status=%d",
                    str(target.font_id),
                    target.name_en,
                    result.status,
                )
                error_count += 1
                errors_detail.append(
                    {
                        "slug": target.slug,
                        "name_en": target.name_en,
                        "reason": f"metadata_pb_fetch_failed:http_{result.status}",
                    }
                )
                continue

            # 파싱
            content_text = result.content.decode("utf-8", errors="replace")
            meta = parse_metadata_pb(content_text)

            # 권리사 추출 및 판정
            rights_holder = extract_rights_holder(meta.copyright or "")
            foundry_res = resolve_foundry(target.noonnu_foundry, rights_holder, normalization)

            # specimen URL 생성
            specimen_url = build_specimen_url(target.name_en)
            license_source_url = build_license_source_url(target.license_type, target.name_en)

            # Tier A 근거 스냅샷: dry_run이면 저장을 건너뛰고 evidence_id는 None으로 남긴다
            # (리포트에 evidence 없음이 그대로 드러남). font_source_snapshots.source_kind
            # CHECK는 official/public/noonnu만 허용해 archive를 저장할 수 없으므로,
            # google/fonts 공개 저장소 원문이라는 의미에서 'public'을 근거 등급으로 쓴다
            # (링크 자체의 archive 등급과는 별개 축, 스펙 0장).
            evidence_id: UUID | None = None
            if not dry_run:
                extracted = {
                    "evidence_role": "tier-a-metadata-pb",
                    "designer": meta.designer,
                    "copyright": meta.copyright,
                }
                normalized_sha256 = hashlib.sha256(
                    json.dumps(
                        extracted, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    ).encode("utf-8")
                ).hexdigest()
                snapshot = SnapshotDraft(
                    font_id=target.font_id,
                    provider="google-fonts",
                    provider_record_id=target.name_en,
                    source_kind="public",
                    document_kind="metadata",
                    request_url=metadata_url,
                    final_url=result.final_url,
                    http_status=result.status,
                    raw_text=None,
                    raw_sha256=hashlib.sha256(result.content).hexdigest(),
                    normalized_sha256=normalized_sha256,
                    extracted=extracted,
                    evidence_locations={"metadata_pb": metadata_url},
                    extraction_rule_id="tier-a-metadata-pb-v1",
                    parser_version="tier-a-meta-v1",
                    collected_at=datetime.now(UTC),
                )
                evidence_id = store.save_snapshot(run_id, snapshot)

            # 1. foundry 필드
            finding_foundry = FindingDraft(
                font_id=target.font_id,
                field_name="foundry",
                before_value=target.noonnu_foundry,
                proposed_value=foundry_res.value,
                evidence_id=evidence_id,
                confidence="reference",
                review_reason=foundry_res.reason,
                auto_applicable=(foundry_res.status == "auto"),
            )
            if not dry_run:
                store.save_finding(run_id, finding_foundry)
            findings_created += 1
            findings_detail.append(_finding_detail(target, finding_foundry))

            # 2. foundry_url 필드 (정규화 사전의 evidence_url)
            if foundry_res.value is not None:
                entry = normalization.resolve(rights_holder or "")
                if entry is not None:
                    finding_foundry_url = FindingDraft(
                        font_id=target.font_id,
                        field_name="foundry_url",
                        before_value=None,
                        proposed_value=entry.evidence_url,
                        evidence_id=evidence_id,
                        confidence="reference",
                        review_reason="normalization_evidence",
                        auto_applicable=(entry.status == "approved"),
                    )
                    if not dry_run:
                        store.save_finding(run_id, finding_foundry_url)
                    findings_created += 1
                    findings_detail.append(_finding_detail(target, finding_foundry_url))

            # 3. download_url + download_source_kind (쌍으로 생성)
            specimen_source_kind = registry.classify(specimen_url)
            if may_update_source_kind(target.download_source_kind, specimen_source_kind):
                finding_download_url = FindingDraft(
                    font_id=target.font_id,
                    field_name="download_url",
                    before_value=None,
                    proposed_value=specimen_url,
                    evidence_id=evidence_id,
                    confidence="reference",
                    review_reason="specimen_page_fallback",
                    auto_applicable=(specimen_source_kind in AUTO_APPLICABLE_SOURCE_KINDS),
                )
                if not dry_run:
                    store.save_finding(run_id, finding_download_url)
                findings_created += 1
                findings_detail.append(_finding_detail(target, finding_download_url))

                finding_download_kind = FindingDraft(
                    font_id=target.font_id,
                    field_name="download_source_kind",
                    before_value=target.download_source_kind,
                    proposed_value=specimen_source_kind,
                    evidence_id=evidence_id,
                    confidence="reference",
                    review_reason="specimen_page_fallback",
                    auto_applicable=(specimen_source_kind in AUTO_APPLICABLE_SOURCE_KINDS),
                )
                if not dry_run:
                    store.save_finding(run_id, finding_download_kind)
                findings_created += 1
                findings_detail.append(_finding_detail(target, finding_download_kind))

            # 4. license_source_url 필드
            license_source_kind = registry.classify(license_source_url)
            if may_update_source_kind(target.license_source_kind, license_source_kind):
                finding_license_url = FindingDraft(
                    font_id=target.font_id,
                    field_name="license_source_url",
                    before_value=None,
                    proposed_value=license_source_url,
                    evidence_id=evidence_id,
                    confidence="reference",
                    review_reason="github_license_file",
                    auto_applicable=(license_source_kind in AUTO_APPLICABLE_SOURCE_KINDS),
                )
                if not dry_run:
                    store.save_finding(run_id, finding_license_url)
                findings_created += 1
                findings_detail.append(_finding_detail(target, finding_license_url))

            success_count += 1

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "tier_a_meta_collection_error: font_id=%s, name=%s, error=%s",
                str(target.font_id),
                target.name_en,
                str(exc),
            )
            error_count += 1
            errors_detail.append(
                {
                    "slug": target.slug,
                    "name_en": target.name_en,
                    "reason": f"{type(exc).__name__}:{exc}",
                }
            )

    return {
        "target_count": len(targets),
        "success_count": success_count,
        "error_count": error_count,
        "findings_created": findings_created,
        "findings": findings_detail,
        "errors": errors_detail,
    }
