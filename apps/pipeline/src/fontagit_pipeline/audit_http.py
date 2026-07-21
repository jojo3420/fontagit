"""감사 수집에서 외부 링크를 안전하게 관찰하는 HTTP 경계."""

import hashlib
import ipaddress
import socket
import subprocess
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

from fontagit_pipeline.audit_models import DownloadStatus

_MAX_BYTES = 1_048_576
_MAX_BODY_BYTES = 32 * 1024 * 1024
_MAX_REDIRECTS = 5
_READ_CHUNK_SIZE = 64 * 1024
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_CURL_BASE = (
    "curl",
    "-q",
    "--silent",
    "--show-error",
    "--fail-with-body",
    "--proto",
    "=http,https",
    "--noproxy",
    "*",
    "--max-time",
    "20",
    "--connect-timeout",
    "5",
    "--max-filesize",
    str(_MAX_BYTES),
    "--max-redirs",
    "0",
)


class FetchError(RuntimeError):
    """외부 링크를 관찰할 수 없을 때의 안전한 오류."""


class UnsafeAddressError(FetchError):
    """사설망 또는 형식이 잘못된 대상에 대한 요청 차단."""


class FetchTimeoutError(FetchError):
    """정해진 시간 안에 응답하지 않은 요청."""


class ResponseTooLargeError(FetchError):
    """응답 본문이 허용 크기를 넘긴 요청."""


class NetworkFetchError(FetchError):
    """HTTP 응답을 받지 못한 네트워크 요청."""


class RedirectLimitError(FetchError):
    """리다이렉트 횟수가 설정된 상한을 넘긴 요청."""


@dataclass(frozen=True)
class FetchResult:
    """검증된 공개 IP에 고정해 얻은 한 URL의 최종 응답."""

    status: int
    final_url: str
    content: bytes
    content_sha256: str
    redirect_count: int


@dataclass(frozen=True)
class _PublicTarget:
    url: str
    host: str
    port: int
    addresses: tuple[str, ...]


def _unsafe_url() -> UnsafeAddressError:
    return UnsafeAddressError("URL is not allowed for link observation")


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        return _is_public_address(mapped)
    return not (
        address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or getattr(address, "is_site_local", False)
        or not address.is_global
    )


def _canonical_host(hostname: str) -> tuple[str, ipaddress.IPv4Address | ipaddress.IPv6Address | None]:
    host = hostname.rstrip(".").lower()
    if not host or host == "localhost" or host.endswith(".local"):
        raise _unsafe_url()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise _unsafe_url() from error
        labels = host.split(".")
        if (
            len(labels) < 2
            or len(host) > 253
            or any(
                not label
                or len(label) > 63
                or label[0] == "-"
                or label[-1] == "-"
                or any(not (char.isascii() and (char.isalnum() or char == "-")) for char in label)
                for label in labels
            )
        ):
            raise _unsafe_url()
        return host, None
    if not _is_public_address(address):
        raise _unsafe_url()
    return str(address), address


def _split_public_url(url: str) -> tuple[SplitResult, str, int]:
    try:
        parts = urlsplit(url)
        port = parts.port
    except (TypeError, ValueError) as error:
        raise _unsafe_url() from error
    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"} or parts.username is not None or parts.password is not None:
        raise _unsafe_url()
    if not parts.netloc or parts.hostname is None:
        raise _unsafe_url()
    host, _ = _canonical_host(parts.hostname)
    effective_port = port if port is not None else (443 if scheme == "https" else 80)
    if effective_port < 1 or effective_port > 65535:
        raise _unsafe_url()
    return parts, host, effective_port


def _normalized_url(parts: SplitResult, host: str, port: int) -> str:
    scheme = parts.scheme.lower()
    default_port = 443 if scheme == "https" else 80
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port == default_port else f"{display_host}:{port}"
    return urlunsplit((scheme, netloc, parts.path or "/", parts.query, ""))


def _resolve_public_target(url: str) -> _PublicTarget:
    parts, host, port = _split_public_url(url)
    try:
        literal_address = ipaddress.ip_address(host)
    except ValueError:
        literal_address = None
    if literal_address is not None:
        return _PublicTarget(_normalized_url(parts, host, port), host, port, (str(literal_address),))

    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise NetworkFetchError("DNS lookup failed") from error

    addresses: list[str] = []
    for family, _, _, _, sockaddr in records:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            continue
        raw_address = sockaddr[0]
        if not isinstance(raw_address, str):
            raise _unsafe_url()
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as error:
            raise _unsafe_url() from error
        if not _is_public_address(address):
            raise _unsafe_url()
        canonical = str(address)
        if canonical not in addresses:
            addresses.append(canonical)
    if not addresses:
        raise NetworkFetchError("DNS lookup returned no public address")
    return _PublicTarget(_normalized_url(parts, host, port), host, port, tuple(addresses))


def _resolve_argument(target: _PublicTarget) -> str:
    display_host = f"[{target.host}]" if ":" in target.host else target.host
    addresses = ",".join(
        f"[{address}]" if ":" in address else address for address in target.addresses
    )
    return f"{display_host}:{target.port}:{addresses}"


