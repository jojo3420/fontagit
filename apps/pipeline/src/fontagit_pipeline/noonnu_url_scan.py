"""눈누 상세를 다시 받아 공식 URL을 전수 대조한다.

중단에 대비해 판정 1건마다 상태 파일에 append 한다. 재개 시 완료로 취급하는 것은
성공, 또는 재시도해도 결과가 같은 결정론적 파싱 실패(retryable_error=False)뿐이다.
네트워크-HTTP 오류처럼 다시 시도할 가치가 있는 실패는 completed에서 제외해 다음
실행에서 다시 요청하고, 같은 font_id가 여러 줄로 남으면 마지막 줄을 최신 판정으로
채택한다. 이렇게 실패와 완료를 구분해야 배치 단위 기록이 실패 건을 완료로 삼켜버린
문제(#142)를 실제로 피할 수 있다.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from fontagit_pipeline.audit_noonnu import extract_noonnu_font
from fontagit_pipeline.noonnu_url_audit import judge_official_url

logger = logging.getLogger(__name__)

_BASE_DELAY = 1.5
_JITTER = 0.7
_BACKOFF_DELAY = 30.0
_RATE_LIMIT_BACKOFF_BASE = 120.0
_RATE_LIMIT_BACKOFF_MAX = 960.0
_RATE_LIMIT_STATUS_CODES = frozenset({403, 429})
_MAX_CONSECUTIVE_FAILURES = 5


@dataclass(frozen=True)
class ScanTarget:
    """스캔 대상 폰트 1종."""

    font_id: str
    slug: str
    source_url: str
    db_official_url: str | None
    db_license_source_url: str | None
    db_license_verified: bool


@dataclass(frozen=True)
class ScanRecord:
    """판정 1건의 직렬화 단위."""

    font_id: str
    slug: str
    source_url: str
    db_official_url: str | None
    db_license_source_url: str | None
    db_license_verified: bool
    new_official_url: str | None
    new_foundry: str | None
    classification: str
    contamination_type: str
    recommended_action: str
    evidence: str
    error: str | None = None
    retryable_error: bool = False


class ScanAbortedError(RuntimeError):
    """연속 실패가 한계를 넘어 안전하게 중단했다."""


def _load_records(state_path: Path) -> dict[str, ScanRecord]:
    """상태 파일에 기록된 판정을 font_id별로 복원한다.

    같은 font_id가 여러 줄로 남아 있으면(재시도 후 재기록) 마지막 줄을 채택한다.
    """
    if not state_path.exists():
        return {}
    records: dict[str, ScanRecord] = {}
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        record = ScanRecord(
            font_id=str(payload.get("font_id", "")),
            slug=str(payload.get("slug", "")),
            source_url=str(payload.get("source_url", "")),
            db_official_url=payload.get("db_official_url"),
            db_license_source_url=payload.get("db_license_source_url"),
            db_license_verified=bool(payload.get("db_license_verified", False)),
            new_official_url=payload.get("new_official_url"),
            new_foundry=payload.get("new_foundry"),
            classification=str(payload.get("classification", "no_container")),
            contamination_type=str(payload.get("contamination_type", "none")),
            recommended_action=str(payload.get("recommended_action", "keep")),
            evidence=str(payload.get("evidence", "")),
            error=payload.get("error"),
            retryable_error=bool(payload.get("retryable_error", False)),
        )
        records[record.font_id] = record
    return records


def _load_completed_ids(records: dict[str, ScanRecord]) -> set[str]:
    """재시도가 필요 없는(완료된) font_id 집합을 만든다.

    성공과 결정론적 파싱 실패(retryable_error=False)는 완료로 취급해 재개 시
    건너뛴다. 네트워크-HTTP 오류처럼 재시도 가치가 있는 실패(retryable_error=True)만
    미완료로 남겨 다음 실행에서 다시 요청한다.
    """
    return {font_id for font_id, record in records.items() if not record.retryable_error}


def _append_record(state_path: Path, record: ScanRecord) -> None:
    """판정 1건을 상태 파일에 덧붙인다."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def _resolve_backoff_seconds(exc: Exception, consecutive_failures: int) -> float:
    """실패 원인에 따라 다음 요청 전 대기 시간을 정한다.

    429/403은 서버가 요청 예의를 지키라고 보내는 신호이므로, 연속으로 받을수록
    지수적으로 늘려 안전 중단(_MAX_CONSECUTIVE_FAILURES)에 가까워지게 한다.
    """
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in _RATE_LIMIT_STATUS_CODES:
        return min(
            _RATE_LIMIT_BACKOFF_BASE * (2.0 ** (consecutive_failures - 1)),
            _RATE_LIMIT_BACKOFF_MAX,
        )
    return _BACKOFF_DELAY


