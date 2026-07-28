# 눈누 official_url 오염 전수 검증 및 정정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 눈누에서 수집한 Tier B 폰트 1,110종의 `official_url`과 `license_source_url`을 전수 재검증하고, 오염된 172종 이상을 증거와 함께 정정한다.

**Architecture:** 눈누 상세 페이지를 다시 받아 감사 파서로 공식 URL을 추출하고, 현재 DB 값과 대조해 판정한다. 판정 결과는 기존 감사 파이프라인의 증거(snapshot)와 검수 후보(finding)로 저장되어, 이미 있는 `review approve` → `manifest build` → `manifest apply` 경로를 그대로 탄다. 새 쓰기 경로를 만들지 않는다.

**Tech Stack:** Python 3.12, httpx, BeautifulSoup, pydantic, supabase-py, pytest, PostgreSQL(Supabase) + pgTAP

## Global Constraints

- 설계 문서: `docs/superpowers/specs/2026-07-28-noonnu-official-url-audit-design.md`
- 대상 이슈: #150. #141과 #142는 **이 계획에 포함하지 않는다** (별도 PR)
- 선행 완료: PR #149 (커밋 `0dd2548`) — 눈누 시드 추출기의 본문 한정 수정
- 모든 DB 쓰기는 manifest RPC를 통한다. 직접 UPDATE 금지 (`audit_store.py` 규정)
- prod DB 쓰기는 사용자에게 쿼리 전문과 승인 패키지를 제시해 승인받은 뒤에만 실행
- 테스트: `cd apps/pipeline && uv run pytest`
- 린트: `cd apps/pipeline && uv run ruff check . && uv run mypy src`
- 코드 컨벤션: Type Hints 100%, Docstring 한국어, `print` 금지(`logging` 사용)
- 눈누 요청 시 `_USER_AGENT`(`FontAgitSeedBot/0.1`)와 robots.txt 준수를 유지한다. 브라우저 UA로 바꾸지 않는다

---

## 진행 현황 (2026-07-29 기준)

| Task | 상태 | 비고 |
|---|---|---|
| 1. 감사 파서 확장 | 완료 | `2743846`, `a552509` |
| 2. 대조 판정 | 완료 후 재작업 | `e016f57` → 리뷰 반영 `2758022` |
| 3. 스캔 실행기 | 완료 후 재작업 | `493f263` → `b0acd10`, `6e01e22` |
| 4. CLI + 요약 | 완료 후 재작업 | `9ec3f9c` → 진행 중 |
| 5~8 | 미착수 | PR #151 머지 후 |

PR #151에 대해 자체 코드 리뷰(code-reviewer)와 Codex 리뷰를 각각 한 차례 받았고, 두 리뷰에서 나온 결함을 Task 1~4에 되먹여 수정했다. 그래서 아래 Step 체크박스가 켜져 있어도 그 산출물은 최초 작성분과 다르다.

되먹인 주요 결함은 다음과 같다.

