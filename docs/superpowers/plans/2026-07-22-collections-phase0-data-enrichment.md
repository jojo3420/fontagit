# 컬렉션 확장 0단계: 데이터 정비(굵기+태그) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 눈누 Tier B 1,110종의 스타일/무드 태그(tags)와 굵기(weights)를 신 감사(audit) 파이프라인으로 fonts 테이블에 채워, /collections 자동화와 /fonts 섹션 균형의 공통 데이터 토대를 만든다.

**Architecture:** 신규 파이프라인을 만들지 않는다. 이미 존재하는 감사 경로(`audit_noonnu.py` 추출 → `audit_runner.py` metadata 감사 → `audit_manifest.py` manifest → `apply_font_audit_manifest` RPC 반영)를 사용한다. 유일한 코드 갭은 `_collect_metadata_evidence()`가 눈누 snapshot의 tags를 finding 생성용 extracted dict에 넣지 않는 것으로, 이 한 곳을 연결하면 추출-비교-manifest-적용 사슬이 완성된다. 나머지는 실행 런북이다.

**Tech Stack:** Python 3(pydantic, beautifulsoup4, httpx, pytest), Supabase(PostgREST + RPC, fontagit 스키마), 실행은 Linux 필요.

## Global Constraints

- fonts 쓰기는 오직 `apply_font_audit_manifest` RPC(migration 0018)로만. 직접 UPDATE/PATCH 금지.
- tags/weights finding은 `auto_applicable=False`(needs_review). 자동 승인 금지 — 검수 후 manifest apply.
- `category_ko`는 제약상 {고딕, 명조, 손글씨, 장식}만 허용(migration 0001 `fonts_cat_chk`). 이번 0단계는 category_ko를 바꾸지 않는다(tags/weights만).
- published 폰트는 파이프라인이 건드리지 않는다(기존 안전장치 유지).
- `run_metadata_audit()`는 Linux 전용. mac 개발 환경에서는 Task 1(코드+테스트)까지만 검증 가능, Task 2 이후 대량 실행은 Linux 환경에서 수행.
- dev 조회는 `Accept-Profile: fontagit`, 쓰기 RPC는 fontagit 스키마 대상. dev 타깃은 `zgxtfcpiokhkcrywlxmc.supabase.co`.
- 이 plan은 0단계(데이터 정비)만 다룬다. B단계(자동 컬렉션)와 A단계(태그 컬렉션)는 별도 plan.

---

## Task 0: 정비 전 기준선 스냅샷 (dev/prod 현황)

Codex 듀얼 리뷰 Must(절 11-2 5번) 반영. 정비 전 dev와 prod의 tags/weights 채움률을 기록해, 실행 후 증가를 증거로 확인한다.

**Files:**
- Create: `docs/progress/phase0-baseline-20260722.md` (측정 결과 기록)

**Interfaces:**
- Produces: 기준선 수치(published 총수, weights 채움 수, tags 채움 수) — Task 3 검증이 이 값과 대조.

- [ ] **Step 1: dev 기준선 측정**

`apps/web/.env.local`의 `NEXT_PUBLIC_SUPABASE_ANON_KEY`로 REST 조회(읽기 전용).

Run:
```bash
cd apps/web
ANON=$(grep -E '^NEXT_PUBLIC_SUPABASE_ANON_KEY=' .env.local | head -1 | cut -d= -f2- | tr -d '"'\'' ')
URL=https://zgxtfcpiokhkcrywlxmc.supabase.co
H=(-H "apikey: $ANON" -H "Authorization: Bearer $ANON" -H "Accept-Profile: fontagit")
# published 총수
curl -s -I "$URL/rest/v1/fonts?select=id&status=eq.published" "${H[@]}" -H "Prefer: count=exact" | grep -i content-range
# tags 비어있지 않은 수
curl -s -I "$URL/rest/v1/fonts?select=id&status=eq.published&tags=neq.{}" "${H[@]}" -H "Prefer: count=exact" | grep -i content-range
# weights 비어있지 않은 수
curl -s -I "$URL/rest/v1/fonts?select=id&status=eq.published&weights=neq.{}" "${H[@]}" -H "Prefer: count=exact" | grep -i content-range
```
Expected: 총 1240, tags 채움 0(또는 소수), weights 채움 약 405.

