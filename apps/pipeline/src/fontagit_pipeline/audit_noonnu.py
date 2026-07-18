"""눈누 상세 페이지에서 감사에 필요한 사실만 추출한다."""

from __future__ import annotations

import hashlib
import re
from typing import Literal
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field


DownloadStatus = Literal["pending", "verified", "needs_review", "broken"]
ExtractorKind = Literal["deterministic", "llm"]


class NoonnuFontSnapshot(BaseModel):
    """눈누 상세 영역에서 결정론적으로 뽑은 감사용 사실값."""

    source_url: str
    page_id: str | None = None
    name_ko: str | None = None
    name_en: str | None = None
    foundry: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    price: str | None = None
    download_candidates: list[str] = Field(default_factory=list)
    download_status: DownloadStatus = "needs_review"
    license_text: str | None = None
    license_permissions: dict[str, str] = Field(default_factory=dict)
    font_face_css: list[str] = Field(default_factory=list)
    font_file_candidates: list[str] = Field(default_factory=list)
    weights: list[int] = Field(default_factory=list)
    styles: list[str] = Field(default_factory=list)
    evidence_locations: dict[str, str] = Field(default_factory=dict)
    raw_text: str | None = None
    raw_sha256: str | None = None
    global_social_links: list[str] = Field(default_factory=list)
    license_id: str | None = None
    license_version: str | None = None
    extractor: ExtractorKind = "deterministic"
    template_selector: str | None = None
    template_version: str | None = None
    finding_status: str | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    reviewed_permissions: dict[str, str | None] = Field(default_factory=dict)


def extract_noonnu_font(html: str, source_url: str) -> NoonnuFontSnapshot:
    """폰트 상세 영역에서만 다운로드·라이선스·메타데이터 후보를 추출한다.

    눈누는 참고 출처이므로 내려받기 URL과 허용표를 곧바로 검증된 사실로 만들지
    않는다. 원문 보관 정책 기본값은 structured-only라 HTML 원문은 반환하지 않는다.
    """
    soup = BeautifulSoup(html, "html.parser")
    detail = soup.select_one("[data-font-detail]")
    if not isinstance(detail, Tag):
        detail = soup.find("article")

    raw_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
    if not isinstance(detail, Tag):
        return NoonnuFontSnapshot(source_url=source_url, raw_sha256=raw_sha256)

    evidence: dict[str, str] = {}
    name_ko = _text(detail.select_one("[data-font-name]")) or _heading_text(detail)
    if name_ko:
        evidence["name_ko"] = "[data-font-name]"
    name_en = _text(detail.select_one("[data-font-name-en]"))
    foundry = _text(detail.select_one("[data-foundry]")) or _label_value(detail, "제작")
    if foundry:
        evidence["foundry"] = "[data-foundry]"
    category = _text(detail.select_one("[data-category]")) or _label_value(detail, "분류")
    tags = _texts(detail.select("[data-tags] li"))
    price = _text(detail.select_one("[data-price]"))

    downloads = _download_candidates(detail, source_url)
    if downloads:
        evidence["download_candidates"] = "[data-download-cta]"

    license_element = detail.select_one("[data-license-body]")
    license_text = _text(license_element)
    permissions = _license_permissions(license_element)
    if license_text:
        evidence["license_text"] = "[data-license-body]"

    font_face_css, file_urls, weights, styles = _font_face_metadata(detail, source_url)
    if font_face_css:
        evidence["font_face_css"] = "style"

    return NoonnuFontSnapshot(
        source_url=source_url,
        page_id=_page_id(source_url),
        name_ko=name_ko,
        name_en=name_en,
        foundry=foundry,
        category=category,
        tags=tags,
        price=price,
        download_candidates=downloads,
        download_status="needs_review",
        license_text=license_text,
        license_permissions=permissions,
        font_face_css=font_face_css,
        font_file_candidates=file_urls,
        weights=weights,
        styles=styles,
        evidence_locations=evidence,
        raw_text=None,
        raw_sha256=raw_sha256,
    )


def _text(element: Tag | None) -> str | None:
    if element is None:
        return None
    value = " ".join(element.get_text(" ", strip=True).split())
    return value or None


def _texts(elements: list[Tag]) -> list[str]:
    values = [_text(element) for element in elements]
    return [value for value in values if value is not None]


def _heading_text(detail: Tag) -> str | None:
    heading = detail.find(["h1", "h2"])
    return _text(heading if isinstance(heading, Tag) else None)


def _label_value(detail: Tag, label: str) -> str | None:
    label_node = detail.find(string=re.compile(rf"^\s*{re.escape(label)}\s*$"))
    if label_node is None or not isinstance(label_node.parent, Tag):
        return None
    sibling = label_node.parent.find_next_sibling()
    return _text(sibling if isinstance(sibling, Tag) else None)


def _download_candidates(detail: Tag, source_url: str) -> list[str]:
    candidates: list[str] = []
    for link in detail.select("[data-download-cta][href]"):
        href = link.get("href")
        if isinstance(href, str):
            absolute = _external_http_url(href, source_url)
            if absolute and absolute not in candidates:
                candidates.append(absolute)
    return candidates


def _external_http_url(href: str, source_url: str) -> str | None:
    absolute = urljoin(source_url, href.strip())
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    return absolute


def _license_permissions(license_element: Tag | None) -> dict[str, str]:
    if license_element is None:
        return {}
    extracted: dict[str, str] = {}
    for row in license_element.select("[data-license-permissions] tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        name = _text(cells[0])
        status = _text(cells[-1])
        if name and status and name != "항목":
            extracted[name] = status
    return extracted


def _font_face_metadata(detail: Tag, source_url: str) -> tuple[list[str], list[str], list[int], list[str]]:
    blocks: list[str] = []
    files: list[str] = []
    weights: set[int] = set()
    styles: set[str] = set()
    for style in detail.find_all("style"):
        css = style.get_text("\n", strip=True)
        for block in re.findall(r"@font-face\s*\{.*?\}", css, flags=re.DOTALL | re.IGNORECASE):
            blocks.append(block)
            for raw_url in re.findall(r"url\(\s*['\"]?([^'\")\s]+)", block):
                candidate = _external_http_url(raw_url, source_url)
                if candidate and candidate not in files:
                    files.append(candidate)
            for raw_weight in re.findall(r"font-weight\s*:\s*(\d{3})", block, flags=re.IGNORECASE):
                weights.add(int(raw_weight))
            style_match = re.search(r"font-style\s*:\s*([a-z-]+)", block, flags=re.IGNORECASE)
            if style_match:
                styles.add(style_match.group(1).lower())
    return blocks, files, sorted(weights), sorted(styles)


def _page_id(source_url: str) -> str | None:
    match = re.search(r"/font_page/(\d+)(?:/|$|[?#])", source_url)
    return match.group(1) if match else None
