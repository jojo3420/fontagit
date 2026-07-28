"""눈누 공식 URL 대조 판정 테스트."""

from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot
from fontagit_pipeline.noonnu_url_audit import judge_official_url


def _snapshot(**overrides: object) -> NoonnuFontSnapshot:
    """테스트용 스냅샷을 만든다."""
    payload: dict[str, object] = {
        "source_url": "https://noonnu.cc/font_page/600",
        "foundry": "네이버",
        "official_url": "https://clova.ai/handwriting/list.html",
        "official_url_anchor_text": "다운로드 페이지로 이동",
        "global_social_links": ["https://www.instagram.com/noonnu_official/"],
    }
    payload.update(overrides)
    return NoonnuFontSnapshot(**payload)  # type: ignore[arg-type]


def test_match_when_db_value_equals_reextracted() -> None:
    """DB 값과 재추출 값이 같으면 match이고 변경하지 않는다."""
    verdict = judge_official_url(
        _snapshot(),
        db_official_url="https://clova.ai/handwriting/list.html",
        db_license_source_url="https://clova.ai/handwriting/list.html",
    )
    assert verdict.classification == "match"
    assert verdict.recommended_action == "keep"


def test_noonnu_social_in_db_is_contamination() -> None:
    """DB 값이 눈누 전역 SNS면 오염으로 분류한다."""
    verdict = judge_official_url(
        _snapshot(),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "mismatch"
    assert verdict.contamination_type == "noonnu_social"


def test_anchor_text_download_makes_auto_fix_safe() -> None:
    """앵커 텍스트가 다운로드 계열이면 자동 정정 대상이다."""
    verdict = judge_official_url(
        _snapshot(official_url_anchor_text="다운로드 페이지로 이동"),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "auto_fix_safe"


def test_weak_evidence_requires_manual_review() -> None:
    """제작사명 매칭도 앵커 텍스트 근거도 없으면 사람이 본다."""
    verdict = judge_official_url(
        _snapshot(
            foundry="어떤스튜디오",
            official_url="https://example.com/random",
            official_url_anchor_text="자세히",
        ),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "manual_review"


def test_new_value_is_social_becomes_nullify() -> None:
    """재추출 값도 SNS면 정답으로 쓰지 않고 비운다."""
    verdict = judge_official_url(
        _snapshot(official_url="https://www.instagram.com/some_maker/"),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "nullify"


def test_no_link_when_snapshot_has_no_official_url() -> None:
    """상세에 외부 링크가 없으면 no_link이고 비움 후보다."""
    verdict = judge_official_url(
        _snapshot(official_url=None, official_url_anchor_text=None),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "no_link"
    assert verdict.recommended_action == "nullify"


def test_no_container_keeps_current_value() -> None:
    """페이지 파싱 자체가 실패하면 판단 근거가 없어 변경하지 않는다."""
    verdict = judge_official_url(
        None,
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "no_container"
    assert verdict.recommended_action == "keep"