def scan_targets(
    targets: Iterable[ScanTarget],
    fetcher: Callable[[str], str],
    state_path: Path,
    sleeper: Callable[[float], None] = time.sleep,
) -> list[ScanRecord]:
    """대상을 순회하며 공식 URL을 대조한다.

    Args:
        targets: 스캔 대상 목록.
        fetcher: URL을 받아 HTML을 돌려주는 함수.
        state_path: 진행 상태를 남길 JSONL 경로.
        sleeper: 대기 함수. 테스트에서 즉시 반환하도록 주입한다.

    Returns:
        상태 파일에 이미 있던 판정과 이번에 처리한 판정을 font_id당 1건으로 합친 목록.

    Raises:
        ScanAbortedError: 네트워크-HTTP 등 재시도 가치가 있는 실패가 연속으로
            한계를 넘어 중단한 경우. 결정론적 파싱 실패는 이 카운터에 반영하지 않는다.
    """
    target_list: Sequence[ScanTarget] = list(targets)
    records = _load_records(state_path)
    completed = _load_completed_ids(records)
    consecutive_failures = 0

    for index, target in enumerate(target_list, start=1):
        if target.font_id in completed:
            continue

        if index > 1:
            sleeper(_BASE_DELAY + random.uniform(0.0, _JITTER))

        try:
            html = fetcher(target.source_url)
            snapshot = extract_noonnu_font(html, target.source_url)
        except ValueError as exc:
            # 상세 영역이 없거나 모호한 결정론적 실패. 재시도해도 같은 결과이므로
            # 회로차단기 카운터-백오프에 반영하지 않고 곧바로 완료로 기록한다.
            snapshot = None
            error: str | None = f"{type(exc).__name__}: {exc}"
            retryable_error = False
            logger.warning("파싱 실패(재시도 안 함) %s: %s", target.slug, error)
        except Exception as exc:  # 네트워크-HTTP 등 일시적 실패 → 재개 시 재시도
            snapshot = None
            error = f"{type(exc).__name__}: {exc}"
            retryable_error = True
            consecutive_failures += 1
            backoff = _resolve_backoff_seconds(exc, consecutive_failures)
            logger.warning("수집 실패 %s: %s (대기 %.0f초)", target.slug, error, backoff)
            sleeper(backoff)
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                raise ScanAbortedError(
                    f"연속 {consecutive_failures}건 실패로 중단합니다. "
                    f"상태 파일에서 재개하세요: {state_path}"
                ) from exc
        else:
            error = None
            retryable_error = False
            consecutive_failures = 0

        verdict = judge_official_url(
            snapshot,
            db_official_url=target.db_official_url,
            db_license_source_url=target.db_license_source_url,
        )
        record = ScanRecord(
            font_id=target.font_id,
            slug=target.slug,
            source_url=target.source_url,
            db_official_url=target.db_official_url,
            db_license_source_url=target.db_license_source_url,
            db_license_verified=target.db_license_verified,
            new_official_url=verdict.new_official_url,
            new_foundry=snapshot.foundry if snapshot is not None else None,
            classification=verdict.classification,
            contamination_type=verdict.contamination_type,
            recommended_action=verdict.recommended_action,
            evidence=verdict.evidence,
            error=error,
            retryable_error=retryable_error,
        )
        _append_record(state_path, record)
        records[record.font_id] = record
        logger.info(
            "[%d/%d] %s -> %s / %s",
            index,
            len(target_list),
            target.slug,
            record.classification,
            record.recommended_action,
        )

    return list(records.values())