def _header_values(headers: bytes) -> tuple[int | None, str | None]:
    """curl이 쓴 마지막 응답 헤더 블록에서 상태와 Location만 읽는다."""
    blocks = headers.replace(b"\r\n", b"\n").split(b"\n\n")
    for block in reversed(blocks):
        lines = block.splitlines()
        if not lines or not lines[0].startswith(b"HTTP/"):
            continue
        pieces = lines[0].split()
        if len(pieces) < 2:
            continue
        try:
            status = int(pieces[1])
        except ValueError:
            continue
        for line in lines[1:]:
            key, separator, value = line.partition(b":")
            if separator and key.strip().lower() == b"location":
                return status, value.strip().decode("latin-1")
        return status, None
    return None, None


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)


def _read_limited_body(process: subprocess.Popen[bytes], max_bytes: int) -> bytes:
    if process.stdout is None:
        _stop_process(process)
        raise NetworkFetchError("curl response stream is unavailable")
    content = bytearray()
    try:
        while True:
            remaining = max_bytes - len(content)
            chunk = process.stdout.read(min(_READ_CHUNK_SIZE, remaining + 1))
            if not chunk:
                return bytes(content)
            if len(chunk) > remaining:
                _stop_process(process)
                raise ResponseTooLargeError("response body exceeds byte limit")
            content.extend(chunk)
    except BaseException:
        _stop_process(process)
        raise


def _fetch_once(target: _PublicTarget, max_bytes: int) -> tuple[int, str | None, bytes]:
    with tempfile.TemporaryDirectory(prefix="fontagit-link-") as temporary_directory:
        directory = Path(temporary_directory)
        header_path = directory / "headers"
        command = [
            *_CURL_BASE,
            "--max-filesize",
            str(max_bytes),
            "--resolve",
            _resolve_argument(target),
            "--dump-header",
            str(header_path),
            "--output",
            "-",
            target.url,
        ]
        try:
            process = subprocess.Popen(
                command,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError as error:
            raise NetworkFetchError("curl request failed") from error

        try:
            content = _read_limited_body(process, max_bytes)
            try:
                returncode = process.wait(timeout=21)
            except subprocess.TimeoutExpired as error:
                _stop_process(process)
                raise FetchTimeoutError("link observation timed out") from error
        finally:
            _stop_process(process)

        status, location = _header_values(header_path.read_bytes() if header_path.exists() else b"")
        if returncode == 28:
            raise FetchTimeoutError("link observation timed out")
        if returncode == 63:
            raise ResponseTooLargeError("response body exceeds byte limit")
        if returncode not in {0, 22}:
            raise NetworkFetchError("curl request failed")
        if status is None or status == 0:
            raise NetworkFetchError("curl returned no HTTP response")
        return status, location, content


def fetch_public_url(
    url: str,
    *,
    max_bytes: int | None = None,
    max_body_bytes: int | None = None,
    max_redirects: int = _MAX_REDIRECTS,
    delay_seconds: float = 0.0,
) -> FetchResult:
    """공개 DNS 결과만 고정해 GET하고 리다이렉트마다 다시 검사한다."""
    if max_bytes is not None and max_body_bytes is not None:
        raise ValueError("link observation limits are outside the permitted range")
    body_limit = max_body_bytes if max_body_bytes is not None else max_bytes
    body_limit = _MAX_BYTES if body_limit is None else body_limit
    if (
        body_limit < 1
        or body_limit > _MAX_BODY_BYTES
        or max_redirects < 0
        or max_redirects > _MAX_REDIRECTS
    ):
        raise ValueError("link observation limits are outside the permitted range")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must be non-negative")

    if delay_seconds > 0:
        time.sleep(delay_seconds)

    current_url = url
    redirect_count = 0
    while True:
        target = _resolve_public_target(current_url)
        status, location, content = _fetch_once(target, body_limit)
        if status not in _REDIRECT_STATUSES or location is None:
            return FetchResult(
                status=status,
                final_url=target.url,
                content=content,
                content_sha256=hashlib.sha256(content).hexdigest(),
                redirect_count=redirect_count,
            )
        if redirect_count >= max_redirects:
            raise RedirectLimitError("redirect limit exceeded")
        current_url = urljoin(target.url, location)
        redirect_count += 1


def _field(observation: object, name: str) -> object | None:
    if isinstance(observation, Mapping):
        return observation.get(name)
    return getattr(observation, name, None)


def _observed_at(value: object | None) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo is not None else None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo is not None else None


def classify_download(observations: Sequence[object]) -> DownloadStatus:
    """관찰 기록만으로는 보수적으로 broken 또는 needs_review만 결정한다."""
    broken_observations: list[tuple[str, datetime]] = []
    for observation in observations:
        status = _field(observation, "http_status")
        run_id = _field(observation, "run_id")
        observed_at = _observed_at(_field(observation, "observed_at"))
        if status in {404, 410} and isinstance(run_id, str) and run_id.strip() and observed_at:
            broken_observations.append((run_id, observed_at))

    for index, (first_run_id, first_time) in enumerate(broken_observations):
        for second_run_id, second_time in broken_observations[index + 1 :]:
            if first_run_id != second_run_id and abs(second_time - first_time).total_seconds() >= 86_400:
                return "broken"
    return "needs_review"
