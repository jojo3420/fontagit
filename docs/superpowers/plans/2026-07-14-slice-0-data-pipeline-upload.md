# Slice 0: 데이터 기반 + 파이프라인 업로드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 구글폰트 Tier A 수집 결과를 라이선스 판별 후 Supabase `fontagit` 스키마에 멱등 업로드하고, OFL/Apache/UFL 폰트를 published로 공개한다.

**Architecture:** 기존 파이프라인(수집→변환→JSON 저장)에 두 단계를 잇는다 — (1) google/fonts 저장소 트리로 라이선스 종류를 판별해 공개 여부 결정, (2) supabase-py(secret key)로 `fonts`+`aliases`를 upsert. DB 스키마는 SQL 마이그레이션으로 선(先)적용한다.

**Tech Stack:** Python 3.12, uv, pydantic v2, pydantic-settings, httpx, supabase-py, pytest, ruff, mypy(strict). Supabase(Postgres) `fontagit` 스키마.

## Global Constraints

- Python 3.12, 타입 힌트 100%, Docstring 한국어. `print` 금지 → `logging`.
- 하드코딩 금지, `ruff`/`mypy --strict`/`pytest` 통과.
- Supabase는 ollidam과 공유 인스턴스 → 모든 객체는 `fontagit` 스키마. `public` 접근 금지.
- 라이선스 정직성: `license_type`은 `license_verified=true`일 때만 설정. OFL/Apache-2.0/UFL만 자동 `published`, 그 외 `draft`.
- secret key(`SUPABASE_SECRET_KEY`)는 서버 전용 — 로그-커밋-응답 노출 금지.
- `.env`는 `apps/pipeline/.env` 기준 경로 로드(기존 config 규칙 유지).
- 명령은 `apps/pipeline`에서 `uv run` 기준.

---

### Task 1: Supabase `fontagit` 스키마 마이그레이션

**Files:**
- Create: `supabase/migrations/0001_fontagit_schema.sql`

**Interfaces:**
- Produces: `fontagit.fonts`, `fontagit.aliases`, `fontagit.collections`, `fontagit.collection_items` 테이블 + RLS. 컬럼은 스펙 3절과 동일.

- [ ] **Step 1: 마이그레이션 SQL 작성**

`supabase/migrations/0001_fontagit_schema.sql`:

```sql
create schema if not exists fontagit;
grant usage on schema fontagit to anon, authenticated, service_role;

create table fontagit.fonts (
  id                 uuid primary key default gen_random_uuid(),
  slug               text not null unique,
  name_en            text not null,
  name_ko            text,
  foundry            text,
  source_tier        text not null default 'A',
  category_ko        text not null,
  category_google    text,
  subsets            text[] not null default '{}',
  variants           text[] not null default '{}',
  weights            int[]  not null default '{}',
  is_commercial_free boolean not null default false,
  license_type       text,
  license_verified   boolean not null default false,
  official_url       text not null,
  status             text not null default 'draft',
  version            text,
  last_modified      text,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  constraint fonts_status_chk check (status in ('draft','published','archived')),
  constraint fonts_tier_chk   check (source_tier in ('A','B','C')),
  constraint fonts_cat_chk    check (category_ko in ('고딕','명조','손글씨','장식')),
  constraint fonts_license_verify_chk check (license_type is null or license_verified = true)
);
create index idx_fonts_status on fontagit.fonts(status);

create table fontagit.aliases (
  id         uuid primary key default gen_random_uuid(),
  font_id    uuid not null references fontagit.fonts(id) on delete cascade,
  alias      text not null,
  alias_norm text not null,
  unique (font_id, alias_norm)
);
create index idx_aliases_font on fontagit.aliases(font_id);

create table fontagit.collections (
  id         uuid primary key default gen_random_uuid(),
  slug       text not null unique,
  title      text not null,
  intro      text not null,
  status     text not null default 'draft' check (status in ('draft','published','archived')),
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);
create table fontagit.collection_items (
  collection_id uuid not null references fontagit.collections(id) on delete cascade,
  font_id       uuid not null references fontagit.fonts(id) on delete cascade,
  comment       text,
  sort_order    int not null default 0,
  primary key (collection_id, font_id)
);

grant select on all tables in schema fontagit to anon, authenticated;

alter table fontagit.fonts enable row level security;
alter table fontagit.aliases enable row level security;
alter table fontagit.collections enable row level security;
alter table fontagit.collection_items enable row level security;

create policy anon_read_published_fonts on fontagit.fonts
  for select to anon using (status = 'published');
create policy anon_read_aliases on fontagit.aliases
  for select to anon using (exists (
    select 1 from fontagit.fonts f where f.id = font_id and f.status = 'published'));
create policy anon_read_published_collections on fontagit.collections
  for select to anon using (status = 'published');
create policy anon_read_collection_items on fontagit.collection_items
  for select to anon using (exists (
    select 1 from fontagit.collections c where c.id = collection_id and c.status = 'published'));
```

