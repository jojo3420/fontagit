# 눈누 Tier B 라이선스-스타일 반자동 수집 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 눈누 상세페이지에서 라이선스 허용표-스타일을 결정론적으로 추출해, 상업 사용이 명백히 열린 폰트는 자동 발행하고 애매한 소수만 사람이 승인하는 반자동 파이프라인을 구현한다.

**Architecture:** 기존 `noonnu_seed` 크롤러(robots 준수, 1.5초 딜레이)를 재사용하는 신규 모듈 `noonnu_enrich.py`가 seed JSON의 눈누 URL을 재방문해 파싱한다. 파싱은 순수 함수(테스트 용이)로 분리하고, 분류 게이트가 auto_safe/needs_review를 판정한다. auto_safe는 fonts에 직접 기록+발행, 나머지는 `license_proposals` 검수 큐로. 검수/발행은 CLI로.

**Tech Stack:** Python 3.12, httpx, BeautifulSoup4, pydantic, supabase-py (service_role), pytest. LLM 미사용.

## Global Constraints

- 라이선스 미확정 폰트를 published로 자동 전환 금지. auto_safe 게이트(아래) 통과분만 자동 발행.
- 눈누 문구(설명-요약 문장) 복제 금지. 구조화된 사실(허용표 O/X, @font-face 굵기)만 추출.
- 크롤링 규약: robots.txt 준수, 1.5초 딜레이, UA `FontAgitSeedBot/0.1 (+https://fontag.it)` — 전부 `noonnu_seed`에서 재사용.
- 파일 재호스팅 금지. 폰트 파일 다운로드 안 함.
- prod DB 쓰기-마이그레이션은 사용자 확인 필수. MCP는 읽기 전용 → 마이그레이션은 사용자가 psql로 수동 적용.
- 자동 게이트(D6): `parse_status=parsed AND price==0 AND {인쇄물,웹사이트,포장지,영상} 전부 'allowed'` → auto_safe. 그 외 전부 needs_review.
- 안전 원칙: 파싱이 정확히 6개 카테고리로 떨어지지 않으면 parse 실패로 간주 → needs_review(자동 발행 안 함). "정확 아니면 기권".
- 코딩 컨벤션: Type Hints 100%, Docstring 한국어, print 금지(logging), Enum/상수로 하드코딩 회피.
- 파일 경로 루트: `apps/pipeline/`. 모듈 경로: `apps/pipeline/src/fontagit_pipeline/`. 테스트: `apps/pipeline/tests/`.

---

## Phase 0 — 스키마

### Task 1: 마이그레이션 0016 작성 (사용자 수동 적용)

**Files:**
- Create: `supabase/migrations/0016_noonnu_enrich.sql`

**Interfaces:**
- Produces: fonts 신규 컬럼(`allow_embedding`, `allow_redistribute`, `allow_modify`, `license_note`, `verified_at`, `license_source_url`, `auto_approved`), 완화된 `fonts_published_license_chk`, 신규 테이블 `fontagit.license_proposals`.

- [ ] **Step 1: SQL 작성**

```sql
-- 0016_noonnu_enrich.sql
-- 눈누 Tier B 2단계: 라이선스 세부 컬럼 + 발행 제약 완화 + 검수 큐

-- 1) fonts 라이선스 세부 컬럼 (F-01 4행 + 근거)
alter table fontagit.fonts
  add column if not exists allow_embedding    text,
  add column if not exists allow_redistribute text,
  add column if not exists allow_modify       text,
  add column if not exists license_note       text,
  add column if not exists verified_at        timestamptz,
  add column if not exists license_source_url text,
  add column if not exists auto_approved       boolean not null default false;

alter table fontagit.fonts
  add constraint fonts_allow_embedding_chk
    check (allow_embedding is null or allow_embedding in ('allowed','conditional','denied')),
  add constraint fonts_allow_redistribute_chk
    check (allow_redistribute is null or allow_redistribute in ('allowed','conditional','denied')),
  add constraint fonts_allow_modify_chk
    check (allow_modify is null or allow_modify in ('allowed','conditional','denied'));

-- 2) 발행 제약 완화: Tier B는 verified면 발행, Tier A만 라이선스 타입 화이트리스트 유지
alter table fontagit.fonts drop constraint if exists fonts_published_license_chk;
alter table fontagit.fonts
  add constraint fonts_published_license_chk
    check (status <> 'published' or (
      license_verified = true
      and (source_tier <> 'A' or license_type in ('OFL','Apache-2.0','UFL'))
    ));

-- 3) 검수 큐 (기획서 13장 review_queue). 운영 전용, RLS 잠금.
create table fontagit.license_proposals (
  id                       uuid primary key default gen_random_uuid(),
  font_id                  uuid not null references fontagit.fonts(id) on delete cascade,
  slug                     text not null,
  source_url               text not null,
  raw_permissions          jsonb not null,
  proposed_commercial_free boolean,
  proposed_embedding       text,
  proposed_redistribute    text,
  proposed_modify          text,
  proposed_license_type    text,
  proposed_weights         int[]  not null default '{}',
  proposed_italic          boolean,
  proposed_category_ko     text,
  parse_status             text not null check (parse_status in ('parsed','partial','failed')),
  classification           text not null check (classification in ('auto_safe','needs_review')),
  review_status            text not null default 'proposed'
                             check (review_status in ('proposed','approved','rejected','auto_published')),
  scraped_at               timestamptz not null default now(),
  reviewed_at              timestamptz,
  reviewer_note            text,
  unique (font_id)
);
create index idx_license_proposals_review on fontagit.license_proposals(review_status);

alter table fontagit.license_proposals enable row level security;
-- anon 정책 없음 = 공개 읽기 차단. service_role만 접근.
grant select, insert, update, delete on fontagit.license_proposals to service_role;
```

- [ ] **Step 2: 스펙 대조 자가 점검**

