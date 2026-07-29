# 세션 핸드오프 - 2026-07-29 11:35 KST

> **모드**: superpowers (spec + plan)
> **Feature**: 눈누 official_url 오염 검증 및 정정 (#150, #148)
> **이전 세션 종결 사유**: 사용자 요청 (다음 세션 인계)

## 한 줄 요약

눈누에서 수집한 폰트 172종의 `official_url`이 눈누 홍보 계정으로 오염된 문제를 다룬다. 검출 도구(PR #151)와 manifest 허용 마이그레이션(0026, dev 적용 완료)까지 끝냈고, 남은 일은 **스캔 결과를 감사 finding으로 적재해 실제 데이터를 정정하는 것**이다.

---

## 다음 세션이 가장 먼저 할 일

1. **이 파일을 읽는다**
2. **설계와 계획을 읽는다**
   - `docs/superpowers/specs/2026-07-28-noonnu-official-url-audit-design.md`
   - `docs/superpowers/plans/2026-07-28-noonnu-official-url-audit.md` (체크박스 27/49)
3. **재스캔 결과를 확인한다**: `apps/pipeline/output/noonnu-url-scan-report-v2.json`의 `summary`
4. **아래 "다음 단계"의 MUST부터 시작한다**

⚠️ 브랜치가 둘로 나뉘어 있다. 현재 작업 브랜치는 `feat/noonnu-url-audit-task7`이고, PR #151은 `feat/noonnu-url-audit-150`이다. task7이 150 위에 쌓여 있다.

---

## 작업 컨텍스트

### 사용자 원본 요청

> github 이슈 내용 확인 후 관련도 깊은 순서대로 조치하기 (이슈 트래킹 #62)

이후 #148 -> #150으로 좁혀졌고, Task 5~8(마이그레이션 조사, dev/prod 정정)을 step by step으로 진행하라는 지시를 받았다.

### 사용자 제약 및 결정 (반드시 준수)

🔴 **반드시**
- prod DB 쓰기는 실행 전 쿼리 전문을 보여 승인받는다 (2026-07-29 PreToolUse 가드 훅이 제거돼 기술적 차단이 없다)
- `license_verified`는 오염 172종 전부 `false`로 강등한다 (사용자 결정)
- 정정 방식은 "판정 로직 보강 후 재스캔" 방식을 택했다 (사용자 결정, 호스트 단위 승인이나 개별 검수가 아님)
- nullify는 이번 범위가 아니다. `fonts.official_url`이 NOT NULL이라 불가능하며, 필요해지면 0027(제약 완화 + 잠금 coalesce + 웹 화면 영향)로 별도 진행한다

---

## 결정 사항 (뒤집지 말 것)

| # | 결정 | 근거 |
|---|---|---|
| 1 | 오염 검사를 일치 판정보다 먼저 수행 | 두 값이 똑같이 오염돼도 `match`로 통과하던 구조. Codex 리뷰 Must-fix |
| 2 | `auto_fix_safe`는 AND 조건 (앵커 + 도메인 근거) | OR면 172종을 또 다른 잘못된 값으로 바꿀 위험 |
| 3 | 검증된 제작사 호스트 등록부 25개 도입 | 한글 제작사명이 영문 도메인과 매칭 불가해 전부 manual_review로 떨어지던 문제. 앵커 근거는 여전히 필수 |
| 4 | 플랫폼 호스팅(notion.site, oopy.io 등) 7개는 등록부 제외 | 도메인 소유가 제작사 증명이 아님 |
| 5 | SNS 전면 차단 대신 눈누 계정만 경로 단위 차단 | 제작사가 SNS만 운영하는 경우 정당한 출처 |
| 6 | 0026은 4곳 수정, 낙관적 잠금 coalesce는 제외 | NOT NULL 컬럼이라 도달 불가능한 방어 코드. 대신 tripwire 테스트로 의존성 표시 |
| 7 | MCP 두 서버를 postgres-mcp(쓰기 가능)로 교체 | 사용자 지시. `mcp<2` 핀 필수(최신 mcp에서 fastmcp 경로 없음) |

---

## 진행 상태

| Task | 상태 | 근거 |
|---|---|---|
| 1~4 코드 (검출 도구) | 완료 | PR #151, 커밋 7개 |
| 자체 리뷰 + Codex 리뷰 반영 | 완료 | CRITICAL 1 + HIGH 2 + Must-fix 6건 수정 |
| 5 manifest 조사 | 완료 | `docs/progress/2026-07-29-official-url-manifest-investigation.md` |
| 6 마이그레이션 0026 | 완료 | 로컬 PG 검증 + **dev 적용 완료** (실측 3항목 확인) |
| 7 Step 1 dev 0026 | 완료 | psql 풀러 접속 |
| 7 Step 2 전수 스캔 v1 | 완료 | `output/noonnu-url-scan-report.json`, 오염 172종 확인 |
| 7 Step 2' 재스캔 v2 (등록부 반영) | ⚠️ 진행 중 | 세션 종료 시점 1014/1110. 상태 파일로 재개 가능 |
| 7 Step 4~5 finding 적재 + dev 정정 | 미착수 | **아래 갭 참조** |
| 8 prod 적용 | 미착수 | dev 검증 후 |

---

## 🔴 미해결 갭 (다음 세션의 핵심 과제)

**스캐너가 감사 finding을 DB에 저장하지 않는다.**

`build_manifest(run, approved_findings, current_rows)`(`audit_manifest.py:579`)는 DB에 저장된 감사 run과 승인된 finding을 요구한다. 그런데 현재 `noonnu-url-scan`은 리포트 JSON만 만들고 DB에 아무것도 쓰지 않는다.

설계 문서는 "기존 감사 파이프라인의 review-approve-manifest 경로를 그대로 탄다"고 적었으나 그 연결부가 구현되지 않았다. 정정을 진행하려면 아래 중 하나가 필요하다.

- (A) 스캔 결과를 `SnapshotDraft` + `FindingDraft`로 적재하는 경로 추가 (`AuditStore.start_run/save_snapshot/save_finding` 사용). `AuditStage`는 `bootstrap|legal|metadata|scheduled` 중 선택 필요 — official_url은 metadata 성격이나 license_source_url도 함께 바꾸므로 판단 필요
- (B) 리포트 JSON에서 manifest를 직접 만드는 별도 경로 (evidence_bundle 요구를 우회해야 해서 설계 원칙 위반 소지)

(A)가 정석이나 작업량이 있다. 착수 전 범위를 정하고 사용자 확인을 받는 것을 권한다.

---

## 코드 변경 상태

### 브랜치 `feat/noonnu-url-audit-task7` (현재, main 대비 12커밋)

```
205782f test: 스캔 fixture를 등록부 밖 중립 도메인으로 교체
a45da8d feat: 검증된 제작사 호스트 등록부로 자동 정정 범위 확장
cc083b9 docs: 눈누 official_url 전수 스캔 결과 - 32개 호스트 수렴
af70770 fix: noonnu-url-scan을 audit settings + --target 패턴으로 배선
99019cf feat: manifest에 official_url 정정 허용, nullify는 값 검증에서 거부
76edca1 docs: nullify 불가 실측 반영 - NOT NULL 제약과 0026 범위 축소
4897289 docs: official_url manifest 허용 조사 결과
128cac4 docs: 설계 문서의 robots 준수 서술 정정
(이하 af70770부터는 PR #151 브랜치와 공유)
```

⚠️ **task7 브랜치는 아직 PR이 없다.** PR #151(`feat/noonnu-url-audit-150`, OPEN, MERGEABLE)과 별개다. task7을 어떻게 처리할지(151에 합칠지, 별도 PR로 낼지) 결정이 필요하다.

### 미추적 산출물 (git에 없음, 재생성 가능)

- `apps/pipeline/output/noonnu-url-scan-state.jsonl` / `-report.json` (v1, 등록부 이전)
- `apps/pipeline/output/noonnu-url-scan-state-v2.jsonl` / `-report-v2.json` (v2, 등록부 반영)

---

## v1 스캔 결과 (등록부 이전, 참고용)

```
1,110종 전수, 오류 0, no_container 0건
match 925 / mismatch 184 / no_link 1
keep 925 / manual_review 182 / auto_fix_safe 2 / nullify(보류) 1
오염: noonnu_account 172 (prod 실측과 일치)
```

오염 169건의 재추출 값이 **32개 호스트로 수렴**했다(clova.ai 하나가 109건). 전부 앵커 근거 보유. 상세 표는 `docs/progress/2026-07-29-noonnu-url-scan-result.md`.

v2는 등록부 25개 반영으로 `auto_fix_safe`가 크게 늘 것으로 예상된다(예상 140건 안팎, ⚠️ 미확인).

---

## 다음 단계 (Next)

🔴 **MUST**
- [ ] 재스캔 v2 완료 확인 및 분포 분석 (`output/noonnu-url-scan-report-v2.json`의 summary). 중단됐으면 같은 명령으로 재개
- [ ] 위 "미해결 갭" 해소 방안 결정 후 구현 (finding 적재 경로)
- [ ] dev 정정 적용 + 쓰기 후 재조회 실측
- [ ] task7 브랜치 처리 방침 결정 (PR #151 합류 vs 별도 PR)

🟡 **SHOULD**
- [ ] prod 승인 패키지 작성 (변경 건수, 필드별 건수, 샘플 10건, 전체 slug, 역방향 manifest, 검증 쿼리)
- [ ] prod 적용 후 웹 재배포 (정적 사이트라 DB만 고쳐서는 화면이 안 바뀜)
- [ ] 계획 체크박스 재동기화 (현재 27/49)

🟢 **NICE-TO-DO**
- [ ] `NEXT_PUBLIC_SUPABASE_PASWORD` 키 개명 (DB 비밀번호가 웹 번들 노출 위험 접두사)
- [ ] 오염 판정 호스트 목록이 `audit_noonnu.py`와 `noonnu_url_audit.py`에 중복 정의된 것 통합
- [ ] `_registrable_domain_label`이 Public Suffix List 미사용 휴리스틱 (`com.au` 등 외국 2단계 접미사 미처리)

---

## 핵심 파일 경로

| 카테고리 | 경로 |
|---|---|
| 설계 | `docs/superpowers/specs/2026-07-28-noonnu-official-url-audit-design.md` |
| 계획 | `docs/superpowers/plans/2026-07-28-noonnu-official-url-audit.md` |
| manifest 조사 | `docs/progress/2026-07-29-official-url-manifest-investigation.md` |
| v1 스캔 결과 | `docs/progress/2026-07-29-noonnu-url-scan-result.md` |
| Codex 리뷰 | `docs/review/pr-review-151-20260729-073344.md` |
| 판정 로직 | `apps/pipeline/src/fontagit_pipeline/noonnu_url_audit.py` |
| 스캔 실행기 | `apps/pipeline/src/fontagit_pipeline/noonnu_url_scan.py` |
| 눈누 파서 | `apps/pipeline/src/fontagit_pipeline/audit_noonnu.py` |
| 마이그레이션 | `supabase/migrations/0026_manifest_official_url.sql` |
| pgTAP | `supabase/tests/manifest_official_url_test.sql` |

---

## 검증 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| pytest | 통과 | 472 passed, 4 skipped |
| ruff | 통과 | All checks passed |
| mypy | 기존값 유지 | 70 errors (전부 `__main__.py` 선재) |
| pgTAP 0026 | 통과 | 로컬 PG 17, 5케이스 + 기존 회귀 ALL PASS |
| dev 0026 적용 | 완료 | v_allowed 포함 / value_valid null 거부 / _audit_font_value 매핑 실측 |
| dev 데이터 정정 | ⚠️ 미실행 | 위 갭 때문 |
| prod | ⚠️ 미적용 | 0026도 미적용 |

---

## 재현 명령

```bash
# 재스캔 (재개 가능, 상태 파일 기준)
cd apps/pipeline && uv run python -m fontagit_pipeline noonnu-url-scan --target dev \
  --state output/noonnu-url-scan-state-v2.jsonl --out output/noonnu-url-scan-report-v2.json

# dev psql (비번은 apps/web/.env.local의 NEXT_PUBLIC_SUPABASE_PASWORD)
PGPASSWORD="$PW" /opt/homebrew/opt/postgresql@17/bin/psql \
  "host=aws-0-$REGION.pooler.supabase.com port=5432 dbname=postgres user=postgres.$PID sslmode=require"

# 테스트
cd apps/pipeline && uv run pytest -q && uv run ruff check . && uv run mypy src
```

---

## 재개 프롬프트

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-29-1135-noonnu-official-url-audit.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. 설계-계획 문서를 읽는다
3. git status && git log --oneline -12 로 현재 상태 확인
4. 재스캔 v2 결과(apps/pipeline/output/noonnu-url-scan-report-v2.json)의 summary 확인
5. 핸드오프의 "다음 단계 -> MUST" 항목부터 시작
6. 사용자 제약과 결정 사항은 뒤집지 않는다 (변경 시 사용자 확인 필수)

진행 전에 핸드오프를 읽었음을 확인하고, MUST 중 어디부터 시작할지 한 줄로 보고해주세요.
```
