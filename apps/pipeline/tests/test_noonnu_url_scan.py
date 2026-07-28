"""눈누 공식 URL 전수 스캔 실행기 테스트."""

import json
from pathlib import Path

from fontagit_pipeline.noonnu_url_scan import ScanTarget, scan_targets

_DETAIL_HTML = """
<html><body>
  <header><a href="https://www.instagram.com/noonnu_official/">눈누</a></header>
  <div data-font-detail>
    <h1>효남 늘 화이팅</h1>
    <a href="https://clova.ai/handwriting/list.html">다운로드 페이지로 이동</a>
  </div>
</body></html>
"""


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
