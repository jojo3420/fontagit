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
    assert snapshot.global_social_links == ["https://www.instagram.com/noonnu"]


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


def test_official_url_excludes_noonnu_global_social_links() -> None:
    """상세 영역 밖의 눈누 공식 SNS는 official_url이 되지 않는다."""
    html = """
    <html><body>
      <header><a href="https://www.instagram.com/noonnu_official/">눈누 인스타그램</a></header>
      <div data-font-detail>
        <h1>효남 늘 화이팅</h1>
        <a href="https://clova.ai/handwriting/list.html">다운로드 페이지로 이동</a>
      </div>
    </body></html>
    """
    snapshot = extract_noonnu_font(html, "https://noonnu.cc/font_page/600")

    assert snapshot.official_url == "https://clova.ai/handwriting/list.html"
    assert snapshot.official_url_anchor_text == "다운로드 페이지로 이동"
    assert "https://www.instagram.com/noonnu_official/" in snapshot.global_social_links
    assert "official_url" in snapshot.evidence_locations


def test_official_url_is_none_when_detail_has_no_external_link() -> None:
    """상세 영역에 외부 링크가 없으면 official_url은 None이다."""
    html = """
    <html><body>
      <header><a href="https://www.instagram.com/noonnu_official/">눈누 인스타그램</a></header>
      <div data-font-detail><h1>어떤 폰트</h1><a href="/font_page/601">다른 폰트</a></div>
    </body></html>
    """
    snapshot = extract_noonnu_font(html, "https://noonnu.cc/font_page/600")

    assert snapshot.official_url is None
    assert snapshot.official_url_anchor_text is None
