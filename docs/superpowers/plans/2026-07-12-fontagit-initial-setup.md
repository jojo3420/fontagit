# FontAgit 초기 세팅 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모노레포 뼈대(`apps/web` Next.js 스캐폴드 + `apps/pipeline` Python)와 동작하는 Tier A 구글폰트 수집 스크립트를 만든다.

**Architecture:** pnpm workspace로 web을, uv로 Python 파이프라인을 관리하는 모노레포. 파이프라인은 구글폰트 webfonts API를 1회 조회해 한글 전체 + 라틴 인기 100을 수집하고, SRP로 분리된 순수 함수(필터/정규화/dedup/별칭)로 변환한 뒤 메타 래퍼가 있는 JSON을 원자적으로 저장한다. 인프라 연결은 없다.

**Tech Stack:** Python 3.12 + uv + httpx + pydantic/pydantic-settings + pytest + ruff + mypy. Next.js 15(App Router) + TypeScript + Tailwind + pnpm.

## Global Constraints

- Python `requires-python >= 3.12`. Node `>= 20`. 패키지 매니저: uv(Python), pnpm(web).
- 잠금 파일 `uv.lock`, `pnpm-lock.yaml` 커밋.
- 시크릿 하드코딩 금지. `GOOGLE_FONTS_API_KEY`는 `.env`에서만 로드하고 `.env`는 gitignore.
- API 키를 로그에 남기지 않는다. 요청 URL 로깅 시 `key=***`로 마스킹.
- `print` 금지, `logging` 사용. Type Hints 100%. Docstring 한국어.
- 라이선스는 검증 전 `license=null`, `license_verified=false`. 절대 `"OFL"` 등으로 단정하지 않는다.
- TTF URL 재호스팅/변환/자체 CDN 금지. `official_url`은 공식 specimen 페이지로만.
- `official_url`은 family의 공백만 `+`로 치환(퍼센트 인코딩 금지). 비ASCII family는 건너뛴다.
- 파이프라인 명령은 `apps/pipeline` 작업 디렉터리 기준으로 실행. `.env`도 그 기준.
- 커밋은 컨벤셔널 커밋 형식(`feat:`, `chore:`, `test:`, `docs:`).

---

## File Structure

루트
- `pnpm-workspace.yaml` (생성) — `packages: ['apps/web']`
- `package.json` (생성) — 루트 스크립트, `packageManager` 필드
- `Makefile` (생성) — web/pipeline 공통 명령
- `.nvmrc` (생성) — Node 버전 고정
- `.env.example` (생성) — `GOOGLE_FONTS_API_KEY=`
- `.gitignore` (수정) — Node/`.env`/`output/` 추가

`apps/pipeline`
- `pyproject.toml` (생성) — uv 프로젝트, 의존성, ruff/mypy/pytest 설정
- `src/fontagit_pipeline/__init__.py` (생성)
- `src/fontagit_pipeline/config.py` (생성) — `Settings`, `load_settings()`
- `src/fontagit_pipeline/models.py` (생성) — `GoogleFontRaw`, `FontRecord`, `OutputDocument`
- `src/fontagit_pipeline/transform.py` (생성) — 필터/정규화/dedup/별칭/레코드 변환
- `src/fontagit_pipeline/client.py` (생성) — `mask_key()`, `fetch_webfonts()`
- `src/fontagit_pipeline/writer.py` (생성) — `write_output()` 원자적 저장
- `src/fontagit_pipeline/__main__.py` (생성) — `build_document()`, `main()`
- `tests/fixtures/webfonts_sample.json` (생성) — API 응답 샘플
- `tests/test_models.py`, `tests/test_transform.py`, `tests/test_client.py`, `tests/test_writer.py`, `tests/test_main.py` (생성)

`apps/web`
- `pnpm create next-app`으로 생성 후 테마 토큰 + Pretendard 커스터마이즈.

---

## Task 1: 모노레포 루트 뼈대

**Files:**
- Create: `pnpm-workspace.yaml`, `package.json`, `Makefile`, `.nvmrc`, `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 없음(첫 태스크)
- Produces: 루트 워크스페이스 구조. `make` 타깃 `web-dev`/`collect`/`test`/`lint`은 이후 태스크가 채울 실행 대상.

- [ ] **Step 1: `.nvmrc` 생성**

파일 `.nvmrc`:
```
20
```

- [ ] **Step 2: `pnpm-workspace.yaml` 생성**

```yaml
packages:
  - 'apps/web'
