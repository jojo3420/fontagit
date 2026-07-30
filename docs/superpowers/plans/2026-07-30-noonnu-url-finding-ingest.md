# 눈누 URL 정정 finding 적재 경로 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 눈누 official_url/license_source_url 오염 185종을 근거를 갖춘 감사 경로로 적재해 dev와 prod에 정정 적용한다.

**Architecture:** 기존 스캔기(`noonnu_url_scan.py`)에 감사 저장소 적재를 배선한다. 원문 HTML이 손에 있는 순간에만 정직한 해시를 만들 수 있으므로 크롤과 적재를 한 흐름에 둔다. 적재 이후는 기존 파이프라인(auto-approve -> manifest build -> preflight -> apply)을 그대로 탄다. 새 모듈은 만들지 않는다.

**Tech Stack:** Python 3.12 + uv, httpx, BeautifulSoup, Supabase(PostgreSQL), pytest, ruff, mypy

**설계 문서:** `docs/superpowers/specs/2026-07-30-noonnu-url-finding-ingest-design.md`
**듀얼 리뷰:** `docs/review/review-result-dual-20260730-173719.md`

## Global Constraints

- 작업 디렉터리: `apps/pipeline` (모든 `uv run` 명령은 여기서 실행)
- 크롤 예의: 요청 간 최소 1초 지연, 동시 요청 금지, 브라우저 User-Agent (기존 `noonnu_url_scan._USER_AGENT` 사용)
- prod 쓰기(INSERT/UPDATE/DDL)는 **쿼리 전문을 사용자에게 보여 승인받은 뒤에만** 실행한다
- PR 머지, 브랜치 삭제 등 되돌리기 부담 작업은 사용자 승인 후에만 실행한다
- 기존 판정 로직(`noonnu_url_audit.py`)과 추출 로직(`audit_noonnu.py`)은 변경하지 않는다
- 기존 테스트를 깨뜨리지 않는다: `uv run pytest -q`가 472 passed, 4 skipped 유지
- `uv run ruff check .` 통과, `uv run mypy src`는 **기존 baseline 대비 신규 오류 0건** (총계 70 유지만 확인하면 신규 오류가 기존 오류 감소에 가려진다)
- 타입 힌트 100%, docstring 한국어, `print` 금지(`logging` 사용), 하드코딩 대신 상수
- 오염 URL 상수값: `https://www.instagram.com/noonnu_official/`
- 대상 건수: `auto_fix_safe` 174 / `manual_review` 10 / `nullify` 1 = 185종

---

## File Structure

| 파일 | 역할 | 변경 |
|---|---|---|
| `src/fontagit_pipeline/noonnu_url_scan.py` | 크롤 + 판정 오케스트레이션 | `FetchedPage` 신설, `scan_targets`에 적재 배선 |
| `src/fontagit_pipeline/noonnu_url_ingest.py` | **신설.** `ScanRecord` -> `SnapshotDraft`/`FindingDraft` 변환 | 신규 |
| `src/fontagit_pipeline/__main__.py` | CLI 배선 | `noonnu-url-scan`에 플래그 3개 추가 |
| `tests/test_noonnu_url_ingest.py` | **신설.** 변환 함수 단위 테스트 | 신규 |
| `tests/test_noonnu_url_scan.py` | 기존 스캔 테스트 | 적재 배선 테스트 추가 |
| `scripts/verify-noonnu-url-fix.sql` | **신설.** 검증 쿼리 모음 | 신규 |

변환 로직을 `noonnu_url_scan.py`에 넣지 않고 별도 모듈로 뺀 이유: 스캔기는 이미 600줄이 넘고 크롤-재시도-잠금-판정을 담당한다. 여기에 감사 저장소 스키마 지식까지 넣으면 책임이 둘로 갈린다. 변환은 순수 함수라 저장소 없이 단위 테스트할 수 있다.

---

## Task 1: prod 적용 경로 실측 검증 (코드 변경 없음)

이 작업은 **조사와 문서화만** 한다. 결과에 따라 Task 8의 내용이 달라지므로 반드시 먼저 수행한다.

설계 문서 3.7절이 "manifest는 `SourceKey(provider, provider_record_id)`를 키로 쓰므로 dev/prod의 `fonts.id`가 달라도 대상을 찾는다"고 적었으나, **`provider_record_id`가 어디서 오는지는 미확인**이다. `audit_manifest.py:333-335`는 snapshot에 저장된 `provider_record_id`와 대조할 뿐이므로, snapshot에 무엇을 넣어야 prod에서 올바른 폰트를 찾는지 확인해야 한다.

**Files:**
- Create: `docs/progress/2026-07-30-manifest-prod-path-verification.md`

**Interfaces:**
- Produces: `PROVIDER_RECORD_ID_SOURCE` (Task 3이 snapshot에 넣을 값의 출처와 형식), `CONFIDENCE_VALUE` (Task 3이 `FindingDraft.confidence`에 넣을 값)

- [x] **Step 1: manifest apply가 대상 폰트를 찾는 경로를 코드로 추적**

```bash
cd apps/pipeline
# apply RPC에 무엇이 전달되는지
grep -n "def main_audit_manifest_apply" -A 60 src/fontagit_pipeline/__main__.py | grep -n "rpc\|source_key\|provider_record_id\|font_id"
# 0026 마이그레이션이 대상을 찾는 SQL
grep -n "provider_record_id\|font_sources\|from fontagit.fonts" supabase/../../supabase/migrations/0026_manifest_official_url.sql
```

확인할 것: apply가 `font_id`로 직접 찾는지, `(provider, provider_record_id)`로 조인해 찾는지. 전자라면 prod에는 dev의 `font_id`가 없으므로 **설계 3.7절이 틀린 것이며 Task 8을 전면 재설계해야 한다.**

- [x] **Step 2: dev의 font_sources 실제 컬럼과 값 형식 확인 (읽기 전용)**

```bash
# MCP supabase-dev로 실행
# select column_name from information_schema.columns
#  where table_schema='fontagit' and table_name='font_sources';
# select provider, provider_record_id, source_url from fontagit.font_sources
#  where provider='noonnu' limit 5;
```

`provider_record_id` 컬럼이 없다면 snapshot의 값은 코드가 만들어 넣는 것이며, 그 규칙(`source_url`의 마지막 경로 조각인지 등)을 `audit_bootstrap.py:268,294`에서 확인한다.

- [x] **Step 3: prod에서 같은 조회 (읽기 전용)**

```bash
# MCP supabase-prod로 동일 쿼리 실행
# 대상 185종의 provider_record_id가 각각 정확히 1건인지:
# select provider_record_id, count(*) from fontagit.font_sources
#  where provider='noonnu' group by 1 having count(*) > 1;
```

