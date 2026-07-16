# Tier A stale 폰트 동기화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전체 Tier A 업로드가 성공한 뒤 현재 스냅샷에서 빠진 published 폰트를 안전하게 draft로 전환해 DB와 파이프라인 결과를 일치시킨다.

**Architecture:** 일반 부분 업로드 `upload_records()`는 유지하고, 전체 스냅샷 전용 `upload_tier_a_snapshot()`을 추가한다. 전용 함수는 쓰기 전에 입력을 검증하고 모든 upsert가 성공한 뒤 service_role 전용 DB RPC를 호출한다. DB RPC는 active 최소 100종·stale 최대 5종을 이중 강제한다.

**Tech Stack:** Python 3.12, pytest, supabase-py, PostgreSQL PL/pgSQL, uv

## Global Constraints

- 적용 DB는 dev `zgxtfcpiokhkcrywlxmc`만. prod 쓰기 금지.
- 일반 `upload_records()`는 stale 동기화를 하지 않는다.
- active slug는 Tier A 전체 레코드(published+draft)다.
- active 고유 slug 100종 미만은 첫 DB 쓰기 전에 실패한다.
- stale published Tier A 5종 초과는 DB 갱신 전에 실패한다.
- Tier B/C, archived 행, 별칭 행은 동기화 함수가 변경하지 않는다.
- 새 테스트는 핵심 서비스 3개만 추가한다.

---

## File Structure

| 파일 | 역할 |
|---|---|
| `supabase/migrations/0005_sync_tier_a_fonts.sql` | service_role 전용 stale draft RPC와 DB 안전장치 |
| `apps/pipeline/src/fontagit_pipeline/uploader.py` | 일반 업로드 유지 + 전체 Tier A 스냅샷 업로드 서비스 |
| `apps/pipeline/src/fontagit_pipeline/__main__.py` | CLI가 전체 스냅샷 서비스를 호출 |
| `apps/pipeline/tests/test_uploader.py` | 성공·중간 실패·100종 미만 3개 핵심 테스트 |
| `docs/progress.md` | Task 5 완료 증거와 다음 단계 기록 |

---

### Task 1: DB stale 동기화 RPC

**Files:**
- Create: `supabase/migrations/0005_sync_tier_a_fonts.sql`

**Interfaces:**
- Produces: `fontagit.sync_tier_a_fonts(p_active_slugs text[]) -> integer`
- Security: `SECURITY DEFINER`, 빈 `search_path`, `service_role`만 실행

- [ ] **Step 1: 마이그레이션 SQL 작성**

```sql
begin;

create or replace function fontagit.sync_tier_a_fonts(p_active_slugs text[])
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_active_count integer;
  v_distinct_count integer;
  v_stale_count integer;
begin
  if p_active_slugs is null then
    raise exception 'active slug 목록은 null일 수 없습니다'
      using errcode = '22023';
  end if;

  if exists (
    select 1
    from unnest(p_active_slugs) as slug
    where slug is null or btrim(slug) = ''
  ) then
    raise exception 'active slug에 null/빈 문자열이 있습니다'
      using errcode = '22023';
  end if;

  v_active_count := cardinality(p_active_slugs);
  select count(distinct slug)
    into v_distinct_count
    from unnest(p_active_slugs) as slug;

  if v_active_count <> v_distinct_count then
    raise exception 'active slug에 중복이 있습니다'
      using errcode = '22023';
  end if;

  if v_distinct_count < 100 then
    raise exception 'active Tier A가 100종 미만입니다: %', v_distinct_count
      using errcode = '22023';
  end if;

  lock table fontagit.fonts in share row exclusive mode;

  select count(*)
    into v_stale_count
    from fontagit.fonts as f
   where f.source_tier = 'A'
     and f.status = 'published'
     and not (f.slug = any(p_active_slugs));

  if v_stale_count > 5 then
    raise exception 'stale published Tier A가 5종을 초과합니다: %', v_stale_count
      using errcode = '22023';
  end if;

  update fontagit.fonts as f
     set status = 'draft',
         updated_at = now()
   where f.source_tier = 'A'
     and f.status = 'published'
     and not (f.slug = any(p_active_slugs));

  return v_stale_count;
end;
$$;

revoke execute on function fontagit.sync_tier_a_fonts(text[]) from public;
revoke execute on function fontagit.sync_tier_a_fonts(text[]) from anon, authenticated;
grant execute on function fontagit.sync_tier_a_fonts(text[]) to service_role;

commit;
```