- [ ] **Step 2: psql로 적용**

Run (DB 비번은 `apps/pipeline/.env`의 `SUPABASE_DB_PASSWORD`, 호스트/유저는 Supabase 대시보드 Connection string 참조):
```bash
psql "$SUPABASE_DB_URL" -f supabase/migrations/0001_fontagit_schema.sql
```
Expected: `CREATE SCHEMA` … `CREATE POLICY` 에러 없이 완료.

- [ ] **Step 3: 적용 확인**

Run:
```bash
psql "$SUPABASE_DB_URL" -c "\dt fontagit.*"
```
Expected: `fonts`, `aliases`, `collections`, `collection_items` 4개 표시.

- [ ] **Step 4: 대시보드 노출 스키마 설정**

Supabase 대시보드 → Settings → API → Exposed schemas에 `fontagit` 추가. (수동, PostgREST 접근용. Plan B 웹 fetch 전제.)

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/0001_fontagit_schema.sql
git commit -m "feat(db): fontagit 스키마 마이그레이션(fonts/aliases/collections + RLS)"
```

---

### Task 2: 파이프라인 의존성 + Supabase 설정

**Files:**
- Modify: `apps/pipeline/pyproject.toml`
- Modify: `apps/pipeline/src/fontagit_pipeline/config.py`
- Test: `apps/pipeline/tests/test_config.py`

**Interfaces:**
- Produces: `Settings.supabase_url: str | None`, `Settings.supabase_secret_key: str | None`, `Settings.github_token: str | None`. `load_settings()` 시그니처 불변.

- [ ] **Step 1: supabase 의존성 추가**

`apps/pipeline/pyproject.toml`의 `dependencies`에 추가:
```toml
dependencies = [
    "httpx>=0.27",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "supabase>=2.7",
]
```
Run: `cd apps/pipeline && uv sync`
Expected: `supabase` 설치, `uv.lock` 갱신.

- [ ] **Step 2: 실패 테스트 작성**

`apps/pipeline/tests/test_config.py`에 추가:
```python
def test_settings_optional_supabase(monkeypatch):
    monkeypatch.setenv("GOOGLE_FONTS_API_KEY", "k")
    monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "sb_secret_xxx")
    from fontagit_pipeline.config import load_settings
    s = load_settings()
    assert s.supabase_url == "https://x.supabase.co"
    assert s.supabase_secret_key == "sb_secret_xxx"

def test_settings_supabase_absent_ok(monkeypatch):
    monkeypatch.setenv("GOOGLE_FONTS_API_KEY", "k")
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SECRET_KEY", raising=False)
    from fontagit_pipeline.config import load_settings
    s = load_settings()
    assert s.supabase_url is None
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'supabase_url'`.

- [ ] **Step 4: config 구현**

`config.py`의 `Settings`에 필드 추가(기존 `google_fonts_api_key`-validator 유지):
```python
    supabase_url: str | None = None
    supabase_secret_key: str | None = None
    github_token: str | None = None
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/pipeline/pyproject.toml apps/pipeline/uv.lock apps/pipeline/src/fontagit_pipeline/config.py apps/pipeline/tests/test_config.py
git commit -m "feat(pipeline): supabase 의존성 + Supabase/GitHub 설정 필드 추가"
```

---

### Task 3: FontRecord 필드 확장

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/models.py:19-42`
- Test: `apps/pipeline/tests/test_models.py`

