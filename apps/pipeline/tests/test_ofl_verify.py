"""OFL 표준 라이선스 공식 확인의 핵심 회귀 테스트."""

import json
from pathlib import Path
from unittest.mock import MagicMock


from fontagit_pipeline.licenses import LicenseFetchError
from fontagit_pipeline.ofl_verify import (
    apply_update,
    build_report,
    fetch_ofl_candidates,
    plan_font_update,
)


class TestPlanFontUpdate:
    """순수 함수 plan_font_update의 로직 검증."""

    def test_resolves_ofl_font_with_all_fields(self) -> None:
        """google/fonts에서 OFL 확인된 폰트를 표준 권한으로 제안한다."""
        license_map = {"notosanskr": "OFL"}
        font = {"name_en": "Noto Sans KR"}
        checked_at = "2026-07-20T12:34:56Z"

        result = plan_font_update(font, license_map, checked_at)

        assert result is not None
        assert result["license_status"] == "verified"
        assert result["allow_commercial"] == "allowed"
        assert result["allow_modify"] == "allowed"
        assert result["allow_redistribute"] == "allowed"
        assert result["allow_embedding"] == "allowed"
        assert result["allow_font_sale"] == "denied"
        assert result["attribution_requirement"] == "required"
        assert result["license_source_kind"] == "official"
        assert result["license_source_url"] == "https://github.com/google/fonts/tree/main/ofl/notosanskr"
        assert result["license_checked_at"] == checked_at
        assert result["auto_approved"] is True

    def test_returns_none_for_unconfirmed_font(self) -> None:
        """license_map에 없는 폰트는 None을 반환한다."""
        license_map = {"notosanskr": "OFL"}
        font = {"name_en": "Unknown Font"}

        result = plan_font_update(font, license_map, "2026-07-20T12:34:56Z")

        assert result is None

    def test_returns_none_for_non_ofl_font(self) -> None:
        """라이선스가 OFL이 아니면 None을 반환한다."""
        license_map = {"robotoflex": "Apache-2.0"}
        font = {"name_en": "Roboto Flex"}

        result = plan_font_update(font, license_map, "2026-07-20T12:34:56Z")

        assert result is None

    def test_returns_none_for_empty_name_en(self) -> None:
        """name_en이 빈 문자열이면 None을 반환한다."""
        license_map = {"": "OFL"}
        font = {"name_en": ""}

        result = plan_font_update(font, license_map, "2026-07-20T12:34:56Z")

        assert result is None

    def test_returns_none_for_none_name_en(self) -> None:
        """name_en이 None이면 None을 반환한다."""
        license_map = {"test": "OFL"}
        font = {"name_en": None}

        result = plan_font_update(font, license_map, "2026-07-20T12:34:56Z")

        assert result is None

    def test_handles_font_with_spaces_and_special_chars(self) -> None:
        """폰트명의 공백과 특수문자를 정규화한 후 매핑 조회한다."""
        license_map = {"notosansserif": "OFL"}
        font = {"name_en": "Noto Sans - Serif"}

        result = plan_font_update(font, license_map, "2026-07-20T12:34:56Z")

        assert result is not None
        assert result["license_status"] == "verified"


class TestBuildReport:
    """build_report의 분류와 집계 정확성 검증."""

    def test_classifies_confirmed_and_unconfirmed_fonts(self) -> None:
        """OFL 확인된 폰트와 미확인 폰트를 분류한다."""
        license_map = {"notosanskr": "OFL"}
        candidates = [
            {"id": "1", "name_en": "Noto Sans KR"},
            {"id": "2", "name_en": "Unknown"},
        ]
        checked_at = "2026-07-20T12:34:56Z"

        report = build_report(candidates, license_map, checked_at)

        assert len(report["confirmed"]) == 1
        assert report["confirmed"][0]["id"] == "1"
        assert len(report["unconfirmed"]) == 1
        assert report["unconfirmed"][0]["id"] == "2"

    def test_counts_accuracy(self) -> None:
        """counts 필드의 confirmed/unconfirmed 건수를 정확히 집계한다."""
        license_map = {"font1": "OFL", "font2": "OFL"}
        candidates = [
            {"id": "1", "name_en": "Font 1"},
            {"id": "2", "name_en": "Font 2"},
            {"id": "3", "name_en": "Unknown"},
        ]
        checked_at = "2026-07-20T12:34:56Z"

        report = build_report(candidates, license_map, checked_at)

        assert report["counts"]["confirmed"] == 2
        assert report["counts"]["unconfirmed"] == 1
        assert report["counts"]["total"] == 3

    def test_handles_empty_candidates(self) -> None:
        """빈 후보 목록을 처리한다."""
        license_map = {"font1": "OFL"}
        candidates = []
        checked_at = "2026-07-20T12:34:56Z"

        report = build_report(candidates, license_map, checked_at)

        assert report["counts"]["confirmed"] == 0
        assert report["counts"]["unconfirmed"] == 0
        assert report["counts"]["total"] == 0


