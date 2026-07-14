"""라이선스 판별 모듈."""
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

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
                if entry.get("type") == "tree":
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


async def fetch_license_map(github_token: str | None = None) -> dict[str, str]:
    """google/fonts에서 라이선스 매핑을 조회한다.

    Args:
        github_token: GitHub API 토큰 (선택)

    Returns:
        폰트명→라이선스 타입 매핑
    """
    pass