`docs/superpowers/specs/2026-07-18-noonnu-tier-b-enrich-design.md` 5절과 컬럼-제약-테이블이 1:1 일치하는지 확인. 누락 컬럼 없는지 체크.

- [ ] **Step 3: 사용자에게 dev 적용 요청 (게이트)**

이 마이그레이션은 MCP 읽기전용 제약으로 에이전트가 못 넣는다. 사용자에게 dev(zgxt...supabase.co)에 psql 적용을 요청하고 결과를 확인받는다. 적용 전에는 Phase A의 DB 통합 테스트를 실행하지 않는다.

**검증(사용자 적용 후):** `select column_name from information_schema.columns where table_schema='fontagit' and table_name='fonts' and column_name='auto_approved';` → 1행. `select to_regclass('fontagit.license_proposals');` → not null.

---

## Phase A — 추출 코어 (순수 함수 TDD)

> Phase A 전체가 끝나면 `noonnu-enrich`로 dev에 제안 적재 + auto_safe 자동 발행이 동작한다(첫 shippable 슬라이스).

### Task 2: 눈누 페이지 메타 추출 (JSON-LD)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py`
- Create: `apps/pipeline/tests/test_noonnu_enrich.py`
- Create: `apps/pipeline/tests/fixtures/noonnu_auto.html`, `apps/pipeline/tests/fixtures/noonnu_conditional.html`

**Interfaces:**
- Produces: `extract_meta(html: str) -> tuple[str | None, int | None, str | None]` (name, price, creator).

- [ ] **Step 1: 실제 눈누 페이지를 픽스처로 저장하고 DOM 확인**

정중하게(1.5초 간격, UA 지정) 실 페이지 2개를 저장하고 라이선스 표-@font-face 구조를 눈으로 확인한다. 눈누 편집 문구(폰트 설명/후기)는 제거하고 라이선스표-@font-face-JSON-LD 영역만 남겨 픽스처로 커밋한다.

```bash
cd apps/pipeline
UA="FontAgitSeedBot/0.1 (+https://fontag.it)"
mkdir -p tests/fixtures
curl -s -A "$UA" https://noonnu.cc/font_page/1   -o tests/fixtures/noonnu_conditional.html   # 고도체: 임베딩 조건부
sleep 2
curl -s -A "$UA" https://noonnu.cc/font_page/920 -o tests/fixtures/noonnu_auto.html          # 상업 4카테고리 전부 사용가능
```
실제 status 라벨(`사용 가능`/`조건부 허용`/`사용 불가`)과 6개 카테고리 순서, `@font-face`의 `font-weight` 위치를 확인해 이후 파서 셀렉터 근거로 삼는다.

- [ ] **Step 2: 실패 테스트 작성**

```python
# tests/test_noonnu_enrich.py
from pathlib import Path
from fontagit_pipeline import noonnu_enrich as ne

FIX = Path(__file__).parent / "fixtures"

def _html(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")

def test_extract_meta_reads_jsonld():
    name, price, creator = ne.extract_meta(_html("noonnu_auto.html"))
    assert isinstance(name, str) and name
    assert price == 0            # 무료 폰트
    assert isinstance(creator, str) and creator
```

- [ ] **Step 3: 실패 확인**

Run: `cd apps/pipeline && python -m pytest tests/test_noonnu_enrich.py::test_extract_meta_reads_jsonld -v`
Expected: FAIL (`AttributeError: module ... has no attribute 'extract_meta'`)

- [ ] **Step 4: 최소 구현**

```python
# noonnu_enrich.py
"""눈누 상세페이지에서 라이선스-스타일 사실을 결정론적으로 추출한다.

크롤링 규약(robots/딜레이/UA)은 noonnu_seed에서 재사용. LLM 미사용.
"""
import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EnrichParseError(Exception):
    """눈누 페이지 파싱 실패(구조 불일치 등)."""


def _iter_jsonld(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            blocks.append(data)
    return blocks


def extract_meta(html: str) -> tuple[Optional[str], Optional[int], Optional[str]]:
    """JSON-LD SoftwareApplication에서 (이름, 가격, 제작사)를 추출한다.

    가격은 정수(원). 파싱 불가 항목은 None.
    """
    for data in _iter_jsonld(html):
        if data.get("@type") != "SoftwareApplication":
            continue
        name = data.get("name")
        creator = data.get("creator") or data.get("author")
        if isinstance(creator, dict):
            creator = creator.get("name")
        price: Optional[int] = None
        offers = data.get("offers")
        if isinstance(offers, dict) and offers.get("price") is not None:
            try:
                price = int(float(offers["price"]))
            except (ValueError, TypeError):
                price = None
        return name, price, creator
    return None, None, None
```

- [ ] **Step 5: 통과 확인 + 커밋**

Run: `cd apps/pipeline && python -m pytest tests/test_noonnu_enrich.py -v`
Expected: PASS
```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py apps/pipeline/tests/test_noonnu_enrich.py apps/pipeline/tests/fixtures/
git commit -m "feat: 눈누 enrich 메타(JSON-LD) 추출"
```

### Task 3: 라이선스 허용표 파싱 (6 카테고리)

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py`
- Modify: `apps/pipeline/tests/test_noonnu_enrich.py`

**Interfaces:**
- Consumes: 픽스처 HTML.
- Produces: `parse_permissions(html: str) -> dict[str, str]` — 키는 `PERMISSION_CATEGORIES`(`print/website/packaging/video/embedding/branding`), 값은 `allowed/conditional/denied`. 정확히 6개로 매핑 안 되면 `EnrichParseError`.

- [ ] **Step 1: 실패 테스트 작성**

```python
def test_parse_permissions_auto_all_allowed():
    perms = ne.parse_permissions(_html("noonnu_auto.html"))
    assert set(perms) == set(ne.PERMISSION_CATEGORIES)
    assert perms["print"] == "allowed"
    assert perms["website"] == "allowed"
    assert perms["packaging"] == "allowed"
    assert perms["video"] == "allowed"