_NO_CONTAINER_THRESHOLD = 0.05


def summarize(records: Sequence[ScanRecord]) -> dict[str, object]:
    """판정 분포를 집계한다.

    no_container 비율이 5%를 넘으면 눈누 페이지 구조 가정이 틀린 것이므로
    정정을 진행하지 않고 폴백 선택자 설계를 다시 봐야 한다.
    """
    total = len(records)
    classification: dict[str, int] = {}
    action: dict[str, int] = {}
    contamination: dict[str, int] = {}
    for record in records:
        classification[record.classification] = classification.get(record.classification, 0) + 1
        action[record.recommended_action] = action.get(record.recommended_action, 0) + 1
        contamination[record.contamination_type] = (
            contamination.get(record.contamination_type, 0) + 1
        )

    no_container_ratio = (classification.get("no_container", 0) / total) if total else 0.0
    return {
        "total": total,
        "classification": classification,
        "recommended_action": action,
        "contamination_type": contamination,
        "error_count": sum(1 for record in records if record.error),
        "no_container_ratio": no_container_ratio,
        "structure_assumption_ok": no_container_ratio <= _NO_CONTAINER_THRESHOLD,
    }


_PAGE_SIZE = 1000


def _select_all_rows(
    table: object, columns: str, eq_filters: dict[str, str]
) -> list[dict[str, object]]:
    """1,000행 응답 제한을 넘는 전체 행을 range()로 페이지네이션해 읽는다.

    Supabase는 기본적으로 한 번에 1,000행만 반환하므로, 대상 규모(1,110종)에서
    페이지네이션 없이 읽으면 조용히 잘린다.
    """
    rows: list[dict[str, object]] = []
    offset = 0
    while True:
        query = table.select(columns)  # type: ignore[attr-defined]
        for column, value in eq_filters.items():
            query = query.eq(column, value)
        page = query.range(offset, offset + _PAGE_SIZE - 1).execute()
        page_rows = page.data
        if not isinstance(page_rows, list):
            raise RuntimeError(f"{columns} 조회 결과가 올바르지 않습니다")
        rows.extend(page_rows)
        if len(page_rows) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    return rows


def load_scan_targets(client: object) -> list[ScanTarget]:
    """눈누에서 온 발행 폰트와 그 상세 URL을 읽는다.

    font_sources(provider='noonnu')에 상세 URL이 있고, fonts에 현재 값이 있다.
    """
    schema = client.schema("fontagit")  # type: ignore[attr-defined]
    source_rows = _select_all_rows(
        schema.table("font_sources"),
        "font_id, source_url",
        {"provider": "noonnu"},
    )
    url_by_font: dict[str, str] = {
        str(row["font_id"]): str(row["source_url"]) for row in source_rows
    }
    if not url_by_font:
        return []

    font_rows = _select_all_rows(
        schema.table("fonts"),
        "id, slug, official_url, license_source_url, license_verified",
        {"status": "published"},
    )
    targets: list[ScanTarget] = []
    for row in font_rows:
        font_id = str(row["id"])
        source_url = url_by_font.get(font_id)
        if source_url is None:
            continue
        targets.append(
            ScanTarget(
                font_id=font_id,
                slug=str(row["slug"]),
                source_url=source_url,
                db_official_url=row.get("official_url"),  # type: ignore[arg-type]
                db_license_source_url=row.get("license_source_url"),  # type: ignore[arg-type]
                db_license_verified=bool(row.get("license_verified", False)),
            )
        )
    return targets
