# 세션 핸드오프 — 2026-07-22 21:00 KST

> ⚠️ **SUPERSEDED (2026-07-23)**: 이 핸드오프의 "미해결 상태"(Docker 이미지 없음, 크롤 backoff 미구현 등)는 이후 세션에서 해소됨 — 준비 Task A(Docker)-C(backoff)는 PR #99로 구현 완료. 실행 경로는 `execution-REVISED.md`로 정정됨. 최신 인계는 `handoff/2026-07-23-*-collections-phase0-execution.md` 참조. 이 문서는 역사 기록.

> **모드**: superpowers-plan
> **Feature**: collections-expansion (컬렉션 확장 0단계)
> **이전 세션 종결 사유**: 0단계 코드(Task1) 완료+머지, Task2~3는 준비 plan까지 도달 후 사용자 인계 요청

## 한 줄 요약

/collections가 3개뿐인 병목이 "폰트 분류 데이터 결측"임을 실측 규명하고, 기존 신 감사(audit) 파이프라인으로 tags/weights를 채우는 0단계를 설계 → 코드 Task1(눈누 tags를 metadata evidence에 연결) 구현+PR #98 develop 머지까지 완료했다. 다음은 Task2~3(도커에서 감사 실행 → dev 반영)을 위한 코드 준비 3건이다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. **이 핸드오프 파일을 읽는다**
2. **문서를 읽는다**:
   - `docs/superpowers/specs/2026-07-22-collections-expansion-design.md` (설계 전체, 절 11 착수 전 확정 항목)
   - `docs/superpowers/plans/2026-07-22-collections-phase0-task23-execution-prep.md` (다음 착수 대상, 미체크 23개)
   - `docs/superpowers/plans/2026-07-22-collections-phase0-data-enrichment.md` (0단계 원 plan, Task1은 코드 완료됨)
   - 메모리 `project-collections-expansion.md` (재개점 요약)
3. **git 상태 확인**: `git checkout feature/collections-task23-prep && git status && git log --oneline -6`
4. **아래 "다음 단계 MUST"의 Task A부터 시작** (Docker 이미지)

---

## 작업 컨텍스트

### 사용자 원본 요청

> prod, dev "/collections" 페이지에 컬렉션이 3개만 존재함. 리얼서버가 오픈한 만큼 컬렉션 수를 최대화할 수 있는 기획이 필요. 컬렉션 하위 계층 구성 여부 검토. 다른 폰트사이트 벤치마킹 후 기획 완성.

### 추가 합의-변경 사항

- 목적: 탐색+SEO+볼륨 (감성/브랜딩 제외)
- 운영: 자동 파이프라인 중심 + 에디토리얼 소수
- 계층: 2단(상위 축 → 하위 컬렉션)
- 저장: DB 규칙 엔진(collections에 kind/rule/generated_at 추가)
- Task2~3 실행 환경: mac의 Docker(Linux 컨테이너)
- deploy: 웹(apps/web) 무변경이라 스킵

### 사용자 제약-금지사항 (반드시 준수)

🔴 **반드시 (must)**:
- fonts 쓰기는 `apply_font_audit_manifest` RPC로만. 직접 PATCH/UPDATE 금지
- tags/weights finding은 `auto_applicable=False`. 검수 게이트 후 apply
- published 폰트의 status는 안 바꿈(메타데이터 tags/weights는 apply RPC로 갱신 O)
- prod 적용은 별도 게이트(`--approved-hash`), 이번 범위는 dev까지
- Codex 코드 리뷰 스킬은 사용자 명시 호출 시에만(자동 실행 금지)

---

## Plan / Design 인덱스

