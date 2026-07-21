# Tier A OFL prod 승격 구현 계획 (#89 재편)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 `ofl_verify.py`에 `--target prod` + 이중 게이트(google/fonts 공식 확인 + dev verified 교차)를 추가해 prod Tier A OFL 128종을 pending → verified로 승격한다.

**Architecture:** 새 CLI 없이 `ofl_verify.py`의 주입형 순수 함수 구조(fetch → plan → report → apply)를 유지하며 확장. `config.py`에 prod 쓰기 자격증명 경계(`prod_write_credentials`)를 dev 패턴 미러로 추가. 게이트 실패분은 pending 유지(fail-closed).

**Tech Stack:** Python 3.12, pydantic-settings, httpx, pytest(uv 실행), Supabase PostgREST.

**Spec:** `docs/superpowers/specs/2026-07-21-tier-a-url-backfill-design.md`

## Global Constraints

- 작업 디렉터리: 모든 명령은 `apps/pipeline`에서 실행 (`uv run pytest ...`, `uv run python -m ...`)
- prod `--apply`는 **사용자 go/no-go 승인 후에만** 실행 (Task 5는 승인 없이 착수 금지)
- verified 자동 부여는 이중 게이트(공식 OFL 확인 + dev verified 교차) 통과분만
- 시크릿 값(키-비밀번호)을 로그-응답에 원문 출력 금지 (env 키 이름만 언급)
- DB 헤더: 조회 `Accept-Profile: fontagit`, 쓰기 `Content-Profile: fontagit` (apply_update에 기존 존재)
- 기존 dev 동작(`--target dev` 기본값) 무변경 — 기존 테스트 전부 green 유지

---

### Task 1: `config.py::prod_write_credentials()` (TDD)

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/config.py`
- Test: `apps/pipeline/tests/test_config.py`

**Interfaces:**
- Produces: `AuditSettings.prod_write_credentials() -> tuple[str, str]` — (prod_url, prod_secret_key) 반환, allowlist 미승인 시 ValueError. 신규 필드 `supabase_audit_prod_allowlist: str | None`(env `SUPABASE_AUDIT_PROD_ALLOWLIST`)

- [x] **Step 1: 실패하는 테스트 작성** — `tests/test_config.py` 끝에 추가:

```python
def test_prod_write_credentials_requires_settings() -> None:
    """prod URL/키가 없으면 prod 쓰기를 거부한다."""
    with pytest.raises(ValueError, match="SUPABASE_PROD_URL"):
        AuditSettings(_env_file=None).prod_write_credentials()
    with pytest.raises(ValueError, match="SUPABASE_PROD_SECRET_KEY"):
        AuditSettings(
            supabase_prod_url="https://supabase.example.com", _env_file=None
        ).prod_write_credentials()


def test_prod_write_credentials_requires_allowlist() -> None:
    """allowlist 승인 없는 prod origin은 자체호스팅/managed 모두 거부한다."""
    with pytest.raises(ValueError, match="SUPABASE_AUDIT_PROD_ALLOWLIST"):
        AuditSettings(
            supabase_prod_url="https://supabase.example.com",
            supabase_prod_secret_key="prod-key",
            _env_file=None,
        ).prod_write_credentials()
    with pytest.raises(ValueError, match="SUPABASE_AUDIT_PROD_ALLOWLIST"):
        AuditSettings(
            supabase_prod_url="https://prod-ref.supabase.co",
            supabase_prod_secret_key="prod-key",
            supabase_audit_prod_allowlist="other-ref",
            _env_file=None,
        ).prod_write_credentials()


def test_prod_write_credentials_accepts_approved() -> None:
    """allowlist가 origin(자체호스팅) 또는 ref(managed)를 승인하면 통과한다."""
    assert AuditSettings(
        supabase_prod_url="https://supabase.example.com",
        supabase_prod_secret_key="prod-key",
        supabase_audit_prod_allowlist="https://supabase.example.com",
        _env_file=None,
    ).prod_write_credentials() == ("https://supabase.example.com", "prod-key")
    assert AuditSettings(
        supabase_prod_url="https://prod-ref.supabase.co",
        supabase_prod_secret_key="prod-key",
        supabase_audit_prod_allowlist="prod-ref",
        _env_file=None,
    ).prod_write_credentials() == ("https://prod-ref.supabase.co", "prod-key")
