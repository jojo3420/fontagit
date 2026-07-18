"""안전한 외부 링크 관찰의 핵심 보안 계약."""

import json
import socket
import subprocess
from pathlib import Path

import pytest

from fontagit_pipeline.audit_http import (
    FetchTimeoutError,
    NetworkFetchError,
    ResponseTooLargeError,
    UnsafeAddressError,
    classify_download,
    fetch_public_url,
)


class _CompletedCurl:
    returncode = 0
    stderr = ""

    def __init__(self, status: int = 200) -> None:
        self.stdout = str(status)


class _StreamingCurl:
    returncode = 0
    stderr = ""

    def __init__(self, chunks: list[bytes], status: int = 200) -> None:
        self.stdout = _ChunkStream(chunks)
        self.stderr = _ChunkStream([])
        self.terminated = False
        self.waited = False

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return self.returncode

    def poll(self) -> int | None:
        return self.returncode if self.waited or self.terminated else None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.terminated = True


class _ChunkStream:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = iter(chunks)

    def read(self, _: int = -1) -> bytes:
        return next(self._chunks, b"")


def _dns_result(address: str) -> list[tuple[object, ...]]:
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr: tuple[object, ...]
    if family == socket.AF_INET6:
        sockaddr = (address, 443, 0, 0)
    else:
        sockaddr = (address, 443)
    return [(family, socket.SOCK_STREAM, 6, "", sockaddr)]


def test_public_https_rechecks_redirect_and_uses_pinned_curl_resolution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """각 hop은 공개 IP로 다시 확인하고 curl은 그 IP만 사용한다."""
    dns_calls: list[str] = []
    curl_calls: list[list[str]] = []
    headers = [
        b"HTTP/1.1 302 Found\r\nLocation: https://cdn.example/font.woff2\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Type: font/woff2\r\n\r\n",
    ]

    def fake_getaddrinfo(host: str, port: int, **_: object) -> list[tuple[object, ...]]:
        dns_calls.append(host)
        return _dns_result("93.184.216.34" if host == "fonts.example" else "1.1.1.1")

    def fake_popen(argv: list[str], *, shell: bool, **_: object) -> _StreamingCurl:
        curl_calls.append(argv)
        header_path = Path(argv[argv.index("--dump-header") + 1])
        response_headers = headers.pop(0)
        header_path.write_bytes(response_headers)
        assert shell is False
        return _StreamingCurl([b"font-data"])

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr("tempfile.gettempdir", lambda: str(tmp_path))

    result = fetch_public_url("https://fonts.example/download")

    assert result.status == 200
    assert result.final_url == "https://cdn.example/font.woff2"
    assert dns_calls == ["fonts.example", "cdn.example"]
    assert len(curl_calls) == 2
    assert "--resolve" in curl_calls[0]
    assert "fonts.example:443:93.184.216.34" in curl_calls[0]
    assert "cdn.example:443:1.1.1.1" in curl_calls[1]
    assert "--location" not in curl_calls[0]


@pytest.mark.parametrize(
    "addresses",
    [
        ["93.184.216.34", "169.254.169.254"],
        ["93.184.216.34", "10.0.0.1"],
        ["2606:4700:4700::1111", "::1"],
    ],
)
def test_private_or_metadata_dns_result_is_blocked_before_curl(
    monkeypatch: pytest.MonkeyPatch, addresses: list[str]
) -> None:
    """혼합 DNS 응답도 하나라도 내부망이면 요청 전체를 차단한다."""
    called = False

    def fake_getaddrinfo(host: str, port: int, **_: object) -> list[tuple[object, ...]]:
        return [item for address in addresses for item in _dns_result(address)]

    def fake_run(*_: object, **__: object) -> _CompletedCurl:
        nonlocal called
        called = True
        return _CompletedCurl()

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(UnsafeAddressError):
        fetch_public_url("https://metadata.example/latest")

    assert called is False


@pytest.mark.parametrize(
    ("returncode", "error"),
    [(28, FetchTimeoutError), (18, NetworkFetchError)],
)
def test_curl_transport_failure_cannot_be_mistaken_for_http_success(
    monkeypatch: pytest.MonkeyPatch, returncode: int, error: type[Exception]
) -> None:
    """남은 200 헤더·stdout이 있어도 timeout/전송 실패는 정상 응답이 아니다."""

    def fake_getaddrinfo(host: str, port: int, **_: object) -> list[tuple[object, ...]]:
        return _dns_result("93.184.216.34")

    def fake_popen(argv: list[str], **_: object) -> _StreamingCurl:
        header_path = Path(argv[argv.index("--dump-header") + 1])
        header_path.write_bytes(b"HTTP/1.1 200 OK\r\n\r\n")
        result = _StreamingCurl([b"partial"])
        result.returncode = returncode
        return result

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with pytest.raises(error):
        fetch_public_url("https://fonts.example/download")


def test_chunked_body_is_terminated_as_soon_as_it_exceeds_limit(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Content-Length가 없어도 max_bytes 다음 1바이트에서 전송을 끊는다."""
    process = _StreamingCurl([b"1234", b"5"])

    def fake_getaddrinfo(host: str, port: int, **_: object) -> list[tuple[object, ...]]:
        return _dns_result("93.184.216.34")

    def fake_popen(*_: object, **__: object) -> _StreamingCurl:
        return process

    def forbidden_run(*_: object, **__: object) -> _CompletedCurl:
        raise AssertionError("body must be streamed instead of collected by subprocess.run")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subprocess, "run", forbidden_run)

    with pytest.raises(ResponseTooLargeError):
        fetch_public_url("https://fonts.example/download", max_bytes=4)

    assert process.terminated is True


def test_broken_requires_two_independent_observations_24_hours_apart() -> None:
    """한 번의 404는 삭제 근거가 아니며, 서로 다른 실행 기록 두 개가 필요하다."""
    fixture = Path(__file__).parent / "fixtures" / "audit" / "link-observations.json"
    observations = json.loads(fixture.read_text(encoding="utf-8"))

    assert classify_download(observations[:1]) == "needs_review"
    assert classify_download(observations) == "broken"