**Interfaces:**
- Consumes: 기존 `FontRecord`(name_en, tier, category, subsets, variants, official_url, license, license_verified, aliases, version, last_modified).
- Produces: `FontRecord`에 필드 추가 — `slug: str`, `source_tier: str = "A"`, `category_ko: str`, `category_google: str`, `weights: list[int]`, `is_commercial_free: bool = False`, `license_type: str | None = None`, `status: str = "draft"`. 기존 `tier` 필드는 제거(→ `source_tier`로 대체), `category`는 `category_google`로 개명.

- [ ] **Step 1: 실패 테스트 작성**

`apps/pipeline/tests/test_models.py`에 추가:
```python
def test_font_record_new_fields():
    from fontagit_pipeline.models import FontRecord
    r = FontRecord(
        slug="noto-sans-kr", name_en="Noto Sans KR", category_ko="고딕",
        category_google="sans-serif", subsets=["korean"], variants=["400"],
        weights=[400], official_url="https://x", aliases=["Noto Sans KR"],
        version="v1", last_modified="2024-01-01",
        is_commercial_free=True, license_type="OFL", license_verified=True,
        status="published",
    )
    assert r.slug == "noto-sans-kr"
    assert r.source_tier == "A"
    assert r.status == "published"

def test_font_record_license_requires_verified():
    import pytest
    from pydantic import ValidationError
    from fontagit_pipeline.models import FontRecord
    with pytest.raises(ValidationError):
        FontRecord(
            slug="x", name_en="X", category_ko="고딕", category_google="serif",
            subsets=[], variants=[], weights=[], official_url="u", aliases=[],
            version="v", last_modified="d",
            license_type="OFL", license_verified=False,  # 위반
        )
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_models.py -v`
Expected: FAIL — 필드 미정의.

- [ ] **Step 3: models 구현**

`models.py`의 `FontRecord`를 교체(기존 `validate_license_requires_verification` validator 유지, 대상 필드명 그대로):
```python
class FontRecord(BaseModel):
    """처리된 폰트 레코드."""

    slug: str
    name_en: str
    name_ko: str | None = None
    source_tier: str = "A"
    category_ko: str
    category_google: str
    subsets: list[str]
    variants: list[str]
    weights: list[int]
    official_url: str
    is_commercial_free: bool = False
    license: str | None = None
    license_type: str | None = None
    license_verified: bool = False
    status: str = "draft"
    aliases: list[str]
    version: str
    last_modified: str

    @model_validator(mode="after")
    def validate_license_requires_verification(self) -> "FontRecord":
        """license/license_type은 verified가 True일 때만 설정 가능하다."""
        if (self.license is not None or self.license_type is not None) and not self.license_verified:
            raise ValueError("라이선스는 license_verified=True일 때만 설정할 수 있습니다")
        return self
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_models.py -v`
Expected: PASS. (기존 to_record 호출부는 Task 6에서 갱신 — 이 시점 test_transform 실패는 정상, Task 6에서 해소.)

- [ ] **Step 5: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/models.py apps/pipeline/tests/test_models.py
git commit -m "feat(pipeline): FontRecord에 slug/category_ko/weights/status 등 확장"
```

---

### Task 4: transform 헬퍼 3종 (category_ko / slug / weights)

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/transform.py`
- Test: `apps/pipeline/tests/test_transform.py`

**Interfaces:**
- Produces:
  - `map_category_ko(google_category: str) -> str` — 고딕/명조/손글씨/장식 중 하나
  - `build_slug(name_en: str) -> str` — 소문자, 공백/특수문자 하이픈, ASCII
  - `extract_weights(variants: list[str]) -> list[int]` — 정규화 variants에서 숫자 weight만(중복 제거, 오름차순)

- [ ] **Step 1: 실패 테스트 작성**

