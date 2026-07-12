"""Transform helpers for font metadata normalization and URL building."""


def normalize_variants(variants: list[str]) -> list[str]:
    """Normalize font variants (regular/italic) to weight+style format.

    Maps:
      'regular' -> '400'
      'italic' -> '400 italic'
      '700' -> '700'
      '700italic' -> '700 italic'
    """
    mapping = {
        "regular": "400",
        "italic": "400 italic",
        "700": "700",
        "700italic": "700 italic",
    }
    return [mapping.get(v, v) for v in variants]


def build_official_url(family: str) -> str:
    """Build official Google Fonts URL for a family.

    Args:
        family: Font family name (ASCII only)

    Returns:
        URL string with family name space-replaced by +

    Raises:
        ValueError: If family contains non-ASCII characters
    """
    if not family.isascii():
        raise ValueError(f"Family name must be ASCII: {family}")
    return f"https://fonts.google.com/specimen/{family.replace(' ', '+')}"


def build_aliases(name_en: str, name_ko: str | None = None) -> list[str]:
    """Build deduplicated list of font name aliases (exact string matching), order preserved.

    Creates candidates: original, lowercase, no-spaces, lowercase+ttf,
    then dedupes by exact string while preserving order.
    """
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
