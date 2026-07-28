"""눈누 공식 URL 전수 스캔 실행기 테스트."""

import json
from pathlib import Path

import httpx

from fontagit_pipeline.noonnu_url_scan import (
    ScanRecord,
    ScanTarget,
    fetch_scan_html,
    scan_targets,
    summarize,
)

_DETAIL_HTML = """
<html><body>
  <header><a href="https://www.instagram.com/noonnu_official/">눈누</a></header>
  <div data-font-detail>
    <h1>효남 늘 화이팅</h1>
    <a href="https://clova.ai/handwriting/list.html">다운로드 페이지로 이동</a>
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
    assert records[0].recommended_action == "auto_fix_safe"
    assert records[0].new_official_url == "https://clova.ai/handwriting/list.html"


def test_scan_skips_already_recorded_targets(tmp_path: Path) -> None:
    """상태 파일에 이미 있는 폰트는 다시 요청하지 않는다."""
    state_path = tmp_path / "state.jsonl"
    font_id = "11111111-1111-1111-1111-111111111111"
    state_path.write_text(
        json.dumps({"font_id": font_id, "classification": "match"}) + "\n",
        encoding="utf-8",
    )
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
            contamination_type="none", recommended_action="keep", evidence="",
        ),
        ScanRecord(
            font_id="2", slug="b", source_url="u", db_official_url=None,
            db_license_source_url=None, db_license_verified=True,
            new_official_url="https://x.kr", new_foundry=None, classification="mismatch",
            contamination_type="noonnu_social", recommended_action="auto_fix_safe", evidence="",
        ),
        ScanRecord(
            font_id="3", slug="c", source_url="u", db_official_url=None,
            db_license_source_url=None, db_license_verified=False,
            new_official_url=None, new_foundry=None, classification="no_container",
            contamination_type="none", recommended_action="keep", evidence="",
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
