"""눈누 상세를 다시 받아 공식 URL을 전수 대조한다.

중단에 대비해 판정 1건마다 상태 파일에 append 한다. 재개 시 완료로 취급하는 것은
성공, 또는 재시도해도 결과가 같은 결정론적 파싱 실패(retryable_error=False)뿐이다.
네트워크-HTTP 오류처럼 다시 시도할 가치가 있는 실패는 completed에서 제외해 다음
실행에서 다시 요청하고, 같은 font_id가 여러 줄로 남으면 마지막 줄을 최신 판정으로
채택한다. 이렇게 실패와 완료를 구분해야 배치 단위 기록이 실패 건을 완료로 삼켜버린
문제(#142)를 실제로 피할 수 있다.

동시 실행 방지, robots.txt 확인, 신뢰 도메인 검증, Retry-After 반영은 #150에서
추가했다. 대상 규모(1,110종)에서 조회가 조용히 잘리거나 재검사 대상이 소리 없이
누락되는 사고(#128 계열)를 막기 위해 조회 정렬-완결성 검증도 함께 강화했다.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import random
import re
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot, extract_noonnu_font
from fontagit_pipeline.noonnu_seed import (
    _ROBOT_USER_AGENT,
    _ROBOTS_URL,
    _USER_AGENT,
    _parse_robots_policy,
)
from fontagit_pipeline.noonnu_url_audit import judge_official_url

logger = logging.getLogger(__name__)

_BASE_DELAY = 1.5
_JITTER = 0.7
_REQUEST_TIMEOUT = 10.0
_BACKOFF_DELAY = 30.0
_RATE_LIMIT_BACKOFF_BASE = 120.0
_RATE_LIMIT_BACKOFF_MAX = 960.0
_RATE_LIMIT_STATUS_CODES = frozenset({403, 429})
_MAX_CONSECUTIVE_FAILURES = 5
_MAX_REDIRECTS = 5
_ALLOWED_SCAN_HOSTS = ("noonnu.cc",)
_MIN_NORMAL_HTML_LENGTH = 30
_BLOCK_PAGE_PATTERN = re.compile(
    r"access denied|forbidden|blocked|captcha|too many requests|rate limit|"
    r"일시적으로 차단|비정상적인 접근|접근이 제한",
    re.IGNORECASE,
)


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
    official_url_contamination: str
    license_source_url_contamination: str
    recommended_action: str
    evidence: str
    error: str | None = None
    retryable_error: bool = False


class ScanAbortedError(RuntimeError):
    """연속 실패, robots.txt 거부 등으로 안전하게 중단했다."""


class ScanLockError(RuntimeError):
    """다른 스캔이 이미 같은 상태 파일을 쓰고 있어 잠금을 얻지 못했다."""


_REQUIRED_RECORD_KEYS = frozenset(
    {
        "font_id",
        "slug",
        "source_url",
        "db_official_url",
        "db_license_source_url",
        "db_license_verified",
        "new_official_url",
        "new_foundry",
        "classification",
        "official_url_contamination",
        "license_source_url_contamination",
        "recommended_action",
        "evidence",
        "error",
        "retryable_error",
    }
)


def _load_records(state_path: Path) -> dict[str, ScanRecord]:
    """상태 파일에 기록된 판정을 font_id별로 복원한다.

    필수 필드가 하나라도 빠진 줄(구버전 스키마, 기록 중 중단 등)은 신뢰할 수 없는
    부분 기록으로 보고 통째로 버린다. 기본값으로 채워 완료로 오인하면 실제로는
    검사되지 않은 대상을 건너뛰게 되기 때문이다. 같은 font_id가 여러 줄로 남아
    있으면(재시도 후 재기록) 마지막 줄을 채택한다.
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
        if not isinstance(payload, dict) or not _REQUIRED_RECORD_KEYS <= payload.keys():
            continue
        record = ScanRecord(
            font_id=str(payload["font_id"]),
            slug=str(payload["slug"]),
            source_url=str(payload["source_url"]),
            db_official_url=payload["db_official_url"],
            db_license_source_url=payload["db_license_source_url"],
            db_license_verified=bool(payload["db_license_verified"]),
            new_official_url=payload["new_official_url"],
            new_foundry=payload["new_foundry"],
            classification=str(payload["classification"]),
            official_url_contamination=str(payload["official_url_contamination"]),
            license_source_url_contamination=str(payload["license_source_url_contamination"]),
            recommended_action=str(payload["recommended_action"]),
            evidence=str(payload["evidence"]),
            error=payload["error"],
            retryable_error=bool(payload["retryable_error"]),
        )
        records[record.font_id] = record
    return records


