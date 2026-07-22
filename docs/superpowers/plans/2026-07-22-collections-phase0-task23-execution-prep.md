# 컬렉션 0단계 Task 2~3 실행 준비 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 눈누 Tier B 1,110종의 tags/weights를 도커(Linux) 환경에서 감사 실행 → manifest 생성 → dev fonts에 반영할 수 있도록, 선행 코드 준비 3건(Docker 이미지, manifest 생성 CLI, P0 안전장치)을 갖춘 뒤 파일럿부터 실행한다.

**Architecture:** 신 감사 파이프라인(`audit_noonnu` → `audit_runner` → `audit_manifest` → `apply_font_audit_manifest` RPC)은 대부분 구현돼 있다. 갭은 세 가지: (1) 실행 환경이 Linux 전용인데 호스트가 mac → Docker Linux 컨테이너로 우회, (2) audit-run 산출물(findings)을 apply 입력(manifest)으로 변환하는 CLI 부재 → `build_manifest` 함수를 래핑하는 서브커맨드 신규, (3) 크롤링 재시도/backoff 미구현 → 대량 실행 전 보강. 이후 파일럿(50종) → 전체(1,110종) → dev apply.

**Tech Stack:** Python 3.12(uv, pydantic, fonttools, httpx, beautifulsoup4, supabase), Docker(Linux 컨테이너), Supabase RPC(fontagit 스키마).

## Global Constraints

- `run_metadata_audit()`는 Linux 전용(`audit_runner.py:450` `sys.platform.startswith("linux")` 체크, `__main__.py:484` 이중 게이트). mac에서는 Docker Linux 컨테이너로만 실행.
- fonts 쓰기는 `apply_font_audit_manifest` RPC(migration 0018)로만. 낙관적 잠금(before 값 + `updated_at` + 화이트리스트, `0018.sql:293-300`)이 이미 구현됨 — 감사 후 DB 변경 시 "stale" 예외로 거부.
- tags/weights finding은 `auto_applicable=False`. dev 먼저, prod는 별도 게이트(`--approved-hash`, `--approval-id`).
- 크롤링: robots.txt 준수(`noonnu_seed.py:25,290-319`), rate limit 1.5초(`noonnu_seed.py:28`), User-Agent `FontAgitSeedBot`.
- env는 `apps/web/.env.local`(dev) + `.env.production`에서 자동 로드(`config.py`). dev 쓰기 = `SUPABASE_DEV_URL` + `SUPABASE_DEV_SECRET_KEY`.
- bootstrap/seed 파일은 이미 존재: `apps/pipeline/output/tier-b-noonnu-seed.json`(재수집 불필요).
- 이 plan은 0단계 Task 2~3의 실행 준비다. 코드 갭 해소(Task A~C) 후 실행(Task D~E).

---

## Task A: 파이프라인 Docker 이미지 구축

**Files:**
- Create: `apps/pipeline/Dockerfile` (또는 `Dockerfile.pipeline`)
- Create: `apps/pipeline/.dockerignore`

**Interfaces:**
- Produces: `fontagit-pipeline:local` 이미지 — Task D~E가 `docker run`으로 사용.

- [ ] **Step 1: Dockerfile 작성**

curl과 fontconfig(fonttools 폰트 파싱 대비)를 포함한 Linux 베이스 + uv로 의존성 설치.

```dockerfile
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl fontconfig ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir uv
WORKDIR /repo/apps/pipeline
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
ENV PATH="/repo/apps/pipeline/.venv/bin:$PATH"
```

- [ ] **Step 2: .dockerignore 작성**

```
.venv
output
__pycache__
*.pyc
```

- [ ] **Step 3: 이미지 빌드 검증**

Run: `docker build -t fontagit-pipeline:local -f apps/pipeline/Dockerfile apps/pipeline`
Expected: 빌드 성공.

- [ ] **Step 4: 컨테이너에서 Linux + import 확인**

Run: `docker run --rm fontagit-pipeline:local python -c "import sys, fontagit_pipeline; print(sys.platform)"`
Expected: `linux` 출력, import 에러 없음.

- [ ] **Step 5: 커밋**

```bash
git add apps/pipeline/Dockerfile apps/pipeline/.dockerignore
git commit -m "chore: 파이프라인 Linux Docker 이미지 (Task 2~3 실행용)"
```

---

## Task B: manifest 생성 CLI 신규

