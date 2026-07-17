"""눈누 상세페이지에서 라이선스-스타일 추출 코어 모듈

LLM 불사용, BeautifulSoup과 정규식만으로 사실 추출 (결정론적).
"""
import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EnrichParseError(Exception):
    """눈누 페이지 파싱 실패"""
    pass


# Task 2: JSON-LD 메타 추출
PERMISSION_CATEGORIES: tuple[str, ...] = (
    "print", "website", "packaging", "video", "embedding", "branding"
)
_COMMERCIAL_KEYS = ("print", "website", "packaging", "video")


def _extract_json_ld_blocks(html: str) -> list[dict]:
    """JSON-LD 블록 모두 추출"""
    soup = BeautifulSoup(html, "html.parser")
    blocks = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            blocks.append(data)
    return blocks


def extract_meta(html: str) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """JSON-LD SoftwareApplication에서 (이름, 가격, 제작사) 추출. 파싱 불가 항목은 None."""
    for data in _extract_json_ld_blocks(html):
        if data.get("@type") != "SoftwareApplication":
            continue
        name = data.get("name")
        creator = data.get("creator") or data.get("author")
        if isinstance(creator, dict):
            creator = creator.get("name")
        price: Optional[int] = None
        offers = data.get("offers")
        if isinstance(offers, dict) and offers.get("price") is not None:
            try:
                price = int(float(offers["price"]))
            except (ValueError, TypeError):
                price = None
        return name, price, creator
    return None, None, None


# Task 3: 라이선스 허용표 파싱
_STATUS_MAP = {
    "사용 가능": "allowed",
    "조건부 허용": "conditional",
    "사용 불가": "denied",
}

_CATEGORY_MAP = {
    "인쇄": "print",
    "웹사이트": "website",
    "포장지": "packaging",
    "영상": "video",
    "임베딩": "embedding",
    "BI/CI": "branding",
}


