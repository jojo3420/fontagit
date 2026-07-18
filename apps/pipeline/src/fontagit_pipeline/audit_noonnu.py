"""눈누 상세 페이지에서 감사에 필요한 사실만 추출한다."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Literal
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field


DownloadStatus = Literal["pending", "verified", "needs_review", "broken"]
ExtractorKind = Literal["deterministic", "llm"]
_FONT_EXTENSIONS = (".woff", ".woff2", ".ttf", ".otf")


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
    """현재 눈누 상세 구조에서 상세 한 건만 추출한다.

    눈누는 참고 출처이므로 다운로드 링크와 라이선스 표를 검증된 사실로
    승격하지 않는다. 원문 보관 기본값은 structured-only다.
    """
    soup = BeautifulSoup(html, "html.parser")
    detail = _detail_root(soup)
    application, application_location = _software_application(soup, source_url)
    raw_sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()

    evidence: dict[str, str] = {}
    name_ko = _json_text(application, "name")
    if name_ko:
        evidence["name_ko"] = f"{application_location}.name"
    else:
        name_node = detail.find(["h1", "h2"])
        name_ko = _text(name_node if isinstance(name_node, Tag) else None)
        if name_ko and isinstance(name_node, Tag):
            evidence["name_ko"] = _selector_path(name_node)

    foundry = _json_nested_text(application, "creator", "name")
    if foundry:
        evidence["foundry"] = f"{application_location}.creator.name"
    else:
        foundry, foundry_node = _label_value(detail, ("제작",))
        if foundry and foundry_node is not None:
            evidence["foundry"] = _selector_path(foundry_node)

    category, category_node = _label_value(detail, ("형태", "분류"))
    if category and category_node is not None:
        evidence["category"] = _selector_path(category_node)

    tags, tag_nodes = _tag_values(detail)
    if tags:
        evidence["tags"] = ", ".join(_selector_path(node) for node in tag_nodes)

    price = _json_nested_text(application, "offers", "price")
    if price is not None:
        evidence["price"] = f"{application_location}.offers.price"

    downloads, download_nodes = _download_candidates(detail, source_url)
    if downloads:
        evidence["download_candidates"] = ", ".join(
            _selector_path(node) for node in download_nodes
        )

    license_element = _section_after_heading(detail, "라이선스 본문", "article")
    license_text = _text(license_element)
    if license_text and license_element is not None:
        evidence["license_text"] = _selector_path(license_element)

    license_table = _section_after_heading(detail, "라이선스 요약표", "table")
    permissions = _license_permissions(license_table)
    if permissions and license_table is not None:
        evidence["license_permissions"] = _selector_path(license_table)

    font_face_css, file_urls, weights, styles, style_nodes = _font_face_metadata(
        detail, source_url
    )
    if font_face_css:
        style_locations = ", ".join(_selector_path(node) for node in style_nodes)
        evidence["font_face_css"] = style_locations
        evidence["font_file_candidates"] = f"{style_locations} @font-face src"
        evidence["weights"] = f"{style_locations} @font-face font-weight"
        evidence["styles"] = f"{style_locations} @font-face font-style"

    return NoonnuFontSnapshot(
        source_url=source_url,
        page_id=_page_id(source_url),
        name_ko=name_ko,
        name_en=None,
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


def _detail_root(soup: BeautifulSoup) -> Tag:
    current = [
        node
        for node in soup.select(".noon-page-content")
        if isinstance(node, Tag) and _is_current_detail(node)
    ]
    if current:
        if len(current) == 1:
            return current[0]
        raise ValueError("font detail region is ambiguous")

    marked = [node for node in soup.select("[data-font-detail]") if isinstance(node, Tag)]
    if len(marked) == 1:
        return marked[0]
    if len(marked) > 1:
        raise ValueError("font detail region is ambiguous")

    candidates = [
        article
        for article in soup.find_all("article")
        if isinstance(article, Tag) and _is_legacy_detail_article(article)
    ]
    if len(candidates) != 1:
        raise ValueError("font detail region is missing or ambiguous")
    return candidates[0]


def _is_current_detail(detail: Tag) -> bool:
    has_name = bool(detail.find(["h1", "h2"]))
    has_download = any(
        _text(link) == "다운로드 페이지로 이동" for link in detail.find_all("a")
    )
    has_license = detail.find(
        string=re.compile(r"^\s*라이선스 본문\s*$")
    ) is not None
    return has_name and has_download and has_license


def _is_legacy_detail_article(article: Tag) -> bool:
    has_name = bool(article.find(["h1", "h2"]))
    has_download = any(
        _text(link) == "다운로드 페이지로 이동" for link in article.find_all("a")
    )
    has_license = _section_after_heading(article, "라이선스 본문", "article") is not None
    return has_name and has_download and has_license


def _software_application(
    soup: BeautifulSoup, source_url: str
) -> tuple[Mapping[str, object], str]:
    matches: list[tuple[Mapping[str, object], str]] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        objects = payload if isinstance(payload, list) else [payload]
        for item in objects:
            if not isinstance(item, Mapping) or item.get("@type") != "SoftwareApplication":
                continue
            item_url = item.get("url")
            if isinstance(item_url, str) and _same_page(item_url, source_url):
                matches.append((item, _selector_path(script)))
    if len(matches) > 1:
        raise ValueError("SoftwareApplication JSON-LD is ambiguous")
    return matches[0] if matches else ({}, "json-ld:SoftwareApplication")


def _same_page(left: str, right: str) -> bool:
    left_parsed = urlparse(left)
    right_parsed = urlparse(right)
    return (
        left_parsed.hostname == right_parsed.hostname
        and left_parsed.path.rstrip("/") == right_parsed.path.rstrip("/")
    )


def _json_text(value: Mapping[str, object], key: str) -> str | None:
    item = value.get(key)
    return item.strip() or None if isinstance(item, str) else None


def _json_nested_text(value: Mapping[str, object], parent: str, key: str) -> str | None:
    nested = value.get(parent)
    return _json_text(nested, key) if isinstance(nested, Mapping) else None


def _text(element: Tag | None) -> str | None:
    if element is None:
        return None
    value = " ".join(element.get_text(" ", strip=True).split())
    return value or None


def _label_value(detail: Tag, labels: tuple[str, ...]) -> tuple[str | None, Tag | None]:
    for label in labels:
        label_node = detail.find(string=re.compile(rf"^\s*{re.escape(label)}\s*$"))
        if label_node is None or not isinstance(label_node.parent, Tag):
            continue
        sibling = label_node.parent.find_next_sibling()
        if isinstance(sibling, Tag):
            return _text(sibling), sibling
    return None, None


def _tag_values(detail: Tag) -> tuple[list[str], list[Tag]]:
    nodes = [
        node
        for node in detail.select('a[href^="/index?search="]')
        if isinstance(node, Tag) and _text(node)
    ]
    return [_text(node) or "" for node in nodes], nodes


def _download_candidates(detail: Tag, source_url: str) -> tuple[list[str], list[Tag]]:
    candidates: list[str] = []
    nodes: list[Tag] = []
    for link in detail.find_all("a", href=True):
        if _text(link) != "다운로드 페이지로 이동":
            continue
        href = link.get("href")
        if not isinstance(href, str):
            continue
        absolute = _http_url(href, source_url)
        if absolute and absolute not in candidates:
            candidates.append(absolute)
            nodes.append(link)
    return candidates, nodes


def _http_url(href: str, source_url: str) -> str | None:
    absolute = urljoin(source_url, href.strip())
    return absolute if urlparse(absolute).scheme in {"http", "https"} else None


def _section_after_heading(detail: Tag, title: str, tag_name: str) -> Tag | None:
    title_node = detail.find(string=re.compile(rf"^\s*{re.escape(title)}\s*$"))
    if title_node is None or not isinstance(title_node.parent, Tag):
        return None
    container = title_node.parent.parent
    if not isinstance(container, Tag):
        return None
    candidate = container.find(tag_name)
    return candidate if isinstance(candidate, Tag) else None


def _license_permissions(table: Tag | None) -> dict[str, str]:
    if table is None:
        return {}
    extracted: dict[str, str] = {}
    for row in table.select("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        name = _text(cells[0])
        status = _text(cells[-1])
        if name and status and name not in {"항목", "카테고리"}:
            extracted[name] = status
    return extracted


def _font_face_metadata(
    detail: Tag, source_url: str
) -> tuple[list[str], list[str], list[int], list[str], list[Tag]]:
    blocks: list[str] = []
    files: list[str] = []
    weights: set[int] = set()
    styles: set[str] = set()
    style_nodes: list[Tag] = []
    for style in detail.find_all("style"):
        css = style.get_text("\n", strip=True)
        matched_blocks = re.findall(
            r"@font-face\s*\{.*?\}", css, flags=re.DOTALL | re.IGNORECASE
        )
        if matched_blocks:
            style_nodes.append(style)
        for block in matched_blocks:
            blocks.append(block)
            for raw_url in re.findall(r"url\(\s*['\"]?([^'\")\s]+)", block):
                candidate = _font_file_url(raw_url, source_url)
                if candidate and candidate not in files:
                    files.append(candidate)
            weight_match = re.search(
                r"font-weight\s*:\s*(normal|bold|[1-9]00)", block, flags=re.IGNORECASE
            )
            if weight_match:
                raw_weight = weight_match.group(1).lower()
                weights.add(
                    {"normal": 400, "bold": 700}[raw_weight]
                    if raw_weight in {"normal", "bold"}
                    else int(raw_weight)
                )
            style_match = re.search(
                r"font-style\s*:\s*([a-z-]+)", block, flags=re.IGNORECASE
            )
            if style_match:
                styles.add(style_match.group(1).lower())
    return blocks, files, sorted(weights), sorted(styles), style_nodes


def _font_file_url(raw_url: str, source_url: str) -> str | None:
    candidate = _http_url(raw_url, source_url)
    if candidate is None:
        return None
    return candidate if urlparse(candidate).path.lower().endswith(_FONT_EXTENSIONS) else None


def _selector_path(node: Tag) -> str:
    parts: list[str] = []
    current: Tag | None = node
    while current is not None and current.name != "[document]":
        if current.get("id"):
            parts.append(f"{current.name}#{current.get('id')}")
            break
        siblings = (
            list(current.parent.find_all(current.name, recursive=False))
            if isinstance(current.parent, Tag)
            else []
        )
        position = siblings.index(current) + 1 if len(siblings) > 1 else None
        attributes = ""
        if current.name == "script" and current.get("type"):
            attributes = f'[type="{current.get("type")}"]'
        part = current.name + attributes + (f":nth-of-type({position})" if position else "")
        parts.append(part)
        current = current.parent if isinstance(current.parent, Tag) else None
    return " > ".join(reversed(parts))


def _page_id(source_url: str) -> str | None:
    match = re.search(r"/font_page/(\d+)(?:/|$|[?#])", source_url)
    return match.group(1) if match else None