- [ ] **Step 2: 정적 검토**

Run:

```bash
rg -n "security definer|set search_path|source_tier = 'A'|status = 'published'|v_distinct_count < 100|v_stale_count > 5|revoke execute|grant execute" supabase/migrations/0005_sync_tier_a_fonts.sql
git diff --check
```

Expected: 8개 안전 조건이 모두 검색되고 `git diff --check` 오류 0.

- [ ] **Step 3: Commit**

```bash
git add supabase/migrations/0005_sync_tier_a_fonts.sql
git commit -m "feat(db): Tier A stale 폰트 draft 동기화 RPC"
```

---

### Task 2: 전체 Tier A 스냅샷 서비스 TDD

**Files:**
- Modify: `apps/pipeline/tests/test_uploader.py`
- Modify: `apps/pipeline/src/fontagit_pipeline/uploader.py`

**Interfaces:**
- Keeps: `upload_records(records, url, secret_key) -> int` — 부분 업로드, stale 동기화 없음
- Produces: `upload_tier_a_snapshot(records, url, secret_key) -> tuple[int, int]`

- [ ] **Step 1: 실패 테스트 3개 작성**

`test_uploader.py` import에 `call`과 `upload_tier_a_snapshot`을 추가하고 아래만 작성한다.

```python
from unittest.mock import call


def _snapshot_records(count: int = 100) -> list[FontRecord]:
    return [
        _rec().model_copy(
            update={
                "slug": f"font-{i:03d}",
                "name_en": f"Font {i:03d}",
                "aliases": [f"Font {i:03d}"],
            }
        )
        for i in range(count)
    ]


def test_upload_tier_a_snapshot_syncs_only_after_all_upserts():
    records = _snapshot_records()
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        schema = mock_create.return_value.schema.return_value
        schema.rpc.return_value.execute.return_value.data = 1

        result = upload_tier_a_snapshot(records, "https://x.supabase.co", "sb_secret")

        assert result == (100, 1)
        names = [rpc_call.args[0] for rpc_call in schema.rpc.call_args_list]
        assert names == ["upsert_font"] * 100 + ["sync_tier_a_fonts"]
        assert schema.rpc.call_args_list[-1] == call(
            "sync_tier_a_fonts",
            {"p_active_slugs": [f"font-{i:03d}" for i in range(100)]},
        )


def test_upload_tier_a_snapshot_skips_sync_after_upsert_failure():
    records = _snapshot_records()
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        schema = mock_create.return_value.schema.return_value
        schema.rpc.return_value.execute.side_effect = [None, RuntimeError("boom")]

        with pytest.raises(RuntimeError, match="boom"):
            upload_tier_a_snapshot(records, "https://x.supabase.co", "sb_secret")

        names = [rpc_call.args[0] for rpc_call in schema.rpc.call_args_list]
        assert names == ["upsert_font", "upsert_font"]


def test_upload_tier_a_snapshot_rejects_fewer_than_100_before_connecting():
    with patch("fontagit_pipeline.uploader.create_client") as mock_create:
        with pytest.raises(ValueError, match="100종 미만"):
            upload_tier_a_snapshot(
                _snapshot_records(99), "https://x.supabase.co", "sb_secret"
            )

        mock_create.assert_not_called()
```

- [ ] **Step 2: RED 확인**

Run:

```bash
cd apps/pipeline
uv run pytest tests/test_uploader.py -v -k tier_a_snapshot
```

Expected: import 오류 또는 `upload_tier_a_snapshot` 미정의로 FAIL.

- [ ] **Step 3: 최소 구현 작성**

`uploader.py`에서 기존 반복을 내부 함수로 추출하고 전용 함수를 추가한다.

