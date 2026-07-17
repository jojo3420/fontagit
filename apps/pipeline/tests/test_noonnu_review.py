"""눈누 라이선스 제안 검수 테스트."""
import json
from datetime import datetime, timezone

import pytest

from fontagit_pipeline import noonnu_review as nr


class TestBuildFontUpdateFromProposal:
    """build_font_update_from_proposal 함수 테스트."""

    def test_basic_fields(self) -> None:
        """기본 필드 변환 검증."""
        proposal = {
            "proposed_commercial_free": True,
            "proposed_embedding": "allowed",
            "proposed_redistribute": "allowed",
            "proposed_modify": "allowed",
            "proposed_license_type": "OFL",
            "proposed_weights": [400, 700],
            "proposed_italic": False,
            "raw_permissions": {
                "embedding": "allowed",
                "print": "allowed",
                "website": "allowed",
                "packaging": "allowed",
                "video": "allowed",
                "branding": "allowed",
            },
        }
        official_url = "https://fonts.google.com/specimen/Roboto"

        result = nr.build_font_update_from_proposal(proposal, official_url)

        assert result["is_commercial_free"] is True
        assert result["allow_embedding"] == "allowed"
        assert result["allow_redistribute"] == "allowed"
        assert result["allow_modify"] == "allowed"
        assert result["license_type"] == "OFL"
        assert result["license_verified"] is True
        assert result["auto_approved"] is False
        assert result["status"] == "published"
        assert result["license_source_url"] == official_url
        assert result["weights"] == [400, 700]
        assert result["variants"] == []

    def test_with_italic(self) -> None:
        """이탤릭 포함 검증."""
        proposal = {
            "proposed_commercial_free": True,
            "proposed_embedding": "allowed",
            "proposed_redistribute": None,
            "proposed_modify": None,
            "proposed_license_type": "Apache",
            "proposed_weights": [],
            "proposed_italic": True,
            "raw_permissions": {
                "embedding": "allowed",
                "print": "allowed",
                "website": "allowed",
                "packaging": "allowed",
                "video": "allowed",
                "branding": "allowed",
            },
        }

        result = nr.build_font_update_from_proposal(proposal, "http://example.com")

        assert result["variants"] == ["italic"]

    def test_license_note_recalculation(self) -> None:
        """조건부 라이선스 노트 재계산 검증."""
        proposal = {
            "proposed_commercial_free": False,
            "proposed_embedding": "conditional",
            "proposed_redistribute": None,
            "proposed_modify": None,
            "proposed_license_type": "custom",
            "proposed_weights": [400],
            "proposed_italic": False,
            "raw_permissions": {
                "embedding": "conditional",
                "print": "allowed",
                "website": "conditional",
                "packaging": "allowed",
                "video": "allowed",
                "branding": "allowed",
            },
        }

        result = nr.build_font_update_from_proposal(proposal, "http://example.com")

        # map_license_rows에서 계산된 license_note 포함 확인
        assert result["license_note"] is not None
        assert "임베딩 조건부" in result["license_note"]

    def test_verified_at_format(self) -> None:
        """verified_at이 ISO 형식인지 검증."""
        proposal = {
            "proposed_commercial_free": True,
            "proposed_embedding": "allowed",
            "proposed_redistribute": None,
            "proposed_modify": None,
            "proposed_license_type": "OFL",
            "proposed_weights": [],
            "proposed_italic": False,
            "raw_permissions": {
                "embedding": "allowed",
                "print": "allowed",
                "website": "allowed",
                "packaging": "allowed",
                "video": "allowed",
                "branding": "allowed",
            },
        }

        result = nr.build_font_update_from_proposal(proposal, "http://example.com")

        # ISO 형식 검증 (확인만)
        assert "verified_at" in result
        assert isinstance(result["verified_at"], str)
        # ISO 형식은 'T'를 포함
        assert "T" in result["verified_at"]

    def test_empty_weights_default(self) -> None:
        """empty weights는 [] 유지."""
        proposal = {
            "proposed_commercial_free": True,
            "proposed_embedding": "allowed",
            "proposed_redistribute": None,
            "proposed_modify": None,
            "proposed_license_type": "OFL",
            "proposed_weights": None,
            "proposed_italic": False,
            "raw_permissions": {
                "embedding": "allowed",
                "print": "allowed",
                "website": "allowed",
                "packaging": "allowed",
                "video": "allowed",
                "branding": "allowed",
            },
        }

        result = nr.build_font_update_from_proposal(proposal, "http://example.com")

        assert result["weights"] == []


class TestSampleSize:
    """sample_size 함수 테스트."""

    def test_total_100_pct_5(self) -> None:
        """100개 중 5% → 5개."""
        assert nr.sample_size(100, 5) == 5

    def test_total_3_pct_5(self) -> None:
        """3개 중 5% → ceil(3*5/100)=1개(최소값)."""
        assert nr.sample_size(3, 5) == 1

    def test_total_0_pct_5(self) -> None:
        """0개 중 5% → 0개."""
        assert nr.sample_size(0, 5) == 0

    def test_negative_total(self) -> None:
        """음수 total → 0개."""
        assert nr.sample_size(-10, 5) == 0

    def test_total_20_pct_10(self) -> None:
        """20개 중 10% → 2개."""
        assert nr.sample_size(20, 10) == 2

    def test_total_1_pct_1(self) -> None:
        """1개 중 1% → ceil(1*1/100)=1개(최소값)."""
        assert nr.sample_size(1, 1) == 1

    def test_total_200_pct_25(self) -> None:
        """200개 중 25% → 50개."""
        assert nr.sample_size(200, 25) == 50