기대: 0행 (중복 없음). 중복이 있으면 목록을 기록하고 사용자에게 보고한 뒤 중단한다.

- [x] **Step 4: auto-approve가 승인 대상을 고르는 조건 확인**

```bash
grep -n "def main_audit_review" -A 50 src/fontagit_pipeline/__main__.py | grep -n "auto_applicable\|confidence\|evidence\|status"
```

확인할 것: `auto_applicable=True`만 보는지, `confidence` 값도 보는지, "evidence-values 대조"가 정확히 무엇을 대조하는지(help 문구에 언급됨). Task 3이 `confidence`에 넣을 값이 여기서 정해진다.

- [x] **Step 5: 결과를 문서로 남기고 커밋**

`docs/progress/2026-07-30-manifest-prod-path-verification.md`에 위 4단계 결과를 표로 정리한다. 각 항목에 실행한 명령과 출력을 함께 남긴다. 추측은 쓰지 않고 확인된 것만 적는다.

```bash
git add docs/progress/2026-07-30-manifest-prod-path-verification.md
git commit -m "docs: manifest prod 적용 경로 실측 검증 (#150)"
```

- [x] **Step 6: 사용자에게 보고하고 승인 대기**

Step 1의 결과가 "font_id로 직접 찾음"이면 설계 3.7절이 틀린 것이므로, **다음 작업으로 넘어가지 말고** 사용자에게 보고한다. `(provider, provider_record_id)` 조인이면 그대로 진행한다.

---

## Task 2: FetchedPage 도입 (final_url, http_status 확보)

`SnapshotDraft`는 `final_url`(필수)과 `http_status`(선택)를 받는데, 현재 `fetch_scan_html`은 HTML 문자열만 돌려준다(`noonnu_url_scan.py:238`). 리다이렉트를 수동 루프로 따라가면서 최종 URL을 이미 알고 있으므로 버리지 않고 함께 반환한다.

기존 `scan_targets(fetcher: Callable[[str], str])`를 쓰는 테스트가 여럿이므로 **기존 시그니처는 그대로 두고** 새 fetcher를 별도 파라미터로 추가한다.

**Files:**
- Modify: `src/fontagit_pipeline/noonnu_url_scan.py` (`FetchedPage` 추가, `fetch_scan_page` 추가)
- Test: `tests/test_noonnu_url_scan.py`

**Interfaces:**
- Produces: `FetchedPage(html: str, final_url: str, http_status: int)`, `fetch_scan_page(client: httpx.Client, url: str) -> FetchedPage`

- [x] **Step 1: 실패하는 테스트를 쓴다**

`tests/test_noonnu_url_scan.py` 끝에 추가:

```python
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
```

파일 상단 import에 `fetch_scan_page`를 추가한다.

- [x] **Step 2: 실패를 확인한다**

```bash
cd apps/pipeline
uv run pytest tests/test_noonnu_url_scan.py::test_fetch_scan_page_returns_final_url_after_redirect -v
```

Expected: FAIL, `ImportError: cannot import name 'fetch_scan_page'`

- [x] **Step 3: 최소 구현**

`noonnu_url_scan.py`의 `fetch_scan_html` 정의 바로 앞에 데이터클래스를 추가한다:

```python
@dataclass(frozen=True)
class FetchedPage:
    """HTML과 함께 감사 근거에 필요한 응답 메타를 담는다."""

    html: str
    final_url: str
    http_status: int
```

`fetch_scan_html` 본문을 `fetch_scan_page`로 옮기고, 기존 함수는 얇은 위임으로 남긴다:

```python
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
```

기존 `fetch_scan_html`의 docstring 중 리다이렉트 정책 설명은 `fetch_scan_page`로 옮긴다.

- [x] **Step 4: 통과 확인 + 회귀**

```bash
cd apps/pipeline
uv run pytest tests/test_noonnu_url_scan.py -q
```

Expected: 새 테스트 PASS, 기존 테스트 전부 PASS

- [x] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py apps/pipeline/tests/test_noonnu_url_scan.py
git commit -m "feat: 스캔 fetch가 최종 URL과 상태 코드를 함께 반환 (#150)"
```

---

## Task 2.5: 사람 배치 승인에 official_url 허용

Task 1에서 확인된 차단 결함을 푼다. `0026` 마이그레이션이 manifest 레벨에서 `official_url`을 허용했으나 Python 승인 화이트리스트가 따라오지 않아, 현재 이 필드는 어떤 경로로도 승인할 수 없다.

사용자 결정(2026-07-30): **사람 배치 승인(`font-audit-review approve`)만 연다.** 무인 승인(`auto-approve`)의 대상 필드는 건드리지 않는다. 실서비스 적용 전 사용자 승인 절차가 이미 있어 실질 게이트가 존재하고, 무인 경로를 열려면 근거-값 대조 로직을 새로 짜야 해 그 자체가 버그 지점이 되기 때문이다.

**Files:**
- Modify: `src/fontagit_pipeline/audit_store.py:27-37`
- Test: `tests/test_audit_store.py`

**Interfaces:**
- Produces: `MANUAL_APPROVABLE_FIELDS`에 `"official_url"` 포함

- [x] **Step 1: 실패하는 테스트를 쓴다**

`tests/test_audit_store.py`에 추가한다(파일이 없으면 신규 생성하고 `from fontagit_pipeline.audit_store import MANUAL_APPROVABLE_FIELDS`를 import한다):

```python
def test_official_url_is_manually_approvable() -> None:
    """0026이 manifest에서 허용한 official_url을 승인 경로도 받아야 한다."""
    assert "official_url" in MANUAL_APPROVABLE_FIELDS


def test_legal_fields_stay_excluded() -> None:
    """법적 판정 필드는 사람 배치 승인 대상이 아니다."""
    assert "allow_commercial" not in MANUAL_APPROVABLE_FIELDS
    assert "license_verified" not in MANUAL_APPROVABLE_FIELDS
