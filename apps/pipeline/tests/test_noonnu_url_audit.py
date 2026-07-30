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
    """DB 값과 재추출 값이 같고 오염이 없으면 match이고 변경하지 않는다."""
    verdict = judge_official_url(
        _snapshot(),
        db_official_url="https://clova.ai/handwriting/list.html",
        db_license_source_url="https://clova.ai/handwriting/list.html",
    )
    assert verdict.classification == "match"
    assert verdict.recommended_action == "keep"


def test_both_db_and_reextracted_noonnu_account_is_contamination_not_match() -> None:
    """DB 값과 재추출 값이 둘 다 눈누 계정으로 같아도 match/keep이 아니라 오염 판정이다.

    172종 오염 사고의 핵심 재현: 오염 검사보다 일치 검사가 먼저면 이 케이스를 놓친다.
    """
    noonnu_account_url = "https://www.instagram.com/noonnu_official/"
    verdict = judge_official_url(
        _snapshot(official_url=noonnu_account_url),
        db_official_url=noonnu_account_url,
        db_license_source_url=noonnu_account_url,
    )
    assert verdict.classification != "match"
    assert verdict.recommended_action != "keep"
    assert verdict.official_url_contamination == "noonnu_account"


def test_license_source_url_only_contamination_is_reported_separately() -> None:
    """official_url은 정상인데 license_source_url만 오염되면 그 필드로만 잡힌다."""
    verdict = judge_official_url(
        _snapshot(),
        db_official_url="https://clova.ai/handwriting/list.html",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.official_url_contamination == "unrelated_external"
    assert verdict.license_source_url_contamination == "noonnu_account"
    assert verdict.classification == "match"
    assert verdict.recommended_action == "keep"


def test_no_link_keeps_clean_db_value() -> None:
    """새 링크를 못 찾아도 DB 값이 정상이면 지우지 않는다."""
    verdict = judge_official_url(
        _snapshot(official_url=None, official_url_anchor_text=None),
        db_official_url="https://clova.ai/handwriting/list.html",
        db_license_source_url="https://clova.ai/handwriting/list.html",
    )
    assert verdict.classification == "no_link"
    assert verdict.recommended_action == "keep"


def test_no_link_nullifies_contaminated_db_value() -> None:
    """새 링크를 못 찾았고 DB 값이 오염됐다면 비운다."""
    verdict = judge_official_url(
        _snapshot(official_url=None, official_url_anchor_text=None),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "no_link"
    assert verdict.recommended_action == "nullify"


def test_anchor_and_foundry_match_makes_auto_fix_safe() -> None:
    """앵커 텍스트와 제작사 도메인 매칭이 모두 맞으면 자동 정정 대상이다."""
    verdict = judge_official_url(
        _snapshot(foundry="Clova", official_url="https://clova.ai/handwriting/list.html"),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "auto_fix_safe"


def test_anchor_only_evidence_requires_manual_review() -> None:
    """앵커 근거만 있고 제작사 도메인 매칭도 등록부 매칭도 없으면 자동 정정하지 않는다 (AND 조건).

    official_url은 등록부(_VERIFIED_FOUNDRY_HOSTS)에 없는 도메인으로 골라
    검증된 제작사 호스트 조건과 섞이지 않게 한다.
    """
    verdict = judge_official_url(
        _snapshot(foundry="네이버", official_url="https://example.com/handwriting/list.html"),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "manual_review"


def test_verified_foundry_host_makes_auto_fix_safe_with_korean_foundry_name() -> None:
    """등록부에 있는 호스트면 한글 제작사명이라 도메인 문자열 매칭이 안 돼도 자동 정정한다."""
    verdict = judge_official_url(
        _snapshot(foundry="네이버", official_url="https://clova.ai/handwriting/list.html"),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "auto_fix_safe"


def test_anchor_with_unverified_platform_host_still_requires_manual_review() -> None:
    """notion.site처럼 등록부에 없는 플랫폼 호스팅 도메인은 앵커가 있어도 자동 정정하지 않는다."""
    verdict = judge_official_url(
        _snapshot(
            foundry="Yanadoo Corp",
            official_url="https://yafitmove.notion.site/move-sans",
        ),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "manual_review"


def test_verified_foundry_host_without_anchor_requires_manual_review() -> None:
    """앵커 근거가 없으면 등록부 호스트여도 자동 정정하지 않는다 (앵커는 여전히 필수)."""
    verdict = judge_official_url(
        _snapshot(
            foundry="네이버",
            official_url="https://clova.ai/handwriting/list.html",
            official_url_anchor_text="자세히",
        ),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "manual_review"


def test_verified_foundry_host_matches_subdomain() -> None:
    """등록부 호스트의 서브도메인도 검증된 것으로 인정한다."""
    verdict = judge_official_url(
        _snapshot(foundry="이민서", official_url="https://galmuri.quiple.dev/font"),
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


def test_foundry_name_does_not_match_unrelated_lookalike_domain() -> None:
    """제작사명이 도메인 부분 문자열로만 겹치는 무관한 도메인은 매칭하지 않는다."""
    verdict = judge_official_url(
        _snapshot(
            foundry="naver",
            official_url="https://naver-fake-site.com/download",
            official_url_anchor_text="다운로드 페이지로 이동",
        ),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "manual_review"


def test_new_value_is_third_party_social_requires_manual_review() -> None:
    """재추출 값이 눈누 계정이 아닌 일반 SNS면 비우지 않고 사람이 본다."""
    verdict = judge_official_url(
        _snapshot(official_url="https://www.instagram.com/some_maker/"),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "mismatch"
    assert verdict.recommended_action == "manual_review"


def test_no_container_keeps_current_value() -> None:
    """페이지 파싱 자체가 실패하면 판단 근거가 없어 변경하지 않는다."""
    verdict = judge_official_url(
        None,
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "no_container"
    assert verdict.recommended_action == "keep"
    assert verdict.official_url_contamination == "noonnu_account"