```

- [x] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_config.py -v -k prod_write`
Expected: FAIL — `AttributeError: 'AuditSettings' object has no attribute 'prod_write_credentials'`

- [x] **Step 3: 구현** — `config.py`:

(a) `AuditSettings` 필드 목록의 `supabase_audit_dev_allowlist` 아래에 추가:

```python
    supabase_audit_prod_allowlist: str | None = None
```

(b) `prod_public_read_credentials` 메서드 위에 추가:

```python
    def prod_write_credentials(self) -> tuple[str, str]:
        """OFL prod 승격 쓰기 전용 prod 자격증명을 안전하게 반환한다.

        dev 경계와 동일하게 allowlist 명시 승인 없이는 거부한다(fail-closed).
        """
        url = _required_setting(self.supabase_prod_url, "SUPABASE_PROD_URL")
        key = _required_setting(self.supabase_prod_secret_key, "SUPABASE_PROD_SECRET_KEY")
        origin = _https_origin(url, "SUPABASE_PROD_URL")
        approved = _allowlist_items(self.supabase_audit_prod_allowlist)
        ref = _supabase_project_ref(origin)
        if ref is not None:
            if not approved or (ref not in approved and origin not in approved):
                raise ValueError(
                    "SUPABASE_AUDIT_PROD_ALLOWLIST must approve the managed prod URL or project ref"
                )
        else:
            allowed_origins = {
                _https_origin(item, "SUPABASE_AUDIT_PROD_ALLOWLIST") for item in approved
            }
            if not allowed_origins or origin not in allowed_origins:
                raise ValueError(
                    "SUPABASE_AUDIT_PROD_ALLOWLIST must explicitly approve the self-hosted prod origin"
                )
        return url, key
```

(c) `_required_setting`의 에러 메시지를 dev 전용 문구에서 일반화 (기존 테스트는 `SUPABASE_DEV`/`SUPABASE_PROD` prefix 매칭이라 영향 없음):

```python
def _required_setting(value: str | None, name: str) -> str:
    if not value or not value.strip():
        raise ValueError(f"{name} is required for audit writes")
    return value.strip()
```

- [x] **Step 4: 전체 config 테스트 green 확인**

Run: `uv run pytest tests/test_config.py -v`
Expected: 전부 PASS (기존 테스트 포함)

- [x] **Step 5: Commit**

```bash
git add src/fontagit_pipeline/config.py tests/test_config.py
git commit -m "feat: prod 쓰기 자격증명 경계 prod_write_credentials 추가 (#89)"
```

---

### Task 2: 이중 게이트 — `fetch_dev_verified_keys` + `build_report` 교차 검증 (TDD)

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/ofl_verify.py`
- Test: `apps/pipeline/tests/test_ofl_verify.py`

**Interfaces:**
- Consumes: `normalize_family_dir(name_en: str) -> str` (licenses.py, ofl_verify에 이미 import됨)
- Produces:
  - `fetch_dev_verified_keys(client, base: str, headers: dict[str, str]) -> set[str]` — dev의 OFL verified 폰트 name_en 정규화 집합
  - `build_report(candidates, license_map, checked_at, dev_verified_keys: set[str] | None = None) -> dict` — keys가 None이면 기존 동작 그대로(하위 호환), set이면 게이트 2 불일치분을 `{**font, "reason": "dev-verified-mismatch"}`로 unconfirmed에 분류

- [x] **Step 1: 실패하는 테스트 작성** — `tests/test_ofl_verify.py` 끝에 추가 (import에 `fetch_dev_verified_keys` 추가):

```python
class TestFetchDevVerifiedKeys:
    """dev verified 교차 게이트용 조회."""

    def test_returns_normalized_name_set(self) -> None:
        """name_en을 정규화한 집합을 반환하고 null 이름은 건너뛴다."""
        client = MagicMock()
        client.get.return_value.json.return_value = [
            {"name_en": "Noto Sans KR"},
            {"name_en": "Roboto"},
            {"name_en": None},
        ]
        keys = fetch_dev_verified_keys(client, "https://dev.example/rest/v1", {})
        assert keys == {"notosanskr", "roboto"}
        called_url = client.get.call_args[0][0]
        assert "license_type=eq.OFL" in called_url
        assert "license_status=eq.verified" in called_url


