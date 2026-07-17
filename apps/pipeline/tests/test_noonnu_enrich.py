"""눈누 상세페이지 라이선스-스타일 추출 테스트"""
import json
from pathlib import Path

import pytest

from fontagit_pipeline import noonnu_enrich as ne


def _html(name: str) -> str:
    """테스트 픽스처 로드"""
    path = Path(__file__).parent / "fixtures" / f"{name}.html"
    return path.read_text(encoding="utf-8")


class TestExtractMeta:
    """Task 2: JSON-LD 메타 추출"""

    def test_extract_meta_gets_name_price_creator(self):
        html = _html("noonnu_conditional")
        name, price, creator = ne.extract_meta(html)
        assert name is not None
        assert price == 0
        assert creator is not None

    def test_extract_meta_returns_none_when_no_schema(self):
        name, price, creator = ne.extract_meta("<html><body>no schema</body></html>")
        assert name is None
        assert price is None
        assert creator is None


class TestParsePermissions:
    """Task 3: 라이선스 허용표 파싱(6 카테고리)"""

    def test_parse_permissions_conditional_embedding(self):
        """고도체(font_page/1): 임베딩=conditional, 나머지=allowed"""
        html = _html("noonnu_conditional")
        perms = ne.parse_permissions(html)
        assert perms["embedding"] == "conditional"
        assert perms["print"] == "allowed"
        assert perms["website"] == "allowed"
        assert perms["packaging"] == "allowed"
        assert perms["video"] == "allowed"
        assert perms["branding"] == "allowed"

    def test_parse_permissions_all_allowed(self):
        """font_page/920: 상업 4 카테고리 전부 allowed"""
        html = _html("noonnu_auto")
        perms = ne.parse_permissions(html)
        assert perms["print"] == "allowed"
        assert perms["website"] == "allowed"
        assert perms["packaging"] == "allowed"
        assert perms["video"] == "allowed"
        assert perms["embedding"] == "allowed"
        assert perms["branding"] == "allowed"

    def test_parse_permissions_missing_table_raises(self):
        """테이블 없음: EnrichParseError"""
        with pytest.raises(ne.EnrichParseError):
            ne.parse_permissions("<html><body>no table</body></html>")

    def test_parse_permissions_exact_six_categories(self):
        """정확히 6개 카테고리 반환"""
        html = _html("noonnu_conditional")
        perms = ne.parse_permissions(html)
        assert set(perms.keys()) == set(ne.PERMISSION_CATEGORIES)

    def test_parse_permissions_unknown_status_raises(self):
        """게이트 카테고리의 미지 상태값: EnrichParseError (M4 검증)"""
        html = """<table><tr><td></td><td></td><td></td></tr>
                  <tr><td>인쇄</td><td></td><td>미알려진상태</td></tr>
                  <tr><td>웹사이트</td><td></td><td>사용 가능</td></tr>
                  <tr><td>포장지</td><td></td><td>사용 가능</td></tr>
                  <tr><td>영상</td><td></td><td>사용 가능</td></tr>
                  <tr><td>임베딩</td><td></td><td>사용 가능</td></tr>
                  <tr><td>BI/CI</td><td></td><td>사용 가능</td></tr></table>"""
        with pytest.raises(ne.EnrichParseError, match="게이트 카테고리"):
            ne.parse_permissions(html)

    def test_parse_permissions_duplicate_category_raises(self):
        """중복 카테고리: EnrichParseError (M4 검증)"""
        html = """<table><tr><td></td><td></td><td></td></tr>
                  <tr><td>인쇄</td><td></td><td>사용 가능</td></tr>
                  <tr><td>인쇄</td><td></td><td>사용 불가</td></tr></table>"""
        with pytest.raises(ne.EnrichParseError, match="중복 카테고리"):
            ne.parse_permissions(html)

    def test_parse_permissions_embedding_empty_allowed(self):
        """임베딩 빈값 + 상업4 allowed → embedding=None으로 저장, 파싱 성공"""
        html = """<table><tr><td></td><td></td><td></td></tr>
                  <tr><td>인쇄</td><td></td><td>사용 가능</td></tr>
                  <tr><td>웹사이트</td><td></td><td>사용 가능</td></tr>
                  <tr><td>포장지</td><td></td><td>사용 가능</td></tr>
                  <tr><td>영상</td><td></td><td>사용 가능</td></tr>
                  <tr><td>임베딩</td><td></td><td></td></tr>
                  <tr><td>BI/CI</td><td></td><td>사용 가능</td></tr></table>"""
        perms = ne.parse_permissions(html)
        assert perms["print"] == "allowed"
        assert perms["website"] == "allowed"
        assert perms["packaging"] == "allowed"
        assert perms["video"] == "allowed"
        assert perms["embedding"] is None  # 빈값 → None
        assert perms["branding"] == "allowed"

    def test_parse_permissions_branding_empty_allowed(self):
        """branding 빈값 + 상업4 allowed → branding=None으로 저장, 파싱 성공"""
        html = """<table><tr><td></td><td></td><td></td></tr>
                  <tr><td>인쇄</td><td></td><td>사용 가능</td></tr>
                  <tr><td>웹사이트</td><td></td><td>사용 가능</td></tr>
                  <tr><td>포장지</td><td></td><td>사용 가능</td></tr>
                  <tr><td>영상</td><td></td><td>사용 가능</td></tr>
                  <tr><td>임베딩</td><td></td><td>사용 가능</td></tr>
                  <tr><td>BI/CI</td><td></td><td></td></tr></table>"""
        perms = ne.parse_permissions(html)
        assert perms["print"] == "allowed"
        assert perms["website"] == "allowed"
        assert perms["packaging"] == "allowed"
        assert perms["video"] == "allowed"
        assert perms["embedding"] == "allowed"
        assert perms["branding"] is None  # 빈값 → None

    def test_parse_permissions_commercial_category_empty_raises(self):
        """게이트 카테고리(website) 빈값 → EnrichParseError"""
        html = """<table><tr><td></td><td></td><td></td></tr>
                  <tr><td>인쇄</td><td></td><td>사용 가능</td></tr>
                  <tr><td>웹사이트</td><td></td><td></td></tr>
                  <tr><td>포장지</td><td></td><td>사용 가능</td></tr>
                  <tr><td>영상</td><td></td><td>사용 가능</td></tr>
                  <tr><td>임베딩</td><td></td><td>사용 가능</td></tr>
                  <tr><td>BI/CI</td><td></td><td>사용 가능</td></tr></table>"""
        with pytest.raises(ne.EnrichParseError, match="게이트 카테고리"):
            ne.parse_permissions(html)

    def test_parse_permissions_commercial_category_unknown_status_raises(self):
        """게이트 카테고리(print) 미지 상태 → EnrichParseError"""
        html = """<table><tr><td></td><td></td><td></td></tr>
                  <tr><td>인쇄</td><td></td><td>미지상태</td></tr>
                  <tr><td>웹사이트</td><td></td><td>사용 가능</td></tr>
                  <tr><td>포장지</td><td></td><td>사용 가능</td></tr>
                  <tr><td>영상</td><td></td><td>사용 가능</td></tr>
                  <tr><td>임베딩</td><td></td><td>사용 가능</td></tr>
                  <tr><td>BI/CI</td><td></td><td>사용 가능</td></tr></table>"""
        with pytest.raises(ne.EnrichParseError, match="게이트 카테고리"):
            ne.parse_permissions(html)