- [ ] **Step 2: prod 기준선 측정 (접근 가능 시)**

prod는 자체호스팅(SSH 터널). 접근 수단이 준비돼 있으면 같은 쿼리를 prod 대상으로 실행. 접근 불가 시 "prod 미측정 — dev 기준으로 진행, 배포 전 재확인"이라고 기록한다(silent skip 금지).

- [ ] **Step 3: 기준선 파일 작성 및 커밋**

측정치를 `docs/progress/phase0-baseline-20260722.md`에 표로 기록.

```bash
git add docs/progress/phase0-baseline-20260722.md
git commit -m "docs: phase0 데이터 정비 전 dev/prod 기준선 기록"
```

---

## Task 1: 눈누 tags를 metadata 감사 evidence에 연결 (코드, TDD)

**Files:**
- Modify: `apps/pipeline/src/fontagit_pipeline/audit_runner.py` (`_collect_metadata_evidence()`, line 662 부근 `extracted` dict 생성 직후)
- Test: `apps/pipeline/tests/test_audit_runner.py`

**Interfaces:**
- Consumes: `audit_noonnu.NoonnuFontSnapshot.tags: list[str]` (audit_noonnu.py:30), 함수 내 지역변수 `parsed`(noonnu 분기에서 `_parse_candidate()`로 생성, line 589)와 `source_kind`(line 604에서 `"noonnu"`).
- Produces: `_collect_metadata_evidence()`가 반환하는 snapshot의 `extracted["tags"]`(눈누 태그 리스트). `audit_metadata.compare_metadata()`가 이를 읽어(audit_metadata.py:350-364) tags FindingDraft를 생성한다.

**배경:** `compare_metadata()`는 이미 `("category","tags")`를 처리하지만(audit_metadata.py:350), `_collect_metadata_evidence()`가 눈누 분기에서 `extracted` dict(audit_runner.py:662, `{**merged.extracted(), ...}`)에 tags를 넣지 않아 finding이 생성되지 않는다. weights는 `merged.extracted()`(파일 @font-face 파싱)에 이미 포함되므로 이 태스크 대상이 아니다.

- [ ] **Step 1: 실패 테스트 작성**

`tests/test_audit_runner.py`에 추가. 기존 metadata 테스트(`test_metadata_findings_keep_current_values_and_saved_evidence`, line 425)의 픽스처 구성 방식(FontTarget, noonnu HTML fixture, monkeypatch로 fetch mock)을 재사용한다. 눈누 소스로 evidence를 수집했을 때 반환 snapshot의 `extracted`에 태그가 담기는지 검증한다.

```python
def test_metadata_evidence_includes_noonnu_tags(monkeypatch, tmp_path):
    # 기존 test_metadata_findings_... 와 동일하게 FontTarget + noonnu HTML fixture 구성.
    # noonnu 상세 HTML에는 a[href^="/index?search="] 태그 링크가 포함되어야 함
    # (tests fixture: noonnu-white-tailed-eagle.html 는 tags=["삐뚤빼뚤"] 를 가짐 - test_audit_noonnu.py:참조).
    snapshot, _merged = _call_collect_metadata_evidence_for_noonnu(  # 기존 테스트의 호출 방식 사용
        target=noonnu_target,
        html_fixture="noonnu-white-tailed-eagle.html",
        monkeypatch=monkeypatch,
    )
    assert snapshot.extracted.get("tags") == ["삐뚤빼뚤"]
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd apps/pipeline && python -m pytest tests/test_audit_runner.py::test_metadata_evidence_includes_noonnu_tags -v`
Expected: FAIL — `snapshot.extracted.get("tags")`가 `None`(현재 tags를 넣지 않음).

- [ ] **Step 3: audit_runner.py 수정 — extracted에 noonnu tags 주입**

`_collect_metadata_evidence()`에서 `extracted = { **merged.extracted(), ... }` 블록(line 662 부근) 생성 직후, 눈누 분기일 때 태그를 주입한다.

