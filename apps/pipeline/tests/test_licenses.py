"""라이선스 판별 모듈 테스트."""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import httpx
import pytest

from fontagit_pipeline.licenses import (
    normalize_family_dir,
    parse_license_map,
    resolve_license_type,
    fetch_license_map,
    LicenseFetchError,
)


@pytest.fixture
def ofl_tree_data():
    """OFL 라이선스 디렉토리 트리 데이터."""
    fixture_path = Path(__file__).parent / "fixtures" / "gh_tree_ofl.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def license_trees(ofl_tree_data):
    """라이선스별 트리 매핑."""
    return {
        "ofl": ofl_tree_data["tree"],
    }


class TestNormalizeFamilyDir:
    """normalize_family_dir 테스트."""

    def test_lowercase_conversion(self):
        """대문자를 소문자로 변환."""
        assert normalize_family_dir("NotaSansKr") == "notasanskr"

    def test_remove_non_alphanumeric(self):
        """비영숫자 문자 제거."""
        assert normalize_family_dir("Noto Sans KR") == "notosanskr"

    def test_mixed_case_and_special(self):
        """대소문자 + 특수문자."""
        assert normalize_family_dir("JUA-Regular") == "juaregular"


class TestParseLicenseMap:
    """parse_license_map 테스트."""

    def test_extract_tree_entries_from_ofl(self, license_trees):
        """OFL 트리에서 tree 타입만 추출."""
        result = parse_license_map(license_trees)
        assert "notosanskr" in result
        assert result["notosanskr"] == "OFL"

    def test_exclude_blob_entries(self, license_trees):
        """blob 타입 제외."""
        result = parse_license_map(license_trees)
        assert "OFL.txt" not in result

    def test_map_license_directories(self, license_trees):
        """라이선스 디렉토리명 매핑."""
        result = parse_license_map(license_trees)
        assert result["notosanskr"] == "OFL"
        assert result["jua"] == "OFL"

    def test_skip_entry_without_path(self):
        """path 키 없는 항목은 KeyError 없이 건너뛴다."""
        trees = {"ofl": [{"type": "tree"}, {"type": "tree", "path": "jua"}]}
        result = parse_license_map(trees)
        assert result == {"jua": "OFL"}

    def test_skip_non_dict_entries(self):
        """dict가 아닌 entry는 건너뛴다."""
        trees = {"ofl": [123, {"type": "tree", "path": "jua"}, "invalid"]}
        result = parse_license_map(trees)
        assert result == {"jua": "OFL"}


class TestResolveLicenseType:
    """resolve_license_type 테스트."""

    def test_resolve_existing_license(self, license_trees):
        """존재하는 폰트의 라이선스 조회."""
        license_map = parse_license_map(license_trees)
        result = resolve_license_type("Noto Sans KR", license_map)
        assert result == "OFL"

    def test_resolve_missing_license(self, license_trees):
        """존재하지 않는 폰트."""
        license_map = parse_license_map(license_trees)
        result = resolve_license_type("NonExistent Font", license_map)
        assert result is None

    def test_normalize_before_lookup(self, license_trees):
        """조회 전 normalize 적용."""
        license_map = parse_license_map(license_trees)
        result = resolve_license_type("Jua", license_map)
        assert result == "OFL"


class TestFetchLicenseMap:
    """fetch_license_map 테스트."""

    def test_fetch_license_map_raises_on_http_error(self):
        """httpx 오류 발생 시 LicenseFetchError를 raise한다."""
        with patch("fontagit_pipeline.licenses.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_client.get.side_effect = httpx.ConnectError("연결 실패")

            with pytest.raises(LicenseFetchError):
                fetch_license_map()

    def test_fetch_license_map_raises_on_status_error(self):
        """HTTP 상태 오류 발생 시 LicenseFetchError를 raise한다."""
        with patch("fontagit_pipeline.licenses.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            )
            mock_client.get.return_value = mock_response

            with pytest.raises(LicenseFetchError):
                fetch_license_map()

    def test_fetch_license_map_raises_on_malformed_json(self):
        """응답 본문 JSON 파싱 실패 시 LicenseFetchError로 감싼다."""
        with patch("fontagit_pipeline.licenses.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_client.get.return_value = mock_response

            with pytest.raises(LicenseFetchError):
                fetch_license_map()

    def test_fetch_license_map_missing_tree_key_raises_error(self):
        """루트 응답에 tree 키가 없으면 LicenseFetchError를 raise한다."""
        with patch("fontagit_pipeline.licenses.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {}
            mock_client.get.return_value = mock_response

            with pytest.raises(LicenseFetchError):
                fetch_license_map()

    def test_fetch_license_map_tree_not_list_raises_error(self):
        """tree 값이 배열이 아니면 LicenseFetchError를 raise한다."""
        with patch("fontagit_pipeline.licenses.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {"tree": "not_a_list"}
            mock_client.get.return_value = mock_response

            with pytest.raises(LicenseFetchError):
                fetch_license_map()
