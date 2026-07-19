from pathlib import Path

import pytest

from fontagit_pipeline.audit_noonnu import extract_noonnu_font


FIXTURES = Path(__file__).parent / "fixtures" / "audit"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_extracts_only_font_detail_and_uses_structured_only_storage() -> None:
    snapshot = extract_noonnu_font(
        _fixture("noonnu-white-tailed-eagle.html"),
        "https://noonnu.cc/font_page/613",
    )

    assert snapshot.page_id == "613"
    assert snapshot.name_ko == "흰꼬리수리"
    assert snapshot.foundry == "네이버"
    assert snapshot.category == "손글씨"
    assert snapshot.tags == ["삐뚤빼뚤"]
    assert snapshot.price == "0"
    assert snapshot.download_candidates == ["https://clova.ai/handwriting/list.html"]
    assert snapshot.font_file_candidates == [
        "https://cdn.jsdelivr.net/gh/projectnoonnu/naverfont_11@1.0/White_kkorisuri.woff"
    ]
    assert snapshot.weights == [400]
    assert snapshot.styles == ["normal"]
    assert "application/ld+json" in snapshot.evidence_locations["name_ko"]
    assert "article" in snapshot.evidence_locations["license_text"]
    assert "style" in snapshot.evidence_locations["font_file_candidates"]
    assert snapshot.license_text is not None
    assert snapshot.license_permissions == {"인쇄": "허용"}
    assert snapshot.raw_text is None
    assert len(snapshot.raw_sha256) == 64
    assert snapshot.global_social_links == []


def test_preserves_reported_404_candidate_for_later_observation() -> None:
    snapshot = extract_noonnu_font(
        _fixture("noonnu-hoengseong-cow.html"),
        "https://noonnu.cc/font_page/854",
    )

    assert snapshot.foundry == "횡성군"
    assert snapshot.download_candidates == [
        "https://www.hsg.go.kr/intro/00000014/00003147.web"
    ]
    assert snapshot.download_status == "needs_review"


@pytest.mark.parametrize(
    "html",
    [
        "<article><h2>관련 폰트</h2><a href='/other'>보기</a></article>",
        """
        <div class="noon-page-content"><h2>폰트 하나</h2></div>
        <div class="noon-page-content"><h2>폰트 둘</h2></div>
        """,
    ],
)
def test_unmarked_articles_must_identify_one_font_detail(html: str) -> None:
    """관련 폰트 카드나 여러 후보를 첫 article로 오인하지 않는다."""
    with pytest.raises(ValueError, match="font detail region"):
        extract_noonnu_font(html, "https://noonnu.cc/font_page/999")
