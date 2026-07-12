"""Transform helpers for font metadata normalization and URL building."""

import logging

from fontagit_pipeline.models import GoogleFontRaw, FontRecord

logger = logging.getLogger(__name__)


def normalize_variants(variants: list[str]) -> list[str]:
    """구글 variants를 '숫자 weight' 또는 '숫자 italic' 형태로 정규화한다."""
    mapping = {
        "regular": "400",
        "italic": "400 italic",
        "700": "700",
        "700italic": "700 italic",
    }
    return [mapping.get(v, v) for v in variants]


def build_official_url(family: str) -> str:
    """family의 공백만 '+'로 바꿔 공식 specimen URL을 만든다. 비ASCII family는 ValueError."""
    if not family.isascii():
        raise ValueError(f"Family name must be ASCII: {family}")
    return f"https://fonts.google.com/specimen/{family.replace(' ', '+')}"


def build_aliases(name_en: str, name_ko: str | None = None) -> list[str]:
    """검색용 기본 별칭 목록을 만든다(동일 문자열 기준 중복 제거, 순서 유지)."""
    candidates = [
        name_en,
        name_en.lower(),
        name_en.lower().replace(" ", ""),
        f"{name_en.lower()} ttf",
    ]
    if name_ko:
        candidates += [name_ko, name_ko.replace(" ", "")]
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        key = c
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


def filter_korean(fonts: list[GoogleFontRaw]) -> list[GoogleFontRaw]:
    """subset에 korean을 포함하는 폰트를 필터링한다 (순서 유지)."""
    return [font for font in fonts if "korean" in font.subsets]


def select_latin_top(fonts: list[GoogleFontRaw], limit: int = 100) -> list[GoogleFontRaw]:
    """subset에 latin을 포함하는 상위 폰트를 선택한다 (인기도 순서 기준, 최대 limit개)."""
    latin_fonts = [font for font in fonts if "latin" in font.subsets]
    return latin_fonts[:limit]


def merge_dedup(
    korean: list[GoogleFontRaw], latin: list[GoogleFontRaw]
) -> list[GoogleFontRaw]:
    """family 기준으로 한국어 폰트를 먼저, 라틴 폰트 중 미등재 항목을 이어붙인다."""
    result = korean[:]
    seen = {font.family for font in korean}
    for font in latin:
        if font.family not in seen:
            result.append(font)
            seen.add(font.family)
    return result


def to_record(raw: GoogleFontRaw) -> FontRecord:
    """GoogleFontRaw를 FontRecord로 변환한다 (license=None, license_verified=False)."""
    return FontRecord(
        name_en=raw.family,
        name_ko=None,
        tier="A",
        category=raw.category,
        subsets=raw.subsets,
        variants=normalize_variants(raw.variants),
        official_url=build_official_url(raw.family),
        license=None,
        license_verified=False,
        aliases=build_aliases(raw.family),
        version=raw.version,
        last_modified=raw.lastModified,
    )


def build_records(
    fonts: list[GoogleFontRaw], latin_limit: int = 100
) -> list[FontRecord]:
    """폰트 목록을 레코드로 변환한다 (한국어+라틴 통합, 중복 제거, 변환 실패 시 건너뜀)."""
    merged = merge_dedup(filter_korean(fonts), select_latin_top(fonts, latin_limit))
    records: list[FontRecord] = []
    for raw in merged:
        try:
            records.append(to_record(raw))
        except ValueError as exc:
            logger.warning("레코드 변환 건너뜀 (%s): %s", raw.family, exc)
    return records
