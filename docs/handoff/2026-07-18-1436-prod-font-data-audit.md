# 세션 핸드오프 — 2026-07-18 14:36 KST

> **모드**: simple-change
> **Feature**: prod-font-data-audit
> **이전 세션 종결 사유**: 사용자가 다음 세션 인계를 요청함

## 한 줄 요약

prod 1,240종의 다운로드·라이선스·일반 메타데이터 전수 조사 설계와 13개 Task 구현 계획을 확정했다. 다음 세션은 다른 UI 변경을 건드리지 않는 별도 worktree에서 Task 1부터 구현한다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. 이 핸드오프 파일을 읽는다: `docs/handoff/2026-07-18-1436-prod-font-data-audit.md`
2. 아래 문서를 순서대로 모두 읽는다.
   - `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md`
   - `docs/superpowers/plans/2026-07-18-prod-font-data-audit.md`
   - `docs/review/review-result-20260718-142131.md`
3. `git status --short`, `git log --oneline -10`, `git fetch origin`으로 상태를 다시 확인한다.
4. 현재 worktree의 미커밋 UI 파일은 다른 작업 소유이므로 수정·스테이징·삭제하지 않는다.
5. `superpowers:using-git-worktrees`로 구현 전용 worktree와 `codex/prod-font-data-audit-implementation` 브랜치를 만든다.
6. 구현 브랜치가 `origin/develop`보다 1커밋 뒤인 상태를 재확인한 뒤 안전하게 동기화하고, 충돌 시 자동 해결하지 않는다.
7. `superpowers:executing-plans`로 Plan의 Task 1부터 시작한다.

---

## 작업 컨텍스트

### 사용자 원본 요청

> prod 폰트 데이터를 전수 조사하여 잘못된 다운로드 링크와 적재 원인을 고치고, 라이선스 본문을 보강하며 기존 파이프라인의 재발 버그를 막는다.

추가 핵심 요구:

> 한글 폰트 판별이 가능해야 한다. 눈누 폰트의 subsets가 비어 있으면 한글인지 영어인지 분간할 수 없다.

### 확인된 실제 원인

- `apps/pipeline/output/tier-b-noonnu-seed.json`: 1,157건 모두 `subsets` 필드가 없다.
- `NoonnuSeedRecord` 모델과 `_build_draft_font_row()`가 `subsets`를 생성·적재하지 않는다.
- `fontagit.fonts.subsets`는 `text[] not null default '{}'`라 누락이 오류가 아니라 빈 배열로 숨는다.
- Tier A 136건은 subsets가 모두 있고 빈 배열은 0건이다.
- `source_tier='B'`는 출처 구분일 뿐 한글 글리프 지원 증거가 아니다.

### 추가 합의·변경 사항

- 출처는 제작사 공식 페이지를 최우선으로 하고 승인된 공공기관, 눈누 참고 순서로 사용한다.
- 눈누에서는 폰트와 직접 관련된 모든 정보만 수집·저장한다.
- 라이선스 핵심 조건은 FontAgit 문장으로 요약하고 원문은 내부 증거로 저장한다. 사용자는 원문 링크로 이동한다.
- 공식·공공기관 근거가 없으면 페이지는 유지하지만 다운로드 버튼을 제거하고 재확인 상태를 표시한다.
- 목록 화면 필터 다양화 작업은 취소되어 이번 범위에서 제외한다.
- 실제 폰트 파일의 Unicode cmap으로 한글·라틴을 판정한다.
- KS X 1001 공통 한글 2,350자를 모두 지원하면 korean verified 후보로 본다.
- 일부 한글만 있으면 확인된 latin 정보는 보존하되 script_status는 needs_review다.
- 같은 face의 분할 파일은 cmap 합집합을 먼저 만들고, 동적·미리보기용 부분 파일은 자동 확정 근거에서 제외한다.
- 빈 subsets는 영문이 아니라 미확인이다. UI는 미확인 시 한글·영문 혼합 견본을 사용한다.
- 50종 legal+metadata 파일럿에서 부분 파일과 partial 한글 비율을 먼저 측정한다.

### 사용자 제약·금지사항

🔴 **반드시 (must)**:

