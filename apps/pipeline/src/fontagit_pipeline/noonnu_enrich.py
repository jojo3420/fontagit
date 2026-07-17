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
    """JSON-LD에서 폰트명, 페이지ID, 설명 추출

    Returns:
        (name, font_page_id, description)
        font_page_id는 source_url https://noonnu.cc/font_page/N 에서 추출

    Raises:
        EnrichParseError: JSON-LD 또는 필수 필드 없음
    """
    soup = BeautifulSoup(html, "html.parser")
    blocks = _extract_json_ld_blocks(html)

    if not blocks:
        raise EnrichParseError("JSON-LD 블록 없음")

    data = blocks[0]  # 첫 번째 SoftwareApplication

    name = data.get("name")
    description = data.get("description")

    # 페이지 ID 추출 (URL에서)
    font_page_id = None
    if "url" in data:
        match = re.search(r"/font_page/(\d+)", str(data["url"]))
        if match:
            font_page_id = int(match.group(1))

    return name, font_page_id, description


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
    """@font-face에서 font-weight와 italic 여부 추출

    Returns:
        (weights=[400, 700, ...], has_italic=True/False)

    Raises:
        EnrichParseError: @font-face 없음
    """
    soup = BeautifulSoup(html, "html.parser")
    styles = soup.find_all("style")

    font_face_text = ""
    for style in styles:
        if "@font-face" in (style.string or ""):
            font_face_text = style.string
            break

    if not font_face_text:
        raise EnrichParseError("@font-face 없음")

    # font-weight 추출
    weights_raw = re.findall(r"font-weight\s*:\s*(\d+)", font_face_text)
    weights = sorted(set(int(w) for w in weights_raw))
    if not weights:
        weights = [400]  # 기본값

    # italic 여부
    has_italic = "italic" in font_face_text.lower()

    return weights, has_italic


# Task 5a: 라이선스 타입 추정
def guess_license_type(html: str) -> str:
    """페이지 텍스트에서 라이선스 타입 추정

    반환: "OFL", "CC0", "custom-free", "commercial" (기본값)
    """
    text = BeautifulSoup(html, "html.parser").get_text().lower()

    if "ofl" in text or "open font license" in text:
        return "OFL"
    if "cc0" in text or "크리에이티브 커먼즈" in text:
        return "CC0"
    if "무료" in text and "상업" in text:
        return "custom-free"

    return "commercial"


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
    result: dict[str, Optional[str | bool]] = {}

    # 상업 사용 가능 여부 (print, website, packaging, video 중 하나라도 denied면 False)
    commercial_categories = {"print", "website", "packaging", "video"}
    is_commercial = all(
        permissions.get(cat) != "denied"
        for cat in commercial_categories
    )
    result["is_commercial_free"] = is_commercial

    # 임베딩
    result["allow_embedding"] = permissions.get("embedding")

    # OFL: redistribute=conditional, modify=allowed
    if license_type == "OFL":
        result["allow_redistribute"] = "conditional"
        result["allow_modify"] = "allowed"
    else:
        result["allow_redistribute"] = None
        result["allow_modify"] = None

    # license_note: 조건부/거부 카테고리 기재
    notes = []
    for cat_key, cat_kr in [
        ("embedding", "임베딩"),
        ("print", "인쇄"),
        ("website", "웹사이트"),
        ("packaging", "포장지"),
        ("video", "영상"),
        ("branding", "BI/CI"),
    ]:
        status = permissions.get(cat_key)
        if status == "conditional":
            notes.append(f"{cat_kr}은 조건부 허용")
        elif status == "denied":
            notes.append(f"{cat_kr}은 사용 불가")

    if notes:
        result["license_note"] = "; ".join(notes)
    else:
        result["license_note"] = None

    return result


# Task 6: 분류 게이트
def classify(
    parse_ok: bool,
    perms: Optional[dict[str, str]] = None,
    license_type: Optional[str] = None,
) -> str:
    """파싱 성공 여부 + 권한 구조로 분류

    Returns:
        "auto_safe": 모든 상업 4카테고리 + 임베딩이 allowed
        "needs_review": 조건부/거부 있음 또는 파싱 실패
    """
    if not parse_ok or perms is None:
        return "needs_review"

    # 상업 4 카테고리 + 임베딩이 모두 allowed 여야 auto_safe
    critical = ["print", "website", "packaging", "video", "embedding"]
    if all(perms.get(cat) == "allowed" for cat in critical):
        return "auto_safe"

    return "needs_review"


# Task 7: 제안 조립
def build_proposal(
    font_id: str,
    slug: str,
    source_url: str,
    official_url: str,
    html: str,
) -> dict:
    """완전한 제안 객체 조립

    Returns:
        {
            "font_id": str,
            "slug": str,
            "classification": "auto_safe" | "needs_review",
            "parse_status": "ok" | "failed",
            "proposed_commercial_free": bool | None,
            "proposed_embedding": "allowed" | "conditional" | "denied" | None,
            "proposed_redistribute": ... | None,
            "proposed_modify": ... | None,
            "source_url": str,
            "raw_permissions": dict | None,
            "_font_update": dict | None,  # auto_safe일 때만 채워짐
        }
    """
    parse_ok = False
    perms = None
    license_type = None

    # 파싱 시도
    try:
        perms = parse_permissions(html)
        license_type = guess_license_type(html)
        parse_ok = True
    except EnrichParseError as e:
        logger.warning(f"파싱 실패 {slug}: {e}")

    # 분류
    classification = classify(parse_ok, perms, license_type)

    # 행 매핑
    rows = {}
    if parse_ok and perms:
        rows = map_license_rows(perms, license_type)

    # 기본 제안
    proposal = {
        "font_id": font_id,
        "slug": slug,
        "classification": classification,
        "parse_status": "ok" if parse_ok else "failed",
        "proposed_commercial_free": rows.get("is_commercial_free"),
        "proposed_embedding": rows.get("allow_embedding"),
        "proposed_redistribute": rows.get("allow_redistribute"),
        "proposed_modify": rows.get("allow_modify"),
        "source_url": source_url,
        "raw_permissions": perms,
    }

    # auto_safe일 때만 _font_update 포함
    if classification == "auto_safe" and rows:
        proposal["_font_update"] = {
            "allow_embedding": rows["allow_embedding"],
            "allow_redistribute": rows["allow_redistribute"],
            "allow_modify": rows["allow_modify"],
            "license_note": rows["license_note"],
            "license_verified": True,
            "license_source_url": official_url,
        }
    else:
        proposal["_font_update"] = None

    return proposal