class TestBuildReportCrossCheck:
    """게이트 2(dev verified 교차) 분류."""

    def test_mismatch_goes_to_unconfirmed_with_reason(self) -> None:
        """공식 OFL이어도 dev verified에 없으면 예외로 분류한다(fail-closed)."""
        license_map = {"notosanskr": "OFL", "roboto": "OFL"}
        fonts = [{"name_en": "Noto Sans KR"}, {"name_en": "Roboto"}]
        report = build_report(
            fonts, license_map, "2026-07-21T00:00:00+00:00",
            dev_verified_keys={"notosanskr"},
        )
        assert report["counts"]["confirmed"] == 1
        assert report["confirmed"][0]["name_en"] == "Noto Sans KR"
        assert report["unconfirmed"][0]["name_en"] == "Roboto"
        assert report["unconfirmed"][0]["reason"] == "dev-verified-mismatch"

    def test_none_keys_keeps_existing_behavior(self) -> None:
        """dev_verified_keys=None(기본)은 기존 dev 동작과 동일하다."""
        license_map = {"notosanskr": "OFL"}
        fonts = [{"name_en": "Noto Sans KR"}]
        report = build_report(fonts, license_map, "2026-07-21T00:00:00+00:00")
        assert report["counts"]["confirmed"] == 1
        assert "reason" not in report["confirmed"][0]
```

- [x] **Step 2: 실패 확인**

Run: `uv run pytest tests/test_ofl_verify.py -v -k "FetchDevVerified or CrossCheck"`
Expected: FAIL — `ImportError: cannot import name 'fetch_dev_verified_keys'`

- [x] **Step 3: 구현** — `ofl_verify.py`:

(a) `fetch_ofl_candidates` 아래에 추가:

```python
def fetch_dev_verified_keys(
    client: httpx.Client, base: str, headers: dict[str, str]
) -> set[str]:
    """dev에서 OFL verified 폰트의 정규화된 name_en 집합을 조회한다.

    prod 승격 시 게이트 2(dev 교차 확인)의 기준 집합으로 쓴다.

    Args:
        client: httpx.Client 인스턴스
        base: dev REST API base URL
        headers: dev API 헤더

    Returns:
        normalize_family_dir 적용된 name_en 집합
    """
    url = f"{base}/fonts?license_type=eq.OFL&license_status=eq.verified&select=name_en"
    response = client.get(url, headers=headers)
    response.raise_for_status()
    return {
        normalize_family_dir(row["name_en"])
        for row in response.json()
        if row.get("name_en")
    }
```

(b) `build_report` 시그니처와 루프 교체 (docstring의 Args에 dev_verified_keys 설명 1줄 추가):

```python
def build_report(
    candidates: list[dict],
    license_map: dict[str, str],
    checked_at: str,
    dev_verified_keys: set[str] | None = None,
) -> dict:
```

루프 본문:

```python
    for font in candidates:
        proposal = plan_font_update(font, license_map, checked_at)
        if proposal is None:
            unconfirmed.append(font)
            continue
        if (
            dev_verified_keys is not None
            and normalize_family_dir(font.get("name_en", "")) not in dev_verified_keys
        ):
            unconfirmed.append({**font, "reason": "dev-verified-mismatch"})
            continue
        confirmed.append({**font, "proposal": proposal})