`apps/pipeline/tests/test_transform.py`에 추가:
```python
from fontagit_pipeline.transform import map_category_ko, build_slug, extract_weights

def test_map_category_ko():
    assert map_category_ko("sans-serif") == "고딕"
    assert map_category_ko("serif") == "명조"
    assert map_category_ko("handwriting") == "손글씨"
    assert map_category_ko("display") == "장식"
    assert map_category_ko("monospace") == "고딕"

def test_build_slug():
    assert build_slug("Noto Sans KR") == "noto-sans-kr"
    assert build_slug("IBM Plex Sans") == "ibm-plex-sans"

def test_extract_weights():
    assert extract_weights(["400", "400 italic", "700"]) == [400, 700]
    assert extract_weights(["300", "300 italic", "100"]) == [100, 300]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_transform.py -k "category_ko or build_slug or extract_weights" -v`
Expected: FAIL — 함수 미정의.

- [ ] **Step 3: 구현**

`transform.py`에 추가:
```python
import re

_CATEGORY_KO_MAP = {
    "sans-serif": "고딕",
    "serif": "명조",
    "handwriting": "손글씨",
    "display": "장식",
    "monospace": "고딕",
}


def map_category_ko(google_category: str) -> str:
    """구글 카테고리를 한글 4분류로 매핑한다(미지정은 고딕)."""
    return _CATEGORY_KO_MAP.get(google_category, "고딕")


def build_slug(name_en: str) -> str:
    """영문명을 URL 슬러그로 변환한다(소문자, 비영숫자 하이픈, 양끝 정리)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name_en.lower()).strip("-")
    return slug


def extract_weights(variants: list[str]) -> list[int]:
    """정규화 variants에서 숫자 weight만 추출한다(중복 제거, 오름차순)."""
    weights: set[int] = set()
    for v in variants:
        head = v.split(" ")[0]
        if head.isdigit():
            weights.add(int(head))
    return sorted(weights)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_transform.py -k "category_ko or build_slug or extract_weights" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/transform.py apps/pipeline/tests/test_transform.py
git commit -m "feat(pipeline): category_ko/slug/weights 변환 헬퍼 추가"
```

---

### Task 5: 라이선스 판별 (`licenses.py`)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/licenses.py`
- Create: `apps/pipeline/tests/fixtures/gh_tree_ofl.json`
- Test: `apps/pipeline/tests/test_licenses.py`

**Interfaces:**
- Produces:
  - `normalize_family_dir(name_en: str) -> str` — 소문자+비영숫자 제거(google/fonts 디렉토리명 규칙)
  - `parse_license_map(trees: dict[str, list[dict]]) -> dict[str, str]` — {"ofl":[{path}], "apache":[...], "ufl":[...]} → {dir_name: license_type}
  - `resolve_license_type(name_en: str, license_map: dict[str, str]) -> str | None`
  - `fetch_license_map(github_token: str | None) -> dict[str, str]` — google/fonts 트리 조회(네트워크)
- license_type 값: `"OFL"` | `"Apache-2.0"` | `"UFL"`.

- [ ] **Step 1: 픽스처 작성**

`apps/pipeline/tests/fixtures/gh_tree_ofl.json`:
```json
{"tree": [
  {"path": "notosanskr", "type": "tree"},
  {"path": "jua", "type": "tree"},
  {"path": "OFL.txt", "type": "blob"}
]}
```

- [ ] **Step 2: 실패 테스트 작성**

`apps/pipeline/tests/test_licenses.py`:
```python
from fontagit_pipeline.licenses import (
    normalize_family_dir, parse_license_map, resolve_license_type,
)

def test_normalize_family_dir():
    assert normalize_family_dir("Noto Sans KR") == "notosanskr"
    assert normalize_family_dir("IBM Plex Sans") == "ibmplexsans"

def test_parse_license_map():
    trees = {
        "ofl": [{"path": "notosanskr", "type": "tree"}, {"path": "OFL.txt", "type": "blob"}],
        "apache": [{"path": "roboto", "type": "tree"}],
        "ufl": [{"path": "ubuntu", "type": "tree"}],
    }
    m = parse_license_map(trees)
    assert m["notosanskr"] == "OFL"
    assert m["roboto"] == "Apache-2.0"
    assert m["ubuntu"] == "UFL"
    assert "OFL.txt" not in m  # blob 제외

def test_resolve_license_type():
    m = {"notosanskr": "OFL"}
    assert resolve_license_type("Noto Sans KR", m) == "OFL"
    assert resolve_license_type("Unknown Font", m) is None
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_licenses.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 4: 구현**

`apps/pipeline/src/fontagit_pipeline/licenses.py`:
```python
"""google/fonts 저장소 기반 라이선스 판별."""