- prod 쓰기·마이그레이션·배포는 dev 전수 조사 보고 후 사용자 명시 승인을 다시 받아야 한다.
- 원문 HTML과 폰트 바이너리는 공개 API나 저장소에 커밋하지 않는다.
- `source_tier`, 한글 이름, 눈누 등록 여부만으로 한글 폰트를 추정하지 않는다.
- 통과율을 맞추려고 2,350자 기준을 임의로 낮추지 않는다.
- 공식 출처를 찾지 못한 값을 verified로 만들지 않는다.
- 다운로드 404·410은 24시간 이상 간격의 독립 실행 2회에서만 broken으로 확정한다.
- 현재 worktree의 UI·PR 리뷰·기존 handoff 파일은 이번 feature 범위가 아니다.
- 핵심 서비스만 테스트하며 한 메서드당 해피 패스 1개와 치명적 예외 1~2개, 최대 3개를 유지한다.

---

## Plan / Design 인덱스

| 단계 | 문서 | 진행률 | 상태 |
|------|------|--------|------|
| Design | `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md` | 체크박스 없음 | ✅ 승인·리뷰 보강 |
| Plan | `docs/superpowers/plans/2026-07-18-prod-font-data-audit.md` | 0/86 | 🚧 구현 미착수 |
| Review | `docs/review/review-result-20260718-142131.md` | Claude 8/10 + Codex 교차 검토 | ✅ 반영 |
| Do | 구현 코드 | 0/13 Tasks | ⏳ 다음 세션 시작 |

---

## 코드 변경 상태 (git)

### 브랜치와 원격

- 현재 브랜치: `codex/prod-font-data-audit-design`
- upstream: `origin/codex/prod-font-data-audit-design`
- push 상태: HEAD와 upstream 동기화
- `origin/develop` 기준: 4커밋 앞, 1커밋 뒤
- 공통 조상: `cbba78c`
- 뒤에 있는 develop 커밋: `b0d807d feat: /fonts 페이지네이션-메타 + 메인/헤더 검색 통일 (#57, #53) (#74)`

### Uncommitted — 다른 작업 소유, 건드리지 말 것

```text
 M apps/web/components/CompareBoard.tsx
 M apps/web/components/FontCard.tsx
 M apps/web/components/Specimen.tsx
 M apps/web/components/SpecimenBox.test.tsx
 M apps/web/components/SpecimenBox.tsx
 M apps/web/lib/specimen.ts
?? apps/web/lib/specimen.test.ts
?? docs/handoff/2026-07-18-1350-github-issues-loop.md
?? docs/review/pr-review-74-20260718-130155.md
?? docs/review/pr-review-75-20260718-142355.md
```

추적 중인 UI 변경 통계: 6개 파일, +14/-12. untracked 파일은 통계에서 제외됨.

### 이번 feature 커밋

| SHA | 메시지 | 상태 |
|-----|--------|------|
| `6c4be0a` | docs: prod 폰트 데이터 전수 조사 설계 | pushed |
| `9e0d25d` | docs: 적대적 리뷰로 폰트 감사 설계 보강 | pushed |
| `ede4ced` | docs: prod 폰트 데이터 감사 구현 계획 추가 | pushed |
| `f74dd7e` | docs: add cmap-based Korean font detection plan | pushed |

---

## 결정 사항 (Decisions)

| # | 결정 | 근거 | 결정 주체 |
|---|------|------|-----------|
| 1 | 제작사 공식 → 공공기관 → 눈누 참고 | 잘못된 SNS·404 링크 재발 방지 | 사용자 |
| 2 | 원문은 내부 증거, 공개 화면은 요약+링크 | 사용자 요구와 저작권·추적성 동시 충족 | 사용자 |
| 3 | 미확인 페이지 유지, CTA 제거 | 접근성과 오안내 위험의 절충 | 사용자 |
| 4 | 폰트 관련 눈누 정보는 모두 수집 | 데이터 확장용 참고 원본 확보 | 사용자 |
| 5 | 빈 subsets는 미확인 | 빈 배열은 적재 누락이지 영문 증거가 아님 | 합의 |
| 6 | 실제 cmap으로 한글 판별 | 출처·이름 추정 제거 | 합의 |
| 7 | 부분·동적 파일은 needs_review | 한글 글자 일부만 있는 파일의 오판 방지 | 적대적·Claude 리뷰 후 보강 |
| 8 | prod 반영은 별도 승인 게이트 | 전수 조사·rollback 검증 후에만 쓰기 | 사용자·설계 |

---

## 블로커·미해결 이슈 (Blockers)