```python
        extracted = {
            **merged.extracted(),
            # ... 기존 키(evidence_role, subsets, script_status 등) 유지 ...
        }
        # 눈누 상세 페이지 태그를 finding 생성용 evidence에 연결.
        # compare_metadata()가 extracted["tags"] 를 읽어 tags finding 을 만든다(auto_applicable=False).
        if source_kind == "noonnu" and parsed is not None:
            extracted["tags"] = list(parsed.tags)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd apps/pipeline && python -m pytest tests/test_audit_runner.py::test_metadata_evidence_includes_noonnu_tags -v`
Expected: PASS.

- [ ] **Step 5: 회귀 확인 (기존 metadata 테스트)**

Run: `cd apps/pipeline && python -m pytest tests/test_audit_runner.py tests/test_audit_metadata.py tests/test_audit_noonnu.py -v`
Expected: 전부 PASS (기존 동작 불변, tags 연결만 추가).

- [ ] **Step 6: 커밋**

```bash
git add apps/pipeline/src/fontagit_pipeline/audit_runner.py apps/pipeline/tests/test_audit_runner.py
git commit -m "feat: 눈누 태그를 metadata 감사 evidence에 연결(#collections-phase0)"
```

---

## Task 2: Tier B metadata 감사 실행 (런북, Linux 환경)

코드가 아닌 실행 절차. mac 개발 환경에서는 불가(`run_metadata_audit` Linux 전용) — Linux 환경에서 수행한다.

**Files:**
- Uses: `output/` 감사 아티팩트(생성물), `apps/pipeline` CLI
- Produces: `output/audit/pilot-metadata*.json`(관측/findings), tags-weights finding

**Interfaces:**
- Consumes: Task 1의 tags 연결(없으면 tags finding이 안 생김).
- Produces: metadata findings 아티팩트 — Task 3의 manifest 입력.

- [ ] **Step 1: Tier B bootstrap/seed 준비 확인**

Run: `ls apps/pipeline/output/ | grep -i noonnu`
Expected: `tier-b-noonnu-seed.json`(또는 동등 bootstrap) 존재. 없으면 `python -m fontagit_pipeline noonnu-seed`로 재수집.

- [ ] **Step 2: 크롤링 실패 fallback 정책 확인 (Codex Must 절 11-1 4번)**

`run_metadata_audit`/`_parse_candidate` 경로가 실패 시 (a) 해당 폰트만 건너뛰고 (b) 실패 URL을 로그/아티팩트에 기록하며 (c) 기존 DB 값을 보존하는지 코드로 확인. 미비하면 이 Task를 멈추고 fallback을 먼저 보강(별도 코드 태스크로 승격)한다. robots.txt/SSRF 방어는 기존 `enrich`/`audit_noonnu` 경로에 존재(재확인).

- [ ] **Step 3: 소규모 파일럿(50종) 먼저 실행**

Run:
```bash
cd apps/pipeline
python -m fontagit_pipeline audit-run \
  --bootstrap output/tier-b-noonnu-seed.json \
  --out output/audit \
  --stage metadata \
  --limit 50
```
Expected: `output/audit/`에 metadata 아티팩트 생성, tags/weights finding 포함. 실패율/에러 로그 확인.

- [ ] **Step 4: 파일럿 결과 검수 후 전체 실행**

파일럿에서 tags/weights가 정상 추출됐는지 아티팩트로 확인한 뒤 전체(1,110종) 실행:
```bash
python -m fontagit_pipeline audit-run \
  --bootstrap output/tier-b-noonnu-seed.json \
  --out output/audit \
  --stage metadata
```
Expected: 전 종에 대한 metadata findings. 실패 URL은 기록되고 나머지는 계속 진행(fallback).

---

## Task 3: manifest 생성 + dev 적용 + 검증 (런북)

**Files:**
- Uses: `audit_manifest.py:515 build_manifest()`, `write_manifest_bundle()`(704), `__main__.py:589 main_audit_manifest_apply()`
- Produces: dev fonts 테이블의 tags/weights 채워짐

**Interfaces:**
- Consumes: Task 2의 metadata findings 아티팩트.

- [ ] **Step 1: manifest 번들 생성**

