# 업로드 원자성 + stale alias 동기화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 폰트 업로드를 Postgres 함수(RPC) 기반 폰트별 원자 트랜잭션으로 바꿔 fonts/aliases 불일치와 stale alias를 제거하고, licenses.py의 GitHub 응답 방어를 강화한다.

**Architecture:** Supabase(Postgres)에 `fontagit.upsert_font(p_font, p_aliases)` 함수를 신설해 폰트 1개당 fonts upsert + 기존 aliases 전량 삭제 + 새 aliases 삽입을 단일 트랜잭션으로 실행한다. `uploader.py`는 폰트당 RPC 1회를 호출하고, 첫 실패 시 즉시 중단한다. `licenses.py`는 GitHub 트리 응답을 `.get()` 기반으로 안전하게 파싱한다.

**Tech Stack:** Python 3.12, uv, supabase-py 2.x, pydantic v2, httpx, pytest, ruff, mypy(strict). Supabase(Postgres) `fontagit` 스키마.

## Global Constraints

- Python 3.12, 타입 힌트 100%, Docstring 한국어. `print` 금지 → `logging`.
- 하드코딩 금지, `ruff check`/`mypy --strict`/`pytest` 통과.
- Supabase는 ollidam과 공유 인스턴스 → 모든 객체는 `fontagit` 스키마. `public` 접근 금지.
- secret key(`SUPABASE_SECRET_KEY`)는 서버 전용 — 로그-커밋-응답 노출 금지.
- 명령은 `apps/pipeline`에서 `uv run` 기준.
- 변경 범위: `apps/pipeline` + `supabase`만. UI/다른 스키마/다른 디렉터리 금지.

## File Structure

- `apps/pipeline/src/fontagit_pipeline/licenses.py` (수정) — GitHub 트리 응답 방어 파싱. 책임: 라이선스 판별.
- `supabase/migrations/0002_upsert_font_rpc.sql` (생성) — `fontagit.upsert_font` RPC 함수 + EXECUTE 권한 제한. 책임: 원자 업로드 트랜잭션.
- `apps/pipeline/src/fontagit_pipeline/uploader.py` (수정) — `build_alias_rows` 시그니처 변경 + `upload_records` RPC 재작성. 책임: 레코드 → Supabase 업로드.
- 테스트: `apps/pipeline/tests/test_licenses.py`, `apps/pipeline/tests/test_uploader.py` (수정).

---

### Task 1: licenses.py GitHub 응답 방어

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/licenses.py:37-109`
- Test: `apps/pipeline/tests/test_licenses.py`

**Interfaces:**
- Consumes: 없음(기존 모듈 내부 함수 강화).
- Produces: `parse_license_map`/`_get_tree_sha`/`fetch_license_map` 동작 불변, 단 GitHub 응답 구조 이상 시 `KeyError` 대신 안전 스킵 또는 `LicenseFetchError`.

- [ ] **Step 1: 실패 테스트 작성**

`apps/pipeline/tests/test_licenses.py`의 `TestParseLicenseMap` 클래스에 메서드 추가:

```python
    def test_skip_entry_without_path(self):
        """path 키 없는 항목은 KeyError 없이 건너뛴다."""
        trees = {"ofl": [{"type": "tree"}, {"type": "tree", "path": "jua"}]}
        result = parse_license_map(trees)
        assert result == {"jua": "OFL"}