```

- [x] **Step 4: 전체 ofl_verify 테스트 green 확인**

Run: `uv run pytest tests/test_ofl_verify.py -v`
Expected: 전부 PASS (기존 테스트 포함 — None 기본값이라 하위 호환)

- [x] **Step 5: Commit**

```bash
git add src/fontagit_pipeline/ofl_verify.py tests/test_ofl_verify.py
git commit -m "feat: OFL 승격 이중 게이트 - dev verified 교차 확인 (#89)"
```

---

### Task 3: `--target dev|prod` CLI 배선 + env allowlist

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/ofl_verify.py` (main + argparse)
- Modify: `apps/web/.env.production` (env 키 1줄 추가)

**Interfaces:**
- Consumes: Task 1의 `prod_write_credentials()`, Task 2의 `fetch_dev_verified_keys`/`build_report(dev_verified_keys=...)`
- Produces: `main(apply: bool = False, report_path: str | None = None, target: str = "dev") -> int`

- [x] **Step 1: main() 확장** — 자격증명 로드 블록(`dev_url, dev_key = ...`부터 `headers = {...}`까지)을 교체:

```python
        # 타깃별 쓰기 자격증명. prod는 게이트 2용 dev 자격증명도 함께 로드한다.
        settings = load_audit_settings()
        if target == "prod":
            write_url, write_key = settings.prod_write_credentials()
            dev_url, dev_key = settings.dev_write_credentials()
        else:
            write_url, write_key = settings.dev_write_credentials()
        base = write_url.rstrip("/") + "/rest/v1"
        headers = {
            "apikey": write_key,
            "Authorization": f"Bearer {write_key}",
            "Accept-Profile": "fontagit",
        }
```

`main` 시그니처/docstring 갱신:

```python
def main(
    apply: bool = False,
    report_path: str | None = None,
    target: str = "dev",
) -> int:
```

report_path 기본값 계산 (try 블록 첫 줄에):

```python
        if report_path is None:
            report_path = (
                "output/audit/ofl-verify-report.json"
                if target == "dev"
                else "output/audit/ofl-verify-prod-report.json"
            )
```

`candidates = fetch_ofl_candidates(...)` 다음, `report = build_report(...)` 호출 전에 게이트 2 조회 추가하고 build_report에 전달:

```python
            dev_verified_keys = None
            if target == "prod":
                dev_base = dev_url.rstrip("/") + "/rest/v1"
                dev_headers = {
                    "apikey": dev_key,
                    "Authorization": f"Bearer {dev_key}",
                    "Accept-Profile": "fontagit",
                }
                dev_verified_keys = fetch_dev_verified_keys(client, dev_base, dev_headers)
                logger.info("dev verified 교차 기준 %d종 로드", len(dev_verified_keys))

            checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            report = build_report(candidates, license_map, checked_at, dev_verified_keys)
```

- [x] **Step 2: argparse 배선** — `--report-path`의 default를 `None`으로 바꾸고 `--target` 추가:

```python
    parser.add_argument(
        "--report-path",
        default=None,
        help="결과 report JSON 저장 경로 (기본: 타깃별 자동)",
    )
    parser.add_argument(
        "--target",
        choices=["dev", "prod"],
        default="dev",
        help="승격 대상 DB (prod는 dev verified 교차 게이트 활성화)",
    )

    args = parser.parse_args()
    sys.exit(main(apply=args.apply, report_path=args.report_path, target=args.target))
```

- [x] **Step 3: env allowlist 추가** — 리포지토리 루트에서 (값을 화면에 출력하지 않고 SUPABASE_PROD_URL 값을 복사):

```bash
grep -q '^SUPABASE_AUDIT_PROD_ALLOWLIST=' apps/web/.env.production || \
  sed -n 's/^SUPABASE_PROD_URL=/SUPABASE_AUDIT_PROD_ALLOWLIST=/p' apps/web/.env.production >> apps/web/.env.production
grep -c '^SUPABASE_AUDIT_PROD_ALLOWLIST=' apps/web/.env.production
```

Expected: `1`

- [x] **Step 4: 회귀 확인 (전체 스위트 + dev dry-run 무변경 확인)**