```

- [x] **Step 2: 실패를 확인한다**

```bash
cd apps/pipeline
uv run pytest tests/test_audit_store.py -k "manually_approvable or legal_fields" -v 2>&1 | tail -8
```

Expected: `test_official_url_is_manually_approvable` FAIL, `test_legal_fields_stay_excluded` PASS

- [x] **Step 3: 상수에 필드를 추가한다**

`audit_store.py:27-37`을 다음으로 바꾼다. 알파벳 순서가 아니라 기존 나열 순서를 유지하고 마지막에 덧붙인다:

```python
MANUAL_APPROVABLE_FIELDS = frozenset(
    {
        "tags",
        "weights",
        "foundry",
        "foundry_url",
        "download_url",
        "download_source_kind",
        "license_source_url",
        "official_url",
    }
)
```

기존에 상수 위에 docstring이나 주석이 있으면 그대로 두고, 없으면 아래 한 줄을 상수 바로 뒤에 붙인다:

```python
"""사람이 검수를 마쳤을 때만 승인 가능한 필드. 법적 판정 필드는 영구 제외한다.

`official_url`은 0026 마이그레이션이 manifest 허용 필드에 넣었으나 이 상수에
빠져 있어 승인이 막혀 있었다(#150 Task 1에서 발견).
"""
```

- [x] **Step 4: 통과 확인 + 전체 회귀**

```bash
cd apps/pipeline
uv run pytest -q 2>&1 | tail -4
```

Expected: 신규 2건 PASS, 기존 473 passed 유지

⚠️ 이 상수를 참조하는 곳이 5군데(`__main__.py:1440,1441,1489`, `audit_store.py:566`)이므로 기존 테스트가 필드 목록을 하드코딩해 단언하고 있다면 함께 깨진다. 깨지면 그 테스트가 무엇을 지키려던 것인지 확인하고, 목록 자체를 검사하는 테스트라면 `official_url`을 더한다.

- [x] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/audit_store.py apps/pipeline/tests/test_audit_store.py
git commit -m "fix: official_url을 사람 배치 승인 대상에 추가 (#150)"
```

---

## Task 3: ScanRecord -> 감사 Draft 변환

순수 함수만 담은 새 모듈이다. 저장소나 네트워크에 의존하지 않으므로 단위 테스트가 쉽다.

**Files:**
- Create: `src/fontagit_pipeline/noonnu_url_ingest.py`
- Test: `tests/test_noonnu_url_ingest.py`

**Interfaces:**
- Consumes: `ScanRecord`(Task 대상 판정 1건), `FetchedPage`(Task 2), `SnapshotDraft`/`FindingDraft`(`audit_store.py:40,62`)
- Produces:
  - `NOONNU_ACCOUNT_URL: str`
  - `AUTO_APPLICABLE_ACTIONS: frozenset[str]`
  - `provider_record_id_from_source_url(source_url: str) -> str`
  - `build_snapshot_draft(record: ScanRecord, page: FetchedPage) -> SnapshotDraft`
  - `build_finding_drafts(record: ScanRecord, evidence_id: UUID) -> list[FindingDraft]`

- [x] **Step 1: 실패하는 테스트를 쓴다**

`tests/test_noonnu_url_ingest.py` 신규 작성:

```python
"""눈누 URL 스캔 결과를 감사 저장소 draft로 옮기는 변환 테스트."""

from uuid import UUID

from fontagit_pipeline.noonnu_url_ingest import (
    build_finding_drafts,
    build_snapshot_draft,
    provider_record_id_from_source_url,
)
from fontagit_pipeline.noonnu_url_scan import FetchedPage, ScanRecord

_EVIDENCE_ID = UUID("11111111-1111-1111-1111-111111111111")
_FONT_ID = "22222222-2222-2222-2222-222222222222"
_NOONNU_ACCOUNT = "https://www.instagram.com/noonnu_official/"


def _record(**overrides: object) -> ScanRecord:
    """auto_fix_safe 판정 1건을 기본값으로 만든다."""
    base = {
        "font_id": _FONT_ID,
        "slug": "sample-font",
        "source_url": "https://noonnu.cc/font_page/589",
        "db_official_url": _NOONNU_ACCOUNT,
        "db_license_source_url": _NOONNU_ACCOUNT,
        "db_license_verified": True,
        "new_official_url": "https://clova.ai/handwriting",
        "new_foundry": "네이버",
        "classification": "mismatch",
        "official_url_contamination": "noonnu_account",
        "license_source_url_contamination": "noonnu_account",
        "recommended_action": "auto_fix_safe",
        "evidence": "앵커 텍스트 '다운로드 페이지로 이동' + 검증된 제작사 호스트",
        "error": None,
        "retryable_error": False,
    }
    base.update(overrides)
    return ScanRecord(**base)  # type: ignore[arg-type]


def _page() -> FetchedPage:
    return FetchedPage(
        html="<html><body>본문</body></html>",
        final_url="https://noonnu.cc/font_page/589",
        http_status=200,
    )


def test_provider_record_id_extracted_from_source_url() -> None:
    assert provider_record_id_from_source_url("https://noonnu.cc/font_page/589") == "589"


def test_snapshot_hash_is_deterministic() -> None:
    """같은 입력은 항상 같은 해시를 낳는다."""
    first = build_snapshot_draft(_record(), _page())
    second = build_snapshot_draft(_record(), _page())

    assert first.normalized_sha256 == second.normalized_sha256
    assert first.raw_sha256 == second.raw_sha256


def test_snapshot_carries_response_metadata() -> None:
    snapshot = build_snapshot_draft(_record(), _page())

    assert snapshot.provider == "noonnu"
    assert snapshot.provider_record_id == "589"
    assert snapshot.request_url == "https://noonnu.cc/font_page/589"
    assert snapshot.final_url == "https://noonnu.cc/font_page/589"
    assert snapshot.http_status == 200
    assert snapshot.extracted["official_url"] == "https://clova.ai/handwriting"


def test_auto_fix_safe_produces_two_applicable_findings() -> None:
    """official_url과 license_source_url 두 건이 자동 적용 대상으로 나온다."""
    findings = build_finding_drafts(_record(), _EVIDENCE_ID)

    by_field = {f.field_name: f for f in findings}
    assert set(by_field) == {"official_url", "license_source_url"}
    assert by_field["official_url"].proposed_value == "https://clova.ai/handwriting"
    assert by_field["license_source_url"].proposed_value == "https://noonnu.cc/font_page/589"
    assert all(f.auto_applicable for f in findings)
    assert all(f.evidence_id == _EVIDENCE_ID for f in findings)
    assert all(f.before_value == _NOONNU_ACCOUNT for f in findings)


def test_manual_review_is_not_auto_applicable() -> None:
    findings = build_finding_drafts(
        _record(recommended_action="manual_review"), _EVIDENCE_ID
    )

    assert findings
    assert not any(f.auto_applicable for f in findings)


def test_nullify_splits_by_field() -> None:
    """official_url은 대체값이 없어 사람 검수로, license_source_url은 자동 정정."""
    findings = build_finding_drafts(
        _record(
            recommended_action="nullify",
            classification="no_link",
            new_official_url=None,
        ),
        _EVIDENCE_ID,
    )

    by_field = {f.field_name: f for f in findings}
    assert by_field["license_source_url"].auto_applicable is True
    assert by_field["license_source_url"].proposed_value == "https://noonnu.cc/font_page/589"
    assert by_field["official_url"].auto_applicable is False
    assert by_field["official_url"].proposed_value is None


def test_uncontaminated_field_is_skipped() -> None:
    """오염되지 않은 필드는 finding을 만들지 않는다."""
    findings = build_finding_drafts(
        _record(
            db_license_source_url="https://noonnu.cc/font_page/589",
            license_source_url_contamination="none",
        ),
        _EVIDENCE_ID,
    )

    assert {f.field_name for f in findings} == {"official_url"}
```

