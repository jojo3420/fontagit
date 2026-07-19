# 세션 핸드오프 — 2026-07-19 22:12 KST

> **모드**: simple-change (연계 문서는 superpowers specs/plans)
> **Feature**: prod-font-data-audit — 파이프라인 실행-검증 마무리
> **이전 세션 종결 사유**: 사용자 인계 요청 (파이프라인 검증 미완)

## 한 줄 요약

한글 폰트 견본 수정(#75)에서 출발한 "눈누 subsets 백필"이 여러 세션을 거치며 **폰트 파일 cmap(문자→글리프 매핑 테이블) 기반 한글 판정 감사(audit) 파이프라인**으로 확장됐다. 파이프라인 코드는 일부 main 병합(#76, #85)됐고 cmap 판정+웹 연동은 `codex/prod-font-data-audit` 브랜치에 **미병합**으로 남아 있다. 정작 **파이프라인을 실제 dev/prod DB에 돌려 검증-적용하는 단계가 미완**이라, 다음 세션이 이를 마무리해야 한다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. 이 핸드오프 파일을 읽는다: `docs/handoff/2026-07-19-2212-prod-font-data-audit-pipeline-verify.md`
2. 아래 문서를 순서대로 읽는다:
   - `docs/handoff/2026-07-18-1436-prod-font-data-audit.md` (직전 감사 핸드오프 — 결정사항 원본)
   - `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md` (설계)
   - `docs/superpowers/plans/2026-07-18-prod-font-data-audit.md` (13개 Task 계획, 실행/검증 명령 포함)
3. 상태 재확인: `git fetch origin && git log --oneline -15 main && git log --oneline main..codex/prod-font-data-audit`
4. 미병합 브랜치 `codex/prod-font-data-audit`의 델타를 파악하고, 병합 전략(rebase/PR)을 정한다.
5. 아래 "다음 단계 → MUST"의 파이프라인 실행-검증부터 시작한다.

---

## 작업 컨텍스트

### 사용자 원본 요청 (이번 세션)

> 후속 별건으로 눈누 subsets 데이터 백필 진행. 이후 여러 세션/이전 codex가 관련 커밋-PR을 만들고 작업을 완료했지만 **파이프라인 실행-검증은 못 했다.** 다음 세션에서 이 이슈 조치를 마무리해야 한다.

### 배경 흐름 (어떻게 여기까지 왔나)

- `#75`(견본 수정)에서 임시 방편으로 `sourceTier === "B"`를 한글로 간주. 근본 데이터(눈누 subsets 빈 배열)는 미해결로 남김.
- 그 근본 해결이 별도 감사 설계로 발전 → 단순 백필이 아니라 **실제 폰트 파일 cmap을 읽어 한글/라틴 지원을 판정**하는 방향으로 확정.
- 원인 확인: `apps/pipeline/output/tier-b-noonnu-seed.json` 1,157건 전부 `subsets` 없음. `NoonnuSeedRecord`/`_build_draft_font_row()`가 subsets 미생성. `fontagit.fonts.subsets`는 `text[] not null default '{}'`라 누락이 빈 배열로 숨음. Tier A 136건은 subsets 정상.

### 사용자 제약-금지사항 (반드시 준수)

🔴 **반드시 (must)**:
- **prod DB 쓰기는 사용자 확인 필수** (조회만 자동, 쓰기 금지). dev 먼저 검증 후 단계적 prod 적용.
- **자동 승인 금지**: 감사 결과는 `needs_review` 게이트를 거쳐 사람 검수 후 반영.
- 다른 worktree의 미커밋 파일은 다른 작업 소유 → 수정-스테이징-삭제 금지 (아래 worktree 표 참조).
- 충돌 발생 시 자동 해결하지 말고 사용자에게 보고.

---

## Plan / Design 인덱스

| 단계 | 문서 | 상태 |
|------|------|------|
| Design(spec) | `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md` | ✅ 확정 |
| Plan | `docs/superpowers/plans/2026-07-18-prod-font-data-audit.md` (13 Task, `audit_runner`가 파일럿/1-2단계 오케스트레이션) | ✅ 확정 |
| 직전 핸드오프 | `docs/handoff/2026-07-18-1436-prod-font-data-audit.md` | 참고 |
| Do(구현) | 파이프라인 코드 대부분 완료(main + 미병합 브랜치), **실행-검증 미완** | 🚧 |

---

## 코드 변경 상태 (git)

### main 반영 완료 (병합됨)

| PR/SHA | 내용 |
|-----|------|
| `#75` `024da4d` | 한글 폰트 견본 팬그램 수정 (sourceTier=B 임시 판정) |
| `#76` `7fbd807` | safe production font data audit pipeline (`apps/pipeline/.../audit_*.py`) |
| `#78`/`#79`/`#81`/`#85` | develop→main 승격, 내부출처 노출 제거, deploy.sh 브랜치/태그 인자, pipeline이 apps/web/.env.* SSoT 공유 |

현재 main HEAD: `820c232` (#85).

### ⚠️ 미병합 — `codex/prod-font-data-audit` (main보다 10+ 커밋 앞섬)

| SHA | 내용 |
|-----|------|
| `b999d92` | feat: 실제 폰트 파일 cmap 기반 한글 지원 검증을 **웹 화면에 연동** (미배포) |
| `b834c40` | feat: detect font script coverage from cmap |
| `4e78224` | fix: harden font metadata audit evidence |
| `deaffbd` | feat: schedule read-only font link audits |
| 기타 | audit credential/hostname 검증, review notes 보존, legacy noonnu writer 제거 등 |

> 이 브랜치가 cmap 판정 + 웹 연동의 실체. main 미병합 = prod 미반영. 병합/배포 필요.

### 이번(현재) 세션 커밋

| SHA | 메시지 |
|-----|--------|
| `ce00aa4` | docs: progress 일지 갱신 - #75 한글 폰트 견본 팬그램 수정 |

### Worktree 현황 (건드리지 말 것)

| 경로 | 브랜치 | 상태 |
|------|--------|------|
| `.worktrees/cleanup-test-build-warnings` | `codex/cleanup-test-build-warnings` | 미커밋 test 3파일(search/page.test, useDebouncedSuggestions.test, next.config) — 다른 작업 |
| `.claude/worktrees/feature+compare-home-merge` | `worktree-feature+compare-home-merge` | locked |

---

## 결정 사항 (Decisions) — 뒤집지 말 것 (변경 시 사용자 확인)

| # | 결정 | 근거 |
|---|------|------|
| 1 | 한글/라틴은 **실제 폰트 파일 cmap**으로 판정 (subsets-sourceTier 아님) | subsets 빈 배열, sourceTier는 출처 구분일 뿐 글리프 증거 아님 |
| 2 | KS X 1001 공통 한글 2,350자 전부 지원 시 `korean verified` 후보 | 부분 지원은 `script_status=needs_review` |
| 3 | 빈 subsets = "영문"이 아니라 **"미확인"**. UI는 미확인 시 한글-영문 혼합 견본 | 오판 방지 |
| 4 | 출처 우선순위: 제작사 공식 > 승인 공공기관 > 눈누(참고) | 라이선스 신뢰도 |
| 5 | 자동 승인 금지, `needs_review` 게이트 후 사람 검수 | 데이터 품질 |
| 6 | 50종 legal+metadata 파일럿으로 부분파일-partial 한글 비율 먼저 측정 | 리스크 선측정 |
| 7 | 공식-공공 근거 없으면 페이지 유지하되 다운로드 버튼 제거+재확인 표시 | 라이선스 리스크 |

---

## 블로커 - 미해결 이슈 (Blockers)

| # | 이슈 | 영향 | 다음 시도 |
|---|------|------|----------|
| 1 | **감사 파이프라인 미실행-미검증** (핵심) | subsets/한글 판정 데이터 미반영 | dev DB 상대로 파일럿→1-2단계 실행, 결과 검수 |
| 2 | cmap 판정+웹연동 `codex/prod-font-data-audit` **미병합** | prod 미반영 | 델타 검토 후 rebase/PR 병합, 배포 |
| 3 | ⚠️ 파이프라인 정확한 실행 명령 미확정 | 실행 착수 지연 | Plan Task 섹션 + `apps/pipeline/src/fontagit_pipeline/__main__.py`/`audit_runner.py`(`run_legal_audit`/`run_metadata_audit`) 읽어 CLI 확정 (`uv run` 기반) |
| 4 | ⚠️ prod DB SSH 터널(5433) 세션 시작 시 꺼져 있을 수 있음 | prod 조회/적용 불가 | 터널 기동 확인 (memory: ref-supabase-mcp-envs) |

---

## 다음 단계 (Next)

🔴 **MUST** (마무리 차단):
- [ ] `codex/prod-font-data-audit` 델타 파악 → main 대비 병합 전략 결정(rebase/PR)
- [ ] 감사 파이프라인 실행 명령 확정 (Plan Task + `audit_runner.py`/`__main__.py`, `uv run`)
- [ ] **dev DB에 파일럿(50종) → 1-2단계 실행**, `script_status`/한글 판정/subsets 결과 검수 (needs_review 게이트 확인)
- [ ] 검수 통과분 **prod 적용 (사용자 확인 후)**
- [ ] cmap 웹 연동(`b999d92`) 병합 후 배포, `/fonts`에서 한글 견본 실검증

🟡 **SHOULD**:
- [ ] `#75`의 임시 `sourceTier==="B"` 판정을 cmap 기반 `script_status`로 대체(중복 로직 정리)
- [ ] 파이프라인 테스트 그린 확인: `uv run pytest`, `uv run ruff check`, `uv run mypy src`

🟢 **NICE-TO-DO**:
- [ ] main에 남은 `#75` 중복 파일/정리, worktree 정리(cleanup-test-build-warnings 등 완료 후)

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 감사 파이프라인 | `apps/pipeline/src/fontagit_pipeline/audit_*.py` (runner/noonnu/bootstrap/metadata/license/policy/store/http) |
| 실행 오케스트레이션 | `apps/pipeline/src/fontagit_pipeline/audit_runner.py` (`run_legal_audit`, `run_metadata_audit`) |
| 눈누 seed(원인 데이터) | `apps/pipeline/output/tier-b-noonnu-seed.json` (subsets 누락 1,157건) |
| 견본 판정(웹, #75) | `apps/web/lib/specimen.ts` (`isKoreanFont`) |
| Plan/Design | `docs/superpowers/{plans,specs}/2026-07-18-prod-font-data-audit*.md` |
| 핸드오프(이 파일) | `docs/handoff/2026-07-19-2212-prod-font-data-audit-pipeline-verify.md` |
| env SSoT | `apps/web/.env.local`(dev) `apps/web/.env.production`(prod) — pipeline도 이 두 파일 로드 (memory: ref-env-file-ssot) |

---

## 검증 상태

| 항목 | 상태 |
|------|------|
| 파이프라인 코드 존재 | ✅ (main #76 + 미병합 브랜치) |
| 파이프라인 실행-검증 | ❌ 미실행 (이번 인계 핵심) |
| cmap 웹연동 병합/배포 | ❌ 미병합 |
| `#75` 견본 수정 | ✅ 배포 완료 (fontagit.com, sourceTier=B 임시 판정) |
| dev/prod DB 적용 | ❌ 미적용 |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/handoff/2026-07-19-2212-prod-font-data-audit-pipeline-verify.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. Plan/Design 인덱스의 문서(직전 핸드오프 1436, spec, plan)를 모두 읽는다
3. git fetch origin && git log --oneline -15 main && git log --oneline main..codex/prod-font-data-audit 로 현재 상태 확인
4. 핸드오프의 "다음 단계 → MUST"부터 시작 (파이프라인 실행 명령 확정 → dev 파일럿 실행-검수 → prod 적용은 사용자 확인 후)
5. 사용자 제약을 준수: prod DB 쓰기 확인 필수, 자동 승인 금지(needs_review), 다른 worktree 미커밋 파일 미침해
6. 결정 사항 표(cmap 판정, 빈 subsets=미확인 등)는 뒤집지 않는다 (변경 시 사용자 확인)

핸드오프를 읽었음을 확인하고, MUST 항목 중 어디부터 시작할지 한 줄로 보고해주세요.
```