class TestExtractStyles:
    """Task 4: @font-face 스타일 추출"""

    def test_extract_styles_reads_font_face_weights(self):
        """@font-face에서 font-weight 추출"""
        html = _html("noonnu_conditional")
        weights, italic = ne.extract_styles(html)
        assert isinstance(weights, list)
        assert all(isinstance(w, int) for w in weights)

    def test_extract_styles_detects_italic(self):
        """italic 여부 감지"""
        html = _html("noonnu_conditional")
        weights, italic = ne.extract_styles(html)
        assert isinstance(italic, bool)

    def test_extract_styles_no_font_face_returns_empty(self):
        """@font-face 없음: ([], False) 반환"""
        weights, italic = ne.extract_styles("<html><head></head></html>")
        assert weights == []
        assert italic is False


class TestGuessLicenseType:
    """Task 5a: 라이선스 타입 추정"""

    def test_guess_license_type_always_custom_free(self):
        """M2 수정: 눈누 HTML에서 라이선스를 신뢰성 있게 판별할 수 없으므로 항상 'custom-free' 반환"""
        # OFL 키워드가 있어도
        html1 = "<p>본 폰트는 SIL OFL 1.1 라이선스</p>"
        license_type1 = ne.guess_license_type(html1)
        assert license_type1 == "custom-free"

        # 키워드가 없어도
        html2 = "<html><body></body></html>"
        license_type2 = ne.guess_license_type(html2)
        assert license_type2 == "custom-free"