```

- [ ] **Step 3: 루트 `package.json` 생성**

```json
{
  "name": "fontagit",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "engines": { "node": ">=20" },
  "scripts": {
    "web:dev": "pnpm --filter web dev",
    "web:build": "pnpm --filter web build"
  }
}
```

- [ ] **Step 4: `.env.example` 생성**

```
GOOGLE_FONTS_API_KEY=
```

- [ ] **Step 5: `Makefile` 생성**

```makefile
.PHONY: web-dev collect test lint

web-dev:
	pnpm --filter web dev

collect:
	cd apps/pipeline && uv run python -m fontagit_pipeline

test:
	cd apps/pipeline && uv run pytest

lint:
	cd apps/pipeline && uv run ruff check . && uv run mypy src
```

- [ ] **Step 6: `.gitignore`에 Node/env/output 추가**

기존 파일 끝에 append:
```
# Node
node_modules/
.next/
out/

# env & 파이프라인 산출물
.env
apps/pipeline/output/
```

- [ ] **Step 7: 커밋**

```bash
git add pnpm-workspace.yaml package.json Makefile .nvmrc .env.example .gitignore
git commit -m "chore: scaffold monorepo root (pnpm workspace, make, env)"
```

---

## Task 2: 파이프라인 프로젝트 초기화

**Files:**
- Create: `apps/pipeline/pyproject.toml`, `apps/pipeline/src/fontagit_pipeline/__init__.py`

**Interfaces:**
- Consumes: 루트 구조(Task 1)
- Produces: `uv run` 환경, `fontagit_pipeline` 임포트 가능 패키지, ruff/mypy/pytest 설정.

- [ ] **Step 1: `pyproject.toml` 생성**

```toml
[project]
name = "fontagit-pipeline"
version = "0.1.0"
description = "FontAgit Tier A 수집 파이프라인"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
]

