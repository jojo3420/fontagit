"""눈누에서 재추출한 공식 URL과 DB 값을 대조해 판정한다.

네트워크와 DB를 모르는 순수 함수만 둔다. 실행은 noonnu_url_scan이 맡는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot

Classification = Literal["match", "mismatch", "no_container", "no_link"]
RecommendedAction = Literal["auto_fix_safe", "manual_review", "nullify", "keep"]
ContaminationType = Literal[
    "noonnu_social", "noonnu_internal", "unrelated_external", "shortener", "none"
]

_SOCIAL_HOSTS = (
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "pinterest.com",
    "threads.net",
)
_SHORTENER_HOSTS = ("bit.ly", "t.co", "goo.gl", "han.gl", "vo.la", "url.kr")
_NOONNU_HOSTS = ("noonnu.cc",)
_DOWNLOAD_ANCHOR_PATTERN = re.compile(r"다운로드|공식|홈페이지|바로가기|download|official", re.IGNORECASE)
_NON_WORD_PATTERN = re.compile(r"[^0-9a-z가-힣]+")


@dataclass(frozen=True)
class UrlAuditVerdict:
    """폰트 1종에 대한 대조 판정 결과."""

    classification: Classification
    recommended_action: RecommendedAction
    contamination_type: ContaminationType
    new_official_url: str | None
    evidence: str


def _host(url: str) -> str:
    """URL에서 소문자 호스트를 뽑는다."""
    return urlparse(url).netloc.lower()


def _host_matches(url: str, names: tuple[str, ...]) -> bool:
    """호스트가 주어진 도메인 목록에 속하는지 판정한다."""
    host = _host(url)
    return any(host == name or host.endswith(f".{name}") for name in names)


def _classify_contamination(url: str | None) -> ContaminationType:
    """URL이 어떤 종류의 오염인지 분류한다."""
    if url is None:
        return "none"
    if _host_matches(url, _NOONNU_HOSTS):
        return "noonnu_internal"
    if _host_matches(url, _SHORTENER_HOSTS):
        return "shortener"
    if _host_matches(url, _SOCIAL_HOSTS):
        return "noonnu_social"
    return "unrelated_external"


def _foundry_matches_host(foundry: str | None, url: str) -> bool:
    """제작사명이 도메인 문자열에 나타나는지 본다.

    영문 제작사명은 도메인에 그대로 들어가는 경우가 많아 근거로 쓸 만하다.
    한글 제작사명은 매칭되지 않는 것이 정상이므로 다른 근거로 보완한다.
    """
    if not foundry:
        return False
    normalized = _NON_WORD_PATTERN.sub("", foundry.lower())
    if len(normalized) < 3:
        return False
    host = _host(url).replace("-", "").replace(".", "")
    return normalized in host


def judge_official_url(
    snapshot: NoonnuFontSnapshot | None,
    db_official_url: str | None,
    db_license_source_url: str | None,
) -> UrlAuditVerdict:
    """재추출 스냅샷과 DB 값을 대조해 판정과 조치 권고를 낸다.

    Args:
        snapshot: 눈누 상세 재추출 결과. 파싱 실패 시 None.
        db_official_url: 현재 DB의 official_url.
        db_license_source_url: 현재 DB의 license_source_url.

    Returns:
        판정, 조치 권고, 오염 유형, 새 URL, 근거 문자열.
    """
    if snapshot is None:
        return UrlAuditVerdict(
            classification="no_container",
            recommended_action="keep",
            contamination_type=_classify_contamination(db_official_url),
            new_official_url=None,
            evidence="상세 영역 파싱 실패로 판단 근거 없음",
        )

    new_url = snapshot.official_url
    db_contamination = _classify_contamination(db_official_url)

    if new_url is None:
        action: RecommendedAction = "keep" if db_official_url is None else "nullify"
        return UrlAuditVerdict(
            classification="no_link",
            recommended_action=action,
            contamination_type=db_contamination,
            new_official_url=None,
            evidence="상세 영역에 외부 제작사 링크 없음",
        )

    if new_url == db_official_url and db_official_url == db_license_source_url:
        return UrlAuditVerdict(
            classification="match",
            recommended_action="keep",
            contamination_type="none",
            new_official_url=new_url,
            evidence="재추출 값과 DB 값 일치",
        )

    new_contamination = _classify_contamination(new_url)
    if new_contamination in ("noonnu_social", "noonnu_internal", "shortener"):
        return UrlAuditVerdict(
            classification="mismatch",
            recommended_action="nullify",
            contamination_type=db_contamination,
            new_official_url=None,
            evidence=f"재추출 값도 신뢰 불가({new_contamination})",
        )

    anchor_text = snapshot.official_url_anchor_text or ""
    anchor_ok = bool(_DOWNLOAD_ANCHOR_PATTERN.search(anchor_text))
    foundry_ok = _foundry_matches_host(snapshot.foundry, new_url)

    if anchor_ok or foundry_ok:
        reasons = []
        if anchor_ok:
            reasons.append(f"앵커 텍스트 '{anchor_text}'")
        if foundry_ok:
            reasons.append(f"제작사명 '{snapshot.foundry}' 도메인 매칭")
        return UrlAuditVerdict(
            classification="mismatch",
            recommended_action="auto_fix_safe",
            contamination_type=db_contamination,
            new_official_url=new_url,
            evidence=" + ".join(reasons),
        )

    return UrlAuditVerdict(
        classification="mismatch",
        recommended_action="manual_review",
        contamination_type=db_contamination,
        new_official_url=new_url,
        evidence=f"근거 약함: 앵커 '{anchor_text}', 제작사 '{snapshot.foundry}'",
    )