```

`apps/pipeline/tests/test_licenses.py`의 `TestFetchLicenseMap` 클래스에 메서드 추가:

```python
    def test_fetch_license_map_raises_on_malformed_json(self):
        """응답 본문 JSON 파싱 실패 시 LicenseFetchError로 감싼다."""
        with patch("fontagit_pipeline.licenses.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_client.get.return_value = mock_response

            with pytest.raises(LicenseFetchError):
                fetch_license_map()

    def test_fetch_license_map_missing_tree_key_returns_empty(self):
        """루트 응답에 tree 키가 없으면 빈 매핑을 반환한다(죽지 않음)."""
        with patch("fontagit_pipeline.licenses.httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.json.return_value = {}
            mock_client.get.return_value = mock_response

            assert fetch_license_map() == {}
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_licenses.py -k "skip_entry_without_path or malformed_json or missing_tree_key" -v`
Expected: FAIL — `test_skip_entry_without_path`는 `KeyError: 'path'`, `malformed_json`은 `ValueError`가 `LicenseFetchError`로 안 감싸져 실패.

- [ ] **Step 3: parse_license_map 방어 구현**

`licenses.py`의 `parse_license_map`을 교체:

```python
def parse_license_map(trees: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """라이선스별 트리 데이터에서 폰트명→라이선스 매핑을 추출한다.

    Args:
        trees: 라이선스별 GH tree 데이터 (예: {"ofl": [...]})

    Returns:
        폰트명→라이선스 타입 매핑 (예: {"notosanskr": "OFL"})
    """
    result: dict[str, str] = {}
    for license_dir, license_type in _LICENSE_DIRS.items():
        for entry in trees.get(license_dir, []):
            path = entry.get("path")
            if entry.get("type") == "tree" and path:
                result[path] = license_type
    return result
```

- [ ] **Step 4: _get_tree_sha 방어 구현**

`licenses.py`의 `_get_tree_sha`를 교체:

```python
def _get_tree_sha(client: httpx.Client, headers: dict[str, str]) -> dict[str, str]:
    """루트 트리에서 ofl/apache/ufl 디렉토리의 sha를 얻는다."""
    r = client.get(f"{_GH_API}/repos/google/fonts/git/trees/main", headers=headers)
    r.raise_for_status()
    shas: dict[str, str] = {}
    for entry in r.json().get("tree", []):
        path = entry.get("path")
        sha = entry.get("sha")
        if path in _LICENSE_DIRS and entry.get("type") == "tree" and sha:
            shas[path] = sha
    return shas
```

- [ ] **Step 5: fetch_license_map 방어 구현**

`licenses.py`의 `fetch_license_map`에서 `trees[dir_key] = r.json()["tree"]`를 `.get()`으로 바꾸고, `except`에 `ValueError`(JSON 파싱 실패)를 추가:

```python
def fetch_license_map(github_token: str | None = None) -> dict[str, str]:
    """google/fonts에서 라이선스 매핑을 조회한다.

    Args:
        github_token: GitHub API 토큰 (선택)

    Returns:
        폰트명→라이선스 타입 매핑

    Raises:
        LicenseFetchError: 라이선스 조회 또는 응답 파싱 실패 시
    """
    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    trees: dict[str, list[dict[str, Any]]] = {}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            shas = _get_tree_sha(client, headers)
            for dir_key, sha in shas.items():
                r = client.get(
                    f"{_GH_API}/repos/google/fonts/git/trees/{sha}", headers=headers
                )
                r.raise_for_status()
                trees[dir_key] = r.json().get("tree", [])
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("라이선스 매핑 조회 실패: %s", exc.__class__.__name__)
        raise LicenseFetchError(str(exc)) from exc
    return parse_license_map(trees)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_licenses.py -v`
Expected: PASS (기존 + 신규 전부).

- [ ] **Step 7: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/licenses.py apps/pipeline/tests/test_licenses.py
git commit -m "fix(pipeline): licenses.py GitHub 응답 방어(.get 파싱 + JSON 오류 감싸기)"
```

---

### Task 2: 마이그레이션 0002 — upsert_font RPC 함수

**Files:**
- Create: `supabase/migrations/0002_upsert_font_rpc.sql`

**Interfaces:**
- Consumes: 0001의 `fontagit.fonts`(slug unique), `fontagit.aliases`(font_id FK, (font_id, alias_norm) unique).
- Produces: `fontagit.upsert_font(p_font jsonb, p_aliases jsonb) returns uuid`. `p_font`는 `_FONT_COLS`(slug,name_en,name_ko,source_tier,category_ko,category_google,subsets,variants,weights,is_commercial_free,license_type,license_verified,official_url,status,version,last_modified) 키를 가진 객체. `p_aliases`는 `[{alias, alias_norm}]` 배열.

- [ ] **Step 1: 마이그레이션 SQL 작성**

`supabase/migrations/0002_upsert_font_rpc.sql`:

```sql
-- 폰트 1개당 fonts upsert + aliases 전량 재삽입을 단일 트랜잭션(원자)으로 실행
create or replace function fontagit.upsert_font(p_font jsonb, p_aliases jsonb)
returns uuid
language plpgsql
security definer
set search_path = fontagit, pg_temp
as $$
declare
  v_font_id uuid;
begin
  insert into fontagit.fonts (
    slug, name_en, name_ko, source_tier, category_ko, category_google,
    subsets, variants, weights, is_commercial_free, license_type,
    license_verified, official_url, status, version, last_modified
  )
  values (
    p_font->>'slug',
    p_font->>'name_en',
    p_font->>'name_ko',
    coalesce(p_font->>'source_tier', 'A'),
    p_font->>'category_ko',
    p_font->>'category_google',
    coalesce(array(select jsonb_array_elements_text(p_font->'subsets')), '{}'),
    coalesce(array(select jsonb_array_elements_text(p_font->'variants')), '{}'),
    coalesce(array(select (jsonb_array_elements_text(p_font->'weights'))::int), '{}'),
    coalesce((p_font->>'is_commercial_free')::boolean, false),
    p_font->>'license_type',
    coalesce((p_font->>'license_verified')::boolean, false),
    p_font->>'official_url',
    coalesce(p_font->>'status', 'draft'),
    p_font->>'version',
    p_font->>'last_modified'
  )
  on conflict (slug) do update set
    name_en = excluded.name_en,
    name_ko = excluded.name_ko,
    source_tier = excluded.source_tier,
    category_ko = excluded.category_ko,
    category_google = excluded.category_google,
    subsets = excluded.subsets,
    variants = excluded.variants,
    weights = excluded.weights,
    is_commercial_free = excluded.is_commercial_free,
    license_type = excluded.license_type,
    license_verified = excluded.license_verified,
    official_url = excluded.official_url,
    status = excluded.status,
    version = excluded.version,
    last_modified = excluded.last_modified,
    updated_at = now()
  returning id into v_font_id;

  delete from fontagit.aliases where font_id = v_font_id;

  if jsonb_array_length(coalesce(p_aliases, '[]'::jsonb)) > 0 then
    insert into fontagit.aliases (font_id, alias, alias_norm)
    select v_font_id, a->>'alias', a->>'alias_norm'
    from jsonb_array_elements(p_aliases) a;
  end if;

  return v_font_id;
end;
$$;

-- SECURITY DEFINER 함수는 RLS를 우회한다. PostgreSQL 기본 PUBLIC EXECUTE를 회수하고
-- service_role만 실행 가능하게 제한(anon/authenticated 쓰기 차단).
revoke execute on function fontagit.upsert_font(jsonb, jsonb) from public;
revoke execute on function fontagit.upsert_font(jsonb, jsonb) from anon, authenticated;
grant execute on function fontagit.upsert_font(jsonb, jsonb) to service_role;
```

- [ ] **Step 2: psql로 적용**

Run (`SUPABASE_DB_URL`은 대시보드 Connection string, 비번=`apps/pipeline/.env`의 `SUPABASE_DB_PASSWORD`):
```bash
psql "$SUPABASE_DB_URL" -f supabase/migrations/0002_upsert_font_rpc.sql
```
Expected: `CREATE FUNCTION`, `REVOKE`, `GRANT` 에러 없이 완료.

- [ ] **Step 3: 함수 존재 및 권한 확인**

Run:
```bash
psql "$SUPABASE_DB_URL" -c "\df fontagit.upsert_font"
psql "$SUPABASE_DB_URL" -c "select proacl from pg_proc where proname='upsert_font';"
```
Expected: 함수 1개 표시. `proacl`에 `service_role=X`가 있고 `anon`/`authenticated`에는 EXECUTE 없음.

- [ ] **Step 4: Commit**

```bash
git add supabase/migrations/0002_upsert_font_rpc.sql
git commit -m "feat(db): upsert_font RPC(폰트별 원자 upsert + stale alias 재삽입) + EXECUTE 권한 제한"
```

---

### Task 3: uploader.py RPC 재작성

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/uploader.py:44-84`
- Test: `apps/pipeline/tests/test_uploader.py`

**Interfaces:**
- Consumes: Task 2의 `fontagit.upsert_font` RPC, 기존 `build_font_row`(변경 없음), `FontRecord`.
- Produces:
  - `build_alias_rows(aliases: list[str]) -> list[dict[str, Any]]` — `font_id` 제거, `{alias, alias_norm}`만 반환(중복/빈값 제거 유지).
  - `upload_records(records, url, secret_key) -> int` — 폰트당 `schema.rpc("upsert_font", {"p_font": ..., "p_aliases": ...})` 1회, 첫 실패 시 slug 로그 후 예외 전파.

- [ ] **Step 1: 실패 테스트 작성(기존 테스트 수정 + 신규)**

`apps/pipeline/tests/test_uploader.py` 상단 import를 교체:

```python
from unittest.mock import patch, MagicMock

from fontagit_pipeline.models import FontRecord
from fontagit_pipeline.uploader import (
    build_font_row,
    build_alias_rows,
    normalize_alias,
    upload_records,
)
```

기존 `test_build_alias_rows_dedup_norm`을 교체(font_id 인자 제거):

```python
def test_build_alias_rows_dedup_norm():
    rows = build_alias_rows(["Noto Sans", "noto sans"])  # 정규화 동일
    assert len(rows) == 1
    assert rows[0]["alias"] == "Noto Sans"
    assert rows[0]["alias_norm"] == "notosans"
    assert "font_id" not in rows[0]
```

파일 끝에 신규 테스트 추가:

```python
def test_upload_records_calls_rpc_per_font():
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        mock_schema = mock_client.schema.return_value

        n = upload_records([_rec()], "https://x.supabase.co", "sb_secret")

        assert n == 1
        mock_client.schema.assert_called_once_with("fontagit")
        mock_schema.rpc.assert_called_once()
        name, payload = mock_schema.rpc.call_args.args
        assert name == "upsert_font"
        assert payload["p_font"]["slug"] == "noto-sans-kr"
        assert "id" not in payload["p_font"]
        assert payload["p_aliases"][0]["alias_norm"] == "notosanskr"
        assert "font_id" not in payload["p_aliases"][0]
        mock_schema.rpc.return_value.execute.assert_called_once()


def test_upload_records_raises_on_rpc_failure():
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        mock_client = MagicMock()
        mock_create.return_value = mock_client
        mock_schema = mock_client.schema.return_value
        mock_schema.rpc.return_value.execute.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            upload_records([_rec()], "https://x.supabase.co", "sb_secret")
```

`test_uploader.py` 상단에 `import pytest` 추가(없으면).

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_uploader.py -v`
Expected: FAIL — `build_alias_rows`가 아직 `font_id` 인자를 요구하고, `upload_records`가 RPC를 안 부름.

- [ ] **Step 3: build_alias_rows 시그니처 변경**

`uploader.py`의 `build_alias_rows`를 교체:

```python
def build_alias_rows(aliases: list[str]) -> list[dict[str, Any]]:
    """aliases 행을 만든다(alias_norm 기준 중복/빈값 제거). font_id는 DB 함수가 채운다."""
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for alias in aliases:
        norm = normalize_alias(alias)
        if norm and norm not in seen:
            seen.add(norm)
            rows.append({"alias": alias, "alias_norm": norm})
    return rows
```

- [ ] **Step 4: upload_records RPC 재작성**

`uploader.py`의 `upload_records`를 교체:

```python
def upload_records(records: list[FontRecord], url: str, secret_key: str) -> int:
    """레코드를 fontagit.upsert_font RPC로 폰트별 원자 업로드하고 처리 건수를 반환한다.

    각 폰트는 단일 트랜잭션(fonts upsert + aliases 재삽입)으로 처리된다.
    첫 실패 시 즉시 중단하며, 이미 처리된 폰트는 유지된다(파이프라인 멱등 재실행).
    """
    client = create_client(url, secret_key)
    schema = client.schema("fontagit")
    count = 0
    for rec in records:
        try:
            schema.rpc(
                "upsert_font",
                {"p_font": build_font_row(rec), "p_aliases": build_alias_rows(rec.aliases)},
            ).execute()
        except Exception:
            logger.error("업로드 실패(중단): slug=%s", rec.slug)
            raise
        count += 1
    logger.info("업로드 완료: %d개", count)
    return count
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd apps/pipeline && uv run pytest tests/test_uploader.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/uploader.py apps/pipeline/tests/test_uploader.py
git commit -m "feat(pipeline): upload_records를 upsert_font RPC 폰트별 원자 호출로 재작성"
```

---

### Task 4: 통합 검증

**Files:**
- 없음(검증 전용). 필요 시 `apps/pipeline` 소스 미세 수정.

**Interfaces:**
- Consumes: Task 1-3 산출물 전체.
- Produces: 없음(그린 스위트 + 실제 업로드 재검증).

- [ ] **Step 1: 전체 테스트 통과**

Run: `cd apps/pipeline && uv run pytest -v`
Expected: PASS (전체 스위트).

- [ ] **Step 2: lint/type 통과**

Run: `cd apps/pipeline && uv run ruff check . && uv run mypy src`
Expected: 에러 없음.

- [ ] **Step 3: 실제 업로드 + 멱등/stale 재검증**

Run (실제 키 필요, `apps/pipeline/.env`에 `SUPABASE_URL`/`SUPABASE_SECRET_KEY` 설정):
```bash
cd apps/pipeline && uv run python -m fontagit_pipeline
```
그다음 카운트 확인:
```bash
psql "$SUPABASE_DB_URL" -c "select count(*) filter (where status='published') as pub, count(*) total from fontagit.fonts;"
psql "$SUPABASE_DB_URL" -c "select count(*) from fontagit.aliases;"
```
동일 명령을 2회 실행해도 `total`과 aliases 카운트가 동일해야 한다(멱등 + stale 미증가).
Expected: `total > 0`, `pub > 0`. 2회차 카운트 == 1회차.

- [ ] **Step 4: 원자성 롤백 수동 확인**

RPC가 폰트별 원자임을 psql로 직접 검증한다. 중복 `alias_norm`을 넣어 insert를 실패시키고, 그 폰트의 기존 상태가 롤백되는지 본다:
```bash
psql "$SUPABASE_DB_URL" -c "select fontagit.upsert_font(
  '{\"slug\":\"__rollback_test__\",\"name_en\":\"RB\",\"category_ko\":\"고딕\",\"category_google\":\"serif\",\"subsets\":[],\"variants\":[],\"weights\":[],\"is_commercial_free\":false,\"license_verified\":false,\"official_url\":\"u\",\"status\":\"draft\",\"version\":\"v\",\"last_modified\":\"d\"}'::jsonb,
  '[{\"alias\":\"a\",\"alias_norm\":\"dup\"},{\"alias\":\"b\",\"alias_norm\":\"dup\"}]'::jsonb);"
psql "$SUPABASE_DB_URL" -c "select count(*) from fontagit.fonts where slug='__rollback_test__';"
```
Expected: 첫 명령은 unique 위반으로 ERROR. 두 번째 count는 `0` — fonts insert가 alias 실패와 함께 롤백됨(원자성 입증). (테스트 흔적 없음 확인.)

- [ ] **Step 5: 최종 상태 보고**

`git log --oneline`으로 Task 1-3 커밋 확인, `git status` clean 확인. 이슈 #8 SHOULD 3건 반영 완료 보고.

---

## Self-Review 결과

- **Spec coverage:** 원자성(Task 2 RPC + Task 3 폰트별 호출), stale alias 삭제-재삽입(Task 2 delete+insert), licenses.py 방어(Task 1). 리뷰 Must(EXECUTE 권한, Task 2 Step 1), Should(컬럼 화이트리스트=RPC 명시 매핑, updated_at=now(), 빈 배열 스킵, build_alias_rows 중복/빈값, 첫 실패 중단=Task 3 Step 4, 롤백 테스트=Task 4 Step 4) 모두 커버.
- **Placeholder scan:** 없음. 모든 코드 스텝에 실제 코드/명령 포함.
- **Type consistency:** `build_alias_rows(aliases)`(Task 3) ↔ 테스트(Task 3 Step 1) 일치. `_FONT_COLS`(uploader 기존) ↔ RPC insert 컬럼(Task 2) 16개 일치. `upsert_font(p_font, p_aliases)` 시그니처가 Task 2-3에서 동일. `build_font_row`는 기존 유지(id 제외, slug 포함).

## 남은 수동 작업(코드 밖)

- Task 2: `psql`로 0002 마이그레이션 적용(자동화 없음). `SUPABASE_DB_URL`은 대시보드 Connection string.
- Task 4 Step 3-4: 실제 Supabase 키 + DB 접속 필요.