```python
_MIN_TIER_A_SNAPSHOT_SIZE = 100


def _upload_records(schema: Any, records: list[FontRecord]) -> int:
    count = 0
    for rec in records:
        try:
            rpc_params: dict[str, Any] = {
                "p_font": build_font_row(rec),
                "p_aliases": build_alias_rows(rec.aliases),
            }
            schema.rpc("upsert_font", rpc_params).execute()
        except Exception:
            logger.error("업로드 실패(중단): slug=%s", rec.slug)
            raise
        count += 1
    return count


def upload_records(records: list[FontRecord], url: str, secret_key: str) -> int:
    """레코드를 부분 업로드한다. stale 폰트 상태는 변경하지 않는다."""
    client = create_client(url, secret_key)
    count = _upload_records(client.schema("fontagit"), records)
    logger.info("업로드 완료: %d개", count)
    return count


def _validate_tier_a_snapshot(records: list[FontRecord]) -> list[str]:
    if any(rec.source_tier != "A" for rec in records):
        raise ValueError("전체 스냅샷에는 Tier A 레코드만 허용됩니다")
    slugs = [rec.slug for rec in records]
    if any(not slug.strip() for slug in slugs):
        raise ValueError("전체 스냅샷에 빈 slug가 있습니다")
    unique_slugs = sorted(set(slugs))
    if len(unique_slugs) != len(slugs):
        raise ValueError("전체 스냅샷에 중복 slug가 있습니다")
    if len(unique_slugs) < _MIN_TIER_A_SNAPSHOT_SIZE:
        raise ValueError(
            f"active Tier A가 100종 미만입니다: {len(unique_slugs)}"
        )
    return unique_slugs


def upload_tier_a_snapshot(
    records: list[FontRecord], url: str, secret_key: str
) -> tuple[int, int]:
    """검증된 전체 Tier A 스냅샷을 업로드하고 stale published를 draft 처리한다."""
    active_slugs = _validate_tier_a_snapshot(records)
    client = create_client(url, secret_key)
    schema = client.schema("fontagit")
    uploaded = _upload_records(schema, records)
    response = schema.rpc(
        "sync_tier_a_fonts", {"p_active_slugs": active_slugs}
    ).execute()
    if not isinstance(response.data, int):
        raise RuntimeError("sync_tier_a_fonts 응답이 정수가 아닙니다")
    logger.info("Tier A stale draft 완료: %d개", response.data)
    return uploaded, response.data
```

- [ ] **Step 4: GREEN 확인**

Run:

```bash
cd apps/pipeline
uv run pytest tests/test_uploader.py -v
uv run pytest -q
```

Expected: uploader 테스트와 전체 테스트 모두 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/uploader.py apps/pipeline/tests/test_uploader.py
git commit -m "feat(pipeline): 전체 Tier A 스냅샷 안전 동기화"
```

---

### Task 3: CLI 전체 스냅샷 연결

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/__main__.py`

**Interfaces:**
- Consumes: `upload_tier_a_snapshot(...) -> tuple[int, int]`

- [ ] **Step 1: CLI 호출 교체**

import를 `upload_records`에서 `upload_tier_a_snapshot`으로 바꾸고 업로드 블록을 아래처럼 수정한다.

```python
try:
    uploaded, drafted = upload_tier_a_snapshot(
        doc.fonts, settings.supabase_url, settings.supabase_secret_key
    )
except Exception as exc:  # 외부 경계
    logger.error("Supabase 업로드 실패: %s", exc.__class__.__name__)
    return 3
logger.info(
    "업로드 %d개(공개 %d개, stale draft %d개)",
    uploaded,
    len(published),
    drafted,
)
```

이 부분은 값을 전달하고 종료 코드를 매핑하는 얇은 CLI 래퍼라 별도 테스트를 추가하지 않는다. 핵심 순서와 실패 차단은 Task 2의 3개 서비스 테스트가 검증한다.

- [ ] **Step 2: 전체 검증**

Run:

```bash
cd apps/pipeline
uv run pytest -q
uv run ruff check .
uv run mypy src
```

Expected: 테스트 0 failures, ruff 오류 0, mypy 오류 0.

- [ ] **Step 3: Commit**