class TestMapLicenseRows:
    """Task 5b: 라이선스 4행 매핑"""

    def test_map_rows_commercial_free_when_four_allowed(self):
        """상업 4 카테고리 전부 allowed: is_commercial_free=True"""
        perms = {
            "print": "allowed",
            "website": "allowed",
            "packaging": "allowed",
            "video": "allowed",
            "embedding": "conditional",
            "branding": "allowed",
        }
        rows = ne.map_license_rows(perms, "custom-free")
        assert rows["is_commercial_free"] is True
        assert rows["allow_embedding"] == "conditional"
        assert "임베딩" in rows["license_note"]

    def test_map_rows_ofl_redistribute_modify_always_none(self):
        """재배포/수정은 눈누 허용표에 없는 정보이므로 항상 None (license_type 무관)"""
        perms = {k: "allowed" for k in ne.PERMISSION_CATEGORIES}
        rows = ne.map_license_rows(perms, "OFL")
        # M2 수정: redistribute/modify는 항상 None
        assert rows["allow_redistribute"] is None
        assert rows["allow_modify"] is None

    def test_map_rows_not_commercial_when_one_denied(self):
        """print=denied: is_commercial_free=False"""
        perms = {
            "print": "denied",
            "website": "allowed",
            "packaging": "allowed",
            "video": "allowed",
            "embedding": "allowed",
            "branding": "allowed",
        }
        rows = ne.map_license_rows(perms, "custom-free")
        assert rows["is_commercial_free"] is False


class TestClassify:
    """Task 6: 분류 게이트"""

    def test_classify_auto_safe_all_allowed(self):
        """상업 4카테고리 모두 allowed + price 0 + official_url: auto_safe"""
        perms = {k: "allowed" for k in ne.PERMISSION_CATEGORIES}
        result = ne.classify(parse_ok=True, price=0, perms=perms, official_url="https://example.com")
        assert result == "auto_safe"

    def test_classify_embedding_conditional_still_auto_safe(self):
        """임베딩 conditional이어도 상업 4 allowed + price 0 + official_url: auto_safe"""
        perms = {
            "print": "allowed",
            "website": "allowed",
            "packaging": "allowed",
            "video": "allowed",
            "embedding": "conditional",
            "branding": "allowed",
        }
        result = ne.classify(parse_ok=True, price=0, perms=perms, official_url="https://example.com")
        assert result == "auto_safe"

    def test_classify_commercial_category_conditional_needs_review(self):
        """상업 카테고리 조건부: needs_review"""
        perms = {
            "print": "allowed",
            "website": "conditional",
            "packaging": "allowed",
            "video": "allowed",
            "embedding": "allowed",
            "branding": "allowed",
        }
        result = ne.classify(parse_ok=True, price=0, perms=perms, official_url="https://example.com")
        assert result == "needs_review"

    def test_classify_price_nonzero_needs_review(self):
        """price != 0: needs_review"""
        perms = {k: "allowed" for k in ne.PERMISSION_CATEGORIES}
        result = ne.classify(parse_ok=True, price=100, perms=perms, official_url="https://example.com")
        assert result == "needs_review"

    def test_classify_parse_fail_needs_review(self):
        """파싱 실패: needs_review"""
        result = ne.classify(parse_ok=False, price=None, perms=None, official_url="https://example.com")
        assert result == "needs_review"

    def test_classify_no_official_url_needs_review(self):
        """official_url 없음: needs_review"""
        perms = {k: "allowed" for k in ne.PERMISSION_CATEGORIES}
        result = ne.classify(parse_ok=True, price=0, perms=perms, official_url=None)
        assert result == "needs_review"


