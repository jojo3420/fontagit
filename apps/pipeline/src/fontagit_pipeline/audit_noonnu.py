"""눈누 상세 페이지에서 감사에 필요한 사실만 추출한다."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
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
    review_evidence_id: str | None = None


def extract_noonnu_font(html: str, source_url: str) -> NoonnuFontSnapshot:
    """폰트 상세 영역에서만 다운로드·라이선스·메타데이터 후보를 추출한다.

    눈누는 참고 출처이므로 내려받기 URL과 허용표를 곧바로 검증된 사실로 만들지
    않는다. 원문 보관 정책 기본값은 structured-only라 HTML 원문은 반환하지 않는다.
    """
    soup = BeautifulSoup(html, "html.parser")
    detail = soup.select_one("[data-font-detail]")
    if not isinstance(detail, Tag):
        detail = _fallback_detail_article(soup)

    raw_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()
    if not isinstance(detail, Tag):
        raise ValueError("font detail article is missing or ambiguous")

    evidence: dict[str, str] = {}
    name_ko, name_selector = _field_text(
        detail,
        "[data-font-name]",
        _heading_text,
    )
    if name_ko:
        evidence["name_ko"] = name_selector
    name_en = _text(detail.select_one("[data-font-name-en]"))
    foundry, foundry_selector = _field_text(
        detail,
        "[data-foundry]",
        lambda element: _label_value(element, "제작"),
    )
    if foundry:
        evidence["foundry"] = foundry_selector
    category = _text(detail.select_one("[data-category]")) or _label_value(detail, "분류")[0]
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


def _field_text(
    detail: Tag,
    selector: str,
    fallback: Callable[[Tag], tuple[str | None, str]],
) -> tuple[str | None, str]:
    selected = detail.select_one(selector)
    value = _text(selected if isinstance(selected, Tag) else None)
    if value:
        return value, selector
    fallback_value, fallback_selector = fallback(detail)
    return fallback_value, fallback_selector


def _heading_text(detail: Tag) -> tuple[str | None, str]:
    heading = detail.find(["h1", "h2"])
    if not isinstance(heading, Tag):
        return None, "h1,h2"
    return _text(heading), heading.name


def _label_value(detail: Tag, label: str) -> tuple[str | None, str]:
    label_node = detail.find(string=re.compile(rf"^\s*{re.escape(label)}\s*$"))
    if label_node is None or not isinstance(label_node.parent, Tag):
        return None, f"label:{label}"
    sibling = label_node.parent.find_next_sibling()
    if not isinstance(sibling, Tag):
        return None, f"{label_node.parent.name} + *"
    return _text(sibling), f"{label_node.parent.name} + {sibling.name}"


def _fallback_detail_article(soup: BeautifulSoup) -> Tag | None:
    candidates = [
        article
        for article in soup.find_all("article")
        if isinstance(article, Tag) and _is_font_detail_article(article)
    ]
    if len(candidates) != 1:
        return None
    return candidates[0]


def _is_font_detail_article(article: Tag) -> bool:
    has_name = bool(article.select_one("[data-font-name]")) or bool(article.find("h1"))
    if not has_name:
        return False
    signals = (
        bool(article.select_one("[data-foundry]"))
        or _label_value(article, "제작")[0] is not None,
        bool(article.select_one("[data-download-cta][href]")),
        bool(article.select_one("[data-license-body]")),
        "@font-face" in article.get_text(),
    )
    return sum(signals) >= 2


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
                candidate = _font_file_url(raw_url, source_url)
                if candidate and candidate not in files:
                    files.append(candidate)
            for raw_weight in re.findall(r"font-weight\s*:\s*(\d{3})", block, flags=re.IGNORECASE):
                weights.add(int(raw_weight))
            style_match = re.search(r"font-style\s*:\s*([a-z-]+)", block, flags=re.IGNORECASE)
            if style_match:
                styles.add(style_match.group(1).lower())
    return blocks, files, sorted(weights), sorted(styles)


def _font_file_url(raw_url: str, source_url: str) -> str | None:
    candidate = _external_http_url(raw_url, source_url)
    if candidate is None:
        return None
    if urlparse(candidate).path.lower().endswith((".woff", ".woff2", ".ttf", ".otf")):
        return candidate
    return None


def _page_id(source_url: str) -> str | None:
    match = re.search(r"/font_page/(\d+)(?:/|$|[?#])", source_url)
    return match.group(1) if match else None