def load_state_records(state_path: Path) -> list[ScanRecord]:
    """상태 파일에 지금까지 기록된 판정을 읽는다.

    스캔이 중단됐을 때 그 시점까지의 부분 리포트를 작성하는 용도로 쓴다.
    """
    return list(_load_records(state_path).values())


def _is_target_completed(record: ScanRecord | None, target: ScanTarget) -> bool:
    """이 record가 이번 target을 다시 검사하지 않아도 될 만큼 완료됐는지 본다.

    성공, 또는 재시도 가치 없는 결정론적 실패만 완료로 인정한다. 그마저도
    기록 당시의 source_url-DB 값이 지금 target과 다르면(운영자가 DB를 손으로
    고쳤거나 다른 눈누 페이지로 바뀐 경우) 그 판정은 이번 대상에 대한 것이
    아니므로 다시 검사한다.
    """
    if record is None or record.retryable_error:
        return False
    return (
        record.source_url == target.source_url
        and record.db_official_url == target.db_official_url
        and record.db_license_source_url == target.db_license_source_url
        and record.db_license_verified == target.db_license_verified
    )


def _append_record(state_path: Path, record: ScanRecord) -> None:
    """판정 1건을 상태 파일에 덧붙인다."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def _is_allowed_scan_url(url: str) -> bool:
    """스캔이 실제로 요청해도 되는 URL인지 검사한다(SSRF 방지).

    최초 대상뿐 아니라 fetch_scan_html의 리다이렉트 매 홉에서도 이 검사를
    거쳐야 한다. 그러지 않으면 눈누 서버가 임의 응답으로 다른 내부/외부
    호스트로 요청을 유도할 수 있다.
    """
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    return any(host == name or host.endswith(f".{name}") for name in _ALLOWED_SCAN_HOSTS)


def _build_untrusted_host_record(target: ScanTarget) -> ScanRecord:
    """눈누 도메인이 아닌 대상은 요청 없이 건너뛰고 그 사유를 남긴다."""
    verdict = judge_official_url(
        None,
        db_official_url=target.db_official_url,
        db_license_source_url=target.db_license_source_url,
    )
    return ScanRecord(
        font_id=target.font_id,
        slug=target.slug,
        source_url=target.source_url,
        db_official_url=target.db_official_url,
        db_license_source_url=target.db_license_source_url,
        db_license_verified=target.db_license_verified,
        new_official_url=None,
        new_foundry=None,
        classification="untrusted_source_host",
        official_url_contamination=verdict.official_url_contamination,
        license_source_url_contamination=verdict.license_source_url_contamination,
        recommended_action="manual_review",
        evidence=f"source_url이 신뢰 도메인(noonnu.cc)이 아니라 요청을 건너뜀: {target.source_url}",
        error="untrusted source_url host",
        retryable_error=False,
    )


@dataclass(frozen=True)
class FetchedPage:
    """HTML과 함께 감사 근거에 필요한 응답 메타를 담는다."""

    html: str
    final_url: str
    http_status: int


def fetch_scan_page(client: httpx.Client, url: str) -> FetchedPage:
    """눈누 상세 페이지를 받아 HTML과 응답 메타를 함께 돌려준다.

    `fetch_scan_html`과 같은 리다이렉트 정책을 쓰되, 감사 근거에 필요한
    최종 URL과 상태 코드를 버리지 않는다.
    """
    current_url = url
    for _ in range(_MAX_REDIRECTS):
        response = client.get(
            current_url,
            timeout=_REQUEST_TIMEOUT,
            headers={"User-Agent": _USER_AGENT},
            follow_redirects=False,
        )
        if not response.has_redirect_location:
            response.raise_for_status()
            return FetchedPage(
                html=response.text,
                final_url=current_url,
                http_status=response.status_code,
            )
        next_url = urljoin(current_url, response.headers["location"])
        if not _is_allowed_scan_url(next_url):
            raise ValueError(f"신뢰할 수 없는 리다이렉트 대상: {next_url}")
        current_url = next_url
    raise ValueError(f"리다이렉트 한도({_MAX_REDIRECTS})를 초과했습니다: {url}")


def fetch_scan_html(client: httpx.Client, url: str) -> str:
    """눈누 상세 HTML만 받는다. 기존 호출부 호환용 얇은 위임이다."""
    return fetch_scan_page(client, url).html


def _looks_like_normal_html_document(html: str) -> bool:
    """받은 내용이 진짜 HTML 문서인지, 차단/오류 페이지로 의심되는지 가른다.

    fetcher 인터페이스가 문자열만 돌려주므로 Content-Type 헤더는 여기서 볼 수
    없다. 본문 길이-태그-차단 문구만 보는 휴리스틱이라, 헤더 없이 판단 가능한
    범위의 한계를 가진다.
    """
    if len(html) < _MIN_NORMAL_HTML_LENGTH:
        return False
    lower = html.lower()
    if "<html" not in lower or "<body" not in lower:
        return False
    return not _BLOCK_PAGE_PATTERN.search(html)


def _parse_retry_after(value: str) -> float | None:
    """Retry-After 헤더 값을 초 단위로 환산한다.

    RFC 9110은 정수초와 HTTP-date 두 형식을 모두 허용한다.
    """
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max((parsed - datetime.now(timezone.utc)).total_seconds(), 0.0)


def _resolve_backoff_seconds(exc: Exception, consecutive_failures: int) -> float:
    """실패 원인에 따라 다음 요청 전 대기 시간을 정한다.

    429/403은 서버가 요청 예의를 지키라고 보내는 신호이므로, Retry-After가 있으면
    그 값을 우선 따르고 없으면 연속 실패 횟수에 따라 지수적으로 늘려 안전 중단
    (_MAX_CONSECUTIVE_FAILURES)에 가까워지게 한다.
    """
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in _RATE_LIMIT_STATUS_CODES:
        retry_after = exc.response.headers.get("Retry-After")
        if retry_after is not None:
            parsed_seconds = _parse_retry_after(retry_after)
            if parsed_seconds is not None:
                return min(parsed_seconds, _RATE_LIMIT_BACKOFF_MAX)
        return min(
            _RATE_LIMIT_BACKOFF_BASE * (2.0 ** (consecutive_failures - 1)),
            _RATE_LIMIT_BACKOFF_MAX,
        )
    return _BACKOFF_DELAY


@contextlib.contextmanager
def acquire_scan_lock(state_path: Path) -> Iterator[None]:
    """동시에 두 스캔이 같은 상태 파일에 쓰지 못하도록 파일 잠금을 건다.

    잠금 파일에 PID를 적어, 비정상 종료로 남은 잠금인지(stale) 실제로 그 PID의
    프로세스가 살아 있는지로 구분한다. 죽어 있으면 회수해 다시 획득하고, 살아
    있으면(또는 판정 불가하면 안전하게 살아있다고 보고) 거부한다.
    """
    lock_path = state_path.with_name(state_path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    _try_acquire_lock_file(lock_path)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _try_acquire_lock_file(lock_path: Path) -> None:
    """잠금 파일을 원자적으로 생성한다. 죽은 프로세스의 잠금이면 회수해 재시도한다."""
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if _lock_owner_is_alive(lock_path):
            raise ScanLockError(f"이미 실행 중인 스캔이 있습니다: {lock_path}") from None
        lock_path.unlink(missing_ok=True)
        _try_acquire_lock_file(lock_path)
        return
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(str(os.getpid()))


def _lock_owner_is_alive(lock_path: Path) -> bool:
    """잠금 파일에 적힌 PID의 프로세스가 살아 있는지 본다.

    PID를 읽을 수 없거나 생존 여부를 판정할 권한이 없으면, 실행 중인 스캔을
    잘못 회수해 두 스캔이 동시에 쓰는 사고를 막기 위해 안전하게 살아있다고 본다.
    """
    try:
        pid = int(lock_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def build_robots_checker(client: httpx.Client) -> Callable[[str], bool]:
    """robots.txt를 1회 받아 URL별 접근 허용 여부를 판정하는 함수를 만든다."""
    robots_text = fetch_scan_html(client, _ROBOTS_URL)
    policy = _parse_robots_policy(robots_text)
    return lambda url: policy.can_fetch(_ROBOT_USER_AGENT, url)


def scan_targets(
    targets: Iterable[ScanTarget],
    fetcher: Callable[[str], str],
    state_path: Path,
    sleeper: Callable[[float], None] = time.sleep,
    robots_checker: Callable[[str], bool] = lambda _url: True,
) -> list[ScanRecord]:
    """대상을 순회하며 공식 URL을 대조한다.

    Args:
        targets: 스캔 대상 목록.
        fetcher: URL을 받아 HTML을 돌려주는 함수.
        state_path: 진행 상태를 남길 JSONL 경로.
        sleeper: 대기 함수. 테스트에서 즉시 반환하도록 주입한다.
        robots_checker: URL별 robots.txt 허용 여부. 기본값은 항상 허용(테스트 호환용).

    Returns:
        이번에 넘어온 target_list에 한해, 상태 파일 기록과 이번 처리 결과를
        font_id당 1건으로 합친 목록. 과거 실행에서 남은 다른 대상의 기록은
        섞이지 않는다.

    Raises:
        ScanAbortedError: robots.txt가 거부하거나, 네트워크-HTTP 등 재시도
            가치가 있는 실패가 연속으로 한계를 넘어 중단한 경우. 결정론적
            파싱 실패는 이 카운터에 반영하지 않는다.
    """
    target_list: Sequence[ScanTarget] = list(targets)
    records = _load_records(state_path)
    consecutive_failures = 0

    for index, target in enumerate(target_list, start=1):
        if _is_target_completed(records.get(target.font_id), target):
            continue

        if not _is_allowed_scan_url(target.source_url):
            record = _build_untrusted_host_record(target)
            _append_record(state_path, record)
            records[record.font_id] = record
            logger.warning("신뢰할 수 없는 호스트라 건너뜀 %s: %s", target.slug, target.source_url)
            continue

        if not robots_checker(target.source_url):
            raise ScanAbortedError(f"robots.txt가 접근을 허용하지 않습니다: {target.source_url}")

        if index > 1:
            sleeper(_BASE_DELAY + random.uniform(0.0, _JITTER))

        should_abort = False
        try:
            html = fetcher(target.source_url)
        except Exception as exc:  # 네트워크-HTTP 등 일시적 실패 → 재개 시 재시도
            snapshot: NoonnuFontSnapshot | None = None
            error: str | None = f"{type(exc).__name__}: {exc}"
            retryable_error = True
            consecutive_failures += 1
            backoff = _resolve_backoff_seconds(exc, consecutive_failures)
            logger.warning("수집 실패 %s: %s (대기 %.0f초)", target.slug, error, backoff)
            sleeper(backoff)
            should_abort = consecutive_failures >= _MAX_CONSECUTIVE_FAILURES
        else:
            consecutive_failures = 0
            try:
                snapshot = extract_noonnu_font(html, target.source_url)
            except ValueError as exc:
                snapshot = None
                error = f"{type(exc).__name__}: {exc}"
                if _looks_like_normal_html_document(html):
                    # 정상적인 상세 페이지인데 컨테이너가 없는 결정론적 실패.
                    # 재시도해도 같은 결과이므로 회로차단기 카운터-백오프에 반영하지 않는다.
                    retryable_error = False
                    logger.warning("파싱 실패(재시도 안 함) %s: %s", target.slug, error)
                else:
                    # 차단/오류 페이지로 의심되는 비정상 응답. 재시도 가치가 있다.
                    retryable_error = True
                    consecutive_failures += 1
                    backoff = _resolve_backoff_seconds(exc, consecutive_failures)
                    logger.warning(
                        "비정상 응답으로 추정되는 파싱 실패(재시도) %s: %s (대기 %.0f초)",
                        target.slug,
                        error,
                        backoff,
                    )
                    sleeper(backoff)
                    should_abort = consecutive_failures >= _MAX_CONSECUTIVE_FAILURES
            except Exception as exc:  # 파싱 중 예상 못한 오류도 안전하게 재시도로 처리
                snapshot = None
                error = f"{type(exc).__name__}: {exc}"
                retryable_error = True
                consecutive_failures += 1
                backoff = _resolve_backoff_seconds(exc, consecutive_failures)
                logger.warning(
                    "파싱 중 예상치 못한 오류(재시도) %s: %s (대기 %.0f초)",
                    target.slug,
                    error,
                    backoff,
                )
                sleeper(backoff)
                should_abort = consecutive_failures >= _MAX_CONSECUTIVE_FAILURES
            else:
                error = None
                retryable_error = False

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
            official_url_contamination=verdict.official_url_contamination,
            license_source_url_contamination=verdict.license_source_url_contamination,
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

        if should_abort:
            raise ScanAbortedError(
                f"연속 {consecutive_failures}건 실패로 중단합니다. "
                f"상태 파일에서 재개하세요: {state_path}"
            )

    target_font_ids = {target.font_id for target in target_list}
    return [record for font_id, record in records.items() if font_id in target_font_ids]


_NO_CONTAINER_THRESHOLD = 0.05


def summarize(records: Sequence[ScanRecord]) -> dict[str, object]:
    """판정 분포를 집계한다.

    no_container 비율이 5%를 넘으면 눈누 페이지 구조 가정이 틀린 것이므로
    정정을 진행하지 않고 폴백 선택자 설계를 다시 봐야 한다.
    """
    total = len(records)
    classification: dict[str, int] = {}
    action: dict[str, int] = {}
    official_contamination: dict[str, int] = {}
    license_contamination: dict[str, int] = {}
    retryable_font_ids: list[str] = []
    for record in records:
        classification[record.classification] = classification.get(record.classification, 0) + 1
        action[record.recommended_action] = action.get(record.recommended_action, 0) + 1
        official_contamination[record.official_url_contamination] = (
            official_contamination.get(record.official_url_contamination, 0) + 1
        )
        license_contamination[record.license_source_url_contamination] = (
            license_contamination.get(record.license_source_url_contamination, 0) + 1
        )
        if record.retryable_error:
            retryable_font_ids.append(record.font_id)

    no_container_ratio = (classification.get("no_container", 0) / total) if total else 0.0
    return {
        "total": total,
        "classification": classification,
        "recommended_action": action,
        "official_url_contamination": official_contamination,
        "license_source_url_contamination": license_contamination,
        "error_count": sum(1 for record in records if record.error),
        "no_container_ratio": no_container_ratio,
        "structure_assumption_ok": no_container_ratio <= _NO_CONTAINER_THRESHOLD,
        "retryable_count": len(retryable_font_ids),
        "retryable_font_ids": retryable_font_ids,
    }


_PAGE_SIZE = 1000


def _select_all_rows(
    table: object, columns: str, eq_filters: dict[str, str], order_by: str
) -> list[dict[str, object]]:
    """1,000행 응답 제한을 넘는 전체 행을 range()로 페이지네이션해 읽는다.

    Supabase는 기본적으로 한 번에 1,000행만 반환하므로, 대상 규모(1,110종)에서
    페이지네이션 없이 읽으면 조용히 잘린다. 정렬 없이 range()만 반복하면 페이지
    사이 순서가 안정적이라는 보장이 없어 행이 중복되거나 누락될 수 있으므로
    order_by로 안정 정렬한 뒤, 받은 행의 정렬 키가 실제로 모두 고유한지 검증한다.
    """
    rows: list[dict[str, object]] = []
    offset = 0
    while True:
        query = table.select(columns)  # type: ignore[attr-defined]
        for column, value in eq_filters.items():
            query = query.eq(column, value)
        page = query.order(order_by).range(offset, offset + _PAGE_SIZE - 1).execute()
        page_rows = page.data
        if not isinstance(page_rows, list):
            raise RuntimeError(f"{columns} 조회 결과가 올바르지 않습니다")
        rows.extend(page_rows)
        if len(page_rows) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE

    unique_keys = {row.get(order_by) for row in rows}
    if len(unique_keys) != len(rows):
        raise RuntimeError(
            f"{columns} 페이지네이션 결과가 정렬 키 '{order_by}' 기준으로 "
            f"{len(rows)}행 중 {len(unique_keys)}개만 고유합니다(중복/누락 의심)"
        )
    return rows


def load_scan_targets(client: object) -> list[ScanTarget]:
    """눈누에서 온 발행 폰트와 그 상세 URL을 읽는다.

    font_sources(provider='noonnu')에 상세 URL이 있고, fonts에 현재 값이 있다.
    """
    schema = client.schema("fontagit")  # type: ignore[attr-defined]
    source_rows = _select_all_rows(
        schema.table("font_sources"),
        "id, font_id, source_url",
        {"provider": "noonnu"},
        order_by="id",
    )
    url_by_font: dict[str, str] = {
        str(row["font_id"]): str(row["source_url"]) for row in source_rows
    }

    font_rows = _select_all_rows(
        schema.table("fonts"),
        "id, slug, official_url, license_source_url, license_verified",
        {"status": "published"},
        order_by="id",
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
    if not targets:
        raise RuntimeError("스캔 대상이 0건입니다. 조회 조건 또는 DB 상태를 확인하세요.")
    return targets