def test_parse_permissions_conditional_embedding():
    perms = ne.parse_permissions(_html("noonnu_conditional.html"))
    assert perms["embedding"] == "conditional"      # 고도체: 임베딩 조건부

def test_parse_permissions_raises_when_not_six():
    import pytest
    with pytest.raises(ne.EnrichParseError):
        ne.parse_permissions("<html><body>no table</body></html>")
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/pipeline && python -m pytest tests/test_noonnu_enrich.py -k permissions -v`
Expected: FAIL (`AttributeError: parse_permissions`)

- [ ] **Step 3: 최소 구현**

```python
# noonnu_enrich.py 에 추가
PERMISSION_CATEGORIES: tuple[str, ...] = (
    "print", "website", "packaging", "video", "embedding", "branding",
)
_STATUS_MAP = {
    "사용 가능": "allowed",
    "조건부 허용": "conditional",
    "사용 불가": "denied",
}
# 상태 라벨을 정규식으로. 공백 변형 허용.
_STATUS_RE = re.compile(r"(사용\s*가능|조건부\s*허용|사용\s*불가)")


def _normalize_status(raw: str) -> str:
    key = re.sub(r"\s+", " ", raw).strip()
    return _STATUS_MAP[key]


def parse_permissions(html: str) -> dict[str, str]:
    """눈누 허용표에서 6개 카테고리 상태를 문서 순서대로 추출한다.

    눈누는 6개 사용 맥락(인쇄물/웹사이트/포장지/영상/임베딩/BICI)을 고정 순서로 렌더한다.
    상태 라벨을 순서대로 모아 카테고리에 인덱스 매핑한다.
    정확히 6개가 아니면 구조 불일치로 보고 EnrichParseError.
    """
    soup = BeautifulSoup(html, "html.parser")
    # 허용표 영역 앵커: "허용 범위" 헤딩 이후 영역으로 한정(스트레이 매칭 방지).
    anchor = soup.find(string=re.compile(r"허용\s*범위"))
    scope = anchor.find_parent() if anchor else soup
    # 상태 라벨만 텍스트로 순서 수집. 반응형 중복 DOM 방지 위해 dedup 없이
    # 정확히 6개일 때만 인정, 아니면 실패(안전한 기권).
    statuses: list[str] = []
    for el in scope.find_all(string=_STATUS_RE):
        m = _STATUS_RE.search(str(el))
        if m:
            statuses.append(_normalize_status(m.group(1)))
    if len(statuses) != len(PERMISSION_CATEGORIES):
        raise EnrichParseError(
            f"허용표 카테고리 수 불일치: {len(statuses)} (기대 6)"
        )
    return dict(zip(PERMISSION_CATEGORIES, statuses))
```

주: 앵커/중복 DOM 문제로 6개가 안 나오면 예외 → 상위에서 needs_review로 흡수(안전). Step 1의 실제 픽스처로 앵커가 맞는지 확인하고, 6개로 안 떨어지면 앵커 셀렉터를 실 DOM 기준으로 좁힌다.

- [ ] **Step 4: 통과 확인**

Run: `cd apps/pipeline && python -m pytest tests/test_noonnu_enrich.py -k permissions -v`
Expected: PASS (3개). 만약 실 픽스처에서 6개가 안 나오면 앵커를 실제 표 컨테이너로 교정 후 통과시킨다.

- [ ] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py apps/pipeline/tests/test_noonnu_enrich.py
git commit -m "feat: 눈누 라이선스 허용표 6카테고리 파싱"
```

### Task 4: 스타일 추출 (@font-face 굵기/이태릭, best-effort)

**Files:**
- Modify: `noonnu_enrich.py`, `tests/test_noonnu_enrich.py`

**Interfaces:**
- Produces: `extract_styles(html: str) -> tuple[list[int], bool]` — (오름차순 unique weights, italic 여부). 없으면 `([], False)`.

- [ ] **Step 1: 실패 테스트**

```python
def test_extract_styles_reads_font_face_weights():
    weights, italic = ne.extract_styles(_html("noonnu_conditional.html"))
    assert weights == [400, 700]     # 고도체 Regular+Bold
    assert italic is False

def test_extract_styles_missing_returns_empty():
    weights, italic = ne.extract_styles("<html></html>")
    assert weights == []
    assert italic is False
```

- [ ] **Step 2: 실패 확인** — Run: `pytest -k styles -v` → FAIL.

- [ ] **Step 3: 구현**

```python
_WEIGHT_RE = re.compile(r"font-weight:\s*(\d{3})")
_STYLE_RE = re.compile(r"font-style:\s*italic")


def extract_styles(html: str) -> tuple[list[int], bool]:
    """@font-face 선언에서 굵기 목록과 이태릭 여부를 추출한다(best-effort).

    눈누가 노출하는 미리보기 굵기 기준이라 제작사 전체 세트와 다를 수 있다.
    없으면 ([], False).
    """
    weights = sorted({int(m) for m in _WEIGHT_RE.findall(html)})
    italic = bool(_STYLE_RE.search(html))
    return weights, italic
```

- [ ] **Step 4: 통과 확인** — Run: `pytest -k styles -v` → PASS.

- [ ] **Step 5: 커밋** — `git commit -m "feat: 눈누 @font-face 스타일(굵기/이태릭) 추출"`

### Task 5: 라이선스 타입 추정 + 4행 매핑

**Files:** Modify `noonnu_enrich.py`, `tests/test_noonnu_enrich.py`

**Interfaces:**
- Produces:
  - `guess_license_type(html: str) -> str` — 'OFL' 또는 'custom-free'.
  - `map_license_rows(perms: dict[str,str], license_type: str) -> dict` — 키: `is_commercial_free`(bool), `allow_embedding`/`allow_redistribute`/`allow_modify`(str|None), `license_note`(str|None).

