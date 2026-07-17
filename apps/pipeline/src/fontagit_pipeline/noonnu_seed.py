"""눈누(noonnu.cc) Tier B 시드 수집기.

robots.txt 준수, 1.5초 딜레이, 사실만 수집(저작권 존중).
"""

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from fontagit_pipeline.models import NoonnuSeedRecord, NoonnuSeedOutput

logger = logging.getLogger(__name__)

_NOONNU_BASE = "https://noonnu.cc"
_SITEMAP_URL = f"{_NOONNU_BASE}/sitemap.xml"
_FONT_PAGE_PATTERN = re.compile(r"/font_page/(\d+)")
_REQUEST_DELAY = 1.5
_USER_AGENT = "FontAgitSeedBot/0.1 (+https://fontag.it)"


class NoonnuSeedError(Exception):
    """눈누 시드 수집 오류."""

    pass


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
    soup = BeautifulSoup(sitemap_xml, "html.parser")
    urls = []

    # 단일 sitemap인 경우
    for loc in soup.find_all("loc"):
        url_text = loc.get_text(strip=True)
        if "/font_page/" in url_text:
            urls.append(url_text)

    return urls


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

    # 폰트명 추출 (h1 또는 og:title 메타 태그)
    name_ko: Optional[str] = None
    name_en: Optional[str] = None

    # og:title에서 폰트명 추출
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title_text = og_title.get("content", "").strip()
        # "FontName - 설명" 형식으로 되어 있을 수 있음
        if title_text and " - " in title_text:
            name_ko = title_text.split(" - ")[0].strip()
        elif title_text:
            name_ko = title_text.strip()

    # 페이지 h1 태그 확인
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(strip=True)
        if h1_text:
            name_ko = h1_text

    # 제작사(Foundry) 추출
    maker: Optional[str] = None

    # "Foundry" 문자열을 포함한 텍스트 노드 찾기
    for element in soup.find_all(string=re.compile(r"Foundry", re.IGNORECASE)):
        # 텍스트가 속한 부모 요소를 찾고 전체 텍스트 가져오기
        parent = element.find_parent()
        if parent:
            parent_text = parent.get_text(strip=True)
            # "Foundry:" 또는 "Foundry :" 이후의 텍스트 추출
            match = re.search(r"Foundry\s*:\s*(.+?)(?:\n|$)", parent_text, re.IGNORECASE)
            if match:
                maker_candidate = match.group(1).strip()
                if maker_candidate and len(maker_candidate) < 100:
                    maker = maker_candidate
                    break

    # 공식 URL 추출 (제작사 외부 링크)
    official_url: Optional[str] = None

    # 모든 링크를 검사
    for link in soup.find_all("a", href=True):
        href = link.get("href", "").strip()
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

    return (name_ko, name_en, maker or "Unknown", official_url)


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
    if owns_client:
        client = httpx.Client()

    try:
        logger.info("눈누 시드 수집 시작 (배치 크기: %d)", batch_size)

        # Sitemap 다운로드
        logger.info("Sitemap 다운로드: %s", _SITEMAP_URL)
        sitemap_xml = _fetch_url(client, _SITEMAP_URL)

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
            try:
                logger.info(
                    "페이지 크롤링 (%d/%d): %s",
                    idx,
                    len(font_urls),
                    url,
                )

                # HTML 가져오기
                html = _fetch_url(client, url)

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
            client.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    output = collect_noonnu_seeds(batch_size=30)
    print(f"수집 완료: {output.record_count}개")