- [x] **Step 2: 실패를 확인한다**

```bash
cd apps/pipeline
uv run pytest tests/test_noonnu_url_ingest.py -q
```

Expected: FAIL, `ModuleNotFoundError: No module named 'fontagit_pipeline.noonnu_url_ingest'`

- [x] **Step 3: 구현**

`src/fontagit_pipeline/noonnu_url_ingest.py` 신규 작성:

```python
"""눈누 URL 스캔 판정을 감사 저장소 draft로 옮긴다.

스캔기(`noonnu_url_scan`)는 크롤과 판정을, 이 모듈은 감사 스키마로의 변환만
맡는다. 저장소나 네트워크에 의존하지 않는 순수 함수라 단위 테스트가 쉽다.
"""

from __future__ import annotations

import hashlib
import json
from urllib.parse import urlparse
from uuid import UUID

from fontagit_pipeline.audit_store import FindingDraft, SnapshotDraft
from fontagit_pipeline.noonnu_url_scan import FetchedPage, ScanRecord

NOONNU_ACCOUNT_URL = "https://www.instagram.com/noonnu_official/"
"""눈누 자체 SNS 주소. 이 값이 들어 있으면 오염이다."""

AUTO_APPLICABLE_ACTIONS = frozenset({"auto_fix_safe"})
"""자동 승인 대상 판정. 나머지는 전부 사람 검수로 남긴다."""

_PROVIDER = "noonnu"
_EXTRACTION_RULE_ID = "noonnu-url-scan-content-anchor-v2"
_PARSER_VERSION = "noonnu-url-scan-v2"
_CONFIDENCE = "reference"


def provider_record_id_from_source_url(source_url: str) -> str:
    """눈누 상세 URL에서 폰트 페이지 번호를 뽑는다.

    예: https://noonnu.cc/font_page/589 -> "589"

    Raises:
        ValueError: 경로 마지막 조각이 비어 있어 식별자를 만들 수 없는 경우.
    """
    record_id = urlparse(source_url).path.rstrip("/").rsplit("/", 1)[-1]
    if not record_id:
        raise ValueError(f"source_url에서 provider_record_id를 얻지 못했습니다: {source_url}")
    return record_id


def build_snapshot_draft(record: ScanRecord, page: FetchedPage) -> SnapshotDraft:
    """판정 1건과 그 근거가 된 응답으로 감사 근거를 만든다."""
    extracted: dict[str, object] = {
        "official_url": record.new_official_url,
        "foundry": record.new_foundry,
        "classification": record.classification,
        "recommended_action": record.recommended_action,
        "anchor_evidence": record.evidence,
    }
    normalized_sha256 = hashlib.sha256(
        json.dumps(
            extracted,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return SnapshotDraft(
        font_id=UUID(record.font_id),
        provider=_PROVIDER,
        provider_record_id=provider_record_id_from_source_url(record.source_url),
        source_kind="noonnu",
        document_kind="font_detail",
        request_url=record.source_url,
        final_url=page.final_url,
        http_status=page.http_status,
        raw_text=None,
        raw_sha256=hashlib.sha256(page.html.encode("utf-8")).hexdigest(),
        normalized_sha256=normalized_sha256,
        extracted=extracted,
        evidence_locations={
            "official_url": record.evidence,
            "license_source_url": "noonnu detail license table",
        },
        extraction_rule_id=_EXTRACTION_RULE_ID,
        parser_version=_PARSER_VERSION,
    )


def build_finding_drafts(record: ScanRecord, evidence_id: UUID) -> list[FindingDraft]:
    """오염된 필드마다 정정 후보를 만든다.

    `auto_applicable`은 07-29 판정이 아니라 이 레코드(재크롤 시점 판정)를
    기준으로 정한다. `official_url`은 대체값이 있을 때만 자동 적용 대상이
    되며, 값이 없으면(`nullify`) 사람 검수로 남긴다. `license_source_url`은
    눈누 상세 페이지라는 확정된 대체값이 있어 판정과 무관하게 채울 수 있다.
    """
    font_id = UUID(record.font_id)
    auto = record.recommended_action in AUTO_APPLICABLE_ACTIONS
    drafts: list[FindingDraft] = []

    if record.official_url_contamination != "none":
        drafts.append(
            FindingDraft(
                font_id=font_id,
                field_name="official_url",
                before_value=record.db_official_url,
                proposed_value=record.new_official_url,
                evidence_id=evidence_id,
                confidence=_CONFIDENCE,
                auto_applicable=auto and record.new_official_url is not None,
                review_reason=(
                    f"눈누 오염({record.official_url_contamination}) 정정: "
                    f"{record.evidence}"
                ),
            )
        )

    if record.license_source_url_contamination != "none":
        drafts.append(
            FindingDraft(
                font_id=font_id,
                field_name="license_source_url",
                before_value=record.db_license_source_url,
                proposed_value=record.source_url,
                evidence_id=evidence_id,
                confidence=_CONFIDENCE,
                auto_applicable=auto or record.recommended_action == "nullify",
                review_reason=(
                    f"눈누 오염({record.license_source_url_contamination}) 정정: "
                    "라이선스 표를 실제로 확인한 눈누 상세 페이지로 교체"
                ),
            )
        )

    return drafts
```

- [x] **Step 4: 통과 확인**

```bash
cd apps/pipeline
uv run pytest tests/test_noonnu_url_ingest.py -q
```

Expected: 7 passed

- [x] **Step 5: Task 1 결과를 반영한다**

Task 1 Step 4에서 확인한 `auto-approve`의 승인 조건이 `confidence` 값을 본다면, `_CONFIDENCE` 상수를 그 값으로 바꾸고 테스트에 단언을 추가한다. `auto_applicable`만 본다면 그대로 둔다. Task 1 문서에서 확인한 사실을 이 모듈 docstring에 한 줄로 근거로 남긴다.

- [x] **Step 6: 린트-타입 확인 후 커밋**

```bash
cd apps/pipeline
uv run ruff check . && uv run mypy src 2>&1 | tail -3
git add apps/pipeline/src/fontagit_pipeline/noonnu_url_ingest.py apps/pipeline/tests/test_noonnu_url_ingest.py
git commit -m "feat: 눈누 URL 판정을 감사 draft로 변환 (#150)"
```