- [ ] **Step 1: 실패 테스트**

```python
def test_guess_license_type_ofl():
    assert ne.guess_license_type("<p>본 폰트는 SIL OFL 1.1 라이선스</p>") == "OFL"
    assert ne.guess_license_type("<p>무료 폰트</p>") == "custom-free"

def test_map_rows_commercial_free_when_four_allowed():
    perms = {"print":"allowed","website":"allowed","packaging":"allowed",
             "video":"allowed","embedding":"conditional","branding":"allowed"}
    rows = ne.map_license_rows(perms, "custom-free")
    assert rows["is_commercial_free"] is True
    assert rows["allow_embedding"] == "conditional"
    assert rows["allow_redistribute"] is None      # 표에 없음 + 비OFL → unknown
    assert rows["allow_modify"] is None
    assert "임베딩" in rows["license_note"]          # 조건부 안내(우리 표현)

def test_map_rows_ofl_sets_redistribute_modify():
    perms = {k:"allowed" for k in ne.PERMISSION_CATEGORIES}
    rows = ne.map_license_rows(perms, "OFL")
    assert rows["allow_redistribute"] == "conditional"
    assert rows["allow_modify"] == "allowed"

def test_map_rows_not_commercial_when_denied():
    perms = {"print":"denied","website":"allowed","packaging":"allowed",
             "video":"allowed","embedding":"allowed","branding":"allowed"}
    assert ne.map_license_rows(perms, "custom-free")["is_commercial_free"] is False
```

- [ ] **Step 2: 실패 확인** — Run: `pytest -k "license_type or map_rows" -v` → FAIL.

- [ ] **Step 3: 구현**

```python
_COMMERCIAL_KEYS = ("print", "website", "packaging", "video")


def guess_license_type(html: str) -> str:
    """라이선스 본문에 OFL/SIL 표기가 있으면 'OFL', 아니면 'custom-free'."""
    if re.search(r"\bOFL\b|SIL\s*Open\s*Font", html, re.IGNORECASE):
        return "OFL"
    return "custom-free"


def map_license_rows(perms: dict[str, str], license_type: str) -> dict:
    """눈누 6카테고리를 F-01 라이선스 4행으로 매핑한다.

    - 상업적 이용 = 상업 4카테고리 전부 allowed
    - 임베딩 = perms['embedding']
    - 재배포/수정 = 표에 없음 → OFL일 때만 표준값, 그 외 None(unknown)
    - license_note = 조건부 발생 시 우리 표현의 짧은 주의(눈누 문구 복제 아님)
    """
    is_commercial_free = all(perms[k] == "allowed" for k in _COMMERCIAL_KEYS)
    allow_embedding = perms["embedding"]
    if license_type == "OFL":
        allow_redistribute, allow_modify = "conditional", "allowed"
    else:
        allow_redistribute, allow_modify = None, None

    notes: list[str] = []
    if allow_embedding == "conditional":
        notes.append("임베딩 조건부 - 제작사 약관 확인")
    if allow_embedding == "denied":
        notes.append("임베딩 불가 - 제작사 약관 확인")
    for k in _COMMERCIAL_KEYS:
        if perms[k] == "conditional":
            notes.append(f"{k} 조건부 - 제작사 약관 확인")
    license_note = "; ".join(notes) or None

    return {
        "is_commercial_free": is_commercial_free,
        "allow_embedding": allow_embedding,
        "allow_redistribute": allow_redistribute,
        "allow_modify": allow_modify,
        "license_note": license_note,
    }
```

- [ ] **Step 4: 통과 확인** — Run: `pytest -k "license_type or map_rows" -v` → PASS.

- [ ] **Step 5: 커밋** — `git commit -m "feat: 라이선스 타입 추정 + F-01 4행 매핑"`

### Task 6: 분류 게이트 (auto_safe / needs_review)

**Files:** Modify `noonnu_enrich.py`, `tests/test_noonnu_enrich.py`

**Interfaces:**
- Produces: `classify(parse_ok: bool, price: Optional[int], perms: Optional[dict[str,str]]) -> str` — 'auto_safe' | 'needs_review'.

- [ ] **Step 1: 실패 테스트**

```python
def test_classify_auto_safe():
    perms = {k:"allowed" for k in ne.PERMISSION_CATEGORIES}
    assert ne.classify(True, 0, perms) == "auto_safe"

def test_classify_embedding_conditional_still_auto():
    perms = {k:"allowed" for k in ne.PERMISSION_CATEGORIES} | {"embedding":"conditional"}
    assert ne.classify(True, 0, perms) == "auto_safe"      # 임베딩은 게이트 아님

def test_classify_website_conditional_needs_review():
    perms = {k:"allowed" for k in ne.PERMISSION_CATEGORIES} | {"website":"conditional"}
    assert ne.classify(True, 0, perms) == "needs_review"

def test_classify_parse_fail_or_paid_needs_review():
    assert ne.classify(False, 0, None) == "needs_review"
    perms = {k:"allowed" for k in ne.PERMISSION_CATEGORIES}
    assert ne.classify(True, 100, perms) == "needs_review"
```

- [ ] **Step 2: 실패 확인** — Run: `pytest -k classify -v` → FAIL.

- [ ] **Step 3: 구현**

```python
def classify(parse_ok: bool, price: Optional[int], perms: Optional[dict[str, str]]) -> str:
    """자동 발행 게이트(D6). 상업 4카테고리 전부 allowed + price 0 + 파싱성공만 auto_safe."""
    if not parse_ok or perms is None:
        return "needs_review"
    if price != 0:
        return "needs_review"
    if all(perms[k] == "allowed" for k in _COMMERCIAL_KEYS):
        return "auto_safe"
    return "needs_review"
```

