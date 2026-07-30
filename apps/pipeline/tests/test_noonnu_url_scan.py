"""눈누 공식 URL 전수 스캔 실행기 테스트."""

import json
import tempfile
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest

from fontagit_pipeline.noonnu_url_scan import (
    FetchedPage,
    IngestContext,
    ScanAbortedError,
    ScanLockError,
    ScanRecord,
    ScanTarget,
    acquire_scan_lock,
    fetch_scan_html,
    fetch_scan_page,
    load_scan_targets,
    scan_targets,
    select_actionable,
    summarize,
)

_DETAIL_HTML = """
<html><body>
  <header><a href="https://www.instagram.com/noonnu_official/">눈누</a></header>
  <div data-font-detail>
    <h1>효남 늘 화이팅</h1>
    <a href="https://example-foundry.test/download">다운로드 페이지로 이동</a>
  </div>
</body></html>
"""

_NO_DETAIL_HTML = "<html><body><p>상세 영역이 없는 페이지</p></body></html>"


def _target(font_id: str = "11111111-1111-1111-1111-111111111111") -> ScanTarget:
    """테스트용 스캔 대상을 만든다."""
    return ScanTarget(
        font_id=font_id,
        slug="효남-늘-화이팅",
        source_url="https://noonnu.cc/font_page/600",
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
        db_license_verified=True,
    )


def _tmp_state() -> Path:
    """호출마다 새 임시 상태 파일 경로를 만든다."""
    return Path(tempfile.mkdtemp()) / "state.jsonl"


def _scan_record(recommended_action: str = "keep") -> ScanRecord:
    """select_actionable 테스트용 최소 판정 레코드를 만든다."""
    return ScanRecord(
        font_id="11111111-1111-1111-1111-111111111111",
        slug="효남-늘-화이팅",
        source_url="https://noonnu.cc/font_page/600",
        db_official_url=None,
        db_license_source_url=None,
        db_license_verified=False,
        new_official_url=None,
        new_foundry=None,
        classification="match",
        official_url_contamination="none",
        license_source_url_contamination="none",
        recommended_action=recommended_action,
        evidence="",
    )


def test_scan_produces_verdict_per_target(tmp_path: Path) -> None:
    """대상마다 판정 레코드를 만든다."""
    state_path = tmp_path / "state.jsonl"

    records = scan_targets(
        [_target()],
        fetcher=lambda url: _DETAIL_HTML,
        state_path=state_path,
        sleeper=lambda seconds: None,
    )

    assert len(records) == 1
    assert records[0].classification == "mismatch"
    # 앵커 텍스트는 다운로드 문구와 일치하지만(anchor_ok) 이 fixture에는 제작사명이
    # 없어 foundry_ok가 성립하지 않으므로, 두 근거를 모두 요구하는
    # judge_official_url은 자동수정이 아니라 사람 확인으로 보낸다.
    assert records[0].recommended_action == "manual_review"
    assert records[0].new_official_url == "https://example-foundry.test/download"


def test_scan_skips_already_recorded_targets(tmp_path: Path) -> None:
    """상태 파일에 이미 있는 완결된 판정은 다시 요청하지 않는다."""
    state_path = tmp_path / "state.jsonl"
    font_id = "11111111-1111-1111-1111-111111111111"
    existing = ScanRecord(
        font_id=font_id,
        slug=_target(font_id).slug,
        source_url=_target(font_id).source_url,
        db_official_url=_target(font_id).db_official_url,
        db_license_source_url=_target(font_id).db_license_source_url,
        db_license_verified=_target(font_id).db_license_verified,
        new_official_url=None,
        new_foundry=None,
        classification="match",
        official_url_contamination="none",
        license_source_url_contamination="none",
        recommended_action="keep",
        evidence="",
    )
    state_path.write_text(json.dumps(asdict(existing), ensure_ascii=False) + "\n", encoding="utf-8")
    requested: list[str] = []

    def _fetcher(url: str) -> str:
        requested.append(url)
        return _DETAIL_HTML

    records = scan_targets(
        [_target(font_id)],
        fetcher=_fetcher,
        state_path=state_path,
        sleeper=lambda seconds: None,
    )

    assert requested == []
    assert len(records) == 1
    assert records[0].classification == "match"


