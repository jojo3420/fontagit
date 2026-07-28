"""눈누에서 재추출한 공식 URL과 DB 값을 대조해 판정한다.

네트워크와 DB를 모르는 순수 함수만 둔다. 실행은 noonnu_url_scan이 맡는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot, is_noonnu_account_url

Classification = Literal["match", "mismatch", "no_container", "no_link"]
RecommendedAction = Literal["auto_fix_safe", "manual_review", "nullify", "keep"]
ContaminationType = Literal[
    "noonnu_account",
    "noonnu_internal",
    "third_party_social",
    "unrelated_external",
    "shortener",
    "none",
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
_TWO_LEVEL_KR_SUFFIXES = frozenset({"co.kr", "or.kr", "go.kr", "ne.kr", "pe.kr", "re.kr", "ac.kr"})
# 이 카테고리는 재추출 값을 정답으로 채택하면 안 되는 신뢰 불가 유형이다.
# third_party_social은 별도 취급(manual_review)이라 여기 넣지 않는다.
_UNTRUSTED_CONTAMINATION_TYPES: tuple[ContaminationType, ...] = (
    "noonnu_account",
    "noonnu_internal",
    "shortener",
)
# unrelated_external은 눈누/SNS/단축 URL이 아닌 정상적인 외부 URL이라 오염이 아니다.
_CONTAMINATED_TYPES: tuple[ContaminationType, ...] = (
    "noonnu_account",
    "noonnu_internal",
    "third_party_social",
    "shortener",
)


@dataclass(frozen=True)
class UrlAuditVerdict:
    """폰트 1종에 대한 대조 판정 결과."""

    classification: Classification
    recommended_action: RecommendedAction
    official_url_contamination: ContaminationType
    license_source_url_contamination: ContaminationType
    new_official_url: str | None
    evidence: str


def _host(url: str) -> str:
    """URL에서 소문자 호스트를 뽑는다.

    netloc은 포트/사용자 정보가 섞여 호스트 판정을 어긋나게 하므로 hostname을 쓴다.
    """
    return (urlparse(url).hostname or "").lower()


def _host_matches(url: str, names: tuple[str, ...]) -> bool:
    """호스트가 주어진 도메인 목록에 속하는지 판정한다."""
    host = _host(url)
    return any(host == name or host.endswith(f".{name}") for name in names)


def _normalize_url(url: str) -> str:
    """URL 동일성 비교용으로 정규화한다.

    끝 슬래시 유무와 기본 포트(80/443) 명시 여부는 같은 주소를 가리키므로 흡수한다.
    """
    parsed = urlparse(url)
    default_port = {"http": 80, "https": 443}.get(parsed.scheme)
    port = parsed.port
    host = _host(url)
    netloc = host if port is None or port == default_port else f"{host}:{port}"
    path = parsed.path.rstrip("/") or "/"
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{netloc}{path}{query}"


def _urls_equal(left: str | None, right: str | None) -> bool:
    """두 URL이 정규화 후에도 같은 주소를 가리키는지 본다."""
    if left is None or right is None:
        return left == right
    return _normalize_url(left) == _normalize_url(right)


def _classify_contamination(url: str | None) -> ContaminationType:
    """URL이 어떤 종류의 오염인지 분류한다."""
    if url is None:
        return "none"
    if is_noonnu_account_url(url):
        return "noonnu_account"
    if _host_matches(url, _NOONNU_HOSTS):
        return "noonnu_internal"
    if _host_matches(url, _SHORTENER_HOSTS):
        return "shortener"
    if _host_matches(url, _SOCIAL_HOSTS):
        return "third_party_social"
    return "unrelated_external"


def _is_contaminated(contamination: ContaminationType) -> bool:
    """오염 유형이 실제로 문제 있는 값을 가리키는지 판정한다."""
    return contamination in _CONTAMINATED_TYPES


def _registrable_domain_label(host: str) -> str:
    """등록 가능한 도메인에서 조직명에 해당하는 라벨만 뽑는다(하이픈 제거).

    서브도메인과 co.kr류 2단계 국가 접미사를 매칭 대상에서 제외해,
    `naver.com`은 잡되 `naver-fake-site.com`처럼 이름만 비슷한 무관 도메인은 걸러낸다.
    """
    labels = [label for label in host.split(".") if label]
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0].replace("-", "")
    suffix_len = 2 if ".".join(labels[-2:]) in _TWO_LEVEL_KR_SUFFIXES else 1
    if len(labels) <= suffix_len:
        return labels[0].replace("-", "")
    return labels[-(suffix_len + 1)].replace("-", "")


def _foundry_matches_host(foundry: str | None, url: str) -> bool:
    """제작사명이 등록 가능한 도메인의 조직명 라벨과 정확히 일치하는지 본다.

    문자열 포함 비교는 `naver`가 `naver-fake-site.com`에도 걸리는 오탐을 낳으므로,
    등록 가능한 도메인 단위로 좁혀 정확히 일치할 때만 근거로 인정한다.
    한글 제작사명은 도메인에 그대로 나타나지 않는 것이 정상이라 매칭되지 않는다.
    """
    if not foundry:
        return False
    normalized = _NON_WORD_PATTERN.sub("", foundry.lower())
    if len(normalized) < 3:
        return False
    return normalized == _registrable_domain_label(_host(url))


def judge_official_url(
    snapshot: NoonnuFontSnapshot | None,
    db_official_url: str | None,
    db_license_source_url: str | None,
) -> UrlAuditVerdict:
    """재추출 스냅샷과 DB 값을 대조해 판정과 조치 권고를 낸다.

    오염 여부를 먼저 독립적으로 판정한 뒤에야 일치 여부를 본다. 순서를 뒤집으면
    official_url과 license_source_url이 똑같이 오염된 172종처럼 "재추출 값이
    DB 값과 같다"는 사실만으로 오염이 정상으로 통과하는 사고가 재발한다.

    Args:
        snapshot: 눈누 상세 재추출 결과. 파싱 실패 시 None.
        db_official_url: 현재 DB의 official_url.
        db_license_source_url: 현재 DB의 license_source_url.

    Returns:
        판정, 조치 권고, official_url/license_source_url 각각의 오염 유형,
        새 URL, 근거 문자열.
    """
    official_contamination = _classify_contamination(db_official_url)
    license_source_contamination = _classify_contamination(db_license_source_url)

    if snapshot is None:
        return UrlAuditVerdict(
            classification="no_container",
            recommended_action="keep",
            official_url_contamination=official_contamination,
            license_source_url_contamination=license_source_contamination,
            new_official_url=None,
            evidence="상세 영역 파싱 실패로 판단 근거 없음",
        )

    new_url = snapshot.official_url

    if new_url is None:
        db_contaminated = _is_contaminated(official_contamination)
        return UrlAuditVerdict(
            classification="no_link",
            recommended_action="nullify" if db_contaminated else "keep",
            official_url_contamination=official_contamination,
            license_source_url_contamination=license_source_contamination,
            new_official_url=None,
            evidence="상세 영역에 외부 제작사 링크 없음",
        )

    new_contamination = _classify_contamination(new_url)

    if new_contamination in _UNTRUSTED_CONTAMINATION_TYPES:
        db_contaminated = _is_contaminated(official_contamination)
        return UrlAuditVerdict(
            classification="mismatch" if db_contaminated else "no_link",
            recommended_action="nullify" if db_contaminated else "keep",
            official_url_contamination=official_contamination,
            license_source_url_contamination=license_source_contamination,
            new_official_url=None,
            evidence=f"재추출 값도 신뢰 불가({new_contamination})",
        )

    if new_contamination == "third_party_social":
        return UrlAuditVerdict(
            classification="mismatch",
            recommended_action="manual_review",
            official_url_contamination=official_contamination,
            license_source_url_contamination=license_source_contamination,
            new_official_url=new_url,
            evidence=f"재추출 값이 일반 SNS({new_url})라 사람 확인 필요",
        )

    if not _is_contaminated(official_contamination) and _urls_equal(new_url, db_official_url):
        return UrlAuditVerdict(
            classification="match",
            recommended_action="keep",
            official_url_contamination=official_contamination,
            license_source_url_contamination=license_source_contamination,
            new_official_url=new_url,
            evidence="재추출 값과 DB 값 일치",
        )

    anchor_text = snapshot.official_url_anchor_text or ""
    anchor_ok = bool(_DOWNLOAD_ANCHOR_PATTERN.search(anchor_text))
    foundry_ok = _foundry_matches_host(snapshot.foundry, new_url)

    if anchor_ok and foundry_ok:
        return UrlAuditVerdict(
            classification="mismatch",
            recommended_action="auto_fix_safe",
            official_url_contamination=official_contamination,
            license_source_url_contamination=license_source_contamination,
            new_official_url=new_url,
            evidence=f"앵커 텍스트 '{anchor_text}' + 제작사명 '{snapshot.foundry}' 도메인 매칭",
        )

    return UrlAuditVerdict(
        classification="mismatch",
        recommended_action="manual_review",
        official_url_contamination=official_contamination,
        license_source_url_contamination=license_source_contamination,
        new_official_url=new_url,
        evidence=f"근거 약함: 앵커 '{anchor_text}', 제작사 '{snapshot.foundry}'",
    )
