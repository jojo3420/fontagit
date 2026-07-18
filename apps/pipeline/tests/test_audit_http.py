"""안전한 외부 링크 관찰의 핵심 보안 계약."""

import json
import socket
import subprocess
from pathlib import Path

import pytest

from fontagit_pipeline.audit_http import (
    UnsafeAddressError,
    classify_download,
    fetch_public_url,
)


class _CompletedCurl:
    returncode = 0
    stderr = ""

    def __init__(self, status: int = 200) -> None:
        self.stdout = str(status)


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

    def fake_run(
        argv: list[str], *, timeout: float, shell: bool, **_: object
    ) -> _CompletedCurl:
        curl_calls.append(argv)
        header_path = Path(argv[argv.index("--dump-header") + 1])
        body_path = Path(argv[argv.index("--output") + 1])
        response_headers = headers.pop(0)
        header_path.write_bytes(response_headers)
        body_path.write_bytes(b"font-data")
        assert timeout == 21
        assert shell is False
        return _CompletedCurl(302 if b" 302 " in response_headers else 200)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(subprocess, "run", fake_run)
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


def test_broken_requires_two_independent_observations_24_hours_apart() -> None:
    """한 번의 404는 삭제 근거가 아니며, 서로 다른 실행 기록 두 개가 필요하다."""
    fixture = Path(__file__).parent / "fixtures" / "audit" / "link-observations.json"
    observations = json.loads(fixture.read_text(encoding="utf-8"))

    assert classify_download(observations[:1]) == "needs_review"
    assert classify_download(observations) == "broken"
