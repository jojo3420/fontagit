from pathlib import Path

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