def test_scan_records_fetch_failure_without_stopping(tmp_path: Path) -> None:
    """한 건이 실패해도 나머지를 계속 처리하고 실패를 남긴다."""
    state_path = tmp_path / "state.jsonl"
    ok_id = "22222222-2222-2222-2222-222222222222"

    def _fetcher(url: str) -> str:
        if url.endswith("/600"):
            raise RuntimeError("boom")
        return _DETAIL_HTML

    targets = [
        _target(),
        ScanTarget(
            font_id=ok_id,
            slug="다른-폰트",
            source_url="https://noonnu.cc/font_page/601",
            db_official_url=None,
            db_license_source_url=None,
            db_license_verified=False,
        ),
    ]

    records = scan_targets(
        targets, fetcher=_fetcher, state_path=state_path, sleeper=lambda seconds: None
    )

    by_id = {record.font_id: record for record in records}
    assert by_id[targets[0].font_id].classification == "no_container"
    assert by_id[targets[0].font_id].error is not None
    assert by_id[ok_id].classification == "mismatch"


def test_state_file_is_written_per_target(tmp_path: Path) -> None:
    """상태 파일은 건 단위로 기록되어 중단에도 진행분이 남는다."""
    state_path = tmp_path / "state.jsonl"

    scan_targets(
        [_target()],
        fetcher=lambda url: _DETAIL_HTML,
        state_path=state_path,
        sleeper=lambda seconds: None,
    )

    lines = state_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["font_id"] == _target().font_id


def test_summarize_counts_by_classification_and_action() -> None:
    """판정과 조치 권고를 각각 집계한다."""
    records = [
        ScanRecord(
            font_id="1", slug="a", source_url="u", db_official_url=None,
            db_license_source_url=None, db_license_verified=False,
            new_official_url=None, new_foundry=None, classification="match",
            official_url_contamination="none", license_source_url_contamination="none",
            recommended_action="keep", evidence="",
        ),
        ScanRecord(
            font_id="2", slug="b", source_url="u", db_official_url=None,
            db_license_source_url=None, db_license_verified=True,
            new_official_url="https://x.kr", new_foundry=None, classification="mismatch",
            official_url_contamination="third_party_social",
            license_source_url_contamination="none",
            recommended_action="auto_fix_safe", evidence="",
        ),
        ScanRecord(
            font_id="3", slug="c", source_url="u", db_official_url=None,
            db_license_source_url=None, db_license_verified=False,
            new_official_url=None, new_foundry=None, classification="no_container",
            official_url_contamination="none", license_source_url_contamination="none",
            recommended_action="keep", evidence="",
        ),
    ]

    summary = summarize(records)

    assert summary["total"] == 3
    assert summary["classification"]["match"] == 1
    assert summary["classification"]["mismatch"] == 1
    assert summary["recommended_action"]["auto_fix_safe"] == 1
    assert summary["no_container_ratio"] == 1 / 3
    assert summary["structure_assumption_ok"] is False


def test_scan_resumes_retryable_failures_and_updates_verdict(tmp_path: Path) -> None:
    """네트워크 실패로 기록된 폰트는 재개 시 다시 요청되고, 성공하면 판정이 갱신된다."""
    state_path = tmp_path / "state.jsonl"
    attempts = {"count": 0}

    def _fetcher(url: str) -> str:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("일시적 네트워크 오류")
        return _DETAIL_HTML

    first_pass = scan_targets(
        [_target()], fetcher=_fetcher, state_path=state_path, sleeper=lambda seconds: None
    )
    assert first_pass[0].classification == "no_container"
    assert first_pass[0].error is not None

    second_pass = scan_targets(
        [_target()], fetcher=_fetcher, state_path=state_path, sleeper=lambda seconds: None
    )

    assert attempts["count"] == 2
    assert len(second_pass) == 1
    assert second_pass[0].classification == "mismatch"
    assert second_pass[0].error is None