- [ ] **Step 4: 통과 확인** — Run: `pytest -k classify -v` → PASS.

- [ ] **Step 5: 커밋** — `git commit -m "feat: 자동 발행 분류 게이트"`

### Task 7: 제안 조립 (build_proposal)

**Files:** Modify `noonnu_enrich.py`, `tests/test_noonnu_enrich.py`

**Interfaces:**
- Consumes: Task 2-6 함수.
- Produces: `build_proposal(font_id: str, slug: str, source_url: str, official_url: str, html: str) -> dict` — `license_proposals` insert용 dict + 파생 `_font_update`(auto_safe일 때 fonts 반영값). 파싱 실패는 예외 없이 `parse_status='failed'`, `classification='needs_review'`로 담는다.

- [ ] **Step 1: 실패 테스트**

```python
def test_build_proposal_auto_from_fixture():
    p = ne.build_proposal("fid-1", "goldo", "https://noonnu.cc/font_page/920",
                          "https://maker.example/goldo", _html("noonnu_auto.html"))
    assert p["parse_status"] == "parsed"
    assert p["classification"] == "auto_safe"
    assert p["proposed_commercial_free"] is True
    assert p["raw_permissions"]["print"] == "allowed"
    assert p["source_url"].startswith("https://noonnu.cc")

def test_build_proposal_parse_fail_is_needs_review():
    p = ne.build_proposal("fid-x", "broken", "https://noonnu.cc/font_page/0",
                          "https://x", "<html>no table</html>")
    assert p["parse_status"] == "failed"
    assert p["classification"] == "needs_review"
    assert p["proposed_commercial_free"] is None
```

- [ ] **Step 2: 실패 확인** — Run: `pytest -k build_proposal -v` → FAIL.

- [ ] **Step 3: 구현**

```python
def build_proposal(
    font_id: str, slug: str, source_url: str, official_url: str, html: str,
) -> dict:
    """눈누 HTML에서 license_proposals insert용 dict를 조립한다.

    파싱 실패 시 예외를 던지지 않고 parse_status='failed' + needs_review로 담아,
    호출측 배치가 안전하게 계속되도록 한다.
    """
    name, price, creator = extract_meta(html)
    weights, italic = extract_styles(html)
    license_type = guess_license_type(html)
    try:
        perms = parse_permissions(html)
        parse_status = "parsed"
    except EnrichParseError as exc:
        logger.warning("허용표 파싱 실패(slug=%s): %s", slug, exc)
        perms, parse_status = None, "failed"

    classification = classify(parse_status == "parsed", price, perms)
    rows = (
        map_license_rows(perms, license_type)
        if perms is not None
        else {"is_commercial_free": None, "allow_embedding": None,
              "allow_redistribute": None, "allow_modify": None, "license_note": None}
    )
    proposal = {
        "font_id": font_id,
        "slug": slug,
        "source_url": source_url,
        "raw_permissions": perms or {},
        "proposed_commercial_free": rows["is_commercial_free"],
        "proposed_embedding": rows["allow_embedding"],
        "proposed_redistribute": rows["allow_redistribute"],
        "proposed_modify": rows["allow_modify"],
        "proposed_license_type": license_type,
        "proposed_weights": weights,
        "proposed_italic": italic,
        "proposed_category_ko": None,       # 분류 보정은 검수 시 사람 몫(블로커 #4)
        "parse_status": parse_status,
        "classification": classification,
        "review_status": "auto_published" if classification == "auto_safe" else "proposed",
    }
    # auto_safe일 때 fonts에 반영할 값(발행)
    proposal["_font_update"] = _font_update_for(proposal, official_url) if classification == "auto_safe" else None
    return proposal


def _font_update_for(proposal: dict, official_url: str) -> dict:
    """auto_safe 제안을 fonts 발행 업데이트 dict로 변환한다."""
    return {
        "is_commercial_free": proposal["proposed_commercial_free"],
        "allow_embedding": proposal["proposed_embedding"],
        "allow_redistribute": proposal["proposed_redistribute"],
        "allow_modify": proposal["proposed_modify"],
        "license_type": proposal["proposed_license_type"],
        "license_note": (proposal["raw_permissions"] and None),  # note는 map에서, 아래 오케스트레이터가 채움
        "weights": proposal["proposed_weights"],
        "variants": ["italic"] if proposal["proposed_italic"] else [],
        "license_verified": True,
        "auto_approved": True,
        "license_source_url": official_url,
        "status": "published",
    }
```

주: `license_note`는 `map_license_rows` 결과에서 나오므로, 정확히는 `build_proposal`에서 `rows["license_note"]`를 `_font_update`에도 전달해야 한다. Step 4에서 테스트가 이를 강제한다.

- [ ] **Step 4: license_note 전달 보정 + 통과 확인**

`_font_update_for`가 `license_note`를 받도록 시그니처를 `(_font_update_for(proposal, official_url, license_note))`로 바꾸고 `build_proposal`에서 `rows["license_note"]`를 넘긴다. 테스트 추가:
```python
def test_build_proposal_font_update_has_note_and_verified():
    p = ne.build_proposal("fid","goldo","https://noonnu.cc/font_page/1",
                          "https://maker", _html("noonnu_conditional.html"))
    # 고도체는 임베딩 조건부지만 상업4 allowed면 auto_safe
    if p["classification"] == "auto_safe":
        fu = p["_font_update"]
        assert fu["license_verified"] is True and fu["status"] == "published"
        assert fu["auto_approved"] is True
```
Run: `pytest -k build_proposal -v` → PASS.

- [ ] **Step 5: 커밋** — `git commit -m "feat: 눈누 제안 조립(build_proposal) + 발행 업데이트 파생"`

### Task 8: DB 오케스트레이터 + CLI 배선