| # | 이슈 | 영향 | 다음 조치 |
|---|------|------|-----------|
| 1 | 현재 worktree에 다른 UI 미커밋 변경 존재 | 구현 파일 충돌·오염 위험 | 구현 전용 worktree 사용 |
| 2 | feature 브랜치가 origin/develop보다 1커밋 뒤 | 최신 웹 변경과 결합 검증 필요 | 새 worktree에서 안전하게 동기화 |
| 3 | 눈누 실제 파일의 부분 서브셋 비율 미측정 | 한글 자동 판정률 불명 | Task 12 전 50종 metadata 파일럿 실행 |
| 4 | prod 적용 승인 미부여 | Task 13 실행 차단 | dev 보고 후 사용자에게 승인 요청 |

---

## 다음 단계 (Next)

🔴 **MUST**:

- [ ] 별도 worktree와 `codex/prod-font-data-audit-implementation` 브랜치 생성
- [ ] `origin/develop` 최신 1커밋과의 동기화·충돌 여부 확인
- [ ] Plan Task 1: additive 감사 스키마·RLS를 테스트 우선으로 구현
- [ ] Task 1 착수 전 dev 실제 `subsets` 타입·기본값과 0016 권한 CHECK 확인
- [ ] Task 1 완료 후 Plan 체크박스와 검증 증거 갱신

🟡 **SHOULD**:

- [ ] Task 2~3을 Plan 순서대로 작은 커밋으로 구현
- [ ] 수집 정책·robots·원문 보관 가능 여부를 실제 실행 전에 검사
- [ ] 폰트 파일 파서는 압축 32 MiB·해제 128 MiB·시간 제한을 지킴

🟢 **NICE-TO-DO**:

- [ ] 50종 파일럿 결과로 제작사별 실패 원인 통계 보강
- [ ] 2,350자 기준 변경 필요 시 별도 설계 승인과 회귀 fixture 추가

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| Plan | `docs/superpowers/plans/2026-07-18-prod-font-data-audit.md` |
| Design | `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md` |
| Review | `docs/review/review-result-20260718-142131.md` |
| 기존 schema | `supabase/migrations/0001_fontagit_schema.sql` |
| 기존 Noonnu 권한 | `supabase/migrations/0016_noonnu_enrich.sql` |
| Noonnu 모델 | `apps/pipeline/src/fontagit_pipeline/models.py` |
| Noonnu import | `apps/pipeline/src/fontagit_pipeline/noonnu_import.py` |
| Tier B seed | `apps/pipeline/output/tier-b-noonnu-seed.json` |
| 핸드오프 | `docs/handoff/2026-07-18-1436-prod-font-data-audit.md` |

---

## 검증 상태

| 항목 | 상태 | 근거 |
|------|------|------|
| 문서 구조 | ✅ | Plan Tasks/Files/Interfaces 13/13/13, 코드 블록 짝 정상 |
| Tier B 원인 | ✅ | seed 1,157건, subsets 필드 0건 |
| Tier A 비교 | ✅ | 136건, 빈 subsets 0건 |
| 외부 리뷰 | ✅ | Claude 8/10, Codex 교차 검토와 보강 완료 |
| 구현 테스트·빌드 | ⚠️ 미실행 | 구현 코드 미착수, 이번 세션은 문서만 변경 |
| prod 데이터 쓰기 | ✅ 미실행 | 승인 전 쓰기 금지 준수 |
| 배포 | ✅ 미실행 | 현재 feature 브랜치이며 deploy.sh는 main 전용 |

---

## 재개 프롬프트 (다음 세션에 그대로 복사·붙여넣기)

```text
이전 세션의 prod 폰트 데이터 전수 조사 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 전체 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/handoff/2026-07-18-1436-prod-font-data-audit.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다.
2. Plan/Design/Review 인덱스의 문서를 모두 읽는다.
3. git status, git log --oneline -10, git fetch origin으로 현재 상태를 확인한다.
4. 기존 worktree의 미커밋 UI·리뷰 파일은 다른 작업 소유이므로 건드리지 않는다.
5. superpowers:using-git-worktrees로 구현 전용 worktree와 codex/prod-font-data-audit-implementation 브랜치를 만든다.
6. origin/develop 동기화 상태를 확인하고 충돌 시 자동 해결하지 않는다.
7. superpowers:executing-plans를 사용해 구현 계획 Task 1부터 시작한다.
8. prod 쓰기·마이그레이션·배포는 dev 보고 후 사용자 명시 승인 전 절대 실행하지 않는다.

진행 전에 핸드오프를 읽었음을 확인하고, 새 worktree 경로와 Task 1의 첫 검증 항목을 한 줄로 보고해주세요.
```

---

✅ 핸드오프 메모 작성 완료. 다음 세션은 위 재개 프롬프트로 시작한다.
