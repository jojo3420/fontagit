"""눈누 URL 스캔 결과를 감사 저장소 draft로 옮기는 변환 테스트."""

from uuid import UUID

import pytest

from fontagit_pipeline.noonnu_url_ingest import (
    build_finding_drafts,
    build_snapshot_draft,
    provider_record_id_from_source_url,
)
from fontagit_pipeline.noonnu_url_scan import FetchedPage, ScanRecord

_EVIDENCE_ID = UUID("11111111-1111-1111-1111-111111111111")
_FONT_ID = "22222222-2222-2222-2222-222222222222"
_NOONNU_ACCOUNT = "https://www.instagram.com/noonnu_official/"


def _record(**overrides: object) -> ScanRecord:
    """auto_fix_safe 판정 1건을 기본값으로 만든다."""
    base = {
        "font_id": _FONT_ID,
        "slug": "sample-font",
        "source_url": "https://noonnu.cc/font_page/589",
        "db_official_url": _NOONNU_ACCOUNT,
        "db_license_source_url": _NOONNU_ACCOUNT,
        "db_license_verified": True,
        "new_official_url": "https://clova.ai/handwriting",
        "new_foundry": "네이버",
        "classification": "mismatch",
        "official_url_contamination": "noonnu_account",
        "license_source_url_contamination": "noonnu_account",
        "recommended_action": "auto_fix_safe",
        "evidence": "앵커 텍스트 '다운로드 페이지로 이동' + 검증된 제작사 호스트",
        "error": None,
        "retryable_error": False,
    }
    base.update(overrides)
    return ScanRecord(**base)  # type: ignore[arg-type]


def _page() -> FetchedPage:
    return FetchedPage(
        html="<html><body>본문</body></html>",
        final_url="https://noonnu.cc/font_page/589",
        http_status=200,
    )


def test_provider_record_id_extracted_from_source_url() -> None:
    assert provider_record_id_from_source_url("https://noonnu.cc/font_page/589") == "589"


def test_provider_record_id_rejects_non_numeric_path() -> None:
    """폰트 페이지 번호가 아닌 경로는 식별자로 쓰지 않는다."""
    with pytest.raises(ValueError):
        provider_record_id_from_source_url("https://noonnu.cc/index")


def test_snapshot_rejects_redirect_to_other_font_page() -> None:
    """리다이렉트로 다른 폰트 페이지에 닿으면 근거로 쓰지 않는다.

    근거는 도착 페이지에서 뽑히는데 provider_record_id는 요청 URL에서
    뽑히므로, 그대로 두면 A 폰트에 B 폰트 제작사 주소가 실린다.
    """
    other_page = FetchedPage(
        html="<html><body>다른 폰트</body></html>",
        final_url="https://noonnu.cc/font_page/590",
        http_status=200,
    )

    with pytest.raises(ValueError, match="다른 폰트 페이지"):
        build_snapshot_draft(_record(), other_page)


def test_snapshot_hash_is_deterministic() -> None:
    """같은 입력은 항상 같은 해시를 낳는다."""
    first = build_snapshot_draft(_record(), _page())
    second = build_snapshot_draft(_record(), _page())

    assert first.normalized_sha256 == second.normalized_sha256
    assert first.raw_sha256 == second.raw_sha256


def test_snapshot_carries_response_metadata() -> None:
    snapshot = build_snapshot_draft(_record(), _page())

    assert snapshot.provider == "noonnu"
    assert snapshot.provider_record_id == "589"
    assert snapshot.request_url == "https://noonnu.cc/font_page/589"
    assert snapshot.final_url == "https://noonnu.cc/font_page/589"
    assert snapshot.http_status == 200
    assert snapshot.extracted["official_url"] == "https://clova.ai/handwriting"


def test_snapshot_matches_db_and_rpc_contract() -> None:
    """document_kind는 0017 체크 제약(download/license/metadata) 안이어야 하고,

    evidence_role은 0027이 눈누 근거 URL 정정을 허용할 때 보는 마커여야 한다.
    dev 실측에서 'font_detail'이 제약 위반으로 첫 폰트부터 적재를 막았다.
    """
    snapshot = build_snapshot_draft(_record(), _page())

    assert snapshot.document_kind in {"download", "license", "metadata"}
    assert snapshot.document_kind == "metadata"
    assert snapshot.source_kind == "noonnu"
    assert snapshot.extracted["evidence_role"] == "noonnu-official-url-anchor"


def test_auto_fix_safe_produces_two_applicable_findings() -> None:
    """official_url과 license_source_url 두 건이 자동 적용 대상으로 나온다."""
    findings = build_finding_drafts(_record(), _EVIDENCE_ID)

    by_field = {f.field_name: f for f in findings}
    assert set(by_field) == {"official_url", "license_source_url"}
    assert by_field["official_url"].proposed_value == "https://clova.ai/handwriting"
    assert by_field["license_source_url"].proposed_value == "https://noonnu.cc/font_page/589"
    assert all(f.auto_applicable for f in findings)
    assert all(f.evidence_id == _EVIDENCE_ID for f in findings)
    assert all(f.before_value == _NOONNU_ACCOUNT for f in findings)


def test_manual_review_is_not_auto_applicable() -> None:
    findings = build_finding_drafts(
        _record(recommended_action="manual_review"), _EVIDENCE_ID
    )

    assert findings
    assert not any(f.auto_applicable for f in findings)


def test_nullify_splits_by_field() -> None:
    """official_url은 대체값이 없어 사람 검수로, license_source_url은 자동 정정."""
    findings = build_finding_drafts(
        _record(
            recommended_action="nullify",
            classification="no_link",
            new_official_url=None,
        ),
        _EVIDENCE_ID,
    )

    by_field = {f.field_name: f for f in findings}
    assert by_field["license_source_url"].auto_applicable is True
    assert by_field["license_source_url"].proposed_value == "https://noonnu.cc/font_page/589"
    assert by_field["official_url"].auto_applicable is False
    assert by_field["official_url"].proposed_value is None


def test_uncontaminated_field_is_skipped() -> None:
    """오염되지 않은 필드는 finding을 만들지 않는다."""
    findings = build_finding_drafts(
        _record(
            db_license_source_url="https://noonnu.cc/font_page/589",
            license_source_url_contamination="none",
        ),
        _EVIDENCE_ID,
    )

    assert {f.field_name for f in findings} == {"official_url"}
