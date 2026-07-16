"""수집 데이터 필터-정규화-변환."""

import logging
import re

from fontagit_pipeline.korean_names import validate_coverage, KoreanNamesError
from fontagit_pipeline.licenses import resolve_license_type
from fontagit_pipeline.models import GoogleFontRaw, FontRecord, KoreanNameEntry

logger = logging.getLogger(__name__)


def normalize_variants(variants: list[str]) -> list[str]:
    """구글 variants를 '숫자 weight' 또는 '숫자 italic' 형태로 정규화한다.

    규칙:
    - "regular" -> "400"
    - "italic" -> "400 italic"
    - "{weight}italic" (예: "500italic") -> "{weight} italic" (예: "500 italic")
    - 기타 값은 그대로 반환.
    """
    result: list[str] = []
    for v in variants:
        if v == "regular":
            result.append("400")
        elif v == "italic":
            result.append("400 italic")
        elif v.endswith("italic") and v != "italic":
            # "100italic", "500italic" 등 -> "100 italic", "500 italic"
            weight = v[:-6]  # "italic" 제거
            result.append(f"{weight} italic")
        else:
            result.append(v)
    return result


def build_official_url(family: str) -> str:
    """family의 공백만 '+'로 바꿔 공식 specimen URL을 만든다. 비ASCII family는 ValueError."""
    if not family.isascii():
        raise ValueError(f"가족 이름은 ASCII여야 합니다: {family}")
    return f"https://fonts.google.com/specimen/{family.replace(' ', '+')}"


def build_aliases(name_en: str, name_ko: str | None = None, extra_aliases: list[str] | None = None) -> list[str]:
    """검색용 기본 별칭 목록을 만든다(동일 문자열 기준 중복 제거, 순서 유지)."""
    candidates = [
        name_en,
        name_en.lower(),
        name_en.lower().replace(" ", ""),
        f"{name_en.lower()} ttf",
    ]
    if name_ko:
        candidates += [name_ko, name_ko.replace(" ", "")]
    if extra_aliases:
        candidates += extra_aliases
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
    """family 기준으로 중복 제거하며 한국어 폰트를 먼저, 라틴 폰트를 이어붙인다.

    전체 병합 시퀀스에서 중복을 제거하며, 순서는 한국어-라틴 순서를 유지한다.
    """
    result: list[GoogleFontRaw] = []
    seen: set[str] = set()

    # 한국어 폰트 먼저 추가
    for font in korean:
        if font.family not in seen:
            result.append(font)
            seen.add(font.family)

    # 라틴 폰트 중 미등재 항목 추가
    for font in latin:
        if font.family not in seen:
            result.append(font)
            seen.add(font.family)

    return result


_CATEGORY_KO_MAP = {
    "sans-serif": "고딕",
    "serif": "명조",
    "handwriting": "손글씨",
    "display": "장식",
    "monospace": "고딕",
}


def map_category_ko(google_category: str) -> str:
    """구글 카테고리를 한글 4분류로 매핑한다(미지정은 고딕)."""
    return _CATEGORY_KO_MAP.get(google_category, "고딕")


def build_slug(name_en: str) -> str:
    """영문명을 URL 슬러그로 변환한다(소문자, 비영숫자 하이픈, 양끝 정리)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name_en.lower()).strip("-")
    return slug


def extract_weights(variants: list[str]) -> list[int]:
    """정규화 variants에서 숫자 weight만 추출한다(중복 제거, 오름차순)."""
    weights: set[int] = set()
    for v in variants:
        head = v.split(" ")[0]
        if head.isdigit():
            weights.add(int(head))
    return sorted(weights)


def to_record(
    raw: GoogleFontRaw,
    license_map: dict[str, str],
    korean_names: dict[str, KoreanNameEntry] | None = None,
) -> FontRecord:
    """GoogleFontRaw를 FontRecord로 변환. license_type 판별 및 상태 결정."""
    license_type = resolve_license_type(raw.family, license_map)
    verified = license_type is not None
    variants = normalize_variants(raw.variants)
    slug = build_slug(raw.family)

    name_ko = None
    extra_aliases = None
    if korean_names and slug in korean_names:
        entry = korean_names[slug]
        name_ko = entry.name_ko
        extra_aliases = entry.aliases if entry.aliases else None

    return FontRecord(
        slug=slug,
        name_en=raw.family,
        name_ko=name_ko,
        source_tier="A",
        category_ko=map_category_ko(raw.category),
        category_google=raw.category,
        subsets=raw.subsets,
        variants=variants,
        weights=extract_weights(variants),
        official_url=build_official_url(raw.family),
        is_commercial_free=verified,
        license=None,
        license_type=license_type,
        license_verified=verified,
        status="published" if verified else "draft",
        aliases=build_aliases(raw.family, name_ko=name_ko, extra_aliases=extra_aliases),
        version=raw.version,
        last_modified=raw.lastModified,
    )



def build_records(
    fonts: list[GoogleFontRaw],
    license_map: dict[str, str],
    latin_limit: int = 100,
    korean_names: dict[str, KoreanNameEntry] | None = None,
) -> list[FontRecord]:
    """병합-중복제거 후 FontRecord 리스트 반환. 변환 실패 시 건너뜀."""
    merged = merge_dedup(filter_korean(fonts), select_latin_top(fonts, latin_limit))
    records: list[FontRecord] = []
    for raw in merged:
        try:
            records.append(to_record(raw, license_map, korean_names=korean_names))
        except ValueError as exc:
            logger.warning("레코드 변환 건너뜀 (%s): %s", raw.family, exc)
    if korean_names is not None:
        published_korean = {r.slug for r in records if r.status == "published" and "korean" in r.subsets}
        validate_coverage(korean_names, published_korean)
    return records
