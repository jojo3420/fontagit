"""눈누 URL 스캔 판정을 감사 저장소 draft로 옮긴다.

스캔기(`noonnu_url_scan`)는 크롤과 판정을, 이 모듈은 감사 스키마로의 변환만
맡는다. 저장소나 네트워크에 의존하지 않는 순수 함수라 단위 테스트가 쉽다.

승인은 사람 배치 승인(font-audit-review approve) 경로를 쓴다. 무인 승인은 대상
필드가 하드코딩돼 있어 이 두 필드를 처리하지 못한다(audit_store.py:897).
"""

from __future__ import annotations

import hashlib
import json
from urllib.parse import urlparse
from uuid import UUID

from fontagit_pipeline.audit_store import FindingDraft, SnapshotDraft
from fontagit_pipeline.noonnu_url_scan import FetchedPage, ScanRecord

NOONNU_ACCOUNT_URL = "https://www.instagram.com/noonnu_official/"
"""눈누 자체 SNS 주소. 이 값이 들어 있으면 오염이다."""

AUTO_APPLICABLE_ACTIONS = frozenset({"auto_fix_safe"})
"""자동 승인 대상 판정. 나머지는 전부 사람 검수로 남긴다."""

_PROVIDER = "noonnu"
_EXTRACTION_RULE_ID = "noonnu-url-scan-content-anchor-v2"
_PARSER_VERSION = "noonnu-url-scan-v2"
_CONFIDENCE = "reference"


def provider_record_id_from_source_url(source_url: str) -> str:
    """눈누 상세 URL에서 폰트 페이지 번호를 뽑는다.

    예: https://noonnu.cc/font_page/589 -> "589"

    Raises:
        ValueError: 경로 마지막 조각이 비어 있어 식별자를 만들 수 없는 경우.
    """
    record_id = urlparse(source_url).path.rstrip("/").rsplit("/", 1)[-1]
    if not record_id:
        raise ValueError(f"source_url에서 provider_record_id를 얻지 못했습니다: {source_url}")
    return record_id


def build_snapshot_draft(record: ScanRecord, page: FetchedPage) -> SnapshotDraft:
    """판정 1건과 그 근거가 된 응답으로 감사 근거를 만든다."""
    extracted: dict[str, object] = {
        "official_url": record.new_official_url,
        "foundry": record.new_foundry,
        "classification": record.classification,
        "recommended_action": record.recommended_action,
        "anchor_evidence": record.evidence,
    }
    normalized_sha256 = hashlib.sha256(
        json.dumps(
            extracted,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return SnapshotDraft(
        font_id=UUID(record.font_id),
        provider=_PROVIDER,
        provider_record_id=provider_record_id_from_source_url(record.source_url),
        source_kind="noonnu",
        document_kind="font_detail",
        request_url=record.source_url,
        final_url=page.final_url,
        http_status=page.http_status,
        raw_text=None,
        raw_sha256=hashlib.sha256(page.html.encode("utf-8")).hexdigest(),
        normalized_sha256=normalized_sha256,
        extracted=extracted,
        evidence_locations={
            "official_url": record.evidence,
            "license_source_url": "noonnu detail license table",
        },
        extraction_rule_id=_EXTRACTION_RULE_ID,
        parser_version=_PARSER_VERSION,
    )


def build_finding_drafts(record: ScanRecord, evidence_id: UUID) -> list[FindingDraft]:
    """오염된 필드마다 정정 후보를 만든다.

    `auto_applicable`은 07-29 판정이 아니라 이 레코드(재크롤 시점 판정)를
    기준으로 정한다. `official_url`은 대체값이 있을 때만 자동 적용 대상이
    되며, 값이 없으면(`nullify`) 사람 검수로 남긴다. `license_source_url`은
    눈누 상세 페이지라는 확정된 대체값이 있어 판정과 무관하게 채울 수 있다.
    """
    font_id = UUID(record.font_id)
    auto = record.recommended_action in AUTO_APPLICABLE_ACTIONS
    drafts: list[FindingDraft] = []

    if record.official_url_contamination != "none":
        drafts.append(
            FindingDraft(
                font_id=font_id,
                field_name="official_url",
                before_value=record.db_official_url,
                proposed_value=record.new_official_url,
                evidence_id=evidence_id,
                confidence=_CONFIDENCE,
                auto_applicable=auto and record.new_official_url is not None,
                review_reason=(
                    f"눈누 오염({record.official_url_contamination}) 정정: "
                    f"{record.evidence}"
                ),
            )
        )

    if record.license_source_url_contamination != "none":
        drafts.append(
            FindingDraft(
                font_id=font_id,
                field_name="license_source_url",
                before_value=record.db_license_source_url,
                proposed_value=record.source_url,
                evidence_id=evidence_id,
                confidence=_CONFIDENCE,
                auto_applicable=auto or record.recommended_action == "nullify",
                review_reason=(
                    f"눈누 오염({record.license_source_url_contamination}) 정정: "
                    "라이선스 표를 실제로 확인한 눈누 상세 페이지로 교체"
                ),
            )
        )

    return drafts
