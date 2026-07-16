"""한글 이름-별칭 큐레이션 매핑 로더 및 검증."""

import json
import logging
from pathlib import Path
from unicodedata import normalize

from fontagit_pipeline.models import KoreanNameEntry

_logger = logging.getLogger(__name__)
_DATA_PATH = Path(__file__).parent / "data" / "korean_names.json"


class KoreanNamesError(Exception):
    """한글 이름 매핑 오류."""

    pass


def load_korean_names(path: Path = _DATA_PATH) -> dict[str, KoreanNameEntry]:
    """매핑 JSON을 로드-검증한다.

    파일 부재/파싱 오류 시 KoreanNamesError 발생. 모든 name_ko는 NFC 정규화된다.

    Args:
        path: korean_names.json 경로. 기본값은 패키지 데이터 디렉토리.

    Returns:
        slug -> KoreanNameEntry 매핑.

    Raises:
        KoreanNamesError: 파일 부재, 파싱 오류, 유효성 검증 실패 시.
    """
    if not path.exists():
        raise KoreanNamesError(f"파일 없음: {path}")

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise KoreanNamesError(f"JSON 파싱 오류: {path}") from e

    mapping = {}
    for slug, entry_dict in data.items():
        # name_ko NFC 정규화
        name_ko = entry_dict.get("name_ko")
        if isinstance(name_ko, str):
            name_ko = normalize("NFC", name_ko)

        entry = KoreanNameEntry(
            name_ko=name_ko,
            aliases=entry_dict.get("aliases", []),
            sources=entry_dict.get("sources", []),
        )
        mapping[slug] = entry

    _logger.debug(f"로드 완료: {len(mapping)}개 항목 from {path}")
    return mapping


def validate_coverage(mapping: dict[str, KoreanNameEntry]) -> None:
    """매핑 커버리지를 검증한다.

    모든 항목의 name_ko가 non-None이어야 함. 위반 시 KoreanNamesError 발생.

    Args:
        mapping: KoreanNameEntry 매핑.

    Raises:
        KoreanNamesError: name_ko가 None인 항목이 있을 때.
    """
    missing = [slug for slug, entry in mapping.items() if entry.name_ko is None]
    if missing:
        raise KoreanNamesError(
            f"name_ko is None: {', '.join(missing[:5])}"
            f"{f' (총 {len(missing)}개)' if len(missing) > 5 else ''}"
        )