---

## Task 4: 스캔기에 적재 배선 + 대상 필터

`scan_targets`가 적재 문맥을 받으면 판정 직후 snapshot과 finding을 저장한다. 적재 문맥이 없으면 지금과 똑같이 동작한다(기존 테스트 무손상).

**Files:**
- Modify: `src/fontagit_pipeline/noonnu_url_scan.py`
- Test: `tests/test_noonnu_url_scan.py`

**Interfaces:**
- Consumes: `build_snapshot_draft`, `build_finding_drafts` (Task 3), `FetchedPage` (Task 2)
- Produces:
  - `IngestContext(store: AuditStore, run_id: UUID, page_fetcher: Callable[[str], FetchedPage])`
  - `scan_targets(..., ingest: IngestContext | None = None)`
  - `select_actionable(records: Sequence[ScanRecord]) -> list[ScanRecord]`

- [x] **Step 1: 실패하는 테스트를 쓴다**

`tests/test_noonnu_url_scan.py`에 추가:

```python
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
        fetcher=lambda _url: _CONTAMINATED_HTML,
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
            html=_CONTAMINATED_HTML, final_url=url, http_status=200
        ),
    )

    records = scan_targets(
        [_target()],
        fetcher=lambda _url: _CONTAMINATED_HTML,
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
```

`_target()`, `_tmp_state()`, `_CONTAMINATED_HTML`, `_scan_record()`는 기존 테스트 파일의 헬퍼를 재사용한다. 없으면 기존 테스트가 쓰는 fixture 이름에 맞춰 만든다. import에 `IngestContext`, `FetchedPage`, `select_actionable`을 추가한다.

- [x] **Step 2: 실패를 확인한다**

```bash
cd apps/pipeline
uv run pytest tests/test_noonnu_url_scan.py -k "ingest or actionable" -v
```

Expected: FAIL, `ImportError: cannot import name 'IngestContext'`

- [x] **Step 3: 구현**

`noonnu_url_scan.py`에 추가한다. import에 `from uuid import UUID`, `from fontagit_pipeline.audit_store import AuditStore`, `from fontagit_pipeline.noonnu_url_ingest import build_finding_drafts, build_snapshot_draft`를 더한다.

순환 import 주의: `noonnu_url_ingest`가 `noonnu_url_scan`의 `ScanRecord`/`FetchedPage`를 import하므로, 스캔기 쪽 import는 **함수 안에서** 지연 import한다.

```python
@dataclass(frozen=True)
class IngestContext:
    """판정 결과를 감사 저장소에 적재할 때 필요한 문맥.

    `page_fetcher`가 따로 있는 이유: 감사 근거에는 최종 URL과 상태 코드가
    필요한데 기존 `fetcher`는 HTML만 돌려주기 때문이다. 적재하지 않는
    호출부는 이 문맥 없이 지금까지처럼 `fetcher`만 쓴다.
    """

    store: AuditStore
    run_id: UUID
    page_fetcher: Callable[[str], FetchedPage]


def select_actionable(records: Sequence[ScanRecord]) -> list[ScanRecord]:
    """정정이 필요한 판정만 남긴다(keep 제외)."""
    return [record for record in records if record.recommended_action != "keep"]
```

`scan_targets` 시그니처에 `ingest: IngestContext | None = None`을 더하고, docstring `Args:`에 한 줄 설명을 추가한다. 대상 1건 처리 루프에서 HTML을 받는 부분을 다음으로 바꾼다:

```python
        if ingest is not None:
            page = ingest.page_fetcher(target.source_url)
            html = page.html
        else:
            page = None
            html = fetcher(target.source_url)
```

판정이 끝나 `record`를 만든 직후, 상태 파일에 쓰기 전에 적재한다:

```python
        if ingest is not None and page is not None and record.error is None:
            _ingest_record(ingest, record, page)
```

모듈 하단에 도우미를 추가한다:

```python
def _ingest_record(
    ingest: IngestContext, record: ScanRecord, page: FetchedPage
) -> None:
    """판정 1건을 감사 저장소에 적재한다.

    keep 판정은 정정 대상이 아니므로 적재하지 않는다. 저장 중 예외는 삼키지
    않고 그대로 올린다. 부분 적재 상태로 조용히 넘어가면 나중에 finding 수
    검사에서야 드러나기 때문이다.
    """
    from fontagit_pipeline.noonnu_url_ingest import (
        build_finding_drafts,
        build_snapshot_draft,
    )

    if record.recommended_action == "keep":
        return
    evidence_id = ingest.store.save_snapshot(
        ingest.run_id, build_snapshot_draft(record, page)
    )
    for draft in build_finding_drafts(record, evidence_id):
        ingest.store.save_finding(ingest.run_id, draft)
```

- [x] **Step 4: 통과 확인 + 전체 회귀**

```bash
cd apps/pipeline
uv run pytest -q 2>&1 | tail -5
```

Expected: 기존 472 + 신규 테스트 전부 PASS, 4 skipped 유지

- [x] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py apps/pipeline/tests/test_noonnu_url_scan.py
git commit -m "feat: 스캔 판정을 감사 저장소에 적재 (#150)"
```

---

## Task 5: CLI 플래그와 run 생명주기

**Files:**
- Modify: `src/fontagit_pipeline/__main__.py` (파서 `1970-1986`, `_run_url_scan` `212-`)
- Test: `tests/test_noonnu_url_scan.py`

**Interfaces:**
- Consumes: `IngestContext`, `select_actionable` (Task 4)
- Produces: CLI 플래그 `--store-findings`, `--only-actionable`, `--retry-failed`

- [ ] **Step 1: 파서에 플래그를 더한다**

`__main__.py`의 `url_scan_parser.set_defaults` 바로 앞에 추가:

```python
    url_scan_parser.add_argument(
        "--store-findings",
        action="store_true",
        help="판정을 감사 저장소에 run/snapshot/finding으로 적재한다",
    )
    url_scan_parser.add_argument(
        "--only-actionable",
        type=Path,
        default=None,
        help="이전 스캔 상태 JSONL 경로. keep이 아닌 대상만 재스캔한다",
    )
    url_scan_parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="--only-actionable 상태 파일에서 error가 있는 건만 다시 시도한다",
    )
```

- [ ] **Step 2: 실패하는 테스트를 쓴다**

```python
def test_store_findings_requires_dev_target() -> None:
    """prod 적재는 막는다. 정정은 dev에서 만들고 manifest로 승격한다."""
    args = argparse.Namespace(
        target="prod",
        state=Path("/tmp/s.jsonl"),
        out=Path("/tmp/o.json"),
        limit=0,
        store_findings=True,
        only_actionable=None,
        retry_failed=False,
    )

    assert main_noonnu_url_scan(args) == 1