def test_parsing_failures_do_not_trigger_circuit_breaker(tmp_path: Path) -> None:
    """결정론적 파싱 실패는 회로차단기 카운터에 영향을 주지 않고 no_container로 끝까지 처리된다."""
    state_path = tmp_path / "state.jsonl"
    targets = [
        ScanTarget(
            font_id=f"33333333-3333-3333-3333-33333333333{i}",
            slug=f"폰트-{i}",
            source_url=f"https://noonnu.cc/font_page/{700 + i}",
            db_official_url=None,
            db_license_source_url=None,
            db_license_verified=False,
        )
        for i in range(6)
    ]

    records = scan_targets(
        targets,
        fetcher=lambda url: _NO_DETAIL_HTML,
        state_path=state_path,
        sleeper=lambda seconds: None,
    )

    assert len(records) == 6
    assert all(record.classification == "no_container" for record in records)


def test_rate_limit_status_gets_longer_backoff(tmp_path: Path) -> None:
    """429 응답은 일반 실패(고정 30초)보다 더 긴 대기 시간을 sleeper에 전달한다."""
    state_path = tmp_path / "state.jsonl"
    sleeps: list[float] = []

    def _fetcher(url: str) -> str:
        request = httpx.Request("GET", url)
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("Too Many Requests", request=request, response=response)

    scan_targets(
        [_target()], fetcher=_fetcher, state_path=state_path, sleeper=sleeps.append
    )

    assert len(sleeps) == 1
    assert sleeps[0] > 30.0


def test_retry_after_header_overrides_default_backoff(tmp_path: Path) -> None:
    """429 응답에 Retry-After 헤더가 있으면 그 값이 백오프에 우선 반영된다."""
    state_path = tmp_path / "state.jsonl"
    sleeps: list[float] = []

    def _fetcher(url: str) -> str:
        request = httpx.Request("GET", url)
        response = httpx.Response(429, request=request, headers={"Retry-After": "7"})
        raise httpx.HTTPStatusError("Too Many Requests", request=request, response=response)

    scan_targets([_target()], fetcher=_fetcher, state_path=state_path, sleeper=sleeps.append)

    assert len(sleeps) == 1
    assert sleeps[0] == 7.0


def test_retry_after_header_parses_http_date(tmp_path: Path) -> None:
    """Retry-After가 HTTP-date 형식이어도 초 단위로 환산해 백오프에 반영한다."""
    state_path = tmp_path / "state.jsonl"
    sleeps: list[float] = []
    future = datetime.now(timezone.utc) + timedelta(seconds=10)
    retry_after_value = format_datetime(future, usegmt=True)

    def _fetcher(url: str) -> str:
        request = httpx.Request("GET", url)
        response = httpx.Response(
            429, request=request, headers={"Retry-After": retry_after_value}
        )
        raise httpx.HTTPStatusError("Too Many Requests", request=request, response=response)

    scan_targets([_target()], fetcher=_fetcher, state_path=state_path, sleeper=sleeps.append)

    assert len(sleeps) == 1
    assert 8.0 <= sleeps[0] <= 12.0


