"""눈누 URL 스캔 결과를 감사 저장소 draft로 옮기는 변환 테스트."""

from uuid import UUID

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