`audit-run`은 audit report(findings)를 산출하지만(`write_audit_artifacts`, `audit_runner.py:1251`), `manifest apply`(`__main__.py:589,884-896`)는 manifest(entries with before/after)를 입력받는다. `build_manifest`(`audit_manifest.py:515`)와 `write_manifest_bundle`(704) 함수는 있으나 CLI에서 호출되지 않는다. 이 변환 서브커맨드를 만든다.

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/__main__.py` (서브커맨드 `font-audit-manifest build` 추가)
- Modify: `apps/pipeline/src/fontagit_pipeline/audit_manifest.py` (필요 시 헬퍼)
- Test: `apps/pipeline/tests/test_audit_manifest.py`

**Interfaces:**
- Consumes: `build_manifest(...)`(audit_manifest.py:515), `write_manifest_bundle(bundle, out)`(704) — **먼저 두 함수 시그니처를 정독**해 입력(audit report/findings 경로 또는 객체)과 출력(ManifestBundle) 형식을 확인할 것.
- Produces: `manifest.json` + `.sha256` — Task E의 `manifest apply` 입력.

- [ ] **Step 1: build_manifest / write_manifest_bundle 시그니처 정독**

`audit_manifest.py:515`와 `:704`를 읽어 입력 파라미터(findings 리스트? audit report 파일?)와 반환(ManifestBundle, ManifestPaths)을 확정한다. `manifest apply`가 읽는 manifest 스키마(entries: before/after/expected_updated_at)와 매핑을 파악한다.

- [ ] **Step 2: 실패 테스트 작성**

`tests/test_audit_manifest.py`에 audit-run 산출물 형태의 입력을 주고 `build_manifest`가 apply 가능한 manifest(entries에 before/after 포함)를 만드는지 검증. 정확한 픽스처는 기존 `test_audit_manifest.py`(있으면) 또는 `audit_manifest.py` 내 타입 참조.

```python
def test_build_manifest_from_audit_findings_produces_apply_ready_entries():
    # audit-run findings(또는 report) → build_manifest → bundle
    # bundle.manifest.entries[0] 에 field_name, before, after, expected_updated_at 존재 검증
    ...
```

- [ ] **Step 3: 실패 확인**

Run: `docker run --rm -v $(pwd):/repo fontagit-pipeline:local python -m pytest tests/test_audit_manifest.py -v` (또는 호스트에서 fonttools 설치돼 있으면 직접)
Expected: FAIL.

- [ ] **Step 4: `font-audit-manifest build` 서브커맨드 구현**

`__main__.py`의 `manifest_subparsers`(line 884 부근)에 `build` 서브커맨드 추가. `--report <audit-run json>` → `build_manifest` → `write_manifest_bundle(--out)`. 기존 `apply` 서브커맨드 패턴(`main_audit_manifest_apply`, line 589)을 따른다.

- [ ] **Step 5: 통과 확인 + 커밋**

Run: 같은 pytest → PASS.
```bash
git add apps/pipeline/src/fontagit_pipeline/__main__.py apps/pipeline/src/fontagit_pipeline/audit_manifest.py apps/pipeline/tests/test_audit_manifest.py
git commit -m "feat: audit-run findings를 manifest로 변환하는 build 서브커맨드"
```

---

## Task C: P0 크롤링 안전장치 보강 (재시도/backoff + 오류 분화)

현재 크롤링은 rate limit/robots/fallback(skip and continue)은 있으나(`noonnu_seed.py:337,378`), 재시도/backoff가 없고 일시적 오류(429/503)와 영구 오류(4xx)를 구분하지 않는다(`noonnu_seed.py:377` httpx.HTTPError 일괄 skip). 1,110종 대량 실행 시 네트워크 일시 장애로 폰트가 대량 누락될 수 있다.

**Files:**
- Modify: 크롤링 fetch 경로(`audit_http.py` 또는 `audit_runner.py`의 fetch 지점, `audit_http.py:23,276-280` curl 호출부)
- Test: `apps/pipeline/tests/test_audit_http.py`(또는 해당 테스트)

**Interfaces:**
- Produces: fetch 함수가 429/503/타임아웃 시 지수 backoff로 최대 N회 재시도, 4xx는 즉시 skip. 재시도 소진 시 실패 URL 기록 후 continue(기존 fallback 유지).

- [ ] **Step 1: fetch 경로와 오류 타입 정독**

`audit_http.py`의 curl 호출부(23, 276-280)와 예외 타입(FetchTimeoutError/NetworkFetchError 등)을 확인. 어디에 재시도를 넣을지 결정.

- [ ] **Step 2: 실패 테스트 작성**

503을 2회 반환 후 200을 주는 mock으로 재시도 성공을, 404는 재시도 없이 즉시 실패를 검증.

```python
def test_fetch_retries_on_503_then_succeeds(): ...
def test_fetch_no_retry_on_404(): ...
```

- [ ] **Step 3: 지수 backoff 재시도 구현**

429/503/타임아웃 → `time.sleep(base * 2**attempt)`로 최대 N회(예: 3회) 재시도. 4xx(429 제외) → 즉시 실패. 재시도 소진 → 실패 URL 로그 + 기존 skip 경로.

- [ ] **Step 4: 통과 확인 + 커밋**

Run: `docker run --rm -v $(pwd):/repo fontagit-pipeline:local python -m pytest tests/test_audit_http.py -v` → PASS.
```bash
git commit -m "feat: 크롤링 재시도/backoff + 일시적 오류(429/503) 분화"
```

---

## Task D: 파일럿 50종 감사 실행 (도커 런북)

**Interfaces:**
- Consumes: Task A 이미지, Task B build CLI, Task C 안전장치, bootstrap 파일.

- [ ] **Step 1: 파일럿 감사 실행**

Run:
```bash
docker run --rm \
  -e SUPABASE_DEV_URL -e SUPABASE_DEV_SECRET_KEY -e SUPABASE_PROD_URL \
  -v $(pwd):/repo -w /repo/apps/pipeline fontagit-pipeline:local \
  python -m fontagit_pipeline font-audit-run --stage metadata \
    --bootstrap output/tier-b-noonnu-seed.json \
    --limit 50 --out output/audit/pilot-metadata.json