- 재개 시 실패 건이 완료로 기록돼 영구 누락 (#142와 같은 결함이 계획 자체에 있었음)
- 판정이 오염 검사보다 일치 검사를 먼저 해, 찾아야 할 오염이 정상으로 통과
- `auto_fix_safe`가 OR 조건이라 자동 정정 문턱이 낮음
- 페이지네이션에 정렬이 없어 조용한 중복-누락 가능
- 429/403 백오프가 실전 경로에서 죽은 코드

Task 4의 `Step 6`(실제 DB 소규모 실행)은 `supabase_url`/`supabase_secret_key`가 환경에 없어 수행하지 못했다. 머지 후 env가 있는 환경에서 먼저 확인해야 한다.

---

## File Structure

**신규**

- `apps/pipeline/src/fontagit_pipeline/noonnu_url_audit.py` — 대조 판정과 조치 권고. 순수 함수만 두고 네트워크와 DB를 모른다.
- `apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py` — 전수 스캔 실행. 수집, 재개, 백오프, snapshot/finding 적재.
- `apps/pipeline/tests/test_noonnu_url_audit.py`
- `apps/pipeline/tests/test_noonnu_url_scan.py`
- `supabase/migrations/0026_manifest_official_url.sql`
- `supabase/tests/manifest_official_url_test.sql`

**수정**

- `apps/pipeline/src/fontagit_pipeline/audit_noonnu.py` — `official_url` 추출과 `global_social_links` 채우기 추가
- `apps/pipeline/tests/test_audit_noonnu.py` — 위 동작 테스트
- `apps/pipeline/src/fontagit_pipeline/__main__.py` — `noonnu-url-scan` 서브커맨드 등록

판정 로직(`noonnu_url_audit.py`)과 실행 로직(`noonnu_url_scan.py`)을 나누는 이유는, 판정이 네트워크 없이 테스트 가능해야 하고 이 작업에서 가장 자주 바뀔 부분이기 때문이다.

---

### Task 1: 감사 파서에 공식 URL 추출과 전역 SNS 분리 추가

`audit_noonnu.py`의 `NoonnuFontSnapshot`에는 `global_social_links` 필드가 선언돼 있으나 채우는 코드가 없어 항상 빈 리스트다. `official_url` 개념도 없다. 이 둘을 채운다. 눈누 전역 SNS를 따로 담아야 #148 같은 오염을 판정 단계에서 구분할 수 있다.

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/audit_noonnu.py`
- Test: `apps/pipeline/tests/test_audit_noonnu.py`

**Interfaces:**
- Consumes: 기존 `_detail_root(soup: BeautifulSoup) -> Tag`, `_http_url(href: str, source_url: str) -> str | None`, `_selector_path(node: Tag) -> str`
- Produces: `NoonnuFontSnapshot.official_url: str | None`, `NoonnuFontSnapshot.official_url_anchor_text: str | None`, `NoonnuFontSnapshot.global_social_links: list[str]` (채워짐), `evidence_locations["official_url"]` 셀렉터 경로

- [x] **Step 1: 실패하는 테스트를 작성한다**

`apps/pipeline/tests/test_audit_noonnu.py` 끝에 추가한다.

```python
def test_official_url_excludes_noonnu_global_social_links() -> None:
    """상세 영역 밖의 눈누 공식 SNS는 official_url이 되지 않는다."""
    html = """
    <html><body>
      <header><a href="https://www.instagram.com/noonnu_official/">눈누 인스타그램</a></header>
      <div class="font-detail">
        <h1>효남 늘 화이팅</h1>
        <a href="https://clova.ai/handwriting/list.html">다운로드 페이지로 이동</a>
      </div>
    </body></html>
    """
    snapshot = extract_noonnu_font(html, "https://noonnu.cc/font_page/600")

    assert snapshot.official_url == "https://clova.ai/handwriting/list.html"
    assert snapshot.official_url_anchor_text == "다운로드 페이지로 이동"
    assert "https://www.instagram.com/noonnu_official/" in snapshot.global_social_links
    assert "official_url" in snapshot.evidence_locations


def test_official_url_is_none_when_detail_has_no_external_link() -> None:
    """상세 영역에 외부 링크가 없으면 official_url은 None이다."""
    html = """
    <html><body>
      <header><a href="https://www.instagram.com/noonnu_official/">눈누 인스타그램</a></header>
      <div class="font-detail"><h1>어떤 폰트</h1><a href="/font_page/601">다른 폰트</a></div>
    </body></html>
    """
    snapshot = extract_noonnu_font(html, "https://noonnu.cc/font_page/600")

    assert snapshot.official_url is None
    assert snapshot.official_url_anchor_text is None
```

기존 파일 상단에 `extract_noonnu_font` import가 이미 있으면 그대로 쓴다. 없으면 `from fontagit_pipeline.audit_noonnu import extract_noonnu_font`를 추가한다.

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_noonnu.py -k official_url -v`
Expected: FAIL — `AttributeError: 'NoonnuFontSnapshot' object has no attribute 'official_url'`

- [x] **Step 3: 모델 필드를 추가한다**

`audit_noonnu.py`의 `NoonnuFontSnapshot`에서 `global_social_links` 선언 바로 아래에 추가한다.

```python
    official_url: str | None = None
    official_url_anchor_text: str | None = None
```

- [x] **Step 4: 추출 함수를 추가한다**

`audit_noonnu.py`에 아래 두 함수를 추가한다. `_http_url`, `_selector_path` 정의 근처에 둔다.

```python
_NOONNU_HOSTS = ("noonnu.cc",)
_SOCIAL_HOSTS = (
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "pinterest.com",
    "threads.net",
)


def _is_noonnu_host(url: str) -> bool:
    """URL이 눈누 자체 도메인인지 판정한다."""
    host = urlparse(url).netloc.lower()
    return any(host == name or host.endswith(f".{name}") for name in _NOONNU_HOSTS)


def _is_social_host(url: str) -> bool:
    """URL이 SNS 도메인인지 판정한다."""
    host = urlparse(url).netloc.lower()
    return any(host == name or host.endswith(f".{name}") for name in _SOCIAL_HOSTS)


def _collect_global_social_links(soup: BeautifulSoup, detail: Tag, source_url: str) -> list[str]:
    """상세 영역 바깥에 있는 SNS 링크를 모은다.

    눈누 자체 계정 링크가 제작사 공식 출처로 오인되는 것을 막기 위해 따로 담는다.
    """
    detail_hrefs = {anchor.get("href") for anchor in detail.find_all("a", href=True)}
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str) or href in detail_hrefs:
            continue
        url = _http_url(href, source_url)
        if url is None or not _is_social_host(url):
            continue
        if url not in links:
            links.append(url)
    return links


def _extract_official_url(detail: Tag, source_url: str) -> tuple[str | None, str | None, str | None]:
    """상세 영역 안에서 제작사 공식 URL 후보를 뽑는다.

    Returns:
        (공식 URL, 앵커 텍스트, 셀렉터 경로). 후보가 없으면 모두 None.
    """
    for anchor in detail.find_all("a", href=True):
        href = anchor.get("href")
        if not isinstance(href, str):
            continue
        url = _http_url(href, source_url)
        if url is None or _is_noonnu_host(url):
            continue
        anchor_text = _text(anchor)
        return url, anchor_text, _selector_path(anchor)
    return None, None, None
```

파일 상단 import에 `from urllib.parse import urlparse`가 없으면 추가한다.

- [x] **Step 5: 추출 결과를 스냅샷에 연결한다**

`extract_noonnu_font` 안에서 `detail`을 얻은 뒤, 반환값을 만들기 전에 아래를 넣는다. 기존 코드가 `evidence_locations` 딕셔너리를 조립하는 위치를 찾아 그 다음에 둔다.

```python
    official_url, official_anchor_text, official_selector = _extract_official_url(detail, source_url)
    global_social_links = _collect_global_social_links(soup, detail, source_url)
    if official_selector is not None:
        evidence_locations["official_url"] = official_selector
```

그리고 `NoonnuFontSnapshot(...)` 생성 인자에 아래 세 줄을 추가한다.

```python
        official_url=official_url,
        official_url_anchor_text=official_anchor_text,
        global_social_links=global_social_links,
```

- [x] **Step 6: 테스트가 통과하는지 확인한다**

Run: `cd apps/pipeline && uv run pytest tests/test_audit_noonnu.py -v`
Expected: PASS (신규 2건 포함, 기존 테스트도 그대로 통과)

- [x] **Step 7: 린트와 타입 검사를 돌린다**

Run: `cd apps/pipeline && uv run ruff check . && uv run mypy src`
Expected: 신규 오류 없음. 기존 오류가 있으면 그 수와 내용이 작업 전과 같은지 확인한다.

- [x] **Step 8: 커밋한다**

```bash
git add apps/pipeline/src/fontagit_pipeline/audit_noonnu.py apps/pipeline/tests/test_audit_noonnu.py
git commit -m "feat: 눈누 감사 파서에 공식 URL 추출과 전역 SNS 분리 추가 (#150)"
```

---

### Task 2: 대조 판정과 조치 권고

재추출 값과 DB 값을 비교해 판정하고, 자동 정정 가능 여부를 권고한다. 네트워크와 DB를 모르는 순수 함수로 둬서 모든 분기를 테스트로 덮는다.

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/noonnu_url_audit.py`
- Test: `apps/pipeline/tests/test_noonnu_url_audit.py`

**Interfaces:**
- Consumes: Task 1의 `NoonnuFontSnapshot` (`official_url`, `official_url_anchor_text`, `foundry`, `global_social_links`)
- Produces:
  - `Classification = Literal["match", "mismatch", "no_container", "no_link"]`
  - `RecommendedAction = Literal["auto_fix_safe", "manual_review", "nullify", "keep"]`
  - `UrlAuditVerdict` 데이터클래스
  - `judge_official_url(snapshot: NoonnuFontSnapshot | None, db_official_url: str | None, db_license_source_url: str | None) -> UrlAuditVerdict`

- [x] **Step 1: 실패하는 테스트를 작성한다**

`apps/pipeline/tests/test_noonnu_url_audit.py`를 새로 만든다.

```python
"""눈누 공식 URL 대조 판정 테스트."""

from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot
from fontagit_pipeline.noonnu_url_audit import judge_official_url


def _snapshot(**overrides: object) -> NoonnuFontSnapshot:
    """테스트용 스냅샷을 만든다."""
    payload: dict[str, object] = {
        "source_url": "https://noonnu.cc/font_page/600",
        "foundry": "네이버",
        "official_url": "https://clova.ai/handwriting/list.html",
        "official_url_anchor_text": "다운로드 페이지로 이동",
        "global_social_links": ["https://www.instagram.com/noonnu_official/"],
    }
    payload.update(overrides)
    return NoonnuFontSnapshot(**payload)  # type: ignore[arg-type]


def test_match_when_db_value_equals_reextracted() -> None:
    """DB 값과 재추출 값이 같으면 match이고 변경하지 않는다."""
    verdict = judge_official_url(
        _snapshot(),
        db_official_url="https://clova.ai/handwriting/list.html",
        db_license_source_url="https://clova.ai/handwriting/list.html",
    )
    assert verdict.classification == "match"
    assert verdict.recommended_action == "keep"


def test_noonnu_social_in_db_is_contamination() -> None:
    """DB 값이 눈누 전역 SNS면 오염으로 분류한다."""
    verdict = judge_official_url(
        _snapshot(),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "mismatch"
    assert verdict.contamination_type == "noonnu_social"


def test_anchor_text_download_makes_auto_fix_safe() -> None:
    """앵커 텍스트가 다운로드 계열이면 자동 정정 대상이다."""
    verdict = judge_official_url(
        _snapshot(official_url_anchor_text="다운로드 페이지로 이동"),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "auto_fix_safe"


def test_weak_evidence_requires_manual_review() -> None:
    """제작사명 매칭도 앵커 텍스트 근거도 없으면 사람이 본다."""
    verdict = judge_official_url(
        _snapshot(
            foundry="어떤스튜디오",
            official_url="https://example.com/random",
            official_url_anchor_text="자세히",
        ),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "manual_review"


def test_new_value_is_social_becomes_nullify() -> None:
    """재추출 값도 SNS면 정답으로 쓰지 않고 비운다."""
    verdict = judge_official_url(
        _snapshot(official_url="https://www.instagram.com/some_maker/"),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.recommended_action == "nullify"


def test_no_link_when_snapshot_has_no_official_url() -> None:
    """상세에 외부 링크가 없으면 no_link이고 비움 후보다."""
    verdict = judge_official_url(
        _snapshot(official_url=None, official_url_anchor_text=None),
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "no_link"
    assert verdict.recommended_action == "nullify"


def test_no_container_keeps_current_value() -> None:
    """페이지 파싱 자체가 실패하면 판단 근거가 없어 변경하지 않는다."""
    verdict = judge_official_url(
        None,
        db_official_url="https://www.instagram.com/noonnu_official/",
        db_license_source_url="https://www.instagram.com/noonnu_official/",
    )
    assert verdict.classification == "no_container"
    assert verdict.recommended_action == "keep"
```

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd apps/pipeline && uv run pytest tests/test_noonnu_url_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fontagit_pipeline.noonnu_url_audit'`

- [x] **Step 3: 판정 모듈을 구현한다**

`apps/pipeline/src/fontagit_pipeline/noonnu_url_audit.py`를 만든다.

```python
"""눈누에서 재추출한 공식 URL과 DB 값을 대조해 판정한다.

네트워크와 DB를 모르는 순수 함수만 둔다. 실행은 noonnu_url_scan이 맡는다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from fontagit_pipeline.audit_noonnu import NoonnuFontSnapshot

Classification = Literal["match", "mismatch", "no_container", "no_link"]
RecommendedAction = Literal["auto_fix_safe", "manual_review", "nullify", "keep"]
ContaminationType = Literal[
    "noonnu_social", "noonnu_internal", "unrelated_external", "shortener", "none"
]

_SOCIAL_HOSTS = (
    "instagram.com",
    "facebook.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "pinterest.com",
    "threads.net",
)
_SHORTENER_HOSTS = ("bit.ly", "t.co", "goo.gl", "han.gl", "vo.la", "url.kr")
_NOONNU_HOSTS = ("noonnu.cc",)
_DOWNLOAD_ANCHOR_PATTERN = re.compile(r"다운로드|공식|홈페이지|바로가기|download|official", re.IGNORECASE)
_NON_WORD_PATTERN = re.compile(r"[^0-9a-z가-힣]+")


@dataclass(frozen=True)
class UrlAuditVerdict:
    """폰트 1종에 대한 대조 판정 결과."""

    classification: Classification
    recommended_action: RecommendedAction
    contamination_type: ContaminationType
    new_official_url: str | None
    evidence: str


def _host(url: str) -> str:
    """URL에서 소문자 호스트를 뽑는다."""
    return urlparse(url).netloc.lower()


def _host_matches(url: str, names: tuple[str, ...]) -> bool:
    """호스트가 주어진 도메인 목록에 속하는지 판정한다."""
    host = _host(url)
    return any(host == name or host.endswith(f".{name}") for name in names)


def _classify_contamination(url: str | None) -> ContaminationType:
    """URL이 어떤 종류의 오염인지 분류한다."""
    if url is None:
        return "none"
    if _host_matches(url, _NOONNU_HOSTS):
        return "noonnu_internal"
    if _host_matches(url, _SHORTENER_HOSTS):
        return "shortener"
    if _host_matches(url, _SOCIAL_HOSTS):
        return "noonnu_social"
    return "unrelated_external"


def _foundry_matches_host(foundry: str | None, url: str) -> bool:
    """제작사명이 도메인 문자열에 나타나는지 본다.

    영문 제작사명은 도메인에 그대로 들어가는 경우가 많아 근거로 쓸 만하다.
    한글 제작사명은 매칭되지 않는 것이 정상이므로 다른 근거로 보완한다.
    """
    if not foundry:
        return False
    normalized = _NON_WORD_PATTERN.sub("", foundry.lower())
    if len(normalized) < 3:
        return False
    host = _host(url).replace("-", "").replace(".", "")
    return normalized in host


def judge_official_url(
    snapshot: NoonnuFontSnapshot | None,
    db_official_url: str | None,
    db_license_source_url: str | None,
) -> UrlAuditVerdict:
    """재추출 스냅샷과 DB 값을 대조해 판정과 조치 권고를 낸다.

    Args:
        snapshot: 눈누 상세 재추출 결과. 파싱 실패 시 None.
        db_official_url: 현재 DB의 official_url.
        db_license_source_url: 현재 DB의 license_source_url.

    Returns:
        판정, 조치 권고, 오염 유형, 새 URL, 근거 문자열.
    """
    if snapshot is None:
        return UrlAuditVerdict(
            classification="no_container",
            recommended_action="keep",
            contamination_type=_classify_contamination(db_official_url),
            new_official_url=None,
            evidence="상세 영역 파싱 실패로 판단 근거 없음",
        )

    new_url = snapshot.official_url
    db_contamination = _classify_contamination(db_official_url)

    if new_url is None:
        action: RecommendedAction = "keep" if db_official_url is None else "nullify"
        return UrlAuditVerdict(
            classification="no_link",
            recommended_action=action,
            contamination_type=db_contamination,
            new_official_url=None,
            evidence="상세 영역에 외부 제작사 링크 없음",
        )

    if new_url == db_official_url and db_official_url == db_license_source_url:
        return UrlAuditVerdict(
            classification="match",
            recommended_action="keep",
            contamination_type="none",
            new_official_url=new_url,
            evidence="재추출 값과 DB 값 일치",
        )

    new_contamination = _classify_contamination(new_url)
    if new_contamination in ("noonnu_social", "noonnu_internal", "shortener"):
        return UrlAuditVerdict(
            classification="mismatch",
            recommended_action="nullify",
            contamination_type=db_contamination,
            new_official_url=None,
            evidence=f"재추출 값도 신뢰 불가({new_contamination})",
        )

    anchor_text = snapshot.official_url_anchor_text or ""
    anchor_ok = bool(_DOWNLOAD_ANCHOR_PATTERN.search(anchor_text))
    foundry_ok = _foundry_matches_host(snapshot.foundry, new_url)

    if anchor_ok or foundry_ok:
        reasons = []
        if anchor_ok:
            reasons.append(f"앵커 텍스트 '{anchor_text}'")
        if foundry_ok:
            reasons.append(f"제작사명 '{snapshot.foundry}' 도메인 매칭")
        return UrlAuditVerdict(
            classification="mismatch",
            recommended_action="auto_fix_safe",
            contamination_type=db_contamination,
            new_official_url=new_url,
            evidence=" + ".join(reasons),
        )

    return UrlAuditVerdict(
        classification="mismatch",
        recommended_action="manual_review",
        contamination_type=db_contamination,
        new_official_url=new_url,
        evidence=f"근거 약함: 앵커 '{anchor_text}', 제작사 '{snapshot.foundry}'",
    )
```

- [x] **Step 4: 테스트가 통과하는지 확인한다**

Run: `cd apps/pipeline && uv run pytest tests/test_noonnu_url_audit.py -v`
Expected: PASS 7건

- [x] **Step 5: 린트와 타입 검사를 돌린다**

Run: `cd apps/pipeline && uv run ruff check . && uv run mypy src`
Expected: 신규 오류 없음

- [x] **Step 6: 커밋한다**

```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_url_audit.py apps/pipeline/tests/test_noonnu_url_audit.py
git commit -m "feat: 눈누 공식 URL 대조 판정과 조치 권고 추가 (#150)"
```

---

### Task 3: 전수 스캔 실행기

1,110종을 순회하며 눈누 상세를 다시 받아 판정하고, 진행 상태를 건 단위로 남긴다. 중단되면 이미 처리한 폰트를 건너뛰고 재개한다. `#142`가 드러낸 것과 같은 누락을 만들지 않기 위해 배치가 아니라 건 단위로 기록한다.

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py`
- Test: `apps/pipeline/tests/test_noonnu_url_scan.py`

**Interfaces:**
- Consumes: Task 2의 `judge_official_url`, `UrlAuditVerdict`. 기존 `extract_noonnu_font`, `_fetch_url`, `_REQUEST_DELAY`, `NoonnuSeedError`
- Produces:
  - `ScanTarget` 데이터클래스 (`font_id: str`, `slug: str`, `source_url: str`, `db_official_url: str | None`, `db_license_source_url: str | None`, `db_license_verified: bool`)
  - `ScanRecord` 데이터클래스 (판정 1건의 직렬화 단위)
  - `scan_targets(targets, fetcher, state_path, sleeper=time.sleep) -> list[ScanRecord]`

- [x] **Step 1: 실패하는 테스트를 작성한다**

`apps/pipeline/tests/test_noonnu_url_scan.py`를 새로 만든다.

```python
"""눈누 공식 URL 전수 스캔 실행기 테스트."""

import json
from pathlib import Path

from fontagit_pipeline.noonnu_url_scan import ScanTarget, scan_targets

_DETAIL_HTML = """
<html><body>
  <header><a href="https://www.instagram.com/noonnu_official/">눈누</a></header>
  <div class="font-detail">
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
```

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd apps/pipeline && uv run pytest tests/test_noonnu_url_scan.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fontagit_pipeline.noonnu_url_scan'`

- [x] **Step 3: 실행기를 구현한다**

`apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py`를 만든다.

```python
"""눈누 상세를 다시 받아 공식 URL을 전수 대조한다.

중단에 대비해 판정 1건마다 상태 파일에 append 한다. 재시작 시 이미 기록된
폰트를 건너뛰므로, 배치 단위 기록이 실패 건을 통째로 삼키는 문제(#142)를 피한다.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from fontagit_pipeline.audit_noonnu import extract_noonnu_font
from fontagit_pipeline.noonnu_url_audit import judge_official_url

logger = logging.getLogger(__name__)

_BASE_DELAY = 1.5
_JITTER = 0.7
_BACKOFF_DELAY = 30.0
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


class ScanAbortedError(RuntimeError):
    """연속 실패가 한계를 넘어 안전하게 중단했다."""


def _load_completed_ids(state_path: Path) -> set[str]:
    """상태 파일에서 이미 처리한 font_id를 읽는다."""
    if not state_path.exists():
        return set()
    completed: set[str] = set()
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            completed.add(str(json.loads(line)["font_id"]))
        except (json.JSONDecodeError, KeyError):
            logger.warning("상태 파일에서 읽을 수 없는 줄을 건너뜁니다")
    return completed


def _load_records(state_path: Path) -> list[ScanRecord]:
    """상태 파일에 기록된 판정을 복원한다."""
    if not state_path.exists():
        return []
    records: list[ScanRecord] = []
    for line in state_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(
            ScanRecord(
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
            )
        )
    return records


def _append_record(state_path: Path, record: ScanRecord) -> None:
    """판정 1건을 상태 파일에 덧붙인다."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with state_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


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
        상태 파일에 이미 있던 판정과 이번에 처리한 판정을 합친 목록.

    Raises:
        ScanAbortedError: 연속 실패가 한계를 넘어 중단한 경우.
    """
    target_list: Sequence[ScanTarget] = list(targets)
    completed = _load_completed_ids(state_path)
    records = _load_records(state_path)
    consecutive_failures = 0

    for index, target in enumerate(target_list, start=1):
        if target.font_id in completed:
            continue

        if index > 1:
            sleeper(_BASE_DELAY + random.uniform(0.0, _JITTER))

        try:
            html = fetcher(target.source_url)
            snapshot = extract_noonnu_font(html, target.source_url)
            error: str | None = None
            consecutive_failures = 0
        except Exception as exc:  # 개별 실패가 전체를 멈추지 않게 한다
            snapshot = None
            error = f"{type(exc).__name__}: {exc}"
            consecutive_failures += 1
            logger.warning("수집 실패 %s: %s", target.slug, error)
            sleeper(_BACKOFF_DELAY)
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                raise ScanAbortedError(
                    f"연속 {consecutive_failures}건 실패로 중단합니다. "
                    f"상태 파일에서 재개하세요: {state_path}"
                ) from exc

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
        )
        _append_record(state_path, record)
        records.append(record)
        logger.info(
            "[%d/%d] %s -> %s / %s",
            index,
            len(target_list),
            target.slug,
            record.classification,
            record.recommended_action,
        )

    return records
```

- [x] **Step 4: 테스트가 통과하는지 확인한다**

Run: `cd apps/pipeline && uv run pytest tests/test_noonnu_url_scan.py -v`
Expected: PASS 4건

- [x] **Step 5: 린트와 타입 검사를 돌린다**

Run: `cd apps/pipeline && uv run ruff check . && uv run mypy src`
Expected: 신규 오류 없음

- [x] **Step 6: 커밋한다**

```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py apps/pipeline/tests/test_noonnu_url_scan.py
git commit -m "feat: 눈누 공식 URL 전수 스캔 실행기 추가 (#150)"
```

---

### Task 4: CLI 서브커맨드와 요약 리포트

DB에서 대상을 읽어 스캔을 돌리고, 판정 분포를 요약해 사람이 다음 결정을 내릴 수 있게 한다. 이 명령은 DB를 읽기만 한다.

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py`
- Modify: `apps/pipeline/src/fontagit_pipeline/__main__.py`
- Test: `apps/pipeline/tests/test_noonnu_url_scan.py`

**Interfaces:**
- Consumes: Task 3의 `ScanRecord`, `scan_targets`. 기존 `load_settings()`, `create_client`
- Produces: `summarize(records: Sequence[ScanRecord]) -> dict[str, object]`, `main_noonnu_url_scan(args: argparse.Namespace) -> int`

- [x] **Step 1: 실패하는 테스트를 작성한다**

`apps/pipeline/tests/test_noonnu_url_scan.py`에 추가한다. 상단 import에 `summarize`를 더한다.

```python
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
```

- [x] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd apps/pipeline && uv run pytest tests/test_noonnu_url_scan.py -k summarize -v`
Expected: FAIL — `ImportError: cannot import name 'summarize'`

- [x] **Step 3: 요약 함수를 구현한다**

`noonnu_url_scan.py` 끝에 추가한다.

```python
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
```

`Sequence`는 이미 Task 3에서 import 했다.

- [x] **Step 4: 테스트가 통과하는지 확인한다**

Run: `cd apps/pipeline && uv run pytest tests/test_noonnu_url_scan.py -v`
Expected: PASS 5건

- [x] **Step 5: 대상 조회와 CLI 진입점을 추가한다**

`noonnu_url_scan.py` 끝에 추가한다.

```python
def load_scan_targets(client: object) -> list[ScanTarget]:
    """눈누에서 온 발행 폰트와 그 상세 URL을 읽는다.

    font_sources(provider='noonnu')에 상세 URL이 있고, fonts에 현재 값이 있다.
    """
    sources = (
        client.schema("fontagit")  # type: ignore[attr-defined]
        .table("font_sources")
        .select("font_id, source_url")
        .eq("provider", "noonnu")
        .execute()
    )
    url_by_font: dict[str, str] = {
        str(row["font_id"]): str(row["source_url"]) for row in sources.data
    }
    if not url_by_font:
        return []

    fonts = (
        client.schema("fontagit")  # type: ignore[attr-defined]
        .table("fonts")
        .select("id, slug, official_url, license_source_url, license_verified")
        .eq("status", "published")
        .execute()
    )
    targets: list[ScanTarget] = []
    for row in fonts.data:
        font_id = str(row["id"])
        source_url = url_by_font.get(font_id)
        if source_url is None:
            continue
        targets.append(
            ScanTarget(
                font_id=font_id,
                slug=str(row["slug"]),
                source_url=source_url,
                db_official_url=row.get("official_url"),
                db_license_source_url=row.get("license_source_url"),
                db_license_verified=bool(row.get("license_verified", False)),
            )
        )
    return targets
```

`__main__.py`에 진입점을 추가한다. `main_noonnu_seed` 정의 아래에 둔다.

```python
def main_noonnu_url_scan(args: argparse.Namespace) -> int:
    """눈누 공식 URL 전수 대조 진입점."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    try:
        settings = load_settings()
        if not settings.supabase_url or not settings.supabase_secret_key:
            logger.error("supabase_url 또는 supabase_secret_key가 없습니다")
            return 2
        client = create_client(settings.supabase_url, settings.supabase_secret_key)
        targets = load_scan_targets(client)
        if args.limit:
            targets = targets[: args.limit]
        logger.info("스캔 대상 %d종", len(targets))

        with httpx.Client(headers={"User-Agent": _USER_AGENT}, follow_redirects=True) as http:
            records = scan_targets(
                targets,
                fetcher=lambda url: _fetch_url(http, url),
                state_path=args.state,
            )

        summary = summarize(records)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(
                {"summary": summary, "records": [asdict(record) for record in records]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        logger.info("요약: %s", json.dumps(summary, ensure_ascii=False))
        if not summary["structure_assumption_ok"]:
            logger.error(
                "no_container 비율 %.1f%%가 임계치를 넘었습니다. 정정을 진행하지 마세요.",
                float(summary["no_container_ratio"]) * 100,
            )
            return 4
        return 0
    except ScanAbortedError as exc:
        logger.error("스캔 중단: %s", exc)
        return 5
    except Exception as exc:
        logger.error("예상치 못한 오류: %s", exc)
        return 3
```

`__main__.py` 상단 import에 아래를 추가한다. 이미 있는 것은 건너뛴다.

```python
import httpx
from dataclasses import asdict

from fontagit_pipeline.noonnu_seed import _USER_AGENT, _fetch_url
from fontagit_pipeline.noonnu_url_scan import (
    ScanAbortedError,
    load_scan_targets,
    scan_targets,
    summarize,
)
```

서브커맨드를 등록한다. `seed_parser` 블록 아래에 둔다.

```python
    # noonnu-url-scan 명령
    url_scan_parser = subparsers.add_parser(
        "noonnu-url-scan",
        help="눈누 Tier B 공식 URL 전수 대조 (읽기 전용)",
    )
    url_scan_parser.add_argument(
        "--state", type=Path, required=True, help="진행 상태 JSONL 경로 (재개용)"
    )
    url_scan_parser.add_argument(
        "--out", type=Path, required=True, help="판정 리포트 JSON 저장 경로"
    )
    url_scan_parser.add_argument(
        "--limit", type=int, default=0, help="대상 상한 (0=전체)"
    )
    url_scan_parser.set_defaults(func=main_noonnu_url_scan)
```

- [ ] **Step 6: 소규모 실행으로 동작을 확인한다**

Run:
```bash
cd apps/pipeline && uv run python -m fontagit_pipeline noonnu-url-scan \
  --state /tmp/noonnu-url-scan-state.jsonl \
  --out /tmp/noonnu-url-scan-report.json \
  --limit 5
```
Expected: 종료 코드 0. 리포트 JSON에 5건의 레코드와 요약이 들어 있다. 5건 중 판정이 하나라도 `no_container`면 다음 태스크로 넘어가기 전에 눈누 페이지 구조를 다시 본다.

- [x] **Step 7: 린트와 타입 검사를 돌린다**

Run: `cd apps/pipeline && uv run ruff check . && uv run mypy src`
Expected: 신규 오류 없음

- [x] **Step 8: 커밋한다**

```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/tests/test_noonnu_url_scan.py
git commit -m "feat: noonnu-url-scan 서브커맨드와 판정 요약 추가 (#150)"
```

---

### Task 5: manifest가 official_url을 다룰 수 있는지 조사하고 pgTAP으로 고정

`official_url`은 manifest 허용 필드가 아니다. 그런데 이 필드는 낙관적 잠금의 대조 키로도 쓰여, 허용 목록에 한 줄 넣는 것으로 끝나지 않을 수 있다. **마이그레이션을 쓰기 전에 이 조사를 먼저 한다.**

**Files:**
- Read: `supabase/migrations/0018_apply_font_audit_manifest.sql`, `supabase/migrations/0025_manifest_null_value_compare.sql`
- Create: `docs/progress/2026-07-28-official-url-manifest-investigation.md`

**Interfaces:**
- Produces: 조사 결론 문서. `0026`이 손대야 할 지점 목록

- [ ] **Step 1: `official_url`이 등장하는 모든 지점을 찾는다**

Run:
```bash
grep -n "official_url" supabase/migrations/0018_apply_font_audit_manifest.sql supabase/migrations/0019*.sql supabase/migrations/002*.sql
```
Expected: 최소 아래 지점이 나온다.
```
0018:266  perform ... array['slug','name_en','name_ko','foundry','source_tier','official_url','status'], 'entry.current'
0018:291  or to_jsonb(v_existing.official_url) is distinct from v_entry#>'{current,official_url}'
0018:493  ... array['foundry','name_en','name_ko','official_url','slug','source_tier','updated_at']
```

- [ ] **Step 2: 각 지점이 무엇을 하는지 읽고 기록한다**

세 지점 각각에 대해 아래를 문서에 적는다.

- 266: `entry.current`에 어떤 키가 있어야 하는지 강제하는 검사인가
- 291: 현재 DB 값과 manifest의 `current` 값이 다르면 거부하는 낙관적 잠금인가
- 493: 이 배열이 무엇과 비교되는가 (변경된 컬럼 집합인지, 허용된 불변 컬럼 집합인지)

493이 "변경돼도 되는 컬럼 집합"이라면 `official_url`이 이미 들어 있으므로 추가 작업이 없다. 반대로 "변경되면 안 되는 컬럼 집합"이라면 `0026`에서 이 배열을 함께 고쳐야 한다. **이 판단이 다음 태스크의 범위를 정한다.**

- [ ] **Step 3: 결론을 문서로 남긴다**

`docs/progress/2026-07-28-official-url-manifest-investigation.md`에 아래를 적는다.

```markdown
# official_url manifest 허용 조사 - 2026-07-28

## 배경
#150의 정정 대상 필드 중 official_url이 apply_font_audit_manifest의 v_allowed에 없다.

## 확인한 지점
| 위치 | 역할 | 0026에서 손대야 하는가 |
|---|---|---|
| 0018:266 | (조사 결과) | (예/아니오 + 근거) |
| 0018:291 | (조사 결과) | (예/아니오 + 근거) |
| 0018:493 | (조사 결과) | (예/아니오 + 근거) |

## 결론
0026의 범위: (v_allowed 한 줄만 / 추가로 N개 지점)
```

- [ ] **Step 4: 커밋한다**

```bash
git add docs/progress/2026-07-28-official-url-manifest-investigation.md
git commit -m "docs: official_url manifest 허용 조사 결과 (#150)"
```

---

### Task 6: 0026 마이그레이션과 pgTAP 검증

Task 5의 조사 결론에 따라 마이그레이션을 쓴다. 조사에서 나온 지점만 손대고, 그 이상은 건드리지 않는다.

**Files:**
- Create: `supabase/migrations/0026_manifest_official_url.sql`
- Create: `supabase/tests/manifest_official_url_test.sql`

**Interfaces:**
- Consumes: Task 5의 조사 결론
- Produces: `official_url`을 manifest로 변경할 수 있는 `apply_font_audit_manifest`

- [ ] **Step 1: 실패하는 pgTAP 테스트를 작성한다**

`supabase/tests/manifest_official_url_test.sql`을 만든다. 기존 `supabase/tests/font_audit_manifest_test.sql`의 헤더와 픽스처 구성 방식을 그대로 따른다. 그 파일을 먼저 읽고 같은 스타일로 쓴다.

핵심 케이스는 셋이다.

```sql
-- 1. official_url을 after에 담은 manifest가 통과하고 값이 바뀐다
-- 2. entry.current의 official_url이 현재 DB 값과 다르면 거부된다 (낙관적 잠금 유지)
-- 3. official_url을 바꾼 뒤에도 나머지 불변 컬럼 검사가 통과한다
```

- [ ] **Step 2: 로컬 PostgreSQL에 0001~0025를 순서대로 적용하고 테스트가 실패하는지 확인한다**

`0025`가 `0024`의 함수를 다시 만들기 때문에 순서를 건너뛰면 `manifest field or value is invalid` 오류가 난다(#134 기록). 반드시 번호 순으로 적용한다.

Run: 로컬 PostgreSQL 17에 마이그레이션을 순서대로 적용한 뒤 `supabase/tests/manifest_official_url_test.sql` 실행
Expected: 케이스 1이 FAIL — `manifest field or value is invalid: official_url`

- [ ] **Step 3: 마이그레이션을 작성한다**

`supabase/migrations/0026_manifest_official_url.sql`을 만든다. `0025`의 함수 정의 전체를 복사한 뒤, Task 5에서 확정한 지점만 고친다. 최소한 `v_allowed` 배열에 `official_url`을 넣는다.

```sql
-- 0026: manifest가 official_url을 정정할 수 있게 허용한다.
-- 배경: #150. 눈누 수집 결함으로 172종 이상의 official_url이 눈누 홍보 계정으로 오염됐다.
-- 정정은 manifest RPC 한 곳에서만 이뤄져야 하므로 허용 필드에 추가한다.

create or replace function fontagit.apply_font_audit_manifest(
  -- 0025의 시그니처와 본문을 그대로 가져오고 v_allowed에 official_url을 추가한다
```

`v_allowed`는 아래처럼 된다.

```sql
  v_allowed constant text[] := array[
    'foundry','foundry_url','download_url','license_source_url','license_summary',
    'official_url',
    'download_source_kind','license_source_kind','download_evidence_id','license_evidence_id',
    'download_status','license_status','download_checked_at','license_checked_at',
    'allow_commercial','allow_font_sale','allow_embedding','allow_redistribute','allow_modify',
    'attribution_requirement','is_commercial_free','license_verified','name_en','name_ko',
    'category_ko','tags','weights','variants','subsets','script_status','script_checked_at',
    'script_evidence_id'
  ];
```

`official_url` 컬럼에 값을 반영하는 update 절도 다른 필드와 같은 형태로 추가한다.

```sql
    official_url=case when v_entry->'after' ? 'official_url'
      then nullif(v_entry#>>'{after,official_url}', '') else f.official_url end,
```

- [ ] **Step 4: pgTAP 테스트가 통과하는지 확인한다**

Run: 로컬 PostgreSQL에 `0026`까지 적용한 뒤 `manifest_official_url_test.sql`과 기존 `font_audit_manifest_test.sql`을 모두 실행
Expected: 두 파일 모두 ALL PASS. 기존 테스트가 깨지면 `0026`이 다른 동작을 바꾼 것이므로 되돌려 원인을 찾는다.

- [ ] **Step 5: 커밋한다**

```bash
git add supabase/migrations/0026_manifest_official_url.sql supabase/tests/manifest_official_url_test.sql
git commit -m "feat: manifest에 official_url 정정 허용 (#150)"
```

---

### Task 7: dev 전수 실행과 정정 적용

실제 데이터를 다룬다. dev에서 먼저 끝까지 해보고, 실측을 남긴다.

**Files:**
- 코드 변경 없음. 실행과 기록만 한다
- Create: `docs/progress/2026-07-28-noonnu-url-scan-result.md`

**Interfaces:**
- Consumes: Task 4의 `noonnu-url-scan`, Task 6의 `0026`
- Produces: dev 적용 결과와 실측 수치

- [ ] **Step 1: dev에 0026을 적용한다**

`0021`부터 `0026`까지 번호 순으로 적용됐는지 먼저 확인한 뒤 진행한다.

- [ ] **Step 2: 전수 스캔을 돌린다**

Run:
```bash
cd apps/pipeline && uv run python -m fontagit_pipeline noonnu-url-scan \
  --state output/noonnu-url-scan-state.jsonl \
  --out output/noonnu-url-scan-report.json
```
Expected: 약 20-30분 소요. 종료 코드 0. 중단되면 같은 명령을 다시 실행해 재개한다.

종료 코드가 4면 `no_container` 비율이 임계치를 넘은 것이다. **정정을 진행하지 말고 멈춘다.** 눈누 페이지 구조 가정이 틀린 것이므로 `_detail_root`의 선택자를 다시 봐야 한다.

- [ ] **Step 3: 요약을 확인하고 기록한다**

리포트의 `summary`를 `docs/progress/2026-07-28-noonnu-url-scan-result.md`에 옮긴다. 판정별 건수, 조치 권고별 건수, 오염 유형별 건수, `no_container` 비율을 적는다.

`auto_fix_safe` 건수가 172보다 크게 적으면, 판정 근거(앵커 텍스트 패턴, 제작사명 매칭)가 실제 페이지와 맞지 않는다는 뜻이다. `manual_review`로 빠진 건들의 `evidence` 필드를 20건쯤 훑어보고 패턴을 보강할지 판단한다.

- [ ] **Step 4: auto_fix_safe 건에 대해 finding을 만들고 승인한다**

기존 감사 파이프라인을 그대로 쓴다. 스캔 리포트의 `auto_fix_safe` 레코드를 `FindingDraft`로 바꿔 저장하고, `font-audit-review approve`로 승인한 뒤 `manifest build`로 manifest를 만든다.

필드별로 finding을 나눈다.

- `official_url`: `before_value`=DB 값, `proposed_value`=`new_official_url`
- `license_source_url`: 같은 값으로 정정
- `license_verified`: 설계 문서의 정책표에 따라 결정. 새 URL이 제작사 공식 도메인이지만 라이선스 문구를 확인하지 않았다면 `false`

`nullify` 건은 세 필드를 각각 빈 값과 `false`로 만든다. `manual_review`와 `keep`은 manifest에 넣지 않는다.

- [ ] **Step 5: dev에 적용하고 쓰기 후 재조회로 확인한다**

Run: `manifest preflight` → `manifest apply --target dev`

적용 후 아래를 실행해 실측을 남긴다.

```sql
select count(*) filter (where official_url ilike '%instagram%') as ig_official,
       count(*) filter (where license_source_url ilike '%instagram%') as ig_license,
       count(*) filter (where license_verified and license_source_url ilike '%instagram%') as ig_verified
from fontagit.fonts where status='published';
```
Expected: 세 값 모두 0

- [ ] **Step 6: 결과를 기록하고 커밋한다**

```bash
git add docs/progress/2026-07-28-noonnu-url-scan-result.md
git commit -m "docs: 눈누 공식 URL 전수 스캔 dev 적용 결과 (#150)"
```

---

### Task 8: prod 승인 패키지와 적용

prod는 실서비스 데이터다. 승인 없이 쓰지 않는다.

**Files:**
- 코드 변경 없음

**Interfaces:**
- Consumes: Task 7의 dev 적용 결과와 manifest 번들

- [ ] **Step 1: 승인 패키지를 만들어 사용자에게 제시한다**

아래를 한 묶음으로 정리해 보여주고 승인을 기다린다.

- 변경 건수 총계와 필드별 건수 (`official_url` / `license_source_url` / `license_verified`)
- 변경 전후 샘플 10건 (slug, 이전 값, 새 값)
- 영향받는 전체 slug 목록
- 역방향 manifest 경로
- 적용 후 실행할 검증 쿼리

- [ ] **Step 2: 승인을 받은 뒤 prod에 0026을 적용한다**

`0021`부터 순서대로 적용됐는지 먼저 확인한다. prod에서 `0025`만 먼저 적용했다가 실패한 전례가 있다(#134).

- [ ] **Step 3: manifest를 prod에 적용한다**

Run: `manifest preflight --target prod` → `manifest apply --target prod`

- [ ] **Step 4: 완료 기준을 실측으로 확인한다**

```sql
select
  count(*) filter (where official_url ilike '%instagram%' or official_url ilike '%noonnu.cc%') as bad_official,
  count(*) filter (where license_verified and (license_source_url ilike '%instagram%' or license_source_url ilike '%noonnu.cc%')) as bad_verified
from fontagit.fonts where status='published';
```
Expected: 두 값 모두 0

- [ ] **Step 5: 웹을 재배포한다**

정적 사이트라 DB만 고쳐서는 화면이 바뀌지 않는다. #120 코멘트에서 같은 이유로 반영이 늦어진 전례가 있다. 재배포 후 `https://fontagit.com/fonts/효남-늘-화이팅/`에서 출처 링크가 눈누 인스타그램이 아닌지 직접 확인한다.

- [ ] **Step 6: 이슈를 닫는다**

#150에 아래를 기록하고 닫는다. #148도 함께 닫는다.

- 전수 스캔 결과 요약 (판정별 건수)
- prod 적용 후 검증 쿼리 실측값
- `manual_review`로 남은 건수와 사유
- 역방향 manifest 경로
- 재배포 후 실제 화면 확인 결과

---

## Self-Review

**1. 스펙 커버리지**

| 설계 문서 항목 | 담당 태스크 |
|---|---|
| 대조 스캐너 판정 4갈래 | Task 2 |
| `recommended_action` 4갈래 | Task 2 |
| 리포트 JSON 레코드 형식 | Task 3 (`ScanRecord`), Task 4 (요약) |
| 중단과 재개 (건 단위 상태 파일) | Task 3 |
| 요청 예의 (지터, 백오프, 안전 중단) | Task 3 |
| `__main__.py` 서브커맨드 | Task 4 |
| `no_container` 5% 임계치 | Task 4 (`summarize`), Task 7 (실행 시 중단) |
| manifest `official_url` 허용 | Task 5(조사), Task 6(마이그레이션) |
| `0018` 세 지점 확인 | Task 5 |
| 정정 대상 필드 두 개 명시 | Task 7 Step 4 |
| `license_verified` 정책표 | Task 7 Step 4 |
| prod 승인 패키지 | Task 8 Step 1 |
| 역방향 manifest | Task 7 Step 4, Task 8 Step 1 |
| #150 완료 기준 | Task 8 Step 4, Step 6 |

설계 문서의 `#141`/`#142` 항목은 사용자 지시대로 이 계획에서 제외했다.

**2. 플레이스홀더 점검**

Task 5와 Task 6은 조사 결과에 따라 내용이 달라지는 구조다. 이는 미완성이 아니라 의도된 게이트다. `official_url`이 낙관적 잠금 키를 겸하고 있어, 조사 없이 마이그레이션을 쓰면 잠금을 깨뜨릴 수 있다. Task 5의 산출물 형식과 판단 기준은 구체적으로 지정했다.

Task 7 Step 4는 finding 생성 코드를 담지 않았다. 기존 감사 파이프라인의 review-approve-manifest 경로를 쓰기 때문이고, 어떤 필드에 어떤 값을 넣는지는 명시했다.

**3. 타입 일관성**

- `NoonnuFontSnapshot.official_url` / `official_url_anchor_text` / `global_social_links` — Task 1에서 정의, Task 2에서 사용
- `judge_official_url(snapshot, db_official_url, db_license_source_url) -> UrlAuditVerdict` — Task 2에서 정의, Task 3에서 사용
- `UrlAuditVerdict.classification` / `recommended_action` / `contamination_type` / `new_official_url` / `evidence` — Task 2에서 정의, Task 3에서 `ScanRecord`로 옮겨 담음
- `ScanTarget` / `ScanRecord` / `scan_targets` / `ScanAbortedError` — Task 3에서 정의, Task 4에서 사용
- `summarize(records) -> dict[str, object]` — Task 4에서 정의
- Task 1의 `_extract_official_url`은 `audit_noonnu.py` 안의 비공개 함수다. `noonnu_seed.py`에도 같은 이름의 함수가 있으나 모듈이 달라 충돌하지 않는다

**4. 알려진 위험**

Task 1의 Step 5는 `extract_noonnu_font` 본문의 정확한 위치를 지정하지 못했다. 그 함수가 길고 `evidence_locations` 조립 위치가 여러 곳일 수 있다. 구현자는 함수를 먼저 읽고 스냅샷 생성 직전에 넣어야 한다.