import logging
import re

import httpx

logger = logging.getLogger(__name__)

_GH_API = "https://api.github.com"
_LICENSE_DIRS = {"ofl": "OFL", "apache": "Apache-2.0", "ufl": "UFL"}
_TIMEOUT = httpx.Timeout(10.0, connect=10.0)


def normalize_family_dir(name_en: str) -> str:
    """영문명을 google/fonts 디렉토리명 규칙(소문자, 영숫자만)으로 정규화한다."""
    return re.sub(r"[^a-z0-9]", "", name_en.lower())


def parse_license_map(trees: dict[str, list[dict]]) -> dict[str, str]:
    """라이선스별 트리 항목을 {디렉토리명: license_type}으로 병합한다(tree 타입만)."""
    result: dict[str, str] = {}
    for dir_key, license_type in _LICENSE_DIRS.items():
        for entry in trees.get(dir_key, []):
            if entry.get("type") == "tree":
                result[entry["path"]] = license_type
    return result


def resolve_license_type(name_en: str, license_map: dict[str, str]) -> str | None:
    """영문명으로 라이선스 종류를 찾는다(없으면 None)."""
    return license_map.get(normalize_family_dir(name_en))


def _get_tree_sha(client: httpx.Client, headers: dict[str, str]) -> dict[str, str]:
    """루트 트리에서 ofl/apache/ufl 디렉토리의 sha를 얻는다."""
    r = client.get(f"{_GH_API}/repos/google/fonts/git/trees/main", headers=headers)
    r.raise_for_status()
    shas: dict[str, str] = {}
    for entry in r.json()["tree"]:
        if entry["path"] in _LICENSE_DIRS and entry["type"] == "tree":
            shas[entry["path"]] = entry["sha"]
    return shas


def fetch_license_map(github_token: str | None = None) -> dict[str, str]:
    """google/fonts에서 라이선스 매핑을 조회한다. 실패 시 빈 dict(전부 draft)."""
    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    trees: dict[str, list[dict]] = {}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            shas = _get_tree_sha(client, headers)
            for dir_key, sha in shas.items():
                r = client.get(
                    f"{_GH_API}/repos/google/fonts/git/trees/{sha}", headers=headers
                )
                r.raise_for_status()
                trees[dir_key] = r.json()["tree"]
    except httpx.HTTPError as exc:
        logger.warning("라이선스 매핑 조회 실패, 전부 draft 처리: %s", exc.__class__.__name__)
        return {}
    return parse_license_map(trees)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_licenses.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/licenses.py apps/pipeline/tests/test_licenses.py apps/pipeline/tests/fixtures/gh_tree_ofl.json
git commit -m "feat(pipeline): google/fonts 트리 기반 라이선스 판별"
```

---

### Task 6: to_record 통합

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/transform.py:97-126`
- Test: `apps/pipeline/tests/test_transform.py`

**Interfaces:**
- Consumes: `map_category_ko`, `build_slug`, `extract_weights`(Task 4), `resolve_license_type`(Task 5), 확장된 `FontRecord`(Task 3).
- Produces: `to_record(raw: GoogleFontRaw, license_map: dict[str, str]) -> FontRecord`, `build_records(fonts, license_map, latin_limit=100) -> list[FontRecord]`. 시그니처에 `license_map` 추가.

- [ ] **Step 1: 실패 테스트 작성**