class TestBuildProposal:
    """Task 7: 제안 조립"""

    def test_build_proposal_auto_safe_from_auto_fixture(self):
        """font_page/920(상업4 allowed): auto_safe"""
        html = _html("noonnu_auto")
        p = ne.build_proposal(
            "fid-1",
            "goldo",
            "https://noonnu.cc/font_page/920",
            "https://maker.site",
            html,
        )
        assert p["font_id"] == "fid-1"
        assert p["slug"] == "goldo"
        assert p["parse_status"] == "parsed"
        assert p["classification"] == "auto_safe"
        assert p["proposed_commercial_free"] is True
        assert p["proposed_weights"] is not None
        assert p["proposed_italic"] is not None
        assert p["proposed_license_type"] is not None
        assert p["review_status"] == "auto_published"
        assert "_font_update" in p
        fu = p["_font_update"]
        assert fu["status"] == "published"
        assert fu["license_verified"] is True
        assert fu["auto_approved"] is True

    def test_build_proposal_conditional_embedding_still_auto_safe(self):
        """font_page/1(임베딩 conditional, 상업4 allowed): auto_safe"""
        html = _html("noonnu_conditional")
        p = ne.build_proposal(
            "fid-cond",
            "hodo",
            "https://noonnu.cc/font_page/1",
            "https://maker",
            html,
        )
        assert p["parse_status"] == "parsed"
        assert p["classification"] == "auto_safe"
        assert p["review_status"] == "auto_published"
        assert p["_font_update"] is not None

    def test_build_proposal_parse_fail_is_needs_review(self):
        """파싱 실패: classification=needs_review, parse_status=failed"""
        p = ne.build_proposal(
            "fid-x",
            "broken",
            "https://noonnu.cc/font_page/0",
            "https://x",
            "<html>no table</html>",
        )
        assert p["parse_status"] == "failed"
        assert p["classification"] == "needs_review"
        assert p["proposed_commercial_free"] is None
        assert p["review_status"] == "proposed"
        assert p["_font_update"] is None

    def test_build_proposal_includes_all_fields(self):
        """모든 필드 포함 확인"""
        html = _html("noonnu_auto")
        p = ne.build_proposal("fid", "slug", "https://noonnu.cc/1", "https://official", html)
        required_keys = {
            "font_id", "slug", "source_url", "raw_permissions",
            "proposed_commercial_free", "proposed_embedding", "proposed_redistribute", "proposed_modify",
            "proposed_license_type", "proposed_weights", "proposed_italic", "proposed_category_ko",
            "parse_status", "classification", "review_status", "_font_update"
        }
        assert required_keys.issubset(set(p.keys()))


class TestDeriveSlug:
    """_derive_slug 함수 테스트."""

    def test_derive_slug_with_name_en(self) -> None:
        """name_en이 있으면 build_slug 적용."""
        from fontagit_pipeline.noonnu_enrich import _derive_slug
        slug = _derive_slug("한글명", "English Font")
        assert slug == "english-font"

    def test_derive_slug_without_name_en(self) -> None:
        """name_en이 None이면 name_ko 소문자-하이픈정규화(한글보존)."""
        from fontagit_pipeline.noonnu_enrich import _derive_slug
        slug = _derive_slug("한글 폰트 명", None)
        # 한글은 보존되고 공백은 하이픈으로 변환
        assert slug == "한글-폰트-명"

    def test_derive_slug_with_empty_name_en_ascii_fallback(self) -> None:
        """name_en이 빈 문자열이지만 name_ko가 ASCII면 사용."""
        from fontagit_pipeline.noonnu_enrich import _derive_slug
        slug = _derive_slug("test font name", "")
        # 빈 name_en이므로 name_ko 사용: "test font name" -> "test-font-name"
        assert slug == "test-font-name"