def test_incomplete_state_line_is_not_treated_as_completed(tmp_path: Path) -> None:
    """필수 필드가 빠진 상태 파일 줄은 완료로 인정하지 않고 다시 스캔한다."""
    state_path = tmp_path / "state.jsonl"
    font_id = _target().font_id
    state_path.write_text(json.dumps({"font_id": font_id}) + "\n", encoding="utf-8")
    requested: list[str] = []

    def _fetcher(url: str) -> str:
        requested.append(url)
        return _DETAIL_HTML

    records = scan_targets(
        [_target(font_id)], fetcher=_fetcher, state_path=state_path, sleeper=lambda s: None
    )

    assert requested == [_target(font_id).source_url]
    assert len(records) == 1
    assert records[0].classification == "mismatch"


def test_scan_targets_return_is_limited_to_current_targets(tmp_path: Path) -> None:
    """상태 파일에 과거 대상이 남아 있어도 이번 targets에 없는 font_id는 반환에서 제외된다."""
    state_path = tmp_path / "state.jsonl"
    stale_target = _target(font_id="99999999-9999-9999-9999-999999999999")
    scan_targets(
        [stale_target], fetcher=lambda url: _DETAIL_HTML, state_path=state_path,
        sleeper=lambda s: None,
    )

    current_target = _target(font_id="88888888-8888-8888-8888-888888888888")
    records = scan_targets(
        [current_target], fetcher=lambda url: _DETAIL_HTML, state_path=state_path,
        sleeper=lambda s: None,
    )

    assert {record.font_id for record in records} == {current_target.font_id}


def test_scan_target_is_rechecked_when_db_values_changed(tmp_path: Path) -> None:
    """저장된 판정의 DB 값이 현재 대상과 달라지면 완료로 인정하지 않고 다시 검사한다."""
    state_path = tmp_path / "state.jsonl"
    original = _target()
    scan_targets(
        [original], fetcher=lambda url: _DETAIL_HTML, state_path=state_path,
        sleeper=lambda s: None,
    )

    changed = ScanTarget(
        font_id=original.font_id,
        slug=original.slug,
        source_url=original.source_url,
        db_official_url="https://changed-foundry.example.com",
        db_license_source_url=original.db_license_source_url,
        db_license_verified=original.db_license_verified,
    )
    requested: list[str] = []

    def _fetcher(url: str) -> str:
        requested.append(url)
        return _DETAIL_HTML

    records = scan_targets(
        [changed], fetcher=_fetcher, state_path=state_path, sleeper=lambda s: None
    )

    assert requested == [changed.source_url]
    assert len(records) == 1


def test_circuit_breaker_records_last_failure_before_aborting(tmp_path: Path) -> None:
    """연속 실패 한계에 도달해 중단해도 마지막 실패 레코드가 상태 파일에 남는다."""
    state_path = tmp_path / "state.jsonl"
    targets = [
        ScanTarget(
            font_id=f"circuit-{i}",
            slug=f"폰트-{i}",
            source_url=f"https://noonnu.cc/font_page/{800 + i}",
            db_official_url=None,
            db_license_source_url=None,
            db_license_verified=False,
        )
        for i in range(5)
    ]

    def _fetcher(url: str) -> str:
        raise RuntimeError("네트워크 다운")

    with pytest.raises(ScanAbortedError):
        scan_targets(targets, fetcher=_fetcher, state_path=state_path, sleeper=lambda s: None)

    lines = state_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 5
    last = json.loads(lines[-1])
    assert last["font_id"] == targets[-1].font_id
    assert last["retryable_error"] is True


def test_download_success_resets_network_failure_counter(tmp_path: Path) -> None:
    """다운로드 성공 후 파싱만 실패해도 네트워크 연속 실패 카운터가 초기화된다."""
    state_path = tmp_path / "state.jsonl"

    def _make_target(i: int) -> ScanTarget:
        return ScanTarget(
            font_id=f"reset-{i}",
            slug=f"폰트-{i}",
            source_url=f"https://noonnu.cc/font_page/{900 + i}",
            db_official_url=None,
            db_license_source_url=None,
            db_license_verified=False,
        )

    targets = [_make_target(i) for i in (0, 1, 2, 3, 4, 5, 6, 7, 8)]
    normal_no_container_html = "<html><body>" + ("일반 안내 문구입니다. " * 30) + "</body></html>"

    def _fetcher(url: str) -> str:
        index = int(url.rsplit("/", 1)[-1]) - 900
        if index == 4:
            return normal_no_container_html
        raise RuntimeError("일시적 네트워크 오류")

    records = scan_targets(
        targets, fetcher=_fetcher, state_path=state_path, sleeper=lambda s: None
    )

    assert len(records) == 9
    by_id = {record.font_id: record for record in records}
    assert by_id["reset-4"].retryable_error is False