```bash
git add apps/pipeline/src/fontagit_pipeline/__main__.py
git commit -m "feat(pipeline): CLI를 Tier A 전체 동기화에 연결"
```

---

### Task 4: dev 마이그레이션 적용·재적재·전수 검증

**Files:**
- Modify: `docs/progress.md`

**Interfaces:**
- Consumes: `apps/pipeline/.env`, 루트 `.env.sandbox`, migration 0005, Task 2~3 코드
- Environment: dev `zgxtfcpiokhkcrywlxmc` only

- [ ] **Step 1: dev DB 기준값 확인**

psql로 published/total, Tier B/C 상태, `Urbanist`/`Geist` 상태를 조회해 로그로 보관한다. 예상 시작값은 published 131, total 137, Urbanist/Geist published다.

- [ ] **Step 2: migration 0005를 dev에 적용**

루트에서 환경을 로드하고 pooler로 실행한다. 비밀번호 값은 출력하지 않는다.

```bash
set -a
source apps/pipeline/.env
source .env.sandbox
set +a
host="aws-0-${SUPABASE_PROJECT_REGION}.pooler.supabase.com"
conn="host=${host} port=5432 dbname=postgres user=postgres.${SUPABASE_PROJECT_ID} sslmode=require connect_timeout=10"
PGPASSWORD="$supabase_password" psql -X "$conn" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/0005_sync_tier_a_fonts.sql
```

Expected: `CREATE FUNCTION`, `REVOKE`, `GRANT`, `COMMIT`, exit 0.

- [ ] **Step 3: DB 안전장치 실증**

아래 두 호출은 오류로 끝나야 한다.

```sql
select fontagit.sync_tier_a_fonts(
  array(select 'guard-' || g from generate_series(1, 99) as g)
);

select fontagit.sync_tier_a_fonts(
  array(
    select slug from fontagit.fonts
    where source_tier='A' and status='published'
    order by slug limit 100
  )
);
```

첫 호출은 `100종 미만`, 두 번째는 `stale ... 5종 초과` 오류여야 한다. 호출 전후 published/total과 Tier B/C 상태가 같아야 한다.

- [ ] **Step 4: 전체 테스트 후 파이프라인 재적재**

```bash
cd apps/pipeline
uv run pytest -q
uv run python -m fontagit_pipeline
```

Expected: exit 0, 업로드 136개, 공개 130개, stale draft 1개.

- [ ] **Step 5: dev 완료 기준 전수 검증**

검증 항목:

1. DB published 130, total 137.
2. `Urbanist=draft`, `Geist=published`.
3. 현재 `tier-a.json` published Tier A slug와 DB published Tier A slug 차이 0.
4. name_ko 31종, 한글 alias 보유 32종.
5. 한글 38종 name_ko+alias_norm 전수 대조 차이 0.
6. 라틴 published 92종 name_ko null.
7. 재적재 전후 공통 라틴 slug 내용 차이 0.
8. Tier B/C 상태 변화 0.
9. prod 쓰기 0.

- [ ] **Step 6: progress 기록과 Commit**

`docs/progress.md` 최상단 진행 기록에 Slice 0.5 완료, 테스트 수, DB 수치, Urbanist→Geist 변동, stale 안전장치 검증 결과를 추가한다.

```bash
git add docs/progress.md
git commit -m "docs: Slice 0.5 dev 재적재 검증 완료"
```

---

## Self-Review

- 설계 Critical 3건: 부분 응답 대량 비공개(Task 1 DB 이중 가드 + Task 2 사전 검증), 일반 업로드 오용(Task 2 인터페이스 분리), 기존 완료 기준 충돌(Task 4 현재 스냅샷 기준 검증) 모두 추적됨.
- 설계 Warning 2건: 마이그레이션 번호는 상위 문서에서 0005~0008로 정리 완료, 재등장 status는 기존 라이선스 판정에 맡김.
- 테스트는 핵심 서비스 happy path 1개 + 치명적 edge 2개로 총 3개다.
- prod DB 적용 단계가 없고 dev ref를 명시했다.
- 미완성 표식 없음.

**Plan Version:** 1.0 | **Status:** Ready for Implementation | **Date:** 2026-07-16
