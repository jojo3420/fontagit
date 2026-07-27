"""공공누리(KOGL) 유형 판별기 테스트."""

import pytest

from fontagit_pipeline.audit_kogl import KOGL_PERMISSIONS, detect_kogl_type


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("본 저작물은 공공누리 제1유형에 따라 이용할 수 있습니다.", 1),
        ("공공누리 제 4 유형(출처표시+상업적 이용금지+변경금지)", 4),
    ],
)
def test_detect_kogl_type_ok(text: str, expected: int) -> None:
    """정상적인 KOGL 유형 감지를 확인한다."""
    result = detect_kogl_type(text)
    assert result.kogl_type == expected and result.reason == "ok"


def test_detect_kogl_type_edge_cases() -> None:
    """KOGL 유형 미검출-복수-부정문 케이스를 확인한다."""
    assert detect_kogl_type("자유 라이선스입니다").reason == "no_match"
    assert detect_kogl_type("공공누리 제1유형과 제3유형이 병기").reason == "multiple"
    assert detect_kogl_type("이 폰트는 공공누리 제1유형이 아닙니다").reason == "negation"
    assert detect_kogl_type("").reason == "no_match"


def test_kogl_permissions_table_complete() -> None:
    """4개 유형 전부, DB 권한 필드 5종 + attribution을 커버한다(스펙 S3 표)."""
    keys = {
        "allow_commercial",
        "allow_modify",
        "allow_redistribute",
        "allow_font_sale",
        "allow_embedding",
        "attribution_requirement",
    }
    for kogl_type in (1, 2, 3, 4):
        assert set(KOGL_PERMISSIONS[kogl_type]) == keys
    assert KOGL_PERMISSIONS[1]["allow_commercial"] is True
    assert KOGL_PERMISSIONS[2]["allow_commercial"] is False
    assert KOGL_PERMISSIONS[3]["allow_modify"] is False
    assert (
        KOGL_PERMISSIONS[4]["allow_commercial"] is False
        and KOGL_PERMISSIONS[4]["allow_modify"] is False
    )
    assert all(KOGL_PERMISSIONS[t]["allow_embedding"] is None for t in (1, 2, 3, 4))