```
Expected: `output/audit/pilot-metadata*.json` 생성, tags/weights finding 포함, 실패 URL은 기록되고 나머지 계속. (env는 `--env-file` 또는 export로 주입)

- [ ] **Step 2: 산출물 검수**

pilot-metadata.json에서 tags/weights finding이 눈누 원본과 맞는지, 빈 태그 삭제 제안이 없는지(0단계 Task 1 가드 확인) 샘플 검토.

- [ ] **Step 3: manifest 생성 (Task B CLI)**

Run: `... font-audit-manifest build --report output/audit/pilot-metadata.json --out output/audit/pilot-manifest.json`
Expected: `pilot-manifest.json` + `.sha256`.

- [ ] **Step 4: dev apply (파일럿)**

Run:
```bash
... font-audit-manifest apply --manifest output/audit/pilot-manifest.json \
    --sha256 output/audit/pilot-manifest.json.sha256 --target dev \
    --confirm-hash <sha256>
```
Expected: 50종 tags/weights UPDATE. 낙관적 잠금 통과.

- [ ] **Step 5: dev 검증**

REST로 tags/weights 채움 증가 확인(0단계 plan Task 0 쿼리 방식). 파일럿 결과로 P0 안전장치 충분성 판단.

---

## Task E: 전체 1,110종 실행 + dev 반영

- [ ] **Step 1: 전체 감사 실행**

파일럿이 성공하면 `--limit` 제거(또는 1110)로 전체 실행. 실패율/재시도 로그 모니터링.

- [ ] **Step 2: manifest 생성 → 검수 → dev apply**

Task D Step 3~4 반복(전체 대상). 검수는 자동 정규화 + 샘플 10%.

- [ ] **Step 3: 최종 검증 + 기록**

dev fonts의 tags/weights 채움률이 목표(tags 70%+, weights 90%+) 도달 확인. `docs/progress/`에 결과 기록. B단계 plan 착수 조건 충족 판단.

- [ ] **Step 4: prod 적용은 별도 게이트**

prod는 이 plan 범위 밖. 검수 완료 후 `--target prod` + approved-hash로 별도 진행.

---

## 완료 기준

- Task A~C: Docker 이미지 빌드 성공, manifest build CLI + P0 안전장치 테스트 green.
- Task D: 파일럿 50종이 도커에서 감사 → manifest → dev apply까지 통과, 검증됨.
- Task E: 전체 1,110종 dev 반영, 채움률 목표 도달, 실패 종 목록화(silent skip 금지).

## 미해결/후속

- **manifest 스키마 정확 매핑**: Task B Step 1에서 `build_manifest` 입력/출력을 정독해 audit-run 산출물과 apply 입력 사이 필드 매핑을 확정해야 함(현재 미검증).
- **B단계 plan**: 채워진 tags/weights로 DB 규칙 엔진 + 자동 컬렉션. Codex 듀얼리뷰 Must(materialize 실패처리, 재빌드 트리거, rule 스키마)는 거기서 해소.