def test_only_actionable_loads_non_keep_targets(tmp_path: Path) -> None:
    """상태 파일에서 keep이 아닌 대상만 골라낸다."""
    state = tmp_path / "state.jsonl"
    state.write_text(
        json.dumps({**_record_dict(), "slug": "a", "recommended_action": "keep"})
        + "\n"
        + json.dumps(
            {**_record_dict(), "slug": "b", "recommended_action": "auto_fix_safe"}
        )
        + "\n",
        encoding="utf-8",
    )

    slugs = [r.slug for r in load_actionable_records(state, retry_failed_only=False)]

    assert slugs == ["b"]
```

`load_actionable_records`를 `noonnu_url_scan.py`에서 import한다. `_record_dict()`는 `ScanRecord` 필드를 모두 채운 dict를 돌려주는 헬퍼로, Task 3 테스트의 `_record()`와 같은 값을 쓴다.

- [ ] **Step 3: 실패 확인**

```bash
cd apps/pipeline
uv run pytest tests/test_noonnu_url_scan.py -k "store_findings or only_actionable" -v
```

Expected: FAIL

- [ ] **Step 4: 구현**

`noonnu_url_scan.py`에 추가:

```python
def load_actionable_records(
    state_path: Path, *, retry_failed_only: bool
) -> list[ScanRecord]:
    """이전 상태 파일에서 재스캔 대상을 고른다.

    Args:
        state_path: 이전 실행이 남긴 JSONL 경로.
        retry_failed_only: True면 error가 남은 건만, False면 keep이 아닌 전부.
    """
    records = load_state_records(state_path)
    if retry_failed_only:
        return [record for record in records if record.error is not None]
    return select_actionable(records)
```

`__main__.py`의 `_run_url_scan`에 다음을 넣는다.

인자 검증 (`main_noonnu_url_scan`의 기존 검증 블록 뒤):

```python
    if args.store_findings and args.target != "dev":
        logger.error("--store-findings는 dev에서만 허용됩니다: %s", args.target)
        return 1
    if args.retry_failed and args.only_actionable is None:
        logger.error("--retry-failed는 --only-actionable과 함께 써야 합니다")
        return 1
```

대상 선정 (`_run_url_scan`이 전체 행을 읽는 부분 뒤):

```python
    if args.only_actionable is not None:
        previous = load_actionable_records(
            args.only_actionable, retry_failed_only=args.retry_failed
        )
        wanted = {record.font_id for record in previous}
        targets = [target for target in targets if target.font_id in wanted]
        logger.info("재스캔 대상 %d종으로 좁혔습니다", len(targets))
