# 세션 핸드오프 — 2026-07-15 13:48 KST

> **모드**: superpowers-plan (SDD 실행 완료)
> **Feature**: 업로드 원자성 + stale alias 동기화 (GitHub 이슈 #8 SHOULD 3건)
> **종결 사유**: 코드 구현 완료, 사용자 요청으로 핸드오프 마무리

## 한 줄 요약

이슈 #8 SHOULD 3건(업로드 원자성 / stale alias 동기화 / licenses.py 방어)을 Subagent-Driven Development로 코드 완료했고, sandbox Supabase에 마이그레이션 0002를 적용했다. 다음은 실제 파이프라인 실행으로 멱등-stale-롤백을 재검증하고 PR을 올리는 것이다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. 이 핸드오프 파일을 읽는다
2. Plan/Design/ledger를 읽는다:
   - Plan: `docs/superpowers/plans/2026-07-15-upload-atomicity-alias-sync.md` (4 태스크, 전부 완료)
   - Design: `docs/superpowers/specs/2026-07-15-upload-atomicity-alias-sync-design.md`
   - SDD ledger: `.superpowers/sdd/progress-pipeline-issue8.md` (진행 원장)
   - 듀얼 리뷰: `docs/review/review-result-dual-20260715-124249.md`
3. `git status && git log --oneline -8`로 상태 확인
4. 아래 "다음 단계 → SHOULD"부터 시작 (실제 파이프라인 실행 재검증)

---

## 작업 컨텍스트

### 사용자 원본 요청

이슈 #8(PR #7 듀얼 리뷰에서 식별된 파이프라인 후속 개선)의 SHOULD 3건을 처리. 브레인스토밍 → 설계 → 계획 → SDD 실행 → 핸드오프 순으로 진행.

### 사용자 제약-금지사항 (반드시 준수)

🔴 **반드시 (must)**:
- `fontagit` 스키마 격리 (ollidam과 공유 인스턴스, `public` 금지)
- 라이선스 정직성 (`license_type`은 `license_verified=true`일 때만, OFL/Apache-2.0/UFL만 published)
- secret(SECRET_KEY, DB 비번, 토큰) 로그-커밋-응답 노출 금지
- 변경 범위 `apps/pipeline` + `supabase`만 (UI=apps/web은 다른 세션 전담)
- 서브워커 diff는 컨트롤러가 직접 검증
- 결정 표는 뒤집지 않음 (변경 시 사용자 확인)
- develop에 UI 세션 커밋 병존 — 파일 범위 분리로 공존, 리뷰는 파이프라인 경로만 격리

---

## 결정 사항 (Decisions) — 뒤집지 말 것

| # | 결정 | 근거 |
|---|------|------|
| 1 | 원자성 = 폰트별 원자 (RPC 1회 = 폰트 1개) | 파이프라인 멱등 재실행이라 전체 롤백 불필요, 함수 단순 |
| 2 | stale alias = 삭제 후 재삽입 | 별칭은 폰트 파생 조회 데이터, 이력 보존 불필요, 참조 FK 없음 |
| 3 | RPC EXECUTE 권한 제한 (Must) | SECURITY DEFINER는 RLS 우회, PG 기본 PUBLIC EXECUTE 회수 필요 |

---

## 코드 변경 상태 (git)

uncommitted 코드 없음. 이번 세션 커밋 4개(develop, origin 대비 ahead — UI 커밋과 인터리빙):

| SHA | 메시지 |
|-----|--------|
| `060e827` | fix(licenses): GitHub API 응답 방어 - KeyError 방지 (Task 1) |
| `bfd1320` | feat(db): upsert_font RPC + EXECUTE 권한 제한 (Task 2) |
| `6bf73be` | feat(uploader): RPC upsert_font로 폰트별 원자 트랜잭션 업로드 (Task 3) |
| `0227e2e` | test(uploader): 실패 경로 테스트 추가 + 로그 민감정보 제거 (Task 3 fix) |

문서 커밋(앞선): `cb864b8`(설계), `32e77d5`(듀얼 리뷰 반영), `6d8e60b`(계획).
(참고: untracked `.playwright-mcp/`, `docs/review/screens/`는 UI 세션 산출물 — 건드리지 말 것.)

---

## 완료 내역 (증거 기반)

- **Task 1** licenses.py 방어: `parse_license_map`/`_get_tree_sha`/`fetch_license_map`의 KeyError 방지 + ValueError(JSON 파싱)를 `LicenseFetchError`로 감쌈. 14/14 PASS.
- **Task 2** `supabase/migrations/0002_upsert_font_rpc.sql`: `fontagit.upsert_font(p_font jsonb, p_aliases jsonb)` 함수(fonts upsert + updated_at=now() + 기존 alias 삭제 + 재삽입, 빈 배열 스킵) + `revoke execute from public,anon,authenticated` + `grant to service_role`.
- **Task 3** uploader.py: `upload_records`를 폰트당 RPC 1회로 재작성(첫 실패 즉시 중단), `build_alias_rows` 시그니처에서 font_id 제거. 6/6 PASS.
- **검증**: 전체 75 passed, ruff 통과, mypy 통과(9 files).
- **Final whole-branch review (opus)**: Ready to merge — Critical/Important 0. 데이터계약(_FONT_COLS 16개 ↔ RPC ↔ 스키마)/원자성/보안/SHOULD 3건 정합 확인.
- **DB**: ✅ sandbox Supabase에 0002 적용 완료 (사용자, 2026-07-15).

---

## 블로커 - 미해결 이슈

없음. 차단 요소 없음.

---

## 다음 단계 (Next)

🔴 **MUST**: 없음 (차단 없음).

🟡 **SHOULD** (완성도):
- [ ] 실제 파이프라인 실행 재검증 (Plan Task 4 Step 3-4, sandbox에 0002 적용됐으니 이제 가능):
  - `cd apps/pipeline && GOOGLE_FONTS_API_KEY=... uv run python -m fontagit_pipeline` (SUPABASE_URL/SECRET_KEY 설정 시 업로드)
  - `psql` 재검증: `select count(*) filter (where status='published') pub, count(*) total from fontagit.fonts;` — 2회 실행 시 total/aliases 카운트 동일(멱등+stale 미증가)
  - 원자성 롤백 확인: 중복 alias_norm으로 `fontagit.upsert_font` 호출 시 fonts insert도 롤백(Plan Task 4 Step 4 명령 참조)
- [ ] PR 생성 (파이프라인 4커밋 대상, `request-pr-dual` 등)

🟢 **NICE-TO-DO** (이슈 #8 나머지, 여유 시):
- [ ] `license` / `license_type` 필드 통합 (models.py/transform.py — `license`는 항상 None)
- [ ] 파이프라인 GITHUB_TOKEN 설정 (라이선스 판별 rate limit 방지)

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| Plan | `docs/superpowers/plans/2026-07-15-upload-atomicity-alias-sync.md` |
| Design | `docs/superpowers/specs/2026-07-15-upload-atomicity-alias-sync-design.md` |
| SDD ledger | `.superpowers/sdd/progress-pipeline-issue8.md` |
| 듀얼 리뷰 | `docs/review/review-result-dual-20260715-124249.md` |
| Final review diff | `.superpowers/sdd/final-review-pipeline-issue8.diff` |
| 마이그레이션 | `supabase/migrations/0002_upsert_font_rpc.sql` |
| 업로더 | `apps/pipeline/src/fontagit_pipeline/uploader.py` |
| 라이선스 | `apps/pipeline/src/fontagit_pipeline/licenses.py` |
| 핸드오프 (이 파일) | `docs/superpowers/handoff/2026-07-15-1348-upload-atomicity-issue8.md` |

---

## 검증 상태

| 항목 | 상태 |
|------|------|
| 단위 테스트 | ✅ 전체 75 passed |
| Lint (ruff) | ✅ 통과 |
| 타입 (mypy strict) | ✅ 통과 (9 files) |
| Final code review | ✅ Ready to merge (opus) |
| DB 마이그레이션 0002 | ✅ sandbox 적용 완료 |
| 실제 업로드 멱등/stale/롤백 재검증 | ⚠️ 미실행 (다음 세션 SHOULD) |
| PR | ⚠️ 미생성 |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-15-1348-upload-atomicity-issue8.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. Plan/Design/ledger(.superpowers/sdd/progress-pipeline-issue8.md)를 읽는다
3. git status, git log --oneline -8로 현재 상태 확인
4. 핸드오프 "다음 단계 → SHOULD"부터 시작 — 실제 파이프라인 실행으로 멱등/stale/롤백 재검증
5. 사용자 제약-금지 준수: fontagit 스키마 격리, 라이선스 정직성, secret 미노출, 서브워커 diff 직접 검증, apps/pipeline+supabase만
6. 결정 사항 표는 뒤집지 않음(변경 시 사용자 확인). develop에 UI 세션 커밋 병존 주의.

진행 전에 핸드오프를 읽었음을 확인하고, SHOULD 중 어디부터 시작할지 한 줄로 보고해주세요.
```