def test_untrusted_source_host_is_skipped_without_request(tmp_path: Path) -> None:
    """source_url이 noonnu.cc가 아니면 요청하지 않고 건너뛴다."""
    state_path = tmp_path / "state.jsonl"
    bad_target = ScanTarget(
        font_id="untrusted-1",
        slug="위험",
        source_url="https://internal.example.com/secret",
        db_official_url=None,
        db_license_source_url=None,
        db_license_verified=False,
    )
    requested: list[str] = []

    def _fetcher(url: str) -> str:
        requested.append(url)
        return _DETAIL_HTML

    records = scan_targets(
        [bad_target], fetcher=_fetcher, state_path=state_path, sleeper=lambda s: None
    )

    assert requested == []
    assert len(records) == 1
    assert records[0].retryable_error is False


def test_robots_checker_blocks_scan_before_any_request(tmp_path: Path) -> None:
    """robots_checker가 허용하지 않으면 요청 없이 스캔을 중단한다."""
    state_path = tmp_path / "state.jsonl"
    requested: list[str] = []

    def _fetcher(url: str) -> str:
        requested.append(url)
        return _DETAIL_HTML

    with pytest.raises(ScanAbortedError):
        scan_targets(
            [_target()],
            fetcher=_fetcher,
            state_path=state_path,
            sleeper=lambda s: None,
            robots_checker=lambda url: False,
        )

    assert requested == []


def test_acquire_scan_lock_blocks_concurrent_run(tmp_path: Path) -> None:
    """이미 실행 중인 잠금이 있으면 두 번째 시도는 거부된다."""
    state_path = tmp_path / "state.jsonl"
    with acquire_scan_lock(state_path):
        with pytest.raises(ScanLockError):
            with acquire_scan_lock(state_path):
                pass


