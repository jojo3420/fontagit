"""눈누 상세페이지에서 라이선스-스타일 추출 코어 모듈

LLM 불사용, BeautifulSoup과 정규식만으로 사실 추출 (결정론적).
"""
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup
from supabase import create_client

from fontagit_pipeline.models import NoonnuSeedOutput
from fontagit_pipeline.noonnu_seed import (
    _ROBOT_USER_AGENT,
    _REQUEST_DELAY,
    _ROBOTS_URL,
    _USER_AGENT,
    derive_noonnu_slug,
    _parse_robots_policy,
)

logger = logging.getLogger(__name__)


class EnrichParseError(Exception):
    """눈누 페이지 파싱 실패"""
    pass


class NoonnuEnrichError(Exception):
    """눈누 enrich 오류 (외부 경계)"""
    pass


# Task 2: JSON-LD 메타 추출
PERMISSION_CATEGORIES: tuple[str, ...] = (
    "print", "website", "packaging", "video", "embedding", "branding"
)
_COMMERCIAL_KEYS = ("print", "website", "packaging", "video")


def _extract_json_ld_blocks(html: str) -> list[dict]:  # type: ignore[type-arg]
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


def extract_meta(html: str) -> tuple[Optional[str], Optional[float], Optional[str]]:
    """JSON-LD SoftwareApplication에서 (이름, 가격, 제작사) 추출. 파싱 불가 항목은 None.

    Returns:
        (name, price, creator) 튜플. price는 float (예: 0.0, 0.5, 10.0).
        정수와 소수를 구분하지 않음 (int는 자동으로 float로 변환).
    """
    for data in _extract_json_ld_blocks(html):
        if data.get("@type") != "SoftwareApplication":
            continue
        name = data.get("name")
        creator = data.get("creator") or data.get("author")
        if isinstance(creator, dict):
            creator = creator.get("name")
        price: Optional[float] = None
        offers = data.get("offers")
        if isinstance(offers, dict) and offers.get("price") is not None:
            try:
                price = float(offers["price"])
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