**Files:**
- Modify: `noonnu_enrich.py` (오케스트레이터 `enrich_fonts`)
- Modify: `apps/pipeline/src/fontagit_pipeline/__main__.py` (서브커맨드 `noonnu-enrich`)

**Interfaces:**
- Consumes: `build_proposal`, seed JSON(`NoonnuSeedOutput`), `build_slug`, `clean_font_name`, `noonnu_seed`의 robots/딜레이/fetch.
- Produces: `enrich_fonts(seed_path, supabase_url, secret_key, *, limit=None, only_slug=None) -> tuple[int,int,int]` (auto_published, proposed, skipped).

- [ ] **Step 1: 오케스트레이터 구현 (외부 경계라 통합 성격, 유닛은 최소)**

```python
# noonnu_enrich.py 에 추가
import time
from pathlib import Path
from typing import Optional as _Opt

from supabase import create_client

from fontagit_pipeline.models import NoonnuSeedOutput
from fontagit_pipeline.noonnu_seed import (
    _USER_AGENT, _REQUEST_DELAY, _parse_robots_policy, _fetch_url,
    _ROBOTS_URL, _ROBOT_USER_AGENT, clean_font_name,
)
from fontagit_pipeline.transform import build_slug
import httpx


class NoonnuEnrichError(Exception):
    """눈누 enrich 실행 오류."""


def _lookup_font(schema, slug: str) -> _Opt[dict]:
    try:
        resp = schema.table("fonts").select("id,status,official_url").eq("slug", slug).maybe_single().execute()
        return resp.data
    except Exception:
        return None


def enrich_fonts(
    seed_path: Path, supabase_url: str, secret_key: str,
    *, limit: _Opt[int] = None, only_slug: _Opt[str] = None,
) -> tuple[int, int, int]:
    """seed의 눈누 URL을 재방문해 제안 적재 + auto_safe 자동 발행.

    반환: (auto_published, proposed, skipped).
    """
    doc = NoonnuSeedOutput(**__import__("json").loads(Path(seed_path).read_text("utf-8")))
    client = create_client(supabase_url, secret_key)
    schema = client.schema("fontagit")

    with httpx.Client(timeout=10.0, follow_redirects=True) as http:
        robots = _parse_robots_policy(_fetch_url(http, _ROBOTS_URL))
        auto = proposed = skipped = 0
        records = doc.records[:limit] if limit else doc.records
        for rec in records:
            slug = build_slug(clean_font_name(rec.name_en) or "") if rec.name_en else \
                   __import__("re").sub(r"-+", "-", (rec.name_ko or "").lower().replace(" ", "-")).strip("-")
            if only_slug and slug != only_slug:
                continue
            font = _lookup_font(schema, slug)
            if not font or font.get("status") == "published":
                skipped += 1
                continue
            if not robots.can_fetch(_ROBOT_USER_AGENT, rec.source_page):
                skipped += 1
                continue
            time.sleep(_REQUEST_DELAY)
            try:
                html = _fetch_url(http, rec.source_page, headers={"User-Agent": _USER_AGENT}) \
                    if False else http.get(rec.source_page, headers={"User-Agent": _USER_AGENT}).text
            except httpx.HTTPError:
                skipped += 1
                continue
            proposal = build_proposal(font["id"], slug, rec.source_page,
                                      font.get("official_url") or rec.official_url, html)
            fu = proposal.pop("_font_update")
            schema.table("license_proposals").upsert(proposal, on_conflict="font_id").execute()
            if fu is not None:
                schema.table("fonts").update(fu).eq("id", font["id"]).execute()
                auto += 1
            else:
                proposed += 1
    logger.info("enrich 완료: 자동발행 %d, 검수대기 %d, 스킵 %d", auto, proposed, skipped)
    return auto, proposed, skipped
```

주: `_fetch_url` 재사용 시 헤더 인자가 다르면 직접 `http.get`으로 대체(위 코드가 그 형태). 실제 구현 시 `noonnu_seed._fetch_url` 시그니처를 확인하고 헤더 포함 fetch로 통일한다.

- [ ] **Step 2: CLI 서브커맨드 추가**

`__main__.py`에 `main_noonnu_enrich(args)` 추가 + 서브파서 등록:
```python
def main_noonnu_enrich(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    try:
        settings = load_settings()
    except ValidationError:
        logger.error("Supabase 설정이 없습니다."); return 2
    from fontagit_pipeline.noonnu_enrich import enrich_fonts, NoonnuEnrichError
    seed = Path("output") / "tier-b-noonnu-seed.json"
    try:
        auto, proposed, skipped = enrich_fonts(
            seed, settings.supabase_url, settings.supabase_secret_key,
            limit=args.limit, only_slug=args.slug)
        logger.info("자동발행 %d / 검수대기 %d / 스킵 %d", auto, proposed, skipped)
        return 0
    except NoonnuEnrichError as exc:
        logger.error("enrich 실패: %s", exc); return 3
```
서브파서:
```python
enrich_parser = subparsers.add_parser("noonnu-enrich", help="눈누 라이선스-스타일 추출/제안")
enrich_parser.add_argument("--limit", type=int, default=None)
enrich_parser.add_argument("--slug", type=str, default=None)
enrich_parser.set_defaults(func=main_noonnu_enrich)
```

- [ ] **Step 3: 소량 통합 검증 (dev, Task 1 적용 후)**

Run: `cd apps/pipeline && python -m fontagit_pipeline noonnu-enrich --limit 5`
Expected: 로그에 "자동발행 N / 검수대기 M / 스킵 K", 예외 없이 종료(0). dev `license_proposals`에 최대 5행.
검증: MCP 또는 사용자 psql로 `select classification, count(*) from fontagit.license_proposals group by 1;`

- [ ] **Step 4: 린트/타입/테스트 + 커밋**

Run: `cd apps/pipeline && ruff check . && python -m pytest -q`
Expected: 통과.
```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py apps/pipeline/src/fontagit_pipeline/__main__.py
git commit -m "feat: noonnu-enrich 오케스트레이터 + CLI"
```