def test_acquire_scan_lock_recovers_stale_lock_from_dead_pid(tmp_path: Path) -> None:
    """잠금 파일의 PID가 죽어 있으면 stale로 보고 회수해 다시 획득한다."""
    state_path = tmp_path / "state.jsonl"
    lock_path = state_path.with_name(state_path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("999999999", encoding="utf-8")

    with acquire_scan_lock(state_path):
        pass

    assert not lock_path.exists()


class _FakeQuery:
    """Supabase 쿼리 빌더의 select/eq/order/range/execute 체이닝을 흉내낸다."""

    def __init__(self, rows: list[dict[str, object]], order_calls: list[str]) -> None:
        self._rows = rows
        self._order_calls = order_calls
        self._range: tuple[int, int] | None = None

    def select(self, columns: str) -> "_FakeQuery":
        return self

    def eq(self, column: str, value: str) -> "_FakeQuery":
        return self

    def order(self, column: str) -> "_FakeQuery":
        self._order_calls.append(column)
        return self

    def range(self, start: int, end: int) -> "_FakeQuery":
        self._range = (start, end)
        return self

    def execute(self) -> SimpleNamespace:
        assert self._range is not None, "order/range 호출 없이 execute됨"
        start, end = self._range
        return SimpleNamespace(data=self._rows[start : end + 1])


class _FakeTable:
    """호출마다 새 `_FakeQuery`를 내주는 테이블. order_calls로 정렬 호출을 추적한다."""

    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.order_calls: list[str] = []

    def select(self, columns: str) -> _FakeQuery:
        return _FakeQuery(self.rows, self.order_calls)


class _FakeSchema:
    def __init__(self, tables: dict[str, _FakeTable]) -> None:
        self._tables = tables

    def table(self, name: str) -> _FakeTable:
        return self._tables[name]


class _FakeClient:
    def __init__(self, schema: _FakeSchema) -> None:
        self._schema = schema

    def schema(self, name: str) -> _FakeSchema:
        return self._schema


@pytest.mark.parametrize("total_sources", [999, 1000, 1001, 1110])
def test_load_scan_targets_paginates_past_1000_rows(total_sources: int) -> None:
    """font_sources/fonts 조회가 1,000행 제한을 넘겨도 정렬 페이지네이션으로 전부 읽는다."""
    source_rows = [
        {"id": f"src-{i:05d}", "font_id": f"font-{i:05d}", "source_url": f"https://noonnu.cc/font_page/{i}"}
        for i in range(total_sources)
    ]
    font_rows = [
        {
            "id": f"font-{i:05d}", "slug": f"slug-{i}", "official_url": None,
            "license_source_url": None, "license_verified": False,
        }
        for i in range(total_sources)
    ]
    tables = {"font_sources": _FakeTable(source_rows), "fonts": _FakeTable(font_rows)}
    client = _FakeClient(_FakeSchema(tables))

    targets = load_scan_targets(client)

    assert len(targets) == total_sources
    assert len({t.font_id for t in targets}) == total_sources
    assert tables["font_sources"].order_calls and all(
        call == "id" for call in tables["font_sources"].order_calls
    )
    assert tables["fonts"].order_calls and all(
        call == "id" for call in tables["fonts"].order_calls
    )


def test_main_rejects_negative_limit() -> None:
    """--limit이 음수면 스캔을 시작하지 않고 0이 아닌 종료 코드를 낸다."""
    import argparse

    from fontagit_pipeline.__main__ import main_noonnu_url_scan

    args = argparse.Namespace(
        target="dev", state=Path("s.jsonl"), out=Path("o.json"), limit=-1
    )

    assert main_noonnu_url_scan(args) != 0


def test_main_rejects_same_state_and_out_path(tmp_path: Path) -> None:
    """--state와 --out이 같은 경로면 스캔을 시작하지 않고 0이 아닌 종료 코드를 낸다."""
    import argparse

    from fontagit_pipeline.__main__ import main_noonnu_url_scan

    same_path = tmp_path / "same.jsonl"
    args = argparse.Namespace(target="dev", state=same_path, out=same_path, limit=0)

    assert main_noonnu_url_scan(args) != 0


def test_main_returns_nonzero_when_retryable_records_remain(tmp_path: Path) -> None:
    """스캔이 끝까지 돌았지만 retryable_error가 남으면 종료 코드가 0이 아니다."""
    import argparse
    from unittest.mock import MagicMock, patch

    from fontagit_pipeline.__main__ import main_noonnu_url_scan

    fake_summary: dict[str, object] = {
        "total": 1,
        "classification": {"no_container": 1},
        "recommended_action": {"keep": 1},
        "official_url_contamination": {"none": 1},
        "license_source_url_contamination": {"none": 1},
        "error_count": 1,
        "no_container_ratio": 0.0,
        "structure_assumption_ok": True,
        "retryable_count": 1,
        "retryable_font_ids": ["font-1"],
    }
    args = argparse.Namespace(
        target="dev",
        state=tmp_path / "state.jsonl",
        out=tmp_path / "report.json",
        limit=0,
    )

    with (
        patch("fontagit_pipeline.config.load_audit_settings") as mock_settings,
        patch("supabase.create_client"),
        patch("fontagit_pipeline.__main__.load_scan_targets", return_value=[_target()]),
        patch("fontagit_pipeline.__main__.build_robots_checker", return_value=lambda url: True),
        patch("fontagit_pipeline.__main__.scan_targets", return_value=[]),
        patch("fontagit_pipeline.__main__.summarize", return_value=fake_summary),
    ):
        mock_settings.return_value = MagicMock(
            supabase_dev_url="https://test.supabase.co",
            supabase_dev_secret_key="secret",
            supabase_prod_url=None,
            supabase_prod_secret_key=None,
        )
        result = main_noonnu_url_scan(args)

    assert result != 0


def test_cli_rejects_noonnu_url_scan_without_target(tmp_path: Path) -> None:
    """--target 없이 noonnu-url-scan을 호출하면 argparse가 거부한다."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "fontagit_pipeline",
            "noonnu-url-scan",
            "--state",
            str(tmp_path / "state.jsonl"),
            "--out",
            str(tmp_path / "report.json"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "--target" in result.stderr


def test_main_reads_dev_credentials_when_target_is_dev(tmp_path: Path) -> None:
    """--target dev면 supabase_dev_url/supabase_dev_secret_key로 client를 만든다."""
    import argparse
    from unittest.mock import MagicMock, patch

    from fontagit_pipeline.__main__ import main_noonnu_url_scan

    args = argparse.Namespace(
        target="dev",
        state=tmp_path / "state.jsonl",
        out=tmp_path / "report.json",
        limit=0,
    )

    with (
        patch("fontagit_pipeline.config.load_audit_settings") as mock_settings,
        patch("supabase.create_client") as mock_create_client,
        patch("fontagit_pipeline.__main__.load_scan_targets", return_value=[]),
        patch("fontagit_pipeline.__main__.build_robots_checker", return_value=lambda url: True),
        patch("fontagit_pipeline.__main__.scan_targets", return_value=[]),
    ):
        mock_settings.return_value = MagicMock(
            supabase_dev_url="https://dev.supabase.co",
            supabase_dev_secret_key="dev-secret",
            supabase_prod_url="https://prod.supabase.co",
            supabase_prod_secret_key="prod-secret",
        )
        main_noonnu_url_scan(args)

    mock_create_client.assert_called_once_with("https://dev.supabase.co", "dev-secret")


def test_main_reads_prod_credentials_when_target_is_prod(tmp_path: Path) -> None:
    """--target prod면 supabase_prod_url/supabase_prod_secret_key로 client를 만든다."""
    import argparse
    from unittest.mock import MagicMock, patch

    from fontagit_pipeline.__main__ import main_noonnu_url_scan

    args = argparse.Namespace(
        target="prod",
        state=tmp_path / "state.jsonl",
        out=tmp_path / "report.json",
        limit=0,
    )

    with (
        patch("fontagit_pipeline.config.load_audit_settings") as mock_settings,
        patch("supabase.create_client") as mock_create_client,
        patch("fontagit_pipeline.__main__.load_scan_targets", return_value=[]),
        patch("fontagit_pipeline.__main__.build_robots_checker", return_value=lambda url: True),
        patch("fontagit_pipeline.__main__.scan_targets", return_value=[]),
    ):
        mock_settings.return_value = MagicMock(
            supabase_dev_url="https://dev.supabase.co",
            supabase_dev_secret_key="dev-secret",
            supabase_prod_url="https://prod.supabase.co",
            supabase_prod_secret_key="prod-secret",
        )
        main_noonnu_url_scan(args)

    mock_create_client.assert_called_once_with("https://prod.supabase.co", "prod-secret")


def test_main_reports_missing_target_credentials(tmp_path: Path) -> None:
    """--target 환경의 url/secret 중 하나라도 비어 있으면 exit 2를 낸다."""
    import argparse
    from unittest.mock import MagicMock, patch

    from fontagit_pipeline.__main__ import main_noonnu_url_scan

    args = argparse.Namespace(
        target="prod",
        state=tmp_path / "state.jsonl",
        out=tmp_path / "report.json",
        limit=0,
    )

    with patch("fontagit_pipeline.config.load_audit_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            supabase_dev_url="https://dev.supabase.co",
            supabase_dev_secret_key="dev-secret",
            supabase_prod_url=None,
            supabase_prod_secret_key=None,
        )
        result = main_noonnu_url_scan(args)

    assert result == 2


def test_fetch_scan_html_preserves_status_code_for_backoff(tmp_path: Path) -> None:
    """스캔 전용 fetcher를 거쳐도 429 상태 코드가 보존되어 긴 백오프가 걸린다.

    noonnu_seed._fetch_url은 HTTP 오류를 NoonnuSeedError로 감싸 상태 코드를
    지워버린다. fetch_scan_html은 httpx 예외를 그대로 올려보내야 한다.
    """
    state_path = tmp_path / "state.jsonl"
    sleeps: list[float] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, request=request)

    transport = httpx.MockTransport(_handler)
    with httpx.Client(transport=transport) as client:
        scan_targets(
            [_target()],
            fetcher=lambda url: fetch_scan_html(client, url),
            state_path=state_path,
            sleeper=sleeps.append,
        )

    assert len(sleeps) == 1
    assert sleeps[0] > 30.0


def test_fetch_scan_page_returns_final_url_after_redirect() -> None:
    """리다이렉트를 따라간 뒤 최종 URL과 상태 코드를 함께 돌려준다."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/font_page/1":
            return httpx.Response(
                302, headers={"location": "https://noonnu.cc/font_page/2"}
            )
        return httpx.Response(200, text="<html><body>ok</body></html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    page = fetch_scan_page(client, "https://noonnu.cc/font_page/1")

    assert page.html == "<html><body>ok</body></html>"
    assert page.final_url == "https://noonnu.cc/font_page/2"
    assert page.http_status == 200


class _RecordingStore:
    """save_snapshot/save_finding 호출만 기록하는 테스트용 저장소."""

    def __init__(self) -> None:
        self.snapshots: list[object] = []
        self.findings: list[object] = []
        self._next = 0

    def save_snapshot(self, run_id: UUID, snapshot: object) -> UUID:
        self.snapshots.append(snapshot)
        self._next += 1
        return UUID(int=self._next)

    def save_finding(self, run_id: UUID, finding: object) -> UUID:
        self.findings.append(finding)
        self._next += 1
        return UUID(int=self._next)


def test_scan_targets_without_ingest_does_not_store() -> None:
    """적재 문맥이 없으면 기존 동작 그대로다."""
    store = _RecordingStore()
    records = scan_targets(
        [_target()],
        fetcher=lambda _url: _DETAIL_HTML,
        state_path=_tmp_state(),
        sleeper=lambda _s: None,
    )

    assert records
    assert store.snapshots == []


def test_scan_targets_with_ingest_saves_snapshot_and_findings() -> None:
    """적재 문맥이 있으면 판정 1건당 snapshot 1건 + finding 2건을 남긴다."""
    store = _RecordingStore()
    ingest = IngestContext(
        store=store,  # type: ignore[arg-type]
        run_id=UUID(int=99),
        page_fetcher=lambda url: FetchedPage(
            html=_DETAIL_HTML, final_url=url, http_status=200
        ),
    )

    records = scan_targets(
        [_target()],
        fetcher=lambda _url: _DETAIL_HTML,
        state_path=_tmp_state(),
        sleeper=lambda _s: None,
        ingest=ingest,
    )

    assert len(records) == 1
    assert len(store.snapshots) == 1
    assert len(store.findings) == 2


def test_select_actionable_drops_keep() -> None:
    """keep 판정은 정정 대상에서 제외한다."""
    keep = _scan_record(recommended_action="keep")
    fix = _scan_record(recommended_action="auto_fix_safe")

    assert select_actionable([keep, fix]) == [fix]