`apps/pipeline/tests/test_transform.py`에 추가:
```python
def test_to_record_published_for_ofl():
    from fontagit_pipeline.models import GoogleFontRaw
    from fontagit_pipeline.transform import to_record
    raw = GoogleFontRaw(
        family="Noto Sans KR", variants=["regular", "700"], subsets=["korean", "latin"],
        version="v1", lastModified="2024-01-01", files={}, category="sans-serif",
    )
    rec = to_record(raw, {"notosanskr": "OFL"})
    assert rec.slug == "noto-sans-kr"
    assert rec.category_ko == "고딕"
    assert rec.weights == [400, 700]
    assert rec.license_type == "OFL"
    assert rec.is_commercial_free is True
    assert rec.license_verified is True
    assert rec.status == "published"

def test_to_record_draft_for_unknown_license():
    from fontagit_pipeline.models import GoogleFontRaw
    from fontagit_pipeline.transform import to_record
    raw = GoogleFontRaw(
        family="Mystery Font", variants=["regular"], subsets=["latin"],
        version="v1", lastModified="2024-01-01", files={}, category="serif",
    )
    rec = to_record(raw, {})
    assert rec.license_type is None
    assert rec.license_verified is False
    assert rec.status == "draft"
    assert rec.is_commercial_free is False
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_transform.py -k "to_record" -v`
Expected: FAIL — `to_record()` 인자/필드 불일치.

- [ ] **Step 3: 구현**

`transform.py`의 `to_record`와 `build_records`를 교체:
```python
def to_record(raw: GoogleFontRaw, license_map: dict[str, str]) -> FontRecord:
    """GoogleFontRaw를 FontRecord로 변환한다. OFL/Apache/UFL이면 공개(published)."""
    from fontagit_pipeline.licenses import resolve_license_type

    variants = normalize_variants(raw.variants)
    license_type = resolve_license_type(raw.family, license_map)
    verified = license_type is not None
    return FontRecord(
        slug=build_slug(raw.family),
        name_en=raw.family,
        name_ko=None,
        source_tier="A",
        category_ko=map_category_ko(raw.category),
        category_google=raw.category,
        subsets=raw.subsets,
        variants=variants,
        weights=extract_weights(variants),
        official_url=build_official_url(raw.family),
        is_commercial_free=verified,
        license_type=license_type,
        license_verified=verified,
        status="published" if verified else "draft",
        aliases=build_aliases(raw.family),
        version=raw.version,
        last_modified=raw.lastModified,
    )


def build_records(
    fonts: list[GoogleFontRaw], license_map: dict[str, str], latin_limit: int = 100
) -> list[FontRecord]:
    """폰트 목록을 레코드로 변환한다(한국어+라틴 통합, 중복 제거, 변환 실패 시 건너뜀)."""
    merged = merge_dedup(filter_korean(fonts), select_latin_top(fonts, latin_limit))
    records: list[FontRecord] = []
    for raw in merged:
        try:
            records.append(to_record(raw, license_map))
        except ValueError as exc:
            logger.warning("레코드 변환 건너뜀 (%s): %s", raw.family, exc)
    return records
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_transform.py -v`
Expected: PASS (기존 transform 테스트 포함 전부).

- [ ] **Step 5: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/transform.py apps/pipeline/tests/test_transform.py
git commit -m "feat(pipeline): to_record에 라이선스 판별-공개상태 통합"
```

---

### Task 7: Supabase 업로더 (`uploader.py`)

**Files:**
- Create: `apps/pipeline/src/fontagit_pipeline/uploader.py`
- Test: `apps/pipeline/tests/test_uploader.py`

**Interfaces:**
- Consumes: 확장된 `FontRecord`(Task 3).
- Produces:
  - `build_font_row(rec: FontRecord) -> dict` — fonts upsert용 행(id 제외)
  - `build_alias_rows(font_id: str, aliases: list[str]) -> list[dict]` — {font_id, alias, alias_norm}
  - `normalize_alias(alias: str) -> str`
  - `upload_records(records, url, secret_key) -> int` — upsert 실행, 처리 건수 반환(네트워크)

- [ ] **Step 1: 실패 테스트 작성**

`apps/pipeline/tests/test_uploader.py`:
```python
from fontagit_pipeline.models import FontRecord
from fontagit_pipeline.uploader import build_font_row, build_alias_rows, normalize_alias

def _rec():
    return FontRecord(
        slug="noto-sans-kr", name_en="Noto Sans KR", category_ko="고딕",
        category_google="sans-serif", subsets=["korean"], variants=["400"],
        weights=[400], official_url="https://x", aliases=["Noto Sans KR", "노토 산스"],
        version="v1", last_modified="2024-01-01",
        is_commercial_free=True, license_type="OFL", license_verified=True,
        status="published",
    )