```

적재 문맥 준비 (`with httpx.Client(...) as http:` 블록 안, `scan_targets` 호출 직전).
⚠️ `client`는 Supabase 클라이언트(`__main__.py:245`)이고 httpx 쪽은 `http`(`:263`)다. 헷갈리지 말 것:

```python
    ingest: IngestContext | None = None
    run_id: UUID | None = None
    if args.store_findings:
        # url/secret은 이 함수 앞부분에서 이미 None 체크된 지역 변수다.
        # settings.supabase_dev_url을 직접 넘기면 Optional 때문에 mypy가 늘어난다.
        store = SupabaseAuditStore.from_dev_credentials(url, secret)
        baseline_sha256 = hashlib.sha256(
            json.dumps(
                sorted(target.font_id for target in targets), separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        run_id = store.start_run(
            stage="metadata",
            target_count=len(targets),
            baseline_sha256=baseline_sha256,
            dry_run=False,
        )
        logger.info("감사 run 시작: %s (대상 %d종)", run_id, len(targets))
        ingest = IngestContext(
            store=store,
            run_id=run_id,
            page_fetcher=lambda target_url: fetch_scan_page(http, target_url),
        )
```

스캔 호출에 `ingest=ingest`를 넘기고, 스캔 종료 후 run을 닫는다:

```python
    if ingest is not None and run_id is not None:
        actionable = select_actionable(records)
        expected_findings = sum(
            len(build_finding_drafts(record, uuid4())) for record in actionable
        )
        logger.info(
            "적재 완료: 대상 %d종, 예상 finding %d건",
            len(actionable),
            expected_findings,
        )
        ingest.store.complete_run(run_id, {"summary": summary})
```

`--retry-failed` 없이 `auto_fix_safe` 대상에 실패가 남았으면 종료 코드 6(기존 재시도 코드)이 그대로 뜬다. 설계의 "실패 시 apply 중단"은 Task 7의 게이트에서 이 종료 코드로 판단한다.

- [ ] **Step 5: 통과 확인 + 전체 회귀**

```bash
cd apps/pipeline
uv run pytest -q 2>&1 | tail -5
uv run ruff check . && uv run mypy src 2>&1 | tail -3
```

- [ ] **Step 6: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py apps/pipeline/tests/test_noonnu_url_scan.py
git commit -m "feat: noonnu-url-scan에 적재-대상필터-재시도 플래그 추가 (#150)"
```

---

## Task 6: 검증 쿼리 파일

**Files:**
- Create: `scripts/verify-noonnu-url-fix.sql`

- [x] **Step 1: 쿼리 파일을 만든다**

```sql
-- 눈누 official_url 오염 정정 검증 (#150)
-- dev와 prod에서 동일하게 실행한다. :run_id는 적재 run의 UUID로 치환.

-- (1) 오염 잔존: 적용 후 사람 검수 대기분만 남아야 한다
select count(*) as contaminated_remaining
from fontagit.fonts
where official_url = 'https://www.instagram.com/noonnu_official/'
   or license_source_url = 'https://www.instagram.com/noonnu_official/';

-- (2) 정정 반영 건수: 기대 175
--     (auto_fix_safe 174 + google-sans-flex의 license_source_url 1)
select count(*) as corrected
from fontagit.fonts f
join fontagit.font_sources s on s.font_id = f.id and s.provider = 'noonnu'
where f.license_source_url like 'https://noonnu.cc/font_page/%';

-- (3) 사람 검수 대기: 미승인으로 남아야 한다
select count(*) as pending_review
from fontagit.font_audit_findings
where run_id = :run_id
  and auto_applicable = false
  and status <> 'approved';

-- (4) 적재 정합성: finding 수가 대상 폰트 수의 2배 근방인지
select
  count(*) as findings,
  count(distinct font_id) as fonts,
  count(distinct evidence_id) as evidences
from fontagit.font_audit_findings
where run_id = :run_id;
```

- [x] **Step 2: dev에서 실행해 문법을 확인한다 (읽기 전용)**

MCP `supabase-dev`로 (1), (2), (4)를 실행한다. (3)은 run_id가 없으므로 Task 7 이후에 돌린다. 컬럼명이 실제와 다르면 여기서 드러나므로 즉시 고친다.

- [x] **Step 3: 커밋**

```bash
git add scripts/verify-noonnu-url-fix.sql
git commit -m "chore: 눈누 URL 정정 검증 쿼리 추가 (#150)"
```

---

## Task 7: dev 재스캔-적재-적용 (운영 절차)

여기부터는 코드 변경이 아니라 실행이다. 각 단계의 출력을 근거로 남긴다.

- [ ] **Step 1: 대상 185종 재스캔 + 적재**

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline noonnu-url-scan \
  --target dev \
  --only-actionable output/noonnu-url-scan-state-v2.jsonl \
  --state output/noonnu-url-scan-state-v3.jsonl \
  --out output/noonnu-url-scan-report-v3.json \
  --store-findings 2>&1 | tail -30
echo "exit=$?"
```

기대: exit 0, 대상 185종, 오류 0. 약 7분 소요.

exit 6(재시도 대상 남음)이면 `--retry-failed`를 추가해 다시 돌린다. `auto_fix_safe` 대상에 실패가 남은 채로는 **다음 단계로 넘어가지 않는다.**

- [ ] **Step 2: 07-29 대비 대조 리포트**

v2와 v3의 판정을 슬러그 단위로 비교해 값 불일치와 판정 강등을 목록으로 만든다.

```bash
cd apps/pipeline
uv run python - <<'PY'
import json
from pathlib import Path

def load(path):
    return {
        r["slug"]: r
        for r in (json.loads(line) for line in Path(path).read_text().splitlines() if line)
    }

old = load("output/noonnu-url-scan-state-v2.jsonl")
new = load("output/noonnu-url-scan-state-v3.jsonl")

value_diff, action_diff = [], []
for slug, n in new.items():
    o = old.get(slug)
    if o is None:
        continue
    if o["new_official_url"] != n["new_official_url"]:
        value_diff.append((slug, o["new_official_url"], n["new_official_url"]))
    if o["recommended_action"] != n["recommended_action"]:
        action_diff.append((slug, o["recommended_action"], n["recommended_action"]))

print(f"값 불일치 {len(value_diff)}건")
for row in value_diff:
    print("  ", row)
print(f"판정 변경 {len(action_diff)}건")
for row in action_diff:
    print("  ", row)
PY
```

결과를 사용자에게 보고한다. 판정이 `auto_fix_safe`에서 내려간 건이 있으면 자동 적용 대상에서 빠졌음을 함께 알린다.

- [ ] **Step 3: 적재 정합성 확인**

`scripts/verify-noonnu-url-fix.sql`의 (4)를 dev에서 실행한다. `findings == fonts x 2`가 아니면(nullify 1건 때문에 정확히 2배가 아닐 수 있음) 차이를 설명할 수 있어야 한다. 설명되지 않으면 중단하고 보고한다.

- [ ] **Step 4: 사람 배치 승인**

무인 승인(`auto-approve`)은 대상 필드가 `{tags, weights, foundry, download_url, download_source_kind}`로 하드코딩돼 있어 이 두 필드를 처리하지 못한다(`audit_store.py:897`, Task 1에서 확인). 사람 배치 승인 경로를 쓴다.

먼저 대상 분포만 확인한다:

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-review approve \
  --run-id <RUN_ID> \
  --field official_url --field license_source_url \
  --reviewed-by "#150 dual-review + user approval 2026-07-30" \
  --dry-run 2>&1 | tail -20
```

필드별 분포가 예상과 맞는지 확인한다. `official_url` 174건, `license_source_url` 175건이 기대값이다(license 쪽이 1건 많은 이유는 `google-sans-flex`가 이 필드만 자동 적용 대상이기 때문).

⚠️ 이 명령은 `auto_applicable=False`인 finding까지 승인 대상에 넣을 수 있다. `--dry-run` 출력의 건수가 위 기대값보다 크면 **승인하지 말고** 중단한 뒤, `auto_applicable` 필터가 이 경로에 적용되는지 `__main__.py:1440-1500`을 확인해 보고한다.

건수가 맞으면 `--dry-run`을 빼고 다시 실행한다:

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-review approve \
  --run-id <RUN_ID> \
  --field official_url --field license_source_url \
  --reviewed-by "#150 dual-review + user approval 2026-07-30" 2>&1 | tail -20
```

- [ ] **Step 5: manifest 생성 및 사전점검**

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-manifest build \
  --run-id <RUN_ID> --target dev \
  --out output/noonnu-url-manifest-dev.json 2>&1 | tail -20

uv run python -m fontagit_pipeline font-audit-manifest preflight \
  --manifest output/noonnu-url-manifest-dev.json --target dev 2>&1 | tail -20
```

preflight가 불일치를 보고하면 중단한다.

- [ ] **Step 6: dev 적용**

```bash
cd apps/pipeline
shasum -a 256 output/noonnu-url-manifest-dev.json
uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/noonnu-url-manifest-dev.json \
  --sha256 <SHA_FILE> --target dev --confirm-hash <HASH> 2>&1 | tail -20
```

- [ ] **Step 7: dev 검증**

`scripts/verify-noonnu-url-fix.sql`의 (1)(2)(3)을 dev에서 실행한다. (2)가 175면 통과. 결과를 사용자에게 보고한다.

- [ ] **Step 8: 산출물 커밋**

```bash
git add apps/pipeline/output/noonnu-url-scan-report-v3.json docs/progress/
git commit -m "chore: dev 눈누 URL 정정 적용 결과 (#150)"
```

`output/*.jsonl`은 용량이 크므로 `.gitignore` 상태를 확인하고 리포트 JSON만 담는다.

---

## Task 8: prod 승인 패키지와 적용 (운영 절차)

**⚠️ Task 1의 검증 결과에 따라 이 작업의 내용이 달라진다.** manifest가 `font_id`로 대상을 찾는다면 이 절차는 성립하지 않으므로 재설계가 필요하다.

- [ ] **Step 1: prod manifest 생성**

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-manifest build \
  --run-id <RUN_ID> --target prod \
  --out output/noonnu-url-manifest-prod.json 2>&1 | tail -20
```

- [ ] **Step 2: before 값 대조 (필수 게이트)**

prod manifest의 모든 항목에서 `before`가 오염 URL인지 확인한다.

```bash
cd apps/pipeline
uv run python - <<'PY'
import json
from pathlib import Path

CONTAMINATED = "https://www.instagram.com/noonnu_official/"
manifest = json.loads(Path("output/noonnu-url-manifest-prod.json").read_text())

unexpected = []
for entry in manifest["entries"]:
    for field, value in entry["before"].items():
        if field in ("official_url", "license_source_url") and value != CONTAMINATED:
            unexpected.append((entry["source_key"], field, value))

print(f"전체 {len(manifest['entries'])}건, 예상 밖 before {len(unexpected)}건")
for row in unexpected:
    print("  ", row)
PY
```

예상 밖 항목이 하나라도 있으면 **적용을 중단하고** 목록을 사용자에게 보고한다. dev 승인 이후 prod에서 값이 바뀐 것이므로 재승인이 필요하다.

- [ ] **Step 3: 승인 패키지 작성**

`docs/review/2026-07-30-noonnu-url-prod-approval.md`에 다음을 담는다.

- 변경 건수: 전체, 필드별(`official_url` N건 / `license_source_url` M건)
- 호스트별 분포 (clova.ai 109건 등)
- 샘플 10건의 slug / before / after 표
- 전체 대상 slug 목록
- Step 2의 before 대조 결과
- 되돌리기 방법: `before`/`after`를 뒤집은 역방향 manifest 생성 절차
- 적용에 쓸 명령 전문과 manifest 해시

- [ ] **Step 4: 사용자 승인 요청**

승인 패키지와 **실행할 명령 전문**을 보여주고 승인을 받는다. 승인 없이 다음 단계로 넘어가지 않는다.

- [ ] **Step 5: prod 사전점검**

```bash
cd apps/pipeline
uv run python -m fontagit_pipeline font-audit-manifest preflight \
  --manifest output/noonnu-url-manifest-prod.json --target prod 2>&1 | tail -20
```

- [ ] **Step 6: prod 적용**

```bash
cd apps/pipeline
export FONTAGIT_PROD_MANIFEST_ENABLED=true
shasum -a 256 output/noonnu-url-manifest-prod.json
uv run python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/noonnu-url-manifest-prod.json \
  --sha256 <SHA_FILE> --target prod \
  --confirm-hash <HASH> --approval-id <승인 식별자> 2>&1 | tail -30
```

갱신된 행 수가 승인 패키지의 건수와 일치하는지 확인한다.

- [ ] **Step 7: prod 검증**

`scripts/verify-noonnu-url-fix.sql`의 (1)(2)를 prod에서 실행한다. (2)가 175면 통과.

- [ ] **Step 8: manifest와 해시 보관, 커밋**

```bash
cp apps/pipeline/output/noonnu-url-manifest-prod.json docs/review/
git add docs/review/
git commit -m "chore: prod 눈누 URL 정정 적용 근거 보관 (#150)"
```

---

## Task 9: 재배포와 마무리

정적 사이트라 DB만 고치면 화면이 바뀌지 않는다.

- [ ] **Step 1: 재배포**

```bash
# main 브랜치에서만 동작한다
./scripts/deploy.sh 2>&1 | tail -20
```

⚠️ stale `.next` fetch-cache가 옛 데이터를 굽는 사고 이력이 있다. 배포 전 캐시 상태를 확인한다.

- [ ] **Step 2: 표본 화면 확인**

정정된 폰트 3종의 상세 페이지를 열어 제작사 링크가 눈누 SNS가 아님을 확인한다. 스크린샷 또는 URL을 근거로 남긴다.

- [ ] **Step 3: license_verified 강등 별도 이슈 등록**

```bash
gh issue create --title "눈누만 근거인 폰트의 license_verified 정책 결정" \
  --body "..." --label "priority: medium"
```

본문에 담을 것: #150에서 범위 밖으로 분리한 경위, 172종만 강등하면 기준이 일관되지 않는 문제, `0026:337-339`가 `license_status` 동반 변경을 강제한다는 제약, Tier B 전체가 대상이 되는 논리.

- [ ] **Step 4: 진행 일지 갱신 후 PR 생성**

```bash
git add docs/progress/
git commit -m "docs: #150 눈누 URL 정정 완료 기록"
git push -u origin feat/150-noonnu-url-finding-ingest
gh pr create --title "feat: 눈누 official_url 오염 185종 정정 (#150)" --body "..."
```

PR 머지는 사용자 승인 후에만 한다.

---

## Self-Review 결과

**스펙 커버리지**

| 설계 절 | 대응 작업 |
|---|---|
| 3.2 변경 지점 3곳 | Task 2, 3, 4, 5 |
| 3.3 실행 흐름 0단계(사전 검증) | Task 1 |
| 3.4 snapshot 필드 | Task 3 `build_snapshot_draft` |
| 3.5 finding 2건 + evidence 공유 | Task 3 `build_finding_drafts` |
| 3.6 auto_applicable 매핑 + nullify 분리 | Task 3 (테스트 `test_nullify_splits_by_field`) |
| 3.7 dev/prod 이식 + before 대조 | Task 1, Task 8 Step 2 |
| 3.8 안전장치 | Task 7 Step 5-6, Task 8 Step 5-6 (기존 구조 활용) |
| 3.9 실패 정책 | Task 5 (`--retry-failed`), Task 7 Step 1 게이트 |
| 3.9 run 생명주기 | Task 5 (start_run/complete_run) |
| 3.9 저장 원자성 | Task 4 `_ingest_record`(예외 전파), Task 7 Step 3(정합성 검사) |
| 3.10 되돌리기 | Task 8 Step 3(승인 패키지에 절차 포함), Step 8(보관) |
| 4 검증 | Task 6, 각 Task의 테스트 단계 |
| 5 완료 기준 9개 | Task 7 Step 7, Task 8 Step 7, Task 9 |

**미해결로 남긴 것**

- 설계 3.9의 "시작 시 미완료 run 검사"는 Task 5에 넣지 않았다. `AuditStore` 프로토콜에 미완료 run 조회 메서드가 없어(`audit_store.py:96-130`) 새 메서드 추가가 필요하고, 이는 저장소 계약 변경이라 범위가 커진다. **대신 `--run-id` 기반 격리로 실질 위험을 막는다**(다른 run의 finding은 승인-manifest에 섞이지 않음). 고아 run 정리는 별도 이슈로 남긴다.

**타입 일관성 확인**

`FetchedPage`(Task 2 정의 -> Task 3, 4 사용), `IngestContext`(Task 4 정의 -> Task 5 사용), `build_snapshot_draft`/`build_finding_drafts`(Task 3 정의 -> Task 4, 5 사용), `select_actionable`(Task 4 정의 -> Task 5 사용), `load_actionable_records`(Task 5 정의) 모두 이름과 시그니처가 일치한다.
