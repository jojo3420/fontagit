"""라이선스 판별 모듈."""
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LicenseFetchError(Exception):
    """google/fonts 라이선스 매핑 조회 실패."""

_GH_API = "https://api.github.com"
_TIMEOUT = httpx.Timeout(10.0, connect=10.0)
_LICENSE_DIRS = {
    "ofl": "OFL",
    "apache": "Apache-2.0",
    "ufl": "UFL",
}


def normalize_family_dir(name_en: str) -> str:
    """폰트 영문명을 디렉토리명으로 정규화한다.

    소문자 변환 및 비영숫자 문자 제거.

    Args:
        name_en: 폰트 영문명

    Returns:
        정규화된 디렉토리명
    """
    return re.sub(r"[^a-z0-9]", "", name_en.lower())


def _extract_tree(data: Any) -> list[dict[str, Any]]:
    """GitHub API 응답에서 tree 배열을 추출하고 구조를 검증한다.

    Args:
        data: GitHub API의 JSON 응답

    Returns:
        tree 배열

    Raises:
        LicenseFetchError: 응답이 dict가 아니거나, tree 키가 없거나, tree가 배열이 아닌 경우
    """
    if not isinstance(data, dict):
        raise LicenseFetchError("GitHub API 응답이 dict가 아닙니다")
    if "tree" not in data:
        raise LicenseFetchError("GitHub API 응답에 'tree' 키가 없습니다")
    tree = data["tree"]
    if not isinstance(tree, list):
        raise LicenseFetchError("GitHub API 응답의 'tree' 값이 배열이 아닙니다")
    return tree


def parse_license_map(trees: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """라이선스별 트리 데이터에서 폰트명→라이선스 매핑을 추출한다.

    Args:
        trees: 라이선스별 GH tree 데이터 (예: {"ofl": [...]})

    Returns:
        폰트명→라이선스 타입 매핑 (예: {"notosanskr": "OFL"})
    """
    result = {}
    for license_dir, license_type in _LICENSE_DIRS.items():
        if license_dir in trees:
            for entry in trees[license_dir]:
                if isinstance(entry, dict) and entry.get("type") == "tree" and "path" in entry:
                    result[entry["path"]] = license_type
    return result


def resolve_license_type(
    name_en: str, license_map: dict[str, str]
) -> str | None:
    """폰트 영문명으로 라이선스 타입을 조회한다.

    Args:
        name_en: 폰트 영문명
        license_map: parse_license_map의 결과

    Returns:
        라이선스 타입 (OFL/Apache-2.0/UFL) 또는 None
    """
    return license_map.get(normalize_family_dir(name_en))


def _get_tree_sha(client: httpx.Client, headers: dict[str, str]) -> dict[str, str]:
    """루트 트리에서 ofl/apache/ufl 디렉토리의 sha를 얻는다.

    Raises:
        LicenseFetchError: GitHub API 응답 구조 이상 시
    """
    r = client.get(f"{_GH_API}/repos/google/fonts/git/trees/main", headers=headers)
    r.raise_for_status()
    data = r.json()
    tree = _extract_tree(data)
    shas: dict[str, str] = {}
    for entry in tree:
        if "path" in entry and "sha" in entry and entry.get("type") == "tree":
            if entry["path"] in _LICENSE_DIRS:
                shas[entry["path"]] = entry["sha"]
    return shas


def fetch_license_map(github_token: str | None = None) -> dict[str, str]:
    """google/fonts에서 라이선스 매핑을 조회한다.

    Args:
        github_token: GitHub API 토큰 (선택)

    Returns:
        폰트명→라이선스 타입 매핑

    Raises:
        LicenseFetchError: 라이선스 조회 실패 시
    """
    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    trees: dict[str, list[dict[str, Any]]] = {}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            shas = _get_tree_sha(client, headers)
            for dir_key, sha in shas.items():
                r = client.get(
                    f"{_GH_API}/repos/google/fonts/git/trees/{sha}", headers=headers
                )
                r.raise_for_status()
                data = r.json()
                trees[dir_key] = _extract_tree(data)
    except httpx.HTTPError as exc:
        logger.warning("라이선스 매핑 조회 실패: %s", exc.__class__.__name__)
        raise LicenseFetchError(str(exc)) from exc
    except ValueError as exc:
        logger.warning("라이선스 매핑 JSON 파싱 실패: %s", exc.__class__.__name__)
        raise LicenseFetchError(str(exc)) from exc
    return parse_license_map(trees)
