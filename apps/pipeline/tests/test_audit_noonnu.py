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
    assert snapshot.download_candidates == ["https://clova.ai/handwriting/list.html"]
    assert snapshot.font_file_candidates == [
        "https://cdn.noonnu.cc/font/white-tailed-eagle.woff2"
    ]
    assert snapshot.license_text is not None
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


def test_fallback_evidence_locations_and_font_files_record_actual_detail_sources() -> None:
    """data 속성이 없으면 실제 fallback selector와 폰트 파일만 보관한다."""
    snapshot = extract_noonnu_font(
        """
        <article>
          <h1>테스트 폰트</h1>
          <dl><dt>제작</dt><dd>테스트 제작사</dd></dl>
          <a data-download-cta href="/download">다운로드</a>
          <section data-license-body>원문</section>
          <style>
            @font-face { src: url('/font.woff2?version=1'); font-weight: 400; }
            @font-face { src: url('https://cdn.example.org/font.ttf#subset'); }
            @font-face { src: url('https://cdn.example.org/not-a-font.css'); }
            @font-face { src: url('data:font/woff2;base64,abc'); }
          </style>
        </article>
        """,
        "https://noonnu.cc/font_page/999",
    )

    assert snapshot.evidence_locations["name_ko"] == "h1"
    assert snapshot.evidence_locations["foundry"] == "dt + dd"
    assert snapshot.font_file_candidates == [
        "https://noonnu.cc/font.woff2?version=1",
        "https://cdn.example.org/font.ttf#subset",
    ]


@pytest.mark.parametrize(
    "html",
    [
        "<article><h2>관련 폰트</h2><a href='/other'>보기</a></article>",
        """
        <article><h1>폰트 하나</h1><a data-download-cta href='/a'>다운로드</a><section data-license-body>원문</section></article>
        <article><h1>폰트 둘</h1><a data-download-cta href='/b'>다운로드</a><section data-license-body>원문</section></article>
        """,
    ],
)
def test_unmarked_articles_must_identify_one_font_detail(html: str) -> None:
    """관련 폰트 카드나 여러 후보를 첫 article로 오인하지 않는다."""
    with pytest.raises(ValueError, match="font detail article"):
        extract_noonnu_font(html, "https://noonnu.cc/font_page/999")