class TestFetchOflCandidates:
    """fetch_ofl_candidates의 DB 조회 로직."""

    def test_fetches_candidates_from_dev_db(self, mocker) -> None:
        """license_type=OFL인 폰트들을 조회한다."""
        mock_client = MagicMock()
        base = "https://dev.supabase.com/rest/v1"
        headers = {"apikey": "test-key", "Authorization": "Bearer test-key"}
        response_data = [
            {
                "id": "1",
                "name_en": "Noto Sans KR",
                "license_type": "OFL",
            },
            {
                "id": "2",
                "name_en": "Roboto",
                "license_type": "OFL",
            },
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = response_data
        mock_client.get.return_value = mock_response

        result = fetch_ofl_candidates(mock_client, base, headers)

        assert len(result) == 2
        assert result[0]["name_en"] == "Noto Sans KR"
        assert result[1]["name_en"] == "Roboto"
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "fonts" in call_args[0][0]
        assert "license_type" in call_args[0][0]


class TestApplyUpdate:
    """apply_update의 PATCH 로직과 오류 처리."""

    def test_patches_font_successfully(self, mocker) -> None:
        """폰트 ID에 대해 필드 업데이트를 PATCH한다."""
        mock_client = MagicMock()
        base = "https://dev.supabase.com/rest/v1"
        headers = {"apikey": "test-key"}
        font_id = "550e8400-e29b-41d4-a716-446655440000"
        fields = {
            "license_status": "verified",
            "allow_commercial": "allowed",
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.patch.return_value = mock_response

        result = apply_update(mock_client, base, headers, font_id, fields)

        assert result is True
        mock_client.patch.assert_called_once()
        call_args = mock_client.patch.call_args
        assert font_id in call_args[0][0]
        assert call_args[1]["json"] == fields

    def test_handles_patch_failure(self, mocker) -> None:
        """PATCH 실패(4xx/5xx)를 False로 반환한다."""
        mock_client = MagicMock()
        base = "https://dev.supabase.com/rest/v1"
        headers = {"apikey": "test-key"}
        font_id = "550e8400-e29b-41d4-a716-446655440000"
        fields = {"license_status": "verified"}
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("Server error")
        mock_client.patch.return_value = mock_response

        result = apply_update(mock_client, base, headers, font_id, fields)

        assert result is False


class TestMainFlow:
    """main 함수의 end-to-end 통합 흐름."""

    def test_main_aborts_on_license_fetch_error(self, mocker, tmp_path) -> None:
        """fetch_license_map 실패 시 중단하고 비정상 종료한다."""
        mock_fetch = mocker.patch(
            "fontagit_pipeline.ofl_verify.fetch_license_map",
            side_effect=LicenseFetchError("Network error"),
        )
        mock_load = mocker.patch(
            "fontagit_pipeline.ofl_verify.load_audit_settings"
        )
        mock_load.return_value.dev_write_credentials.return_value = (
            "https://dev.example.com",
            "test-key",
        )
        report_path = str(tmp_path / "report.json")

        from fontagit_pipeline.ofl_verify import main

        exit_code = main(apply=True, report_path=report_path)

        assert exit_code != 0
        mock_fetch.assert_called_once()

    def test_main_writes_report_even_without_apply(self, mocker, tmp_path) -> None:
        """dry-run 모드에서도 report JSON을 생성한다."""
        mocker.patch(
            "fontagit_pipeline.ofl_verify.fetch_license_map",
            return_value={"notosanskr": "OFL"},
        )
        mocker.patch(
            "fontagit_pipeline.ofl_verify.fetch_ofl_candidates",
            return_value=[
                {
                    "id": "1",
                    "name_en": "Noto Sans KR",
                    "name_ko": "노토산스 한글",
                    "license_type": "OFL",
                }
            ],
        )
        mocker.patch(
            "fontagit_pipeline.ofl_verify.apply_update"
        )
        mock_load = mocker.patch(
            "fontagit_pipeline.ofl_verify.load_audit_settings"
        )
        mock_load.return_value.dev_write_credentials.return_value = (
            "https://dev.example.com",
            "test-key",
        )
        report_path = str(tmp_path / "report.json")

        from fontagit_pipeline.ofl_verify import main

        exit_code = main(apply=False, report_path=report_path)

        assert exit_code == 0
        assert Path(report_path).exists()
        report_data = json.loads(Path(report_path).read_text(encoding="utf-8"))
        assert report_data["counts"]["confirmed"] == 1
