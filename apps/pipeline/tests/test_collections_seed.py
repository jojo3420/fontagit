# apps/pipeline/tests/test_collections_seed.py
"""collections_seed 후보 선정 로직 테스트."""

from pathlib import Path

import httpx
import pytest

from fontagit_pipeline import collections_seed as cs
from fontagit_pipeline.collections_seed import (
    NEW_COLLECTIONS,
    insert_collection,
    pick_candidates,
    should_create,
)


def _font(slug: str, tags: list[str], category_ko: str = "고딕") -> dict:
    return {
        "id": f"id-{slug}",
        "slug": slug,
        "name_ko": slug,
        "tags": tags,
        "category_ko": category_ko,
    }


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


def test_분류가_허용목록에_없으면_태그가_맞아도_제외된다() -> None:
    """dev dry-run에서 발견된 문제 재현: 손글씨체가 제목용 임팩트 후보에 섞이면 안 된다."""
    fonts = [
        _font("handwriting-thick", ["두꺼운"], category_ko="손글씨"),
        _font("gothic-thick", ["두꺼운"], category_ko="고딕"),
    ]
    spec = next(c for c in NEW_COLLECTIONS if c["slug"] == "title-impact")
    picked = pick_candidates(fonts, spec, limit=15)
    assert [f["slug"] for f in picked] == ["gothic-thick"]


def test_spec에_categories가_없으면_태그만으로_고른다() -> None:
    fonts = [
        _font("x", ["귀여운"], category_ko="장식"),
        _font("y", ["제목용"], category_ko="고딕"),
    ]
    spec = {"tags": ["귀여운"]}
    picked = pick_candidates(fonts, spec, limit=15)
    assert [f["slug"] for f in picked] == ["x"]


def _make_insert_client(
    *, collection_exists: bool, items_exist: bool, calls: list[tuple[str, str]]
) -> httpx.Client:
    """collections/collection_items 엔드포인트를 흉내 내는 mock 클라이언트."""

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == "/rest/v1/collections" and request.method == "GET":
            return httpx.Response(200, json=[{"id": "col-1"}] if collection_exists else [])
        if path == "/rest/v1/collections" and request.method == "POST":
            return httpx.Response(201, json=[{"id": "col-1"}])
        if path == "/rest/v1/collection_items" and request.method == "GET":
            return httpx.Response(200, json=[{"font_id": "id-a"}] if items_exist else [])
        if path == "/rest/v1/collection_items" and request.method == "POST":
            return httpx.Response(201, json=[])
        raise AssertionError(f"unexpected request: {request.method} {path}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def _one_candidate_plan() -> dict:
    return {"candidates": [{"font_id": "id-a", "slug": "a", "name_ko": "a"}]}


def test_컬렉션이_없으면_컬렉션과_아이템을_모두_생성한다() -> None:
    calls: list[tuple[str, str]] = []
    client = _make_insert_client(collection_exists=False, items_exist=False, calls=calls)
    spec = next(c for c in NEW_COLLECTIONS if c["slug"] == "cute-round")
    ok = insert_collection(client, "https://x/rest/v1", {}, spec, _one_candidate_plan())
    assert ok is True
    assert ("POST", "/rest/v1/collections") in calls
    assert ("POST", "/rest/v1/collection_items") in calls


def test_컬렉션과_아이템이_모두_있으면_아무_쓰기도_하지_않는다() -> None:
    calls: list[tuple[str, str]] = []
    client = _make_insert_client(collection_exists=True, items_exist=True, calls=calls)
    spec = next(c for c in NEW_COLLECTIONS if c["slug"] == "cute-round")
    ok = insert_collection(client, "https://x/rest/v1", {}, spec, _one_candidate_plan())
    assert ok is True
    assert all(method != "POST" for method, _ in calls)


def test_컬렉션은_있는데_아이템이_없으면_아이템만_보정한다() -> None:
    calls: list[tuple[str, str]] = []
    client = _make_insert_client(collection_exists=True, items_exist=False, calls=calls)
    spec = next(c for c in NEW_COLLECTIONS if c["slug"] == "cute-round")
    ok = insert_collection(client, "https://x/rest/v1", {}, spec, _one_candidate_plan())
    assert ok is True
    assert ("POST", "/rest/v1/collection_items") in calls
    assert ("POST", "/rest/v1/collections") not in calls


class _DummySettings:
    """main() 테스트용 더미 설정 (실제 env/네트워크 접근 없음)."""

    def dev_write_credentials(self) -> tuple[str, str]:
        return "https://dummy.supabase.co", "dummy-key"

    def prod_write_credentials(self) -> tuple[str, str]:
        return "https://dummy-prod.supabase.co", "dummy-key"


def test_sort_order_충돌시_apply는_1을_반환하고_쓰지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        path = request.url.path
        if path == "/rest/v1/collections" and request.method == "GET":
            return httpx.Response(200, json=[{"slug": "existing", "sort_order": 10}])
        if path == "/rest/v1/fonts" and request.method == "GET":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected request: {request.method} {path}")

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(cs, "load_audit_settings", lambda: _DummySettings())
    monkeypatch.setattr(cs.httpx, "Client", lambda **_: mock_client)

    result = cs.main(apply=True, report_path=str(tmp_path / "report.json"), target="dev")

    assert result == 1
    assert all(method != "POST" for method, _ in calls)