def test_build_font_row():
    row = build_font_row(_rec())
    assert row["slug"] == "noto-sans-kr"
    assert row["status"] == "published"
    assert row["weights"] == [400]
    assert "id" not in row

def test_normalize_alias():
    assert normalize_alias("Noto Sans KR") == "notosanskr"
    assert normalize_alias("노토 산스") == "노토산스"

def test_build_alias_rows_dedup_norm():
    rows = build_alias_rows("fid-1", ["Noto Sans", "noto sans"])  # 정규화 동일
    assert len(rows) == 1
    assert rows[0]["font_id"] == "fid-1"
    assert rows[0]["alias_norm"] == "notosans"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_uploader.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현**

`apps/pipeline/src/fontagit_pipeline/uploader.py`:
```python
"""수집 레코드를 Supabase fontagit 스키마에 업로드한다."""

import logging
import re

from supabase import create_client

from fontagit_pipeline.models import FontRecord

logger = logging.getLogger(__name__)

_FONT_COLS = (
    "slug", "name_en", "name_ko", "source_tier", "category_ko", "category_google",
    "subsets", "variants", "weights", "is_commercial_free", "license_type",
    "license_verified", "official_url", "status", "version", "last_modified",
)


def normalize_alias(alias: str) -> str:
    """별칭을 정규화한다(소문자, 공백/특수문자 제거). 한글은 유지."""
    return re.sub(r"[\s]+", "", alias.lower())


def build_font_row(rec: FontRecord) -> dict:
    """fonts upsert용 행을 만든다(id/created_at 제외)."""
    data = rec.model_dump()
    return {col: data[col] for col in _FONT_COLS}


def build_alias_rows(font_id: str, aliases: list[str]) -> list[dict]:
    """aliases upsert용 행을 만든다(alias_norm 기준 중복 제거)."""
    seen: set[str] = set()
    rows: list[dict] = []
    for alias in aliases:
        norm = normalize_alias(alias)
        if norm and norm not in seen:
            seen.add(norm)
            rows.append({"font_id": font_id, "alias": alias, "alias_norm": norm})
    return rows


def upload_records(records: list[FontRecord], url: str, secret_key: str) -> int:
    """레코드를 fontagit.fonts/aliases에 멱등 upsert하고 처리 건수를 반환한다."""
    client = create_client(url, secret_key)
    table = client.schema("fontagit")
    count = 0
    for rec in records:
        res = (
            table.table("fonts")
            .upsert(build_font_row(rec), on_conflict="slug")
            .execute()
        )
        font_id = res.data[0]["id"]
        alias_rows = build_alias_rows(font_id, rec.aliases)
        if alias_rows:
            table.table("aliases").upsert(
                alias_rows, on_conflict="font_id,alias_norm"
            ).execute()
        count += 1
    logger.info("업로드 완료: %d개", count)
    return count
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_uploader.py -v`
Expected: PASS (순수 함수만; `upload_records`는 통합에서 검증).

- [ ] **Step 5: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/uploader.py apps/pipeline/tests/test_uploader.py
git commit -m "feat(pipeline): Supabase fontagit 업로더(fonts/aliases upsert)"
```

---

### Task 8: 오케스트레이션 (`__main__`) + 통합 검증

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/__main__.py`
- Test: `apps/pipeline/tests/test_main.py`

**Interfaces:**
- Consumes: `fetch_license_map`(Task 5), `build_records`(Task 6, 시그니처 변경), `upload_records`(Task 7), 확장 `Settings`(Task 2).
- Produces: `build_document(fonts, license_map, generated_at, latin_limit=100)`. main()에 라이선스 조회 + 조건부 업로드.

- [ ] **Step 1: 실패 테스트 작성**

`apps/pipeline/tests/test_main.py`에 추가(기존 build_document 호출 테스트가 있으면 인자 추가로 수정):
```python
def test_build_document_passes_license_map():
    from fontagit_pipeline.models import GoogleFontRaw
    from fontagit_pipeline.__main__ import build_document
    raw = GoogleFontRaw(
        family="Jua", variants=["regular"], subsets=["korean"],
        version="v1", lastModified="2024-01-01", files={}, category="display",
    )
    doc = build_document([raw], {"jua": "OFL"}, "2026-07-14T00:00:00Z")
    assert doc.record_count == 1
    assert doc.fonts[0].status == "published"
    assert doc.fonts[0].category_ko == "장식"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_main.py -k build_document -v`
