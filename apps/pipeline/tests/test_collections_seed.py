# apps/pipeline/tests/test_collections_seed.py
"""collections_seed 후보 선정 로직 테스트."""

from fontagit_pipeline.collections_seed import (
    NEW_COLLECTIONS,
    pick_candidates,
    should_create,
)


def _font(slug: str, tags: list[str]) -> dict:
    return {"id": f"id-{slug}", "slug": slug, "name_ko": slug, "tags": tags}


def test_태그가_겹치는_폰트만_후보가_된다() -> None:
    fonts = [
        _font("a", ["귀여운"]),
        _font("b", ["제목용"]),
        _font("c", ["동글동글", "귀여운"]),
    ]
    spec = next(c for c in NEW_COLLECTIONS if c["slug"] == "cute-round")
    picked = pick_candidates(fonts, spec, limit=15)
    assert [f["slug"] for f in picked] == ["a", "c"]


def test_limit을_넘지_않는다() -> None:
    fonts = [_font(f"f{i}", ["레트로"]) for i in range(30)]
    spec = next(c for c in NEW_COLLECTIONS if c["slug"] == "retro-classic")
    assert len(pick_candidates(fonts, spec, limit=15)) == 15


def test_신규_컬렉션은_4종이고_sort_order가_기존_10개_뒤다() -> None:
    assert len(NEW_COLLECTIONS) == 4
    assert [c["sort_order"] for c in NEW_COLLECTIONS] == [10, 11, 12, 13]
    assert all(c["status"] == "published" for c in NEW_COLLECTIONS)


def test_후보가_최소_기준_미만이면_생성하지_않는다() -> None:
    assert should_create({"candidates": [{}] * 4}) is False
    assert should_create({"candidates": [{}] * 5}) is True