Run: `uv run pytest -q`
Expected: 전부 PASS

Run: `uv run python -m fontagit_pipeline.ofl_verify` (dev dry-run, apply 없음)
Expected: exit 0, "confirmed=132, unconfirmed=0" 로그 (후보는 `license_type=eq.OFL` 132종만 조회됨 — 이미 verified라 재확인만 됨)

- [x] **Step 5: Commit** (.env는 gitignore 대상이라 커밋 안 됨 — 코드만)

```bash
git add src/fontagit_pipeline/ofl_verify.py
git commit -m "feat: ofl_verify --target prod 배선 - 이중 게이트 + 타깃별 리포트 (#89)"
```

---

### Task 4: prod dry-run + 리포트 검증 (쓰기 없음)

**Files:** 없음 (실행-검증만)

- [x] **Step 1: prod dry-run 실행**

Run: `uv run python -m fontagit_pipeline.ofl_verify --target prod`
Expected: exit 0, 리포트 `output/audit/ofl-verify-prod-report.json` 생성. 예상치: confirmed=128, unconfirmed=8 (Apache-2.0 1, UFL 1, license_type null 6 — 게이트 1에서 걸러짐)

- [x] **Step 2: 리포트 검증**

```bash
jq '.counts' output/audit/ofl-verify-prod-report.json
jq -r '.unconfirmed[] | "\(.name_en)\t\(.reason // "not-ofl")"' output/audit/ofl-verify-prod-report.json
jq -r '.confirmed[0].proposal | {license_status, license_source_kind, license_source_url}' output/audit/ofl-verify-prod-report.json
```

Expected: counts `{confirmed: 128, unconfirmed: 0, total: 128}` — 비-OFL 8종(Apache-2.0/UFL/null)은 `license_type=eq.OFL` 조회에 아예 포함되지 않아 리포트 밖(후속 이슈 범위). unconfirmed>0이면 게이트 1/2 실패 건이므로 사유 확인. proposal의 license_status="verified", license_source_kind="official", license_source_url이 `https://github.com/google/fonts/tree/main/ofl/...` 형식.
confirmed가 128이 아니거나 예상 밖 예외가 있으면 **중단하고 사용자에게 보고**.

- [x] **Step 3: go/no-go 승인 요청 (게이트 — 승인 없이 Task 5 착수 금지)**

사용자에게 보고: confirmed N종 / 예외 M종(이름-사유 목록) 요약 제시 후 prod `--apply` 실행 승인을 명시적으로 받는다.

---

### Task 5: prod --apply + 쓰기→읽기 재검증 (사용자 승인 후에만)

**Files:** 없음 (실행-검증만)

- [x] **Step 1: apply 실행**

Run: `uv run python -m fontagit_pipeline.ofl_verify --target prod --apply`
Expected: exit 0, "PATCH 완료: 성공=128, 실패=0" 로그. 실패>0이면 exit 1 — 실패 건 로그 확인 후 사용자 보고.

- [x] **Step 2: 쓰기→읽기 재검증** — 리포지토리 루트에서 prod 재조회(읽기 전용):

```bash
cd apps/web && set -a && . ./.env.production && set +a && cd ../..
curl -s "${SUPABASE_PROD_URL%/}/rest/v1/fonts?source_tier=eq.A&select=license_status" \
  -H "apikey: $SUPABASE_PROD_SECRET_KEY" -H "Authorization: Bearer $SUPABASE_PROD_SECRET_KEY" \
  -H "Accept-Profile: fontagit" | jq 'group_by(.license_status)|map({(.[0].license_status): length})|add'
```

Expected: `{"pending": 8, "verified": 128}` (백필 전: pending 136)

- [x] **Step 3: 결과 보고 + 후속 이슈 등록**

- 사용자에게 결과 보고 (before/after 카운트, 예외 8종 목록)
- 후속 이슈 2건 등록: (1) 비-OFL 8종 개별 검수, (2) Tier A download_url 백필 (dev/prod 전체 null, published 서빙 영향 확인 포함)
