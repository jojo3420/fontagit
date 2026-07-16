"""한글 이름-별칭 큐레이션 매핑 로더."""

import json
import unicodedata
from pathlib import Path

from fontagit_pipeline.models import KoreanNameEntry

_DATA_PATH = Path(__file__).parent / "data" / "korean_names.json"


class KoreanNamesError(Exception):
    """매핑 파일 검증 실패."""


def _nfc(entry: KoreanNameEntry) -> KoreanNameEntry:
    """큐레이션 입력의 NFD(자모 분리) 혼입 방지 — 저장 원문부터 NFC로 통일."""
    return entry.model_copy(
        update={
            "name_ko": unicodedata.normalize("NFC", entry.name_ko) if entry.name_ko else None,
            "aliases": [unicodedata.normalize("NFC", a) for a in entry.aliases],
        }
    )


def load_korean_names(path: Path = _DATA_PATH) -> dict[str, KoreanNameEntry]:
    """매핑 JSON을 로드-검증한다. 파일 부재/파싱 실패/스키마 위반 시 KoreanNamesError."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KoreanNamesError(f"매핑 파일 로드 실패({path}): {exc}") from exc
    try:
        return {slug: _nfc(KoreanNameEntry(**data)) for slug, data in raw.items()}
    except (TypeError, ValueError) as exc:
        raise KoreanNamesError(f"매핑 스키마 위반: {exc}") from exc


def validate_coverage(
    mapping: dict[str, KoreanNameEntry], published_korean_slugs: set[str]
) -> None:
    """published korean subset 폰트와 매핑 키의 완전 일치를 강제한다(침묵 실패 금지)."""
    missing = published_korean_slugs - mapping.keys()
    surplus = mapping.keys() - published_korean_slugs
    if missing:
        raise KoreanNamesError(f"매핑 누락 slug: {sorted(missing)}")
    if surplus:
        raise KoreanNamesError(f"매핑 잉여 slug: {sorted(surplus)}")
