"""눈누(noonnu.cc) Tier B 시드 수집기.

robots.txt 준수, 1.5초 딜레이, 사실만 수집(저작권 존중).
"""

import json
import logging
import re
import time
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from fontagit_pipeline.models import NoonnuSeedRecord, NoonnuSeedOutput

logger = logging.getLogger(__name__)

_NOONNU_BASE = "https://noonnu.cc"
_ROBOTS_URL = f"{_NOONNU_BASE}/robots.txt"
_SITEMAP_URL = f"{_NOONNU_BASE}/sitemap.xml"
_FONT_PAGE_PATTERN = re.compile(r"/font_page/(\d+)")
_REQUEST_DELAY = 1.5
_USER_AGENT = "FontAgitSeedBot/0.1 (+https://fontag.it)"
_ROBOT_USER_AGENT = "FontAgitSeedBot"


class NoonnuSeedError(Exception):
    """눈누 시드 수집 오류."""

    pass


def _parse_robots_policy(robots_text: str) -> RobotFileParser:
    """robots.txt 문자열을 URL 접근 정책으로 변환한다."""
    policy = RobotFileParser()
    policy.set_url(_ROBOTS_URL)
    policy.parse(robots_text.splitlines())
    return policy


def _fetch_url(client: httpx.Client, url: str, timeout: float = 10.0) -> str:
    """URL에서 HTML을 가져온다.

    Args:
        client: httpx 클라이언트.
        url: 요청 URL.
        timeout: 타임아웃 (초).

    Returns:
        응답 HTML 텍스트.

    Raises:
        NoonnuSeedError: HTTP 오류, 타임아웃 등.
    """
    try:
        response = client.get(
            url,
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=True,
        )
        response.raise_for_status()
        return response.text
    except httpx.HTTPError as exc:
        raise NoonnuSeedError(f"HTTP 오류 ({url}): {exc}") from exc


def _parse_sitemap_urls(sitemap_xml: str) -> list[str]:
    """Sitemap XML에서 폰트 페이지 URL을 파싱한다.

    Args:
        sitemap_xml: Sitemap XML 텍스트.

    Returns:
        /font_page/{id} URL 목록.
    """
    root = ElementTree.fromstring(sitemap_xml)
    urls: list[str] = []

    for loc in root.iter():
        if not loc.tag.endswith("loc"):
            continue
        url_text = (loc.text or "").strip()
        if "/font_page/" in url_text:
            urls.append(url_text)

    return urls


def _clean_font_name(value: str) -> str:
    """눈누 사이트 제목의 서비스명과 설명 접미사를 제거한다."""
    return re.split(r"\s*(?:\|\s*눈누|\s+-\s+)", value, maxsplit=1)[0].strip()


def _extract_font_data(
    html: str, source_url: str
) -> Optional[tuple[str, Optional[str], str, Optional[str]]]:
    """HTML에서 폰트 정보를 추출한다.

    폰트명(한글), 폰트명(영문), 제작사, 공식 URL을 추출한다.

    Args:
        html: 폰트 페이지 HTML.
        source_url: 원본 페이지 URL.

    Returns:
        (name_ko, name_en, maker, official_url) 튜플 또는 None(추출 실패).
    """
    soup = BeautifulSoup(html, "html.parser")

    # JSON-LD의 폰트명과 제작사를 최우선 사실값으로 사용한다.
    name_ko: Optional[str] = None
    name_en: Optional[str] = None
    maker: Optional[str] = None

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            document = json.loads(script.get_text(strip=True))
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = document if isinstance(document, list) else [document]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            if candidate.get("@type") != "SoftwareApplication":
                continue

            raw_name = candidate.get("name")
            creator = candidate.get("creator")
            if isinstance(raw_name, str):
                name_ko = _clean_font_name(raw_name)
            if isinstance(creator, dict) and isinstance(creator.get("name"), str):
                maker = creator["name"].strip()
            break

        if name_ko and maker:
            break

    if not name_ko:
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            name_ko = _clean_font_name(str(og_title.get("content", "")))

    if not name_ko:
        heading = soup.find(["h1", "h2"])
        if heading:
            heading_text = heading.get_text(strip=True)
            if heading_text:
                name_ko = _clean_font_name(heading_text)

    # 현재 눈누 화면의 "제작" 라벨 다음 값을 대체 경로로 사용한다.
    if not maker:
        maker_label = soup.find(string=re.compile(r"^\s*제작\s*$"))
        if maker_label and maker_label.parent:
            maker_value = maker_label.parent.find_next_sibling()
            if maker_value:
                maker = maker_value.get_text(strip=True) or None

    if not maker:
        for element in soup.find_all(string=re.compile(r"Foundry", re.IGNORECASE)):
            parent = element.find_parent()
            if parent:
                parent_text = parent.get_text(strip=True)
                match = re.search(
                    r"Foundry\s*:\s*(.+?)(?:\n|$)",
                    parent_text,
                    re.IGNORECASE,
                )
                if match:
                    maker_candidate = match.group(1).strip()
                    if maker_candidate and len(maker_candidate) < 100:
                        maker = maker_candidate
                        break

    # 공식 URL 추출 (제작사 외부 링크)
    official_url: Optional[str] = None

    # 모든 링크를 검사
    for link in soup.find_all("a", href=True):
        href_value = link.get("href")
        if not isinstance(href_value, str):
            continue
        href = href_value.strip()
        if not href or href.startswith("#"):
            continue

        # noonnu 내부 링크 제외
        if "noonnu.cc" in href or href.startswith("/"):
            continue

        # 절대 URL인지 확인
        if href.startswith("http"):
            # 제작사 공식 사이트/SNS 등
            if (
                any(
                    domain in href
                    for domain in [
                        ".kr",
                        ".com",
                        "behance",
                        "instagram",
                        "github",
                        "dribbble",
                    ]
                )
                and official_url is None
            ):
                official_url = href
                break

    if not name_ko or not maker:
        return None

    return (name_ko, name_en, maker, official_url)


