# Task 4 report: SSRF 방어 링크 관찰

## 범위

- `apps/pipeline/src/fontagit_pipeline/audit_http.py`
- `apps/pipeline/tests/test_audit_http.py`
- `apps/pipeline/tests/fixtures/audit/link-observations.json`

기존 web/docs staged·unstaged 변경은 수정하거나 stage 상태를 바꾸지 않았다. prod 요청·쓰기·migration·deploy도 실행하지 않았다.

## RED

`cd apps/pipeline && uv run pytest tests/test_audit_http.py -q`

처음에는 `ModuleNotFoundError: No module named 'fontagit_pipeline.audit_http'`로 실패했다. 새 공개 URL 관찰 모듈이 아직 없어서 발생한, 의도한 실패다.

## GREEN 및 검증

- `uv run pytest tests/test_audit_http.py -q` → `5 passed`
  - 공개 HTTPS → redirect hop마다 DNS 재확인 및 `--resolve` 고정
  - IPv4/IPv6 혼합 DNS 결과 중 private/link-local/loopback 결과 차단
  - 서로 다른 run_id의 404/410 관찰 두 건이 24시간 이상일 때만 `broken`
- `uv run ruff check src/fontagit_pipeline/audit_http.py tests/test_audit_http.py` → PASS
- `uv run mypy src/fontagit_pipeline/audit_http.py` → PASS
- `uv run pytest -q` → `169 passed`
- `uv run mypy src` → 기존 `noonnu_seed.py`, `noonnu_import.py`, `noonnu_review.py`의 7개 오류로 실패. Task 4 파일의 오류는 없고, 이번 변경 전부터 있던 기준선 오류다.
- userinfo, 비허용 scheme, localhost, loopback IPv6, 비표준 hostname의 차단을 외부 요청 없이 확인 → PASS

## 보안 결정과 남은 위험

- `http`/`https` 외 URL, userinfo, 빈·비표준 hostname, loopback/private/link-local/multicast/reserved/unspecified 및 global이 아닌 DNS 결과를 차단한다. A/AAAA 결과 중 하나라도 위험하면 전체 요청을 막는다.
- 자동 redirect를 쓰지 않고, Location마다 URL·DNS를 다시 검사한 뒤 `curl --resolve`로 확인한 IP만 사용한다. proxy 우회(`--noproxy *`), `shell=False`, TLS 기본 검증, 연결 5초/전체 20초/본문 1 MiB/redirect 5회 제한을 적용했다.
- 오류에는 URL, header, query token, 자격증명을 포함하지 않는다. 다만 공개 source URL 자체가 민감 query를 포함하면 이후 저장 단계(Task 6)에서 어떤 URL 필드를 보관할지 추가 정책 검토가 필요하다.

## 커밋

`50e4a23 feat: add safe font link observations`

## 보안 후속 수정: 전송 실패와 스트리밍 크기 제한

### RED

`cd apps/pipeline && uv run pytest tests/test_audit_http.py -q` → `3 failed, 5 passed`

- curl return code 28(timeout)·18(partial/network)인데도 남은 `200` 헤더와 stdout 때문에 정상 `FetchResult`가 반환되는 실패를 재현했다.
- Content-Length 없는 응답이 1MiB보다 1바이트 큰 경우 `subprocess.run`이 본문을 모두 모은 뒤에야 검사해, 스트리밍 중단 계약이 없음을 재현했다.

### GREEN 및 검증

- curl `0`만 정상 전송으로 취급한다. `22`는 HTTP 4xx/5xx 관찰에 한해 헤더의 status를 사용한다. `28`은 `FetchTimeoutError`, `63`은 `ResponseTooLargeError`, 나머지 nonzero는 `NetworkFetchError`로 분류한다.
- body는 curl stdout에서 남은 허용 용량 + 1바이트까지만 읽는다. 초과 바이트가 도착하면 즉시 process를 terminate/wait(필요 시 kill/wait)하고 임시 디렉터리는 정리된다. curl `--max-filesize`도 보조 방어로 유지했다.
- 오류 문구는 URL·헤더·stderr를 포함하지 않는다.
- `uv run pytest tests/test_audit_http.py -q` → `8 passed`
- `uv run ruff check src/fontagit_pipeline/audit_http.py tests/test_audit_http.py` → PASS
- `uv run mypy src/fontagit_pipeline/audit_http.py` → PASS
- `uv run pytest -q` → `172 passed`
- `uv run mypy src` → 기존 `noonnu_seed.py`, `noonnu_import.py`, `noonnu_review.py`의 7개 기준선 오류로 실패. Task 4 파일 오류 없음.

### 남은 위험

- curl 자체의 시간 제한(연결 5초, 전체 20초)에 의존한다. 외부 URL은 실행하지 않았고, DNS·subprocess는 고정 fixture로만 검증했다.
