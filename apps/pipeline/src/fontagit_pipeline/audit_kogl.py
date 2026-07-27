"""공공누리(KOGL) 유형 판별기. 유형 미검출-복수-부정문은 전부 needs_review 경로."""

from __future__ import annotations

import re

from pydantic import BaseModel

# "공공누리"를 포함하는 텍스트에서 모든 "제X유형" 패턴을 찾는다.
_KOGL_TYPE_RE = re.compile(r"제\s*(?P<n>[1-4])\s*유형")
_KOGL_CONTEXT_RE = re.compile(r"공공누리")
_NEGATION_MARKERS = ("아님", "아닙니다", "해당하지 않", "적용되지 않", "제외")
_NEGATION_WINDOW = 30

# 값 None = 그룹 승인 시 공식 기준(kogl.or.kr) 대조로 확정(스펙 S3 — 임베딩은 초안값 없음)
KOGL_PERMISSIONS: dict[int, dict[str, bool | str | None]] = {
    1: {
        "allow_commercial": True,
        "allow_modify": True,
        "allow_redistribute": True,
        "allow_font_sale": False,
        "allow_embedding": None,
        "attribution_requirement": "required",
    },
    2: {
        "allow_commercial": False,
        "allow_modify": True,
        "allow_redistribute": True,
        "allow_font_sale": False,
        "allow_embedding": None,
        "attribution_requirement": "required",
    },
    3: {
        "allow_commercial": True,
        "allow_modify": False,
        "allow_redistribute": True,
        "allow_font_sale": False,
        "allow_embedding": None,
        "attribution_requirement": "required",
    },
    4: {
        "allow_commercial": False,
        "allow_modify": False,
        "allow_redistribute": True,
        "allow_font_sale": False,
        "allow_embedding": None,
        "attribution_requirement": "required",
    },
}


class KoglDetection(BaseModel):
    """공공누리 유형 판별 결과."""

    kogl_type: int | None
    reason: str  # "ok" | "no_match" | "multiple" | "negation"


def detect_kogl_type(license_text: str) -> KoglDetection:
    """라이선스 본문에서 공공누리 유형을 판별한다. 애매하면 전부 미검출 처리.

    Args:
        license_text: 라이선스 텍스트

    Returns:
        KoglDetection: kogl_type은 1-4 또는 None, reason은 "ok", "no_match", "multiple", "negation"
    """
    text = license_text or ""

    # "공공누리"가 없으면 미검출
    if not _KOGL_CONTEXT_RE.search(text):
        return KoglDetection(kogl_type=None, reason="no_match")

    # "공공누리" 컨텍스트 내에서 모든 "제X유형" 찾기
    matches = list(_KOGL_TYPE_RE.finditer(text))
    if not matches:
        return KoglDetection(kogl_type=None, reason="no_match")

    # 여러 유형이 검출되면 복수 판정
    types = {int(m.group("n")) for m in matches}
    if len(types) > 1:
        return KoglDetection(kogl_type=None, reason="multiple")

    # 부정문 체크: 유형 이후 일정 거리 내에 부정 마커 있으면 negation
    for m in matches:
        tail = text[m.end() : m.end() + _NEGATION_WINDOW]
        if any(marker in tail for marker in _NEGATION_MARKERS):
            return KoglDetection(kogl_type=None, reason="negation")

    return KoglDetection(kogl_type=types.pop(), reason="ok")