def parse_permissions(html: str) -> dict[str, str]:
    """라이선스 허용표에서 6 카테고리별 허용 여부 추출

    구조: table > tr (1번째 이후) > td[0]=카테고리, td[2]=상태

    Returns:
        {"print": "allowed", "website": "allowed", ...}

    Raises:
        EnrichParseError: 정확히 6개 카테고리 추출 불가
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if not table:
        raise EnrichParseError("라이선스 허용표(table) 없음")

    rows = table.find_all("tr")[1:]  # 헤더 제외
    result = {}

    for row in rows:
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue

        category_text = cells[0].get_text(strip=True)
        status_text = cells[2].get_text(strip=True)

        # 카테고리 매핑
        category_key = _CATEGORY_MAP.get(category_text)
        if not category_key:
            continue

        # 상태 매핑
        status = _STATUS_MAP.get(status_text)
        if status is None:
            continue

        result[category_key] = status

    # 정확히 6개 카테고리 필수
    if set(result.keys()) != set(PERMISSION_CATEGORIES):
        raise EnrichParseError(
            f"6개 카테고리 미달: {set(result.keys())} vs {set(PERMISSION_CATEGORIES)}"
        )

    return result


# Task 4: @font-face 스타일 추출
def extract_styles(html: str) -> tuple[list[int], bool]:
    """@font-face에서 굵기/이태릭 추출(best-effort). 없으면 ([], False)."""
    weights = sorted({int(m) for m in re.findall(r"font-weight\s*:\s*(\d{3})", html)})
    italic = bool(re.search(r"font-style\s*:\s*italic", html))
    return weights, italic


# Task 5a: 라이선스 타입 추정
def guess_license_type(html: str) -> str:
    """라이선스 본문에 OFL/SIL 표기가 있으면 'OFL', 아니면 'custom-free'."""
    if re.search(r"\bOFL\b|SIL\s*Open\s*Font", html, re.IGNORECASE):
        return "OFL"
    return "custom-free"


# Task 5b: 라이선스 4행 매핑
def map_license_rows(
    permissions: dict[str, str],
    license_type: str
) -> dict[str, Optional[str | bool]]:
    """권한별 DB row 매핑

    Args:
        permissions: parse_permissions 결과
        license_type: guess_license_type 결과

    Returns:
        {
            "is_commercial_free": bool,
            "allow_embedding": "allowed"/"conditional"/"denied",
            "allow_redistribute": "allowed"/"conditional"/"denied" or None,
            "allow_modify": "allowed"/"conditional"/"denied" or None,
            "license_note": str or None,
        }
    """
    is_commercial_free = all(permissions[k] == "allowed" for k in _COMMERCIAL_KEYS)
    allow_embedding = permissions.get("embedding")
    if license_type == "OFL":
        allow_redistribute, allow_modify = "conditional", "allowed"
    else:
        allow_redistribute, allow_modify = None, None

    notes: list[str] = []
    if allow_embedding == "conditional":
        notes.append("임베딩 조건부 - 제작사 약관 확인")
    if allow_embedding == "denied":
        notes.append("임베딩 불가 - 제작사 약관 확인")
    for k in _COMMERCIAL_KEYS:
        if permissions[k] == "conditional":
            notes.append(f"{k} 조건부 - 제작사 약관 확인")
    license_note = "; ".join(notes) or None

    return {
        "is_commercial_free": is_commercial_free,
        "allow_embedding": allow_embedding,
        "allow_redistribute": allow_redistribute,
        "allow_modify": allow_modify,
        "license_note": license_note,
    }


# Task 6: 분류 게이트
def classify(parse_ok: bool, price: Optional[int], perms: Optional[dict[str, str]]) -> str:
    """자동 발행 게이트(D6). 상업 4카테고리 전부 allowed + price 0 + 파싱성공만 auto_safe."""
    if not parse_ok or perms is None:
        return "needs_review"
    if price != 0:
        return "needs_review"
    if all(perms[k] == "allowed" for k in _COMMERCIAL_KEYS):
        return "auto_safe"
    return "needs_review"


# Task 7: 제안 조립
def build_proposal(font_id: str, slug: str, source_url: str, official_url: str, html: str) -> dict:
    """눈누 HTML에서 license_proposals insert용 dict를 조립한다.

    파싱 실패 시 예외를 던지지 않고 parse_status='failed' + needs_review로 담아,
    호출측 배치가 안전하게 계속되도록 한다.
    """
    name, price, creator = extract_meta(html)
    weights, italic = extract_styles(html)
    license_type = guess_license_type(html)
    try:
        perms = parse_permissions(html)
        parse_status = "parsed"
    except EnrichParseError as exc:
        logger.warning("허용표 파싱 실패(slug=%s): %s", slug, exc)
        perms, parse_status = None, "failed"

    classification = classify(parse_status == "parsed", price, perms)
    rows = (map_license_rows(perms, license_type) if perms is not None
            else {"is_commercial_free": None, "allow_embedding": None,
                  "allow_redistribute": None, "allow_modify": None, "license_note": None})

    proposal = {
        "font_id": font_id,
        "slug": slug,
        "source_url": source_url,
        "raw_permissions": perms or {},
        "proposed_commercial_free": rows["is_commercial_free"],
        "proposed_embedding": rows["allow_embedding"],
        "proposed_redistribute": rows["allow_redistribute"],
        "proposed_modify": rows["allow_modify"],
        "proposed_license_type": license_type,
        "proposed_weights": weights,
        "proposed_italic": italic,
        "proposed_category_ko": None,
        "parse_status": parse_status,
        "classification": classification,
        "review_status": "auto_published" if classification == "auto_safe" else "proposed",
    }
    proposal["_font_update"] = (
        _font_update_for(rows, license_type, weights, italic, official_url)
        if classification == "auto_safe" else None
    )
    return proposal


def _font_update_for(rows: dict, license_type: str, weights: list[int],
                     italic: bool, official_url: str) -> dict:
    """auto_safe 제안을 fonts 발행 업데이트로 변환."""
    return {
        "is_commercial_free": bool(rows["is_commercial_free"]),
        "allow_embedding": rows["allow_embedding"],
        "allow_redistribute": rows["allow_redistribute"],
        "allow_modify": rows["allow_modify"],
        "license_type": license_type,
        "license_note": rows["license_note"],
        "weights": weights,
        "variants": ["italic"] if italic else [],
        "license_verified": True,
        "auto_approved": True,
        "license_source_url": official_url,
        "status": "published",
    }