[dependency-groups]
dev = [
    "pytest>=8.2",
    "ruff>=0.5",
    "mypy>=1.10",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fontagit_pipeline"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.mypy]
python_version = "3.12"
strict = true
mypy_path = "src"
```

- [ ] **Step 2: 패키지 `__init__.py` 생성**

파일 `apps/pipeline/src/fontagit_pipeline/__init__.py`:
```python
"""FontAgit Tier A 수집 파이프라인."""
```

- [ ] **Step 3: 의존성 동기화**

Run: `cd apps/pipeline && uv sync`
Expected: `uv.lock` 생성, 가상환경 구성 성공.

- [ ] **Step 4: 임포트 확인**

Run: `cd apps/pipeline && uv run python -c "import fontagit_pipeline; print('ok')"`
Expected: `ok` 출력.

- [ ] **Step 5: 커밋**

```bash
git add apps/pipeline/pyproject.toml apps/pipeline/uv.lock apps/pipeline/src/fontagit_pipeline/__init__.py
git commit -m "chore: init python pipeline project (uv, ruff, mypy, pytest)"
```

---

## Task 3: 데이터 모델

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/models.py`
- Test: `apps/pipeline/tests/test_models.py`

**Interfaces:**
- Consumes: pydantic(Task 2)
- Produces:
  - `GoogleFontRaw(family: str, variants: list[str], subsets: list[str], version: str, lastModified: str, files: dict[str, str], category: str, menu: str | None = None)`
  - `FontRecord(name_en: str, name_ko: str | None, tier: str="A", category: str, subsets: list[str], variants: list[str], official_url: str, license: str | None=None, license_verified: bool=False, aliases: list[str], version: str, last_modified: str)`
  - `OutputDocument(schema_version: int=1, generated_at: str, source: str="google-fonts-webfonts-api", record_count: int, fonts: list[FontRecord])`

- [ ] **Step 1: 실패 테스트 작성**

파일 `apps/pipeline/tests/test_models.py`:
```python
from fontagit_pipeline.models import FontRecord, GoogleFontRaw, OutputDocument


def test_google_font_raw_parses_api_shape():
    raw = GoogleFontRaw(
        family="Noto Sans KR",
        variants=["regular", "700"],
        subsets=["korean", "latin"],
        version="v36",
        lastModified="2024-09-01",
        files={"regular": "https://x/a.ttf"},
        category="sans-serif",
    )
    assert raw.family == "Noto Sans KR"
    assert raw.menu is None


def test_font_record_defaults_license_unverified():
    rec = FontRecord(
        name_en="Roboto",
        name_ko=None,
        category="sans-serif",
        subsets=["latin"],
        variants=["400"],
        official_url="https://fonts.google.com/specimen/Roboto",
        aliases=["Roboto"],
        version="v30",
        last_modified="2024-09-01",
    )
    assert rec.tier == "A"
    assert rec.license is None
    assert rec.license_verified is False


def test_output_document_wraps_records():
    doc = OutputDocument(generated_at="2026-07-12T10:00:00Z", record_count=0, fonts=[])
    assert doc.schema_version == 1
    assert doc.source == "google-fonts-webfonts-api"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: fontagit_pipeline.models`.

- [ ] **Step 3: `models.py` 구현**

파일 `apps/pipeline/src/fontagit_pipeline/models.py`:
```python
"""파이프라인 데이터 모델."""

from pydantic import BaseModel


class GoogleFontRaw(BaseModel):
    """구글폰트 webfonts API 응답 1개 항목의 원형."""

    family: str
    variants: list[str]
    subsets: list[str]
    version: str
    lastModified: str
    files: dict[str, str]
    category: str
    menu: str | None = None


class FontRecord(BaseModel):
    """공개용으로 정규화한 폰트 레코드(미래 fonts 테이블 미러)."""

    name_en: str
    name_ko: str | None = None
    tier: str = "A"
    category: str
    subsets: list[str]
    variants: list[str]
    official_url: str
    license: str | None = None
    license_verified: bool = False
    aliases: list[str]
    version: str
    last_modified: str


class OutputDocument(BaseModel):
    """tier-a.json 출력 계약(메타 + 레코드 배열)."""

    schema_version: int = 1
    generated_at: str
    source: str = "google-fonts-webfonts-api"
    record_count: int
    fonts: list[FontRecord]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_models.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/models.py apps/pipeline/tests/test_models.py
git commit -m "feat: add pipeline data models (raw, record, output document)"
```

---

## Task 4: 변환 헬퍼 (정규화-URL-별칭)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/transform.py`
- Test: `apps/pipeline/tests/test_transform.py`

**Interfaces:**
- Consumes: 없음(순수 함수)
- Produces:
  - `normalize_variants(variants: list[str]) -> list[str]`
  - `build_official_url(family: str) -> str` — 비ASCII family면 `ValueError`
  - `build_aliases(name_en: str, name_ko: str | None = None) -> list[str]`

- [ ] **Step 1: 실패 테스트 작성**

파일 `apps/pipeline/tests/test_transform.py`:
```python
import pytest

from fontagit_pipeline.transform import (
    build_aliases,
    build_official_url,
    normalize_variants,
)


def test_normalize_variants_maps_regular_and_italic():
    assert normalize_variants(["regular", "italic", "700", "700italic"]) == [
        "400",
        "400 italic",
        "700",
        "700 italic",
    ]


def test_build_official_url_replaces_spaces_with_plus():
    assert (
        build_official_url("Noto Sans KR")
        == "https://fonts.google.com/specimen/Noto+Sans+KR"
    )


def test_build_official_url_rejects_non_ascii():
    with pytest.raises(ValueError):
        build_official_url("나눔고딕")


def test_build_aliases_dedupes_case_insensitively_keeping_order():
    assert build_aliases("Noto Sans KR") == [
        "Noto Sans KR",
        "noto sans kr",
        "notosanskr",
        "noto sans kr ttf",
    ]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_transform.py -v`
Expected: FAIL — `ModuleNotFoundError` 또는 import 오류.

- [ ] **Step 3: 헬퍼 구현**

파일 `apps/pipeline/src/fontagit_pipeline/transform.py`:
```python
"""수집 데이터 필터-정규화-변환."""

_SPECIMEN_BASE = "https://fonts.google.com/specimen/"


def normalize_variants(variants: list[str]) -> list[str]:
    """구글 variants를 '숫자 weight' 또는 '숫자 italic' 형태로 정규화한다."""
    result: list[str] = []
    for v in variants:
        if v == "regular":
            result.append("400")
        elif v == "italic":
            result.append("400 italic")
        elif v.endswith("italic"):
            weight = v.removesuffix("italic")
            result.append(f"{weight} italic")
        else:
            result.append(v)
    return result


def build_official_url(family: str) -> str:
    """family의 공백만 '+'로 바꿔 공식 specimen URL을 만든다.

    비ASCII family는 구글 specimen 규칙에 맞지 않으므로 ValueError를 던진다.
    """
    if not family.isascii():
        raise ValueError(f"비ASCII family는 지원하지 않음: {family}")
    return f"{_SPECIMEN_BASE}{family.replace(' ', '+')}"


def build_aliases(name_en: str, name_ko: str | None = None) -> list[str]:
    """검색용 기본 별칭 목록을 만든다(소문자 기준 중복 제거, 순서 유지)."""
    candidates = [
        name_en,
        name_en.lower(),
        name_en.lower().replace(" ", ""),
        f"{name_en.lower()} ttf",
    ]
    if name_ko:
        candidates += [name_ko, name_ko.replace(" ", "")]
    seen: set[str] = set()
    result: list[str] = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_transform.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/transform.py apps/pipeline/tests/test_transform.py
git commit -m "feat: add transform helpers (variants, official url, aliases)"
```

---

## Task 5: 수집 로직 (필터-라틴 100-dedup-레코드)

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/transform.py`
- Modify: `apps/pipeline/tests/test_transform.py`
- Create: `apps/pipeline/tests/fixtures/webfonts_sample.json`

**Interfaces:**
- Consumes: Task 3 모델, Task 4 헬퍼
- Produces:
  - `filter_korean(fonts: list[GoogleFontRaw]) -> list[GoogleFontRaw]`
  - `select_latin_top(fonts: list[GoogleFontRaw], limit: int = 100) -> list[GoogleFontRaw]`
  - `merge_dedup(korean: list[GoogleFontRaw], latin: list[GoogleFontRaw]) -> list[GoogleFontRaw]`
  - `to_record(raw: GoogleFontRaw) -> FontRecord`
  - `build_records(fonts: list[GoogleFontRaw], latin_limit: int = 100) -> list[FontRecord]`

- [ ] **Step 1: 픽스처 생성**

파일 `apps/pipeline/tests/fixtures/webfonts_sample.json` (인기순 정렬 가정, 한글 1 + 라틴 3):
```json
{
  "items": [
    {"family": "Roboto", "variants": ["regular", "700"], "subsets": ["latin"], "version": "v30", "lastModified": "2024-09-01", "files": {"regular": "https://x/roboto.ttf"}, "category": "sans-serif"},
    {"family": "Noto Sans KR", "variants": ["regular", "700"], "subsets": ["korean", "latin"], "version": "v36", "lastModified": "2024-09-01", "files": {"regular": "https://x/notokr.ttf"}, "category": "sans-serif"},
    {"family": "Open Sans", "variants": ["regular"], "subsets": ["latin"], "version": "v40", "lastModified": "2024-09-01", "files": {"regular": "https://x/opensans.ttf"}, "category": "sans-serif"},
    {"family": "Lato", "variants": ["regular"], "subsets": ["latin"], "version": "v24", "lastModified": "2024-09-01", "files": {"regular": "https://x/lato.ttf"}, "category": "sans-serif"}
  ]
}
```

- [ ] **Step 2: 실패 테스트 추가**

`apps/pipeline/tests/test_transform.py` 상단 import에 추가:
```python
import json
from pathlib import Path

from fontagit_pipeline.models import GoogleFontRaw
from fontagit_pipeline.transform import (
    build_records,
    filter_korean,
    merge_dedup,
    select_latin_top,
    to_record,
)

FIXTURE = Path(__file__).parent / "fixtures" / "webfonts_sample.json"


def _load_raw() -> list[GoogleFontRaw]:
    items = json.loads(FIXTURE.read_text())["items"]
    return [GoogleFontRaw(**it) for it in items]
```

파일 끝에 테스트 추가:
```python
def test_filter_korean_keeps_only_korean_subset():
    fonts = _load_raw()
    korean = filter_korean(fonts)
    assert [f.family for f in korean] == ["Noto Sans KR"]


def test_select_latin_top_respects_limit_and_order():
    fonts = _load_raw()
    top2 = select_latin_top(fonts, limit=2)
    assert [f.family for f in top2] == ["Roboto", "Noto Sans KR"]


def test_merge_dedup_unions_by_family_korean_first():
    fonts = _load_raw()
    korean = filter_korean(fonts)
    latin = select_latin_top(fonts, limit=2)
    merged = merge_dedup(korean, latin)
    assert [f.family for f in merged] == ["Noto Sans KR", "Roboto"]


def test_to_record_sets_null_license_and_specimen_url():
    raw = _load_raw()[0]
    rec = to_record(raw)
    assert rec.license is None
    assert rec.license_verified is False
    assert rec.official_url == "https://fonts.google.com/specimen/Roboto"
    assert rec.variants == ["400", "700"]


def test_build_records_full_pipeline_no_duplicates():
    fonts = _load_raw()
    records = build_records(fonts, latin_limit=2)
    families = [r.name_en for r in records]
    assert families == ["Noto Sans KR", "Roboto"]
    assert len(families) == len(set(families))
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_transform.py -v`
Expected: FAIL — 새 함수 import 오류.

- [ ] **Step 4: 수집 로직 구현**

`apps/pipeline/src/fontagit_pipeline/transform.py` 상단에 import 추가:
```python
import logging

from fontagit_pipeline.models import FontRecord, GoogleFontRaw

logger = logging.getLogger(__name__)
```

파일 끝에 함수 추가:
```python
def filter_korean(fonts: list[GoogleFontRaw]) -> list[GoogleFontRaw]:
    """subsets에 'korean'이 있는 폰트만 순서 유지하며 고른다."""
    return [f for f in fonts if "korean" in f.subsets]


def select_latin_top(fonts: list[GoogleFontRaw], limit: int = 100) -> list[GoogleFontRaw]:
    """인기순으로 전달된 목록에서 latin 포함 폰트를 위에서부터 limit개 고른다."""
    latin = [f for f in fonts if "latin" in f.subsets]
    return latin[:limit]


def merge_dedup(
    korean: list[GoogleFontRaw], latin: list[GoogleFontRaw]
) -> list[GoogleFontRaw]:
    """family 키로 합집합. 한글 집합 먼저, 라틴에서 새로운 것만 뒤에 붙인다."""
    seen: set[str] = {f.family for f in korean}
    merged = list(korean)
    for f in latin:
        if f.family not in seen:
            seen.add(f.family)
            merged.append(f)
    return merged


def to_record(raw: GoogleFontRaw) -> FontRecord:
    """원형을 공개용 FontRecord로 변환한다. 라이선스는 검증 전 null."""
    return FontRecord(
        name_en=raw.family,
        name_ko=None,
        tier="A",
        category=raw.category,
        subsets=raw.subsets,
        variants=normalize_variants(raw.variants),
        official_url=build_official_url(raw.family),
        license=None,
        license_verified=False,
        aliases=build_aliases(raw.family),
        version=raw.version,
        last_modified=raw.lastModified,
    )


def build_records(
    fonts: list[GoogleFontRaw], latin_limit: int = 100
) -> list[FontRecord]:
    """전체 수집 알고리즘: 한글 전체 + 라틴 top N 합집합을 레코드로 변환한다.

    비ASCII family 등 변환 불가 폰트는 로그를 남기고 건너뛴다.
    """
    merged = merge_dedup(filter_korean(fonts), select_latin_top(fonts, latin_limit))
    records: list[FontRecord] = []
    for raw in merged:
        try:
            records.append(to_record(raw))
        except ValueError as exc:
            logger.warning("레코드 변환 건너뜀 (%s): %s", raw.family, exc)
    return records
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_transform.py -v`
Expected: PASS (전체 통과).

- [ ] **Step 6: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/transform.py apps/pipeline/tests/test_transform.py apps/pipeline/tests/fixtures/webfonts_sample.json
git commit -m "feat: add collection logic (filter, latin top, dedup, records)"
```

---

## Task 6: API 클라이언트 (타임아웃-재시도-키 마스킹)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/client.py`
- Test: `apps/pipeline/tests/test_client.py`

**Interfaces:**
- Consumes: Task 3 모델, httpx
- Produces:
  - `mask_key(url: str) -> str`
  - `fetch_webfonts(api_key: str, *, client: httpx.Client | None = None, sort: str = "popularity", timeout: float = 10.0, retries: int = 2) -> list[GoogleFontRaw]`

- [ ] **Step 1: 실패 테스트 작성**

파일 `apps/pipeline/tests/test_client.py`:
```python
import httpx
import pytest

from fontagit_pipeline.client import fetch_webfonts, mask_key


def test_mask_key_hides_api_key():
    url = "https://www.googleapis.com/webfonts/v1/webfonts?key=SECRET123&sort=popularity"
    assert "SECRET123" not in mask_key(url)
    assert "key=***" in mask_key(url)


def test_fetch_webfonts_parses_items():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "family": "Roboto",
                        "variants": ["regular"],
                        "subsets": ["latin"],
                        "version": "v30",
                        "lastModified": "2024-09-01",
                        "files": {"regular": "https://x/r.ttf"},
                        "category": "sans-serif",
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    fonts = fetch_webfonts("SECRET123", client=client)
    assert [f.family for f in fonts] == ["Roboto"]


def test_fetch_webfonts_raises_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_webfonts("SECRET123", client=client, retries=0)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: fontagit_pipeline.client`.

- [ ] **Step 3: 클라이언트 구현**

파일 `apps/pipeline/src/fontagit_pipeline/client.py`:
```python
"""구글폰트 webfonts API 클라이언트."""

import logging
import re

import httpx

from fontagit_pipeline.models import GoogleFontRaw

logger = logging.getLogger(__name__)

_API_URL = "https://www.googleapis.com/webfonts/v1/webfonts"
_KEY_RE = re.compile(r"key=[^&]+")


def mask_key(url: str) -> str:
    """URL 안의 API 키를 마스킹한다(로그 노출 방지)."""
    return _KEY_RE.sub("key=***", url)


def fetch_webfonts(
    api_key: str,
    *,
    client: httpx.Client | None = None,
    sort: str = "popularity",
    timeout: float = 10.0,
    retries: int = 2,
) -> list[GoogleFontRaw]:
    """webfonts API를 조회해 원형 목록을 반환한다.

    타임아웃/HTTP 오류는 제한 재시도 후 예외를 전파한다. 로그에는 키를 마스킹한다.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=timeout)
    params = {"key": api_key, "sort": sort}
    try:
        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = client.get(_API_URL, params=params)
                logger.info("webfonts 요청 %s", mask_key(str(resp.request.url)))
                resp.raise_for_status()
                items = resp.json().get("items", [])
                return [GoogleFontRaw(**it) for it in items]
            except (httpx.HTTPError, ValueError) as exc:
                last_exc = exc
                logger.warning("요청 실패(시도 %d/%d): %s", attempt + 1, retries + 1, exc)
        assert last_exc is not None
        raise last_exc
    finally:
        if owns_client:
            client.close()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_client.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/client.py apps/pipeline/tests/test_client.py
git commit -m "feat: add webfonts api client with retry and key masking"
```

---

## Task 7: 원자적 JSON 저장

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/writer.py`
- Test: `apps/pipeline/tests/test_writer.py`

**Interfaces:**
- Consumes: Task 3 `OutputDocument`
- Produces: `write_output(doc: OutputDocument, path: Path) -> None`

- [ ] **Step 1: 실패 테스트 작성**

파일 `apps/pipeline/tests/test_writer.py`:
```python
import json
from pathlib import Path

from fontagit_pipeline.models import OutputDocument
from fontagit_pipeline.writer import write_output


def test_write_output_creates_valid_json(tmp_path: Path):
    doc = OutputDocument(generated_at="2026-07-12T10:00:00Z", record_count=0, fonts=[])
    out = tmp_path / "sub" / "tier-a.json"
    write_output(doc, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == 1
    assert loaded["source"] == "google-fonts-webfonts-api"
    assert loaded["fonts"] == []


def test_write_output_leaves_no_temp_file(tmp_path: Path):
    doc = OutputDocument(generated_at="2026-07-12T10:00:00Z", record_count=0, fonts=[])
    out = tmp_path / "tier-a.json"
    write_output(doc, out)
    assert list(tmp_path.iterdir()) == [out]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: fontagit_pipeline.writer`.

- [ ] **Step 3: writer 구현**

파일 `apps/pipeline/src/fontagit_pipeline/writer.py`:
```python
"""출력 JSON 원자적 저장."""

import os
import tempfile
from pathlib import Path

from fontagit_pipeline.models import OutputDocument


def write_output(doc: OutputDocument, path: Path) -> None:
    """임시 파일에 쓴 뒤 성공 시 목적지로 교체(원자적)한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = doc.model_dump_json(indent=2)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_writer.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/writer.py apps/pipeline/tests/test_writer.py
git commit -m "feat: add atomic json writer"
```

---

## Task 8: 설정 + 오케스트레이션 진입점

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/config.py`, `apps/pipeline/src/fontagit_pipeline/__main__.py`
- Test: `apps/pipeline/tests/test_main.py`

**Interfaces:**
- Consumes: Task 3~7 전부
- Produces:
  - `Settings(google_fonts_api_key: str)`, `load_settings() -> Settings`
  - `build_document(fonts: list[GoogleFontRaw], generated_at: str, latin_limit: int = 100) -> OutputDocument`
  - `main() -> int` (종료 코드 반환)

- [ ] **Step 1: `config.py` 구현**

파일 `apps/pipeline/src/fontagit_pipeline/config.py`:
```python
"""환경 설정 로드."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """.env 기반 파이프라인 설정."""

    google_fonts_api_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def load_settings() -> Settings:
    """설정을 로드한다. 키가 없으면 pydantic ValidationError."""
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 2: 실패 테스트 작성**

파일 `apps/pipeline/tests/test_main.py`:
```python
import json
from pathlib import Path

from fontagit_pipeline.__main__ import build_document
from fontagit_pipeline.models import GoogleFontRaw

RAW = GoogleFontRaw(
    family="Noto Sans KR",
    variants=["regular"],
    subsets=["korean", "latin"],
    version="v36",
    lastModified="2024-09-01",
    files={"regular": "https://x/n.ttf"},
    category="sans-serif",
)


def test_build_document_sets_count_and_meta():
    doc = build_document([RAW], generated_at="2026-07-12T10:00:00Z")
    assert doc.record_count == 1
    assert doc.fonts[0].name_en == "Noto Sans KR"
    assert doc.fonts[0].license is None


def test_build_document_serialises_with_wrapper(tmp_path: Path):
    from fontagit_pipeline.writer import write_output

    doc = build_document([RAW], generated_at="2026-07-12T10:00:00Z")
    out = tmp_path / "tier-a.json"
    write_output(doc, out)
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["record_count"] == 1
    assert loaded["fonts"][0]["license_verified"] is False
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_main.py -v`
Expected: FAIL — `__main__.build_document` 없음.

- [ ] **Step 4: `__main__.py` 구현**

파일 `apps/pipeline/src/fontagit_pipeline/__main__.py`:
```python
"""파이프라인 진입점: 조회 → 변환 → 저장."""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from pydantic import ValidationError

from fontagit_pipeline.client import fetch_webfonts
from fontagit_pipeline.config import load_settings
from fontagit_pipeline.models import GoogleFontRaw, OutputDocument
from fontagit_pipeline.transform import build_records
from fontagit_pipeline.writer import write_output

logger = logging.getLogger(__name__)
_OUTPUT_PATH = Path("output") / "tier-a.json"
_SOURCE = "google-fonts-webfonts-api"


def build_document(
    fonts: list[GoogleFontRaw], generated_at: str, latin_limit: int = 100
) -> OutputDocument:
    """원형 목록을 메타 래퍼가 있는 OutputDocument로 변환한다."""
    records = build_records(fonts, latin_limit)
    return OutputDocument(
        generated_at=generated_at,
        source=_SOURCE,
        record_count=len(records),
        fonts=records,
    )


def main() -> int:
    """수집 실행. 성공 0, 설정 오류 2, 네트워크 오류 3."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        settings = load_settings()
    except ValidationError:
        logger.error("GOOGLE_FONTS_API_KEY가 없습니다. apps/pipeline/.env를 확인하세요.")
        return 2

    try:
        fonts = fetch_webfonts(settings.google_fonts_api_key)
    except httpx.HTTPError as exc:
        logger.error("webfonts 조회 실패: %s", exc)
        return 3

    generated_at = datetime.now(timezone.utc).isoformat()
    doc = build_document(fonts, generated_at)
    write_output(doc, _OUTPUT_PATH)
    logger.info("저장 완료: %s (%d개)", _OUTPUT_PATH, doc.record_count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_main.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: 전체 검증 (테스트 + lint + 타입)**

Run: `cd apps/pipeline && uv run pytest && uv run ruff check . && uv run mypy src`
Expected: 테스트 전체 PASS, ruff/mypy 오류 0.

- [ ] **Step 7: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/config.py apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/tests/test_main.py
git commit -m "feat: add settings and pipeline entrypoint with exit codes"
```

---

## Task 9: 웹 스캐폴드 (Next.js + 테마 + Pretendard)

**Files:**
- Create: `apps/web/*` (create-next-app 생성물)
- Modify: `apps/web/app/globals.css`, `apps/web/tailwind.config.ts`, `apps/web/app/layout.tsx`, `apps/web/app/page.tsx`

**Interfaces:**
- Consumes: 루트 pnpm workspace(Task 1)
- Produces: 빌드되는 홈 뼈대. 딥 그린 테마 토큰 + 다크모드 + Pretendard self-host.

- [ ] **Step 1: Next.js 앱 생성**

Run:
```bash
pnpm create next-app@latest apps/web --ts --tailwind --app --eslint --no-src-dir --import-alias "@/*" --use-pnpm
```
Expected: `apps/web`에 Next.js 15 프로젝트 생성.

- [ ] **Step 2: Pretendard 패키지 추가**

Run: `pnpm --filter web add pretendard`
Expected: `apps/web/package.json`에 `pretendard` 의존성 추가.

- [ ] **Step 3: 딥 그린 테마 토큰 설정**

`apps/web/tailwind.config.ts`의 `theme.extend`에 색 추가:
```ts
extend: {
  colors: {
    brand: { DEFAULT: "#2C5545" },
  },
},
```
그리고 파일 상단 config에 `darkMode: "class",` 추가.

- [ ] **Step 4: Pretendard + CSS 변수 적용**

`apps/web/app/globals.css` 상단에 추가:
```css
@import "pretendard/dist/web/static/pretendard.css";

:root {
  --brand: #2c5545;
}

body {
  font-family: Pretendard, system-ui, sans-serif;
}
```

- [ ] **Step 5: 홈 뼈대 작성**

`apps/web/app/page.tsx` 전체 교체:
```tsx
export default function Home() {
  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-3xl font-bold text-brand">FontAgit</h1>
      <p className="mt-2 text-neutral-600 dark:text-neutral-300">
        당신의 폰트 아지트 (초기 뼈대)
      </p>
    </main>
  );
}
```

- [ ] **Step 6: 빌드 검증**

Run: `pnpm --filter web build`
Expected: 빌드 성공(오류 0). `apps/web/.next` 생성.

- [ ] **Step 7: 커밋**

```bash
git add apps/web pnpm-lock.yaml
git commit -m "feat: scaffold next.js web with brand theme and pretendard"
```

---

## Self-Review 결과

- **Spec coverage:** 스펙 3장 파일구조 → Task 1-2-9. 4-1 모듈 → Task 3-6-7-8. 4-2 수집 알고리즘 → Task 5. 4-3 정규화/URL/별칭/라이선스 → Task 4-5. 4-4 출력 계약 → Task 3-7-8. 5장 web → Task 9. 6장 툴링/버전 → Task 1-2. 7장 검증 → 각 태스크 테스트 + Task 8 Step 6. 8장 리스크(키 마스킹-재시도-원자적 저장-조건 검증) → Task 6-7. 통합(실키) 검증은 스펙대로 수동(키 확보 후 `make collect`).
- **Placeholder scan:** 모든 코드 스텝에 실제 코드 포함, TBD/TODO 없음.
- **Type consistency:** `GoogleFontRaw`/`FontRecord`/`OutputDocument` 필드와 `build_records`/`fetch_webfonts`/`write_output`/`build_document` 시그니처가 태스크 간 일치. `mask_key`, `build_official_url`(ValueError) 등 이름 일관.
- **알려진 한계:** 실제 API 키 없이는 Task 8 Step 6까지만 그린. 통합 실행(`make collect`)은 키 확보 후. mypy strict에서 `Settings()` 호출은 `# type: ignore[call-arg]`로 처리(pydantic-settings 런타임 로드 특성).
