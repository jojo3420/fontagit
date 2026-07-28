# apps/pipeline/tests/test_recategorize.py
"""recategorize 매핑 규칙 테스트."""

from fontagit_pipeline.recategorize import plan_recategorization, resolve_category


def test_손글씨_태그는_손글씨로_교정() -> None:
    assert resolve_category(["캘리그라피", "귀여운"], "고딕") == "손글씨"
    assert resolve_category(["붓글씨"], "고딕") == "손글씨"
    assert resolve_category(["어른 손글씨"], "고딕") == "손글씨"


def test_명조_장식_태그_교정() -> None:
    assert resolve_category(["바탕체"], "고딕") == "명조"
    assert resolve_category(["고전체"], "고딕") == "명조"
    assert resolve_category(["장식체"], "고딕") == "장식"
    assert resolve_category(["레트로"], "고딕") == "장식"


def test_복수_매칭이면_우선순위_손글씨_장식_명조() -> None:
    assert resolve_category(["캘리그라피", "장식체"], "고딕") == "손글씨"
    assert resolve_category(["레트로", "바탕체"], "고딕") == "장식"


def test_매칭_없으면_현재_분류_유지() -> None:
    assert resolve_category(["귀여운", "제목용"], "고딕") == "고딕"
    assert resolve_category([], "명조") == "명조"
    assert resolve_category(None, "고딕") == "고딕"


def test_plan은_변경_행만_담고_분포를_집계한다() -> None:
    rows = [
        {"id": "1", "slug": "a", "tags": ["캘리그라피"], "category_ko": "고딕"},
        {"id": "2", "slug": "b", "tags": ["제목용"], "category_ko": "고딕"},
        {"id": "3", "slug": "c", "tags": ["바탕체"], "category_ko": "명조"},
    ]
    report = plan_recategorization(rows)
    assert len(report["changes"]) == 1
    change = report["changes"][0]
    assert change == {
        "id": "1",
        "slug": "a",
        "from": "고딕",
        "to": "손글씨",
        "matched_tags": ["캘리그라피"],
    }
    assert report["counts"] == {"total": 3, "changed": 1, "unchanged": 2}
    assert report["distribution_after"] == {"고딕": 1, "명조": 1, "손글씨": 1}