def collect_noonnu_seeds(
    batch_size: int = 30,
    output_path: Optional[Path] = None,
    client: Optional[httpx.Client] = None,
) -> NoonnuSeedOutput:
    """눈누 시드를 수집한다.

    Args:
        batch_size: 수집할 폰트 개수.
        output_path: 결과 저장 경로 (기본: output/tier-b-noonnu-seed.json).
        client: httpx 클라이언트 (자체 생성 시 None).

    Returns:
        수집 결과 NoonnuSeedOutput.

    Raises:
        NoonnuSeedError: 수집 실패.
    """
    if output_path is None:
        output_path = Path("output") / "tier-b-noonnu-seed.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    owns_client = client is None
    active_client = client or httpx.Client()

    try:
        logger.info("눈누 시드 수집 시작 (배치 크기: %d)", batch_size)

        logger.info("robots.txt 확인: %s", _ROBOTS_URL)
        robots_policy = _parse_robots_policy(_fetch_url(active_client, _ROBOTS_URL))
        if not robots_policy.can_fetch(_ROBOT_USER_AGENT, _SITEMAP_URL):
            raise NoonnuSeedError("robots.txt가 sitemap 수집을 허용하지 않음")

        # Sitemap 다운로드
        logger.info("Sitemap 다운로드: %s", _SITEMAP_URL)
        sitemap_xml = _fetch_url(active_client, _SITEMAP_URL)

        # 폰트 URL 파싱
        font_urls = _parse_sitemap_urls(sitemap_xml)
        logger.info("발견된 폰트 URL: %d개", len(font_urls))

        if not font_urls:
            raise NoonnuSeedError("Sitemap에서 폰트 URL을 찾을 수 없음")

        # 배치 크기만큼 URL 자르기
        font_urls = font_urls[:batch_size]
        logger.info("수집 대상: %d개 (배치 크기)", len(font_urls))

        records: list[NoonnuSeedRecord] = []
        skip_reasons: dict[str, int] = {}
        collected_at = datetime.now(timezone.utc).isoformat()

        for idx, url in enumerate(font_urls, 1):
            if not robots_policy.can_fetch(_ROBOT_USER_AGENT, url):
                skip_reasons["robots_disallowed"] = (
                    skip_reasons.get("robots_disallowed", 0) + 1
                )
                logger.warning("robots.txt 수집 제외: %s", url)
                continue

            try:
                logger.info(
                    "페이지 크롤링 (%d/%d): %s",
                    idx,
                    len(font_urls),
                    url,
                )

                # HTML 가져오기
                html = _fetch_url(active_client, url)

                # 데이터 추출
                result = _extract_font_data(html, url)
                if result is None:
                    skip_reasons["extraction_failed"] = (
                        skip_reasons.get("extraction_failed", 0) + 1
                    )
                    logger.warning("데이터 추출 실패: %s", url)
                    time.sleep(_REQUEST_DELAY)
                    continue

                name_ko, name_en, maker, official_url = result

                # 필수 필드 검증
                if not name_ko or not maker:
                    skip_reasons["missing_required_fields"] = (
                        skip_reasons.get("missing_required_fields", 0) + 1
                    )
                    logger.warning(
                        "필수 필드 누락 (name_ko=%s, maker=%s): %s",
                        name_ko,
                        maker,
                        url,
                    )
                    time.sleep(_REQUEST_DELAY)
                    continue

                # 레코드 생성
                record = NoonnuSeedRecord(
                    name_ko=name_ko,
                    name_en=name_en,
                    maker=maker,
                    official_url=official_url or url,
                    source_page=url,
                    collected_at=collected_at,
                )

                records.append(record)
                logger.info("수집 성공: %s (제작사: %s)", name_ko, maker)

            except NoonnuSeedError as exc:
                skip_reasons["http_error"] = (
                    skip_reasons.get("http_error", 0) + 1
                )
                logger.warning("HTTP 오류: %s", exc)
            except Exception as exc:
                skip_reasons["unknown_error"] = (
                    skip_reasons.get("unknown_error", 0) + 1
                )
                logger.warning("예상치 못한 오류: %s", exc)

            # 요청 딜레이
            time.sleep(_REQUEST_DELAY)

        logger.info(
            "수집 완료: %d개 성공, %d개 스킵",
            len(records),
            len(font_urls) - len(records),
        )

        # 결과 문서 생성
        output_doc = NoonnuSeedOutput(
            generated_at=collected_at,
            record_count=len(records),
            records=records,
            skipped_count=len(font_urls) - len(records),
            skip_reasons=skip_reasons,
        )

        # JSON 저장
        output_json = output_path.with_suffix(".json")
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(output_doc.model_dump(), f, ensure_ascii=False, indent=2)

        logger.info("결과 저장: %s", output_json)

        return output_doc

    finally:
        if owns_client:
            active_client.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    output = collect_noonnu_seeds(batch_size=30)
    print(f"수집 완료: {output.record_count}개")