findings를 manifest로 변환(`build_manifest` → `write_manifest_bundle`). CLI 경로가 있으면 사용, 없으면 짧은 스크립트로 호출. 산출: `output/audit/audit-manifest.json` + `.sha256`.

- [ ] **Step 2: manifest 내용 검수 (자동 승인 금지)**

tags/weights 항목을 샘플 검토. 특히 tags가 눈누 원본과 일치하는지, 이상 태그(빈 문자열/과다)가 없는지 확인. Global Constraint: `auto_applicable=False`이므로 사람 승인이 게이트.

- [ ] **Step 3: dev에 적용**

Run:
```bash
cd apps/pipeline
SHA=$(cut -d' ' -f1 output/audit/audit-manifest.json.sha256)
python -m fontagit_pipeline font-audit-manifest apply \
  --manifest output/audit/audit-manifest.json \
  --sha256 output/audit/audit-manifest.json.sha256 \
  --confirm-hash "$SHA" \
  --target dev
```
Expected: RPC가 fonts.tags/fonts.weights를 UPDATE. 적용 건수 로그.

- [ ] **Step 4: dev 반영 검증 (기준선 대조)**

Task 0의 쿼리를 다시 실행해 tags/weights 채움 수가 크게 증가했는지 확인.
Expected: tags 채움 수가 0 → 수백~1,000 수준, weights 채움 수가 405 → 1,000+ 수준으로 증가. 증가폭을 `docs/progress/phase0-baseline-20260722.md`에 추가 기록.

- [ ] **Step 5: category_ko 분포 재확인 (섹션 균형)**

Run: Task 0 방식으로 `category_ko` 분포 조회.
Expected: 고딕 편중은 여전(태그는 category_ko를 안 바꿈). 단 이제 tags로 고딕 세분화가 가능해짐 — A단계 plan의 입력이 준비됨.

- [ ] **Step 6: 커밋 (아티팩트/기록)**

```bash
git add docs/progress/phase0-baseline-20260722.md
git commit -m "docs: phase0 데이터 정비 dev 적용 결과 기록"
```

---

## Task 4: 검수 게이트 및 마무리

**Files:**
- Modify: `docs/superpowers/specs/2026-07-22-collections-expansion-design.md`(절 11-1 4번 fallback 확정 반영 시)

- [ ] **Step 1: 태그 출처 표기 확인 (Codex 절 11-2 9번)**

적용된 tags가 "눈누 원본" 출처임을 감사 finding evidence로 추적 가능한지 확인. 추후 자동추론/사람검수 태그와 구분할 근거를 남긴다.

- [ ] **Step 2: 잔여 실패/미반영 종 목록화**

크롤링 실패 또는 tags 미추출 종을 목록화(silent skip 금지). 재크롤 대상으로 기록.

- [ ] **Step 3: B단계 착수 조건 확인**

0단계 완료 기준: dev fonts의 tags/weights 채움률이 목표(예: tags 70%+, weights 90%+) 도달. 도달 시 B단계 plan(자동 컬렉션) 작성 착수 가능. 미달 시 재크롤 반복.

- [ ] **Step 4: prod 적용 여부 결정 (범위 밖 명시)**

prod 적용은 별도 승인/게이트(`--target prod` + approved-hash). 이 0단계 plan은 dev까지. prod는 검수 완료 후 별도 진행.

---

## 완료 기준 (Definition of Done)

- Task 1 코드 수정 + 테스트가 mac 환경에서 green.
- Task 2~3 실행(Linux)으로 dev fonts의 tags/weights 채움률이 목표 도달, 기준선 대비 증가가 증거로 기록됨.
- 실패 종이 silent skip 없이 목록화됨.
- prod 적용은 미포함(별도 게이트).

## 미해결/후속 (다음 plan으로)

- **B단계 plan**: DB 규칙 엔진(collections에 kind/rule/generated_at), 견고 축 자동 컬렉션. Codex Must(materialize 실패처리, 재빌드 트리거, rule 스키마)는 B단계 plan에서 해소.
- **A단계 plan**: 채워진 tags로 스타일/무드 컬렉션 + /fonts 섹션 균형. 태그 표준화 사전.
- **크롤링 fallback**: Task 2 Step 2에서 미비 판정 시 코드 보강 태스크로 승격.