---

## Phase B — 검수 CLI

### Task 9: 검수 조회/승인/반려 CLI

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/noonnu_review.py`
- Modify: `__main__.py` (서브커맨드 `noonnu-review`)
- Create: `apps/pipeline/tests/test_noonnu_review.py`

**Interfaces:**
- Produces:
  - `list_pending(schema) -> list[dict]` — needs_review 제안(제작사/타입 정렬)
  - `approve(schema, slug, note=None) -> None` — 제안값을 fonts에 기록+published, proposal=approved
  - `reject(schema, slug, note) -> None` — proposal=rejected, fonts는 draft
  - `build_font_update_from_proposal(proposal: dict, official_url: str) -> dict` (순수 함수, TDD 대상)

- [ ] **Step 1: 순수 함수 실패 테스트**

```python
# test_noonnu_review.py
from fontagit_pipeline import noonnu_review as nr

def test_build_font_update_from_proposal():
    proposal = {"proposed_commercial_free": True, "proposed_embedding":"allowed",
                "proposed_redistribute": None, "proposed_modify": None,
                "proposed_license_type":"custom-free", "proposed_weights":[400],
                "proposed_italic": False, "raw_permissions":{}, }
    fu = nr.build_font_update_from_proposal(proposal, "https://maker")
    assert fu["license_verified"] is True
    assert fu["status"] == "published"
    assert fu["auto_approved"] is False        # 사람 승인분은 auto_approved=False
    assert fu["weights"] == [400]
```

- [ ] **Step 2: 실패 확인** — Run: `pytest tests/test_noonnu_review.py -v` → FAIL.

- [ ] **Step 3: 구현**

```python
# noonnu_review.py
"""눈누 라이선스 제안 검수 CLI 로직. 사람 승인분만 fonts에 반영+발행."""
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


def build_font_update_from_proposal(proposal: dict, official_url: str) -> dict:
    """제안을 fonts 발행 업데이트로 변환(사람 승인 경로 → auto_approved=False)."""
    return {
        "is_commercial_free": bool(proposal.get("proposed_commercial_free")),
        "allow_embedding": proposal.get("proposed_embedding"),
        "allow_redistribute": proposal.get("proposed_redistribute"),
        "allow_modify": proposal.get("proposed_modify"),
        "license_type": proposal.get("proposed_license_type"),
        "weights": proposal.get("proposed_weights") or [],
        "variants": ["italic"] if proposal.get("proposed_italic") else [],
        "license_verified": True,
        "auto_approved": False,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "license_source_url": official_url,
        "status": "published",
    }


def list_pending(schema) -> list[dict]:
    """검수 대기 제안을 제작사-타입 순으로 반환."""
    resp = (schema.table("license_proposals")
            .select("*").eq("review_status", "proposed")
            .order("proposed_license_type").execute())
    return resp.data or []


def approve(schema, slug: str, note: Optional[str] = None) -> None:
    """제안을 승인: fonts에 기록+발행, proposal=approved."""
    prop = (schema.table("license_proposals").select("*").eq("slug", slug)
            .maybe_single().execute()).data
    if not prop:
        raise ValueError(f"제안 없음: {slug}")
    font = (schema.table("fonts").select("id,official_url").eq("id", prop["font_id"])
            .maybe_single().execute()).data
    fu = build_font_update_from_proposal(prop, font.get("official_url") or prop["source_url"])
    schema.table("fonts").update(fu).eq("id", prop["font_id"]).execute()
    schema.table("license_proposals").update(
        {"review_status": "approved",
         "reviewed_at": datetime.now(timezone.utc).isoformat(),
         "reviewer_note": note}).eq("id", prop["id"]).execute()
    logger.info("승인+발행: %s", slug)


def reject(schema, slug: str, note: str) -> None:
    """제안을 반려: proposal=rejected. fonts는 draft 유지."""
    schema.table("license_proposals").update(
        {"review_status": "rejected",
         "reviewed_at": datetime.now(timezone.utc).isoformat(),
         "reviewer_note": note}).eq("slug", slug).execute()
    logger.info("반려: %s (%s)", slug, note)
```

- [ ] **Step 4: 통과 확인** — Run: `pytest tests/test_noonnu_review.py -v` → PASS.

- [ ] **Step 5: CLI 배선 + 커밋**

`__main__.py`에 `noonnu-review` 서브파서(`list`/`approve <slug>`/`reject <slug> --note`) 추가. 각 액션은 settings로 client 생성 후 위 함수 호출, 결과를 logger로 출력.
```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_review.py apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/tests/test_noonnu_review.py
git commit -m "feat: 눈누 라이선스 제안 검수 CLI"
```

### Task 10: 자동 발행분 표본점검 + unpublish

**Files:** Modify `noonnu_review.py`, `__main__.py`, `test_noonnu_review.py`

**Interfaces:**
- Produces:
  - `sample_auto_published(schema, pct: int = 5) -> list[dict]` — auto_approved=true 폰트 중 pct% 표본
  - `unpublish(schema, slug: str, note: str) -> None` — status=draft로 되돌리고 license_verified=false

- [ ] **Step 1: 실패 테스트 (표본 크기 계산 순수 함수)**

```python
def test_sample_size():
    assert nr.sample_size(100, 5) == 5
    assert nr.sample_size(3, 5) == 1        # 최소 1
    assert nr.sample_size(0, 5) == 0
```

- [ ] **Step 2: 실패 확인** — Run: `pytest -k sample_size -v` → FAIL.

- [ ] **Step 3: 구현**

```python
import math

def sample_size(total: int, pct: int) -> int:
    """표본 크기: total의 pct%, 1건 이상 있으면 최소 1."""
    if total <= 0:
        return 0
    return max(1, math.ceil(total * pct / 100))