Expected: FAIL — `build_document()` 인자 수 불일치.

- [ ] **Step 3: 구현**

`__main__.py` 수정 — import 추가, `build_document`-`main` 갱신:
```python
from fontagit_pipeline.licenses import fetch_license_map
from fontagit_pipeline.uploader import upload_records
```
```python
def build_document(
    fonts: list[GoogleFontRaw],
    license_map: dict[str, str],
    generated_at: str,
    latin_limit: int = 100,
) -> OutputDocument:
    """폰트 원형 목록을 OutputDocument로 변환한다."""
    records = build_records(fonts, license_map, latin_limit)
    return OutputDocument(
        generated_at=generated_at, source=_SOURCE,
        record_count=len(records), fonts=records,
    )
```
`main()`에서 `fetch_webfonts` 성공 후, `build_document` 호출 전에 라이선스 조회 추가하고, JSON 저장 성공 후 Supabase 설정이 있으면 업로드:
```python
    license_map = fetch_license_map(settings.github_token)
    logger.info("라이선스 매핑 %d건", len(license_map))

    generated_at = datetime.now(timezone.utc).isoformat()
    doc = build_document(fonts, license_map, generated_at)
```
저장(`write_output`) 성공 로그 다음에:
```python
    if settings.supabase_url and settings.supabase_secret_key:
        published = [r for r in doc.fonts if r.status == "published"]
        try:
            uploaded = upload_records(doc.fonts, settings.supabase_url, settings.supabase_secret_key)
        except Exception as exc:  # 외부 경계
            logger.error("Supabase 업로드 실패: %s", exc.__class__.__name__)
            return 3
        logger.info("업로드 %d개(공개 %d개)", uploaded, len(published))
    else:
        logger.info("Supabase 설정 없음 — 업로드 건너뜀(로컬 JSON만).")
    return 0
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest -v`
Expected: PASS (전체 스위트).

- [ ] **Step 5: lint/type 통과**

Run: `cd apps/pipeline && uv run ruff check . && uv run mypy src`
Expected: 에러 없음.

- [ ] **Step 6: 통합 실행 + 쓰기→읽기 재검증**

Run(실제 키 필요): `cd apps/pipeline && GOOGLE_FONTS_API_KEY=... uv run python -m fontagit_pipeline`
그다음:
```bash
psql "$SUPABASE_DB_URL" -c "select count(*) filter (where status='published') as pub, count(*) total from fontagit.fonts;"
```
Expected: `total > 0` 그리고 `pub > 0`. 동일 명령 2회 실행해도 `total` 동일(멱등).

- [ ] **Step 7: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/tests/test_main.py
git commit -m "feat(pipeline): 라이선스 조회 + Supabase 업로드 오케스트레이션"
```

---

## Self-Review 결과

- **Spec coverage:** 스키마 4테이블(Task 1), 키/설정(Task 2), tier분리-category-slug-weights(Task 3-4), OFL/Apache/UFL 자동공개(Task 5-6), 멱등 upsert(Task 7), 오케스트레이션+통합검증(Task 8). 스펙 4-6절 커버. 웹(5절)은 Plan B.
- **Placeholder scan:** 없음. 모든 코드 스텝에 실제 코드 포함.
- **Type consistency:** `FontRecord` 필드(Task 3) ↔ `build_font_row`/`_FONT_COLS`(Task 7) ↔ 테스트 일치. `build_records(fonts, license_map, latin_limit)` 시그니처가 Task 6-8에서 동일. `resolve_license_type(name_en, map)` 일관.

## 남은 수동 작업(코드 밖)

- Task 1 Step 4: Supabase 대시보드 Exposed schemas에 `fontagit` 추가.
- `SUPABASE_DB_URL`(psql용 연결 문자열)은 대시보드 Connection string에서 확보(비번=`SUPABASE_DB_PASSWORD`).