| 단계 | 문서 | 진행률 | 상태 |
|------|------|--------|------|
| Design | `specs/2026-07-22-collections-expansion-design.md` | 승인+리뷰반영 완료 | ✅ |
| Plan(0단계) | `plans/2026-07-22-collections-phase0-data-enrichment.md` | Task1 코드 완료(체크박스는 미갱신), Task2~3는 준비 plan으로 분리 | 🚧 |
| Plan(Task2~3 준비) | `plans/2026-07-22-collections-phase0-task23-execution-prep.md` | 0/23 (미착수) | 🚧 |
| 리뷰 | `review/review-result-dual-20260722-153145.md` (듀얼), `review/pr-review-98-20260722-180002.md` (PR#98 Codex) | 반영 완료 | ✅ |

---

## 코드 변경 상태 (git)

### Uncommitted

- `docs/review/pr-review-98-20260722-180002.md` (untracked) — PR #98 Codex 리뷰 원문. 보존용, 커밋 선택.

### 이번 세션 커밋 (모두 push됨)

| SHA | 메시지 | 비고 |
|-----|--------|------|
| `bac4896` | feat: collections expansion phase0 (#98) | develop squash 머지 (설계+0단계plan+Task1 tags연결+Must-fix) |
| `eb69a3c` | docs: Task 2~3 실행 준비 plan | 브랜치 feature/collections-task23-prep |
| `27c2be1` | docs: progress 일지 갱신 | 현재 HEAD |

> PR #98 내부: Task1(e322187) + Must-fix 빈태그 가드(1ed2aa5) + 문서 모순 정정(822fec2)이 squash됨.

---

## 결정 사항 (Decisions) — 뒤집지 말 것

| # | 결정 | 근거 |
|---|------|------|
| 1 | 신규 파이프라인 안 만들고 기존 신 감사 경로(audit_noonnu→audit_runner→apply RPC) 사용 | tags/weights 추출+반영 체인 이미 존재, 코드 갭은 tags 연결 한 곳뿐 |
| 2 | 0단계 코드 갭 = `_collect_metadata_evidence`가 눈누 tags를 extracted에 안 넣음 | compare_metadata는 tags 처리 완비, evidence 연결만 없었음 |
| 3 | 빈 태그는 evidence에 안 넣음 (`and parsed.tags` 가드) | 빈 배열이 "태그 삭제" finding 만드는 버그 (Codex 지적) |
| 4 | /fonts=용도 브라우징, /collections=라이선스+에디토리얼+스타일태그 (역할 재정의) | 이중관리 제거, /fonts와 축 중복 회피 |
| 5 | weights는 코드 수정 불요, metadata 감사 실행하면 @font-face 파싱으로 채워짐 | merged.extracted()에 이미 포함 |

---

## 블로커 - 미해결 이슈 (Blockers)

| # | 이슈 | 영향 | 다음 시도 |
|---|------|------|----------|
| 1 | Docker 이미지 없음(Dockerfile 부재) | Task2~3 실행 차단(run_metadata_audit Linux 전용, audit_runner.py:450) | 준비 plan Task A |
| 2 | manifest 생성 CLI 부재 | Task3(apply) 입력 못 만듦. `build_manifest`(audit_manifest.py:515) 함수는 있으나 CLI 미노출 | 준비 plan Task B (먼저 build_manifest 시그니처 정독) |
| 3 | 크롤링 재시도/backoff 미구현, 429/503 미분화 | 1,110종 대량 실행 시 일시 장애로 대량 누락 위험 | 준비 plan Task C |
| 4 | ⚠️ manifest 스키마 매핑 미검증 | audit-run findings ↔ apply manifest 필드 대응 미확인 | Task B Step1에서 확정 |
| 5 | ⚠️ test_audit_metadata.py는 이 mac에 fontTools 미설치로 collection 불가 | 로컬 전체 테스트 제약(Task1 코드와 무관) | 도커에서 실행하면 해소 |

---

## 다음 단계 (Next)

🔴 **MUST** (Task2~3 진행 차단):
- [ ] Task A: 파이프라인 Docker 이미지(Dockerfile, curl+fontconfig+uv sync)
- [ ] Task B: manifest 생성 CLI(`font-audit-manifest build`, build_manifest 래핑) — build_manifest 시그니처 먼저 정독
- [ ] Task C: 크롤링 P0 안전장치(재시도/backoff, 429/503 분화)

🟡 **SHOULD**:
- [ ] Task D: 파일럿 50종 도커 감사 → manifest → dev apply → 검증
- [ ] Task E: 전체 1,110종 dev 반영 (tags 70%+/weights 90%+ 목표)

🟢 **NICE-TO-DO**:
- [ ] PR #98 Codex 리뷰 원문 커밋 또는 정리
- [ ] 0단계 원 plan의 Task1 체크박스 사후 갱신

> B단계(DB 규칙엔진+자동 컬렉션)는 0단계 데이터 정비 완료 후. Codex 듀얼리뷰 Must(materialize 실패처리, 재빌드 트리거, rule 스키마)는 B단계 plan에서 해소.

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 코드 갭(완료) | `apps/pipeline/src/fontagit_pipeline/audit_runner.py:670` (tags 연결), `:581` (parsed 초기화) |
| manifest 함수 | `apps/pipeline/src/fontagit_pipeline/audit_manifest.py:515` build_manifest, `:704` write_manifest_bundle |
| apply CLI | `apps/pipeline/src/fontagit_pipeline/__main__.py:589,884-896` |
| 감사 추출 | `apps/pipeline/src/fontagit_pipeline/audit_noonnu.py:56` extract_noonnu_font (tags:30, weights:38) |
| Linux 게이트 | `audit_runner.py:450`, `__main__.py:484` |
| 낙관적 잠금 | `supabase/migrations/0018_apply_font_audit_manifest.sql:293-300` |
| bootstrap | `apps/pipeline/output/tier-b-noonnu-seed.json` (존재) |
| 핸드오프(이 파일) | `docs/superpowers/handoff/2026-07-22-2100-collections-phase0.md` |

---

## 검증 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| Task1 단위 테스트 | ✅ 19 passed | test_audit_runner + test_audit_noonnu (rtk proxy로 실행) |
| test_audit_metadata | ⚠️ 미실행 | fontTools 미설치(mac), 도커서 해소 |
| PR #98 | ✅ MERGED (develop) | Codex 리뷰 Must-fix 3건 반영 후 머지 |
| Task2~3 실행 | ❌ 미착수 | 준비 3건(Docker/CLI/P0) 선행 필요 |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-22-2100-collections-phase0.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. Plan/Design 인덱스의 문서(설계 스펙 + Task2~3 준비 plan + 메모리 project-collections-expansion)를 읽는다
3. `git checkout feature/collections-task23-prep && git status && git log --oneline -6`로 현재 상태 확인
4. 핸드오프의 "다음 단계 MUST" Task A(Docker 이미지)부터 시작
5. 사용자 제약(fonts 쓰기는 apply RPC만, published status 불변, prod 별도 게이트)을 반드시 준수
6. 결정 사항 표(신 감사 경로 사용, 빈태그 가드 등)는 뒤집지 않음

진행 전에 핸드오프 파일을 읽었음을 확인하고, MUST Task A/B/C 중 어디부터 시작할지 한 줄로 보고해주세요.
```

---

✅ 핸드오프 메모 작성 완료. 다음 세션은 위 재개 프롬프트로 시작.
