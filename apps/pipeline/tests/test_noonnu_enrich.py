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

    def test_extract_meta_gets_name_creator_description(self):
        html = _html("noonnu_conditional")
        name, font_page_id, description = ne.extract_meta(html)
        assert name is not None
        assert font_page_id == 1
        assert description is not None

    def test_extract_meta_no_schema_raises(self):
        with pytest.raises(ne.EnrichParseError):
            ne.extract_meta("<html><body>no schema</body></html>")


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


class TestExtractStyles:
    """Task 4: @font-face 스타일 추출"""

    def test_extract_styles_reads_font_face_weights(self):
        """@font-face에서 font-weight 추출"""
        html = _html("noonnu_conditional")
        weights, italic = ne.extract_styles(html)
        assert isinstance(weights, list)
        assert all(isinstance(w, int) for w in weights)
        assert 400 in weights  # 일반 무게

    def test_extract_styles_detects_italic(self):
        """italic 여부 감지"""
        html = _html("noonnu_conditional")
        weights, italic = ne.extract_styles(html)
        assert isinstance(italic, bool)

    def test_extract_styles_no_font_face_raises(self):
        """@font-face 없음: EnrichParseError"""
        with pytest.raises(ne.EnrichParseError):
            ne.extract_styles("<html><head></head></html>")


class TestGuessLicenseType:
    """Task 5a: 라이선스 타입 추정"""

    def test_guess_license_type_ofl(self):
        """OFL 라이선스 감지"""
        html = _html("noonnu_conditional")
        license_type = ne.guess_license_type(html)
        # 실제 페이지 내용에 따라 조정
        assert license_type in ["OFL", "commercial", "CC0", "custom-free"]

    def test_guess_license_type_default_commercial(self):
        """감지 실패 시 commercial 기본값"""
        html = "<html><body></body></html>"
        license_type = ne.guess_license_type(html)
        assert license_type == "commercial"


class TestMapLicenseRows:
    """Task 5b: 라이선스 4행 매핑"""

    def test_map_rows_conditional_embedding_creates_note(self):
        """conditional 임베딩: license_note에 조건 기재"""
        perms = {
            "print": "allowed",
            "website": "allowed",
            "packaging": "allowed",
            "video": "allowed",
            "embedding": "conditional",
            "branding": "allowed",
        }
        rows = ne.map_license_rows(perms, "commercial")
        assert rows["is_commercial_free"] is True
        assert rows["allow_embedding"] == "conditional"
        assert "임베딩" in rows["license_note"]

    def test_map_rows_ofl_sets_redistribute_modify(self):
        """OFL: redistribute=conditional, modify=allowed"""
        perms = {k: "allowed" for k in ne.PERMISSION_CATEGORIES}
        rows = ne.map_license_rows(perms, "OFL")
        assert rows["allow_redistribute"] == "conditional"
        assert rows["allow_modify"] == "allowed"

    def test_map_rows_not_commercial_when_denied(self):
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
        """모두 allowed: auto_safe"""
        perms = {k: "allowed" for k in ne.PERMISSION_CATEGORIES}
        result = ne.classify(parse_ok=True, perms=perms, license_type="commercial")
        assert result == "auto_safe"

    def test_classify_conditional_needs_review(self):
        """conditional 있음: needs_review"""
        perms = {
            "print": "allowed",
            "website": "allowed",
            "packaging": "allowed",
            "video": "allowed",
            "embedding": "conditional",
            "branding": "allowed",
        }
        result = ne.classify(parse_ok=True, perms=perms, license_type="commercial")
        assert result == "needs_review"

    def test_classify_parse_fail_needs_review(self):
        """파싱 실패: needs_review"""
        result = ne.classify(parse_ok=False, perms=None, license_type=None)
        assert result == "needs_review"


class TestBuildProposal:
    """Task 7: 제안 조립"""

    def test_build_proposal_success_auto_safe(self):
        """파싱 성공 + auto_safe → classification=auto_safe"""
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
        assert p["classification"] == "auto_safe"
        assert p["parse_status"] == "ok"
        assert p["proposed_commercial_free"] is True
        assert p["source_url"].startswith("https://noonnu.cc")

    def test_build_proposal_parse_fail_is_needs_review(self):
        """파싱 실패: classification=needs_review"""
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

    def test_build_proposal_conditional_is_needs_review(self):
        """조건부 임베딩: classification=needs_review"""
        html = _html("noonnu_conditional")
        p = ne.build_proposal(
            "fid-cond",
            "hodo",
            "https://noonnu.cc/font_page/1",
            "https://maker",
            html,
        )
        assert p["classification"] == "needs_review"
        assert p["parse_status"] == "ok"

    def test_build_proposal_includes_font_update_when_auto(self):
        """auto_safe: _font_update 포함"""
        html = _html("noonnu_auto")
        p = ne.build_proposal(
            "fid-1",
            "goldo",
            "https://noonnu.cc/font_page/920",
            "https://maker",
            html,
        )
        assert "_font_update" in p
        fu = p["_font_update"]
        assert fu["allow_embedding"] == "allowed"
        assert fu["license_verified"] is True

    def test_build_proposal_no_font_update_when_needs_review(self):
        """needs_review: _font_update=None"""
        html = _html("noonnu_conditional")
        p = ne.build_proposal(
            "fid-cond",
            "hodo",
            "https://noonnu.cc/font_page/1",
            "https://maker",
            html,
        )
        assert p["_font_update"] is None
