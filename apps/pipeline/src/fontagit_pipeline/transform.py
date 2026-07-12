"""Transform helpers for font metadata normalization and URL building."""


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
