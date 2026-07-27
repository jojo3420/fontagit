"""Tier A(google-fonts) 공식 메타데이터 수집기.

METADATA.pb(designer/copyright)를 근거 자료로 권리사(foundry)를 판정하고,
구글폰트 specimen 페이지를 archive 등급 download_url fallback으로 제안한다.
링크 등급과 근거 자료 축은 별개다(스펙 0장).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Sequence
from urllib.parse import quote
from uuid import UUID

from pydantic import BaseModel

from fontagit_pipeline.audit_http import FetchResult, fetch_public_url
from fontagit_pipeline.audit_store import FindingDraft
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


class TierATarget(BaseModel):
    """Tier A 수집 대상 폰트."""

    font_id: UUID
    name_en: str
    license_type: str
    noonnu_foundry: str | None = None


def collect_tier_a_meta(
    targets: Sequence[TierATarget],
    store: object,  # AuditStore Protocol
    normalization: BrandNormalization,
    *,
    dry_run: bool = False,
    fetcher: object | None = None,
) -> dict[str, object]:
    """Tier A 폰트 대상별로 METADATA.pb fetch-파싱해 권리사 판정 및 URL 제안을 생성한다.

    Args:
        targets: 수집 대상 폰트 시퀀스
        store: 감사 저장소 (AuditStore Protocol)
        normalization: 권리사 정규화 테이블
        dry_run: True면 DB 쓰기 없이 메모리 저장만
        fetcher: fetch_public_url 함수 또는 None(기본값 사용)

    Returns:
        수집 결과 요약 dict (대상_수, 성공_수, 실패_수 등)
    """
    if fetcher is None:
        fetcher = fetch_public_url

    success_count = 0
    error_count = 0
    findings: list[FindingDraft] = []

    for target in targets:
        try:
            # METADATA.pb URL 구성
            metadata_url = build_metadata_url(target.license_type, target.name_en)

            # Fetch METADATA.pb
            result: FetchResult = fetcher(metadata_url, max_retries=1)  # type: ignore

            if result.status != 200:
                logger.warning(
                    "metadata_pb_fetch_failed",
                    font_id=str(target.font_id),
                    name=target.name_en,
                    url=metadata_url,
                    status=result.status,
                )
                error_count += 1
                continue

            # 파싱
            content_text = result.content.decode("utf-8", errors="replace")
            meta = parse_metadata_pb(content_text)

            # 권리사 추출 및 판정
            rights_holder = extract_rights_holder(meta.copyright or "")
            foundry_res = resolve_foundry(target.noonnu_foundry, rights_holder, normalization)

            # specimen URL 생성 (archive 등급)
            specimen_url = build_specimen_url(target.name_en)

            # FindingDraft 생성: foundry 필드
            findings.append(
                FindingDraft(
                    font_id=target.font_id,
                    field_name="foundry",
                    before_value=target.noonnu_foundry,
                    proposed_value=foundry_res.value,
                    evidence_id=None,
                    confidence="archive",
                    review_reason=foundry_res.reason,
                    auto_applicable=(foundry_res.status == "auto"),
                )
            )

            # FindingDraft 생성: specimen URL (download_url archive fallback)
            findings.append(
                FindingDraft(
                    font_id=target.font_id,
                    field_name="download_url",
                    before_value=None,
                    proposed_value=specimen_url,
                    evidence_id=None,
                    confidence="archive",
                    review_reason="specimen_page_fallback",
                    auto_applicable=True,
                )
            )

            success_count += 1

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "tier_a_meta_collection_error",
                font_id=str(target.font_id),
                name=target.name_en,
                error=str(exc),
            )
            error_count += 1

    return {
        "target_count": len(targets),
        "success_count": success_count,
        "error_count": error_count,
        "findings_count": len(findings),
    }