def parse_permissions(html: str) -> dict[str, Optional[str]]:
    """라이선스 허용표에서 6 카테고리별 허용 여부 추출

    구조: table > tr (1번째 이후) > td[0]=카테고리, td[2]=상태

    게이트 카테고리 (print/website/packaging/video):
    - 유효한 상태값(allowed/conditional/denied) 필수
    - 빈값이거나 미지 상태값이면 EnrichParseError

    게이트 밖 카테고리 (embedding/branding):
    - 빈값 또는 미지 상태값이면 None으로 저장
    - 행 자체가 없어도 None으로 초기화

    Returns:
        {"print": "allowed", ..., "embedding": None, ...}
        게이트 밖 카테고리는 None 가능.

    Raises:
        EnrichParseError: 게이트 4개 카테고리에 유효 상태 없음, 중복 카테고리
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if not table:
        raise EnrichParseError("라이선스 허용표(table) 없음")

    rows = table.find_all("tr")[1:]  # 헤더 제외
    result: dict[str, Optional[str]] = {cat: None for cat in PERMISSION_CATEGORIES}

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

        # 중복 카테고리 검증 - 덮어쓰기로 denied가 allowed로 가려지는 것 방지
        if result[category_key] is not None:
            raise EnrichParseError(
                f"중복 카테고리: {category_key} ('{status_text}' vs '{result[category_key]}')"
            )

        # 상태 매핑
        status = _STATUS_MAP.get(status_text)

        # 게이트 카테고리는 유효 상태 필수
        if category_key in _COMMERCIAL_KEYS:
            if status is None:
                raise EnrichParseError(
                    f"게이트 카테고리 '{category_key}' 유효하지 않은 상태값: '{status_text}'"
                )
            result[category_key] = status
        else:
            # 게이트 밖 카테고리(embedding, branding): 빈값/미지→None
            result[category_key] = status

    # 게이트 4개 카테고리는 모두 유효 상태 필수
    missing_commercial = [k for k in _COMMERCIAL_KEYS if result[k] is None]
    if missing_commercial:
        raise EnrichParseError(
            f"게이트 카테고리 미달 또는 무효 상태: {missing_commercial}"
        )

    return result


# Task 4: @font-face 스타일 추출
def extract_styles(html: str) -> tuple[list[int], bool]:
    """@font-face 블록에서만 굵기/이태릭 추출(best-effort). 없으면 ([], False).

    reason: UI CSS의 font-weight/font-style과 혼동 방지. @font-face 선언만 추출.
    """
    # @font-face 블록 추출 (가장 간단한 정규식: @font-face { ... })
    font_face_pattern = r"@font-face\s*\{[^}]*\}"
    font_face_blocks = re.findall(font_face_pattern, html, re.DOTALL)

    weights_set: set[int] = set()
    italic = False

    for block in font_face_blocks:
        # 각 @font-face 블록에서 font-weight 추출
        weight_matches = re.findall(r"font-weight\s*:\s*(\d{3})", block)
        weights_set.update(int(m) for m in weight_matches)

        # italic 여부 확인
        if re.search(r"font-style\s*:\s*italic", block):
            italic = True

    weights = sorted(weights_set)
    return weights, italic


# Task 5a: 라이선스 타입 추정
def guess_license_type(html: str) -> str:
    """눈누 HTML에서 라이선스 타입을 신뢰성 있게 판별할 수 없으므로 항상 'custom-free' 반환.

    reason: 눈누 허용표에는 항상 "OFL" 행이 있어서 HTML에서 "OFL" 키워드를 찾으면
    거의 모든 폰트가 OFL로 오판되고, 실제 라이선스 정보는 제작사 약관에서만 신뢰할 수 있음.
    """
    return "custom-free"


# Task 5b: 라이선스 4행 매핑
def map_license_rows(
    permissions: dict[str, Optional[str]],
    license_type: str
) -> dict[str, Optional[str | bool]]:
    """권한별 DB row 매핑

    Args:
        permissions: parse_permissions 결과
        license_type: guess_license_type 결과 (현재 항상 'custom-free')

    Returns:
        {
            "is_commercial_free": bool,
            "allow_embedding": "allowed"/"conditional"/"denied",
            "allow_redistribute": None (눈누 허용표에는 없는 정보),
            "allow_modify": None (눈누 허용표에는 없는 정보),
            "license_note": str or None,
        }

    reason: 재배포/수정 권한은 눈누 허용표에 없는 정보이므로 항상 None으로 반환.
    사용자는 상세페이지의 제작사 약관을 확인하여 판단해야 함.
    """
    is_commercial_free = all(permissions[k] == "allowed" for k in _COMMERCIAL_KEYS)
    allow_embedding = permissions.get("embedding")
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
def classify(
    parse_ok: bool,
    price: Optional[float],
    perms: Optional[dict[str, Optional[str]]],
    official_url: Optional[str] = None,
) -> str:
    """자동 발행 게이트(D6). 상업 4카테고리 전부 allowed + price 정확히 0.0 + 파싱성공 + 공식URL 필수만 auto_safe."""
    if not official_url:
        return "needs_review"
    if not parse_ok or perms is None:
        return "needs_review"
    # price가 None이거나 0이 아니면 needs_review (0.5, -0.1 등은 needs_review)
    if price is None or price != 0.0:
        return "needs_review"
    if all(perms[k] == "allowed" for k in _COMMERCIAL_KEYS):
        return "auto_safe"
    return "needs_review"


# Task 7: 제안 조립
def build_proposal(font_id: str, slug: str, source_url: str, official_url: str, html: str) -> dict:  # type: ignore[type-arg]
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
        raw_permissions_data: dict[str, Optional[str]] = perms
    except EnrichParseError as exc:
        logger.warning("허용표 파싱 실패(slug=%s): %s", slug, exc)
        perms, parse_status = None, "failed"
        raw_permissions_data = {"_parse_error": str(exc)}

    classification = classify(parse_status == "parsed", price, perms, official_url)
    rows = (map_license_rows(perms, license_type) if perms is not None
            else {"is_commercial_free": None, "allow_embedding": None,
                  "allow_redistribute": None, "allow_modify": None, "license_note": None})

    proposal = {
        "font_id": font_id,
        "slug": slug,
        "source_url": source_url,
        "raw_permissions": raw_permissions_data,
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


def _font_update_for(rows: dict, license_type: str, weights: list[int],  # type: ignore[type-arg]
                     italic: bool, official_url: str) -> dict:  # type: ignore[type-arg]
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



def _derive_slug(name_ko: str, name_en: Optional[str]) -> str:
    """눈누 폰트명에서 슬러그를 도출한다.

    규칙: name_en이 있으면 clean + build_slug, 없으면 name_ko를 소문자-하이픈정규화.
    공유 함수 derive_noonnu_slug에 위임(import/enrich 정합).

    Args:
        name_ko: 한글 폰트명.
        name_en: 영문 폰트명 (선택사항).

    Returns:
        URL 슬러그.
    """
    return derive_noonnu_slug(name_ko, name_en)


def enrich_fonts(
    seed_path: Optional[Path] = None,
    supabase_url: Optional[str] = None,
    secret_key: Optional[str] = None,
    *,
    limit: Optional[int] = None,
    only_slug: Optional[str] = None,
) -> tuple[int, int, int]:
    """seed의 눈누 URL을 재방문해 제안 적재 + auto_safe 자동 발행.
    
    Args:
        seed_path: seed JSON 경로 (기본: output/tier-b-noonnu-seed.json).
        supabase_url: Supabase URL.
        secret_key: Supabase secret key.
        limit: 처리할 최대 폰트 수 (None=모두).
        only_slug: 특정 슬러그만 처리 (None=모두).
    
    Returns:
        (auto_published, proposed, skipped) 튜플.
    
    Raises:
        NoonnuEnrichError: 파일/DB 오류.
    """
    if seed_path is None:
        seed_path = Path("output") / "tier-b-noonnu-seed.json"
    
    if not supabase_url or not secret_key:
        raise NoonnuEnrichError(
            "SUPABASE_URL과 SUPABASE_SECRET_KEY가 필수입니다"
        )
    
    try:
        with open(seed_path, encoding="utf-8") as f:
            doc = NoonnuSeedOutput(**json.load(f))
    except FileNotFoundError as exc:
        raise NoonnuEnrichError(f"seed JSON 없음: {seed_path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise NoonnuEnrichError(f"seed JSON 파싱 오류: {exc}") from exc
    
    client = create_client(supabase_url, secret_key)
    schema = client.schema("fontagit")
    
    try:
        robots_response = httpx.get(_ROBOTS_URL, timeout=10.0)
        robots_response.raise_for_status()
        robots_policy = _parse_robots_policy(robots_response.text)
    except httpx.HTTPError as exc:
        raise NoonnuEnrichError(f"robots.txt fetch 실패: {exc}") from exc
    
    auto, proposed, skipped = 0, 0, 0
    records = doc.records[:limit] if limit else doc.records
    
    with httpx.Client(follow_redirects=True) as http:
        for rec in records:
            slug = _derive_slug(rec.name_ko, rec.name_en)
            
            if only_slug and slug != only_slug:
                continue
            
            try:
                result: Any = (schema.table("fonts")
                         .select("id,status,official_url")
                         .eq("slug", slug)
                         .maybe_single()
                         .execute())
                font: Any = result.data if result else None
            except Exception as exc:
                logger.warning("폰트 조회 실패(slug=%s): %s", slug, exc.__class__.__name__)
                skipped += 1
                continue
            
            if not font or font.get("status") == "published":
                skipped += 1
                continue
            
            # SSRF 방어: 눈누 도메인만 허용
            if not re.match(r"^https://noonnu\.cc/font_page/\d+$", rec.source_page):
                logger.warning("SSRF 차단 - 허용되지 않은 URL(slug=%s): %s", slug, rec.source_page)
                skipped += 1
                continue

            if not robots_policy.can_fetch(_ROBOT_USER_AGENT, rec.source_page):
                logger.info("robots.txt 차단(slug=%s)", slug)
                skipped += 1
                continue

            time.sleep(_REQUEST_DELAY)
            try:
                html_response = http.get(
                    rec.source_page,
                    headers={"User-Agent": _USER_AGENT},
                    timeout=10.0,
                )
                html_response.raise_for_status()
                html = html_response.text
            except httpx.HTTPError as exc:
                logger.warning("HTML fetch 실패(slug=%s): %s", slug, exc.__class__.__name__)
                skipped += 1
                continue
            
            try:
                proposal = build_proposal(
                    font["id"],
                    slug,
                    rec.source_page,
                    font.get("official_url") or rec.official_url,
                    html,
                )
            except Exception as exc:
                logger.warning("제안 생성 실패(slug=%s): %s", slug, exc.__class__.__name__)
                skipped += 1
                continue
            
            fu = proposal.pop("_font_update")

            # S4: auto 경로 순서 재배치 - 폰트 발행을 먼저, 제안 저장을 나중에
            # 이렇게 하면 폰트 발행 실패 시 auto_published 제안이 남지 않음 (부분 원자성)
            if fu is not None:
                fu["verified_at"] = datetime.now(timezone.utc).isoformat()
                try:
                    schema.table("fonts").update(fu).eq("id", font["id"]).execute()
                except Exception as exc:
                    logger.warning("폰트 발행 실패(slug=%s): %s", slug, exc.__class__.__name__)
                    skipped += 1
                    continue

                # 폰트 발행 성공 후 제안 저장
                try:
                    schema.table("license_proposals").upsert(
                        proposal, on_conflict="font_id"
                    ).execute()
                    auto += 1
                    logger.info("자동발행 완료: %s", slug)
                except Exception as exc:
                    logger.warning("proposal 저장 실패(slug=%s): %s", slug, exc.__class__.__name__)
                    skipped += 1
            else:
                # proposed 경로: 검수 필요
                try:
                    schema.table("license_proposals").upsert(
                        proposal, on_conflict="font_id"
                    ).execute()
                    proposed += 1
                    logger.info("검수 제안 추가: %s", slug)
                except Exception as exc:
                    logger.warning("proposal 저장 실패(slug=%s): %s", slug, exc.__class__.__name__)
                    skipped += 1
    
    logger.info("enrich 완료: 자동발행 %d, 검수대기 %d, 스킵 %d", auto, proposed, skipped)
    return auto, proposed, skipped