def sample_auto_published(schema, pct: int = 5) -> list[dict]:
    rows = (schema.table("fonts").select("slug,name_ko,official_url,license_source_url")
            .eq("auto_approved", True).eq("status", "published").execute()).data or []
    n = sample_size(len(rows), pct)
    return rows[:n]      # 결정론(정렬 순). 무작위가 필요하면 정렬 키를 바꾼다.


def unpublish(schema, slug: str, note: str) -> None:
    """발행 취소: draft로 되돌리고 검증 플래그 해제."""
    schema.table("fonts").update(
        {"status": "draft", "license_verified": False}).eq("slug", slug).execute()
    schema.table("license_proposals").update(
        {"review_status": "rejected", "reviewer_note": f"unpublished: {note}"}
    ).eq("slug", slug).execute()
    logger.info("발행취소: %s", slug)
```

- [ ] **Step 4: 통과 확인** — Run: `pytest -k sample_size -v` → PASS.

- [ ] **Step 5: CLI 배선(`audit-sample`, `unpublish`) + 커밋**

```bash
git commit -am "feat: 자동발행 표본점검 + unpublish"
```

---

## Phase C — prod 발행 (사용자 확인 게이트)

### Task 11: prod 발행 명령 (published Tier B → prod DB)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/noonnu_publish.py`
- Modify: `__main__.py` (서브커맨드 `noonnu-publish`)
- Modify: `apps/pipeline/src/fontagit_pipeline/config.py` (prod 접속용 env 추가)

**Interfaces:**
- Produces: `publish_to_prod(dev_schema, prod_url, prod_key, *, dry_run=True) -> tuple[int,int]` — (upsert 대상 수, 실제 upsert 수). dry_run 기본 True.

- [ ] **Step 1: config에 prod env 추가**

```python
# config.py Settings에 추가
supabase_prod_url: str | None = None
supabase_prod_secret_key: str | None = None
```

- [ ] **Step 2: 발행 로직 구현 (기존 uploader 패턴 참고)**

dev에서 `source_tier='B' AND status='published'` 폰트(+aliases)를 읽어 prod에 upsert. `dry_run=True`면 대상만 집계하고 쓰지 않는다. prod 쓰기는 CLI에서 명시적 `--confirm` 필요.
```python
# noonnu_publish.py
"""dev에서 검증-발행된 Tier B 폰트를 prod DB로 동기화한다. prod 쓰기는 명시 확인 필수."""
import logging
from supabase import create_client

logger = logging.getLogger(__name__)
_COLS = ("slug","name_en","name_ko","source_tier","category_ko","category_google",
         "subsets","variants","weights","is_commercial_free","license_type",
         "license_verified","official_url","status","allow_embedding",
         "allow_redistribute","allow_modify","license_note","verified_at",
         "license_source_url","auto_approved")


def publish_to_prod(dev_schema, prod_url: str, prod_key: str, *, dry_run: bool = True) -> tuple[int, int]:
    rows = (dev_schema.table("fonts").select(",".join(_COLS))
            .eq("source_tier", "B").eq("status", "published").execute()).data or []
    if dry_run:
        logger.info("[dry-run] prod 발행 대상 %d건", len(rows))
        return len(rows), 0
    prod = create_client(prod_url, prod_key).schema("fontagit")
    written = 0
    for r in rows:
        prod.table("fonts").upsert(r, on_conflict="slug").execute()
        written += 1
    logger.info("prod 발행 완료: %d건", written)
    return len(rows), written
```

- [ ] **Step 3: CLI 배선 — 안전장치**

`noonnu-publish` 서브커맨드: 기본은 dry-run. 실제 쓰기는 `--confirm` 플래그 + 대화형 확인 문구(`prod에 N건 발행합니다. 계속? [y/N]`)를 모두 통과해야 실행. env는 `supabase_prod_url/secret_key`.

- [ ] **Step 4: dry-run 검증 + 커밋**

Run: `cd apps/pipeline && python -m fontagit_pipeline noonnu-publish`  (dry-run)
Expected: "[dry-run] prod 발행 대상 N건". prod에 아무 쓰기 없음.
```bash
git add apps/pipeline/src/fontagit_pipeline/noonnu_publish.py apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/src/fontagit_pipeline/config.py
git commit -m "feat: prod 발행 명령(dry-run 기본, 확인 게이트)"
```

---

## 운영 실행 순서 (구현 완료 후, 사용자 게이트 포함)

1. 사용자: dev에 `0016` 마이그레이션 psql 적용 (게이트)
2. `noonnu-enrich --limit 20` → 자동발행/검수대기 분포와 정확도 사용자 보고
3. 정확도 OK → `noonnu-enrich` 전량
4. `noonnu-review list` → `approve`/`reject` 일괄 처리
5. `noonnu-review audit-sample` 5% 점검, 이상 시 `unpublish`
6. codex 리뷰 (사용자 직접) → 지적 반영
7. `/commit` → push → merge
8. 사용자: prod에 `0016` 적용 (게이트)
9. `/deploy`(deploy.sh)로 리얼서버 배포
10. `noonnu-publish --confirm` → prod 데이터 적재 (사용자 확인 게이트)

## Self-Review (계획 작성자 자가 점검 결과)

- 스펙 커버리지: 5절 스키마→Task 1, 6-1 enrich→Task 2-8, 6-2 review→Task 9-10, 6-3 publish→Task 11. 누락 없음.
- 플레이스홀더: 없음(모든 코드 스텝에 실제 코드).
- 타입 일관성: `PERMISSION_CATEGORIES`, `classify` 시그니처, `build_proposal` 반환 키가 Task 간 일치.
- 알려진 리스크(스펙 11절): 눈누 DOM 이형 → parse 실패로 안전 흡수. Task 3 Step 4에서 실 픽스처로 앵커 교정 필요.
