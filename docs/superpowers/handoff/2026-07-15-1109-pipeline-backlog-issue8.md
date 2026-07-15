# 세션 핸드오프 — 2026-07-15 11:09 KST

> **모드**: superpowers-plan
> **Feature**: 파이프라인 후속 개선 (GitHub 이슈 #8)
> **이전 세션 종결 사유**: Slice 0 완료-머지 후 잔여 이슈 처리 인계

## 한 줄 요약

Slice 0 데이터 파이프라인(수집→라이선스 판별→Supabase 업로드)을 완료하고 PR #7로 main 머지했다. 다음 세션은 파이프라인 후속 개선(이슈 #8, 원자성-stale alias-방어 등 5건)을 이어받는다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. **이 핸드오프 파일을 읽는다**
2. **GitHub 이슈 #8을 읽는다**: `gh issue view 8` (https://github.com/jojo3420/fontagit/issues/8) — 잔여작업 체크리스트
3. **PR #7 2차 리뷰 리포트를 읽는다**: `docs/review/pr-review-7-dual-20260715-091549.md` ("다음 iteration" 항목 근거)
4. **Plan 참조**: `docs/superpowers/plans/2026-07-14-slice-0-data-pipeline-upload.md` (Slice 0, 완료)
5. **git 상태 확인**: `git status && git log --oneline -12`
6. **아래 "다음 단계"의 SHOULD 항목부터 시작** (MUST 차단 이슈는 없음)

---

## 작업 컨텍스트

### 사용자 원본 요청
> Slice 0(데이터 기반 + 파이프라인 업로드)을 완성하고, PR 듀얼 리뷰로 검증 후 머지. 잔여 후속 개선은 이슈로 등록.

### 진행 결과
- Slice 0 Task 1-8 전부 완료. PR #7 develop→main 머지 완료.
- 듀얼 리뷰(Codex+agy) 2라운드: Must-fix(라이선스 실패 시 데이터 손실) + Should-fix 반영.
- 후속 개선 5건은 이슈 #8(백로그 엄브렐러)로 등록.

### 사용자 제약-금지사항 (반드시 준수)

🔴 **반드시 (must)**:
- **fontagit 스키마 격리**: 모든 객체는 `fontagit` 스키마. `public` 접근 금지 (ollidam과 인프라 이력 있으나 현재는 FontAgit 전용 프로젝트).
- **라이선스 정직성**: `published`는 `license_verified=true` + `license_type in ('OFL','Apache-2.0','UFL')`만. validator + DB CHECK 이중 강제 유지.
- **secret 미노출**: `.env`-`.env.sandbox`는 gitignore. 로그/응답에 키 원문 금지(httpx 로그 WARNING 억제 유지).
- **서브워커 산출물 diff 직접 검증**: default-worker(구현)-code-reviewer(리뷰) 모두 브리프 이탈이 반복됨(Task 3-4-5-6-7). 메인이 반드시 git diff로 검증 후 커밋.
- **결정 표 뒤집지 않음** (변경 시 사용자 확인).

⚠️ **주의**: develop 브랜치에 **UI/디자인 다른 세션**의 커밋이 병존한다(`44b9c51`, `fbe0a45` = 디자인 정합 Slice 0+1). 파이프라인 세션은 `apps/pipeline/**` + `supabase/**`만 건드린다.

---

## Plan / Design 인덱스

| 문서 | 상태 |
|------|------|
| `docs/superpowers/plans/2026-07-14-slice-0-data-pipeline-upload.md` (Slice 0 파이프라인) | ✅ 완료-머지 |
| `docs/superpowers/plans/2026-07-15-design-fidelity-slice0-1.md` (디자인 정합, **다른 세션**) | 🚧 UI 세션 담당 |
| `.superpowers/sdd/progress.md` | ⚠️ UI 세션과 공유돼 웹 작업 원장으로 교체됨 — Slice 0 상세는 이 핸드오프 + 리뷰 리포트 참조 |
| `docs/progress.md` (사람용 세션 일지) | ✅ 갱신됨 |
| 리뷰 리포트: `docs/review/pr-review-7-dual-20260715-091549.md` | ✅ 2차 리뷰(다음 iteration 근거) |

---

## 코드 변경 상태 (git)

Slice 0 파이프라인 코드는 전부 커밋-머지 완료. Uncommitted는 문서/리뷰 산출물뿐:

```
?? docs/review/pr-review-7-*.md          (듀얼 리뷰 리포트 6개, 참조용)
?? docs/superpowers/handoff/2026-07-14-2209-...md  (이전 핸드오프, 참조용)
```

### 이번 세션 파이프라인 커밋 (main 머지됨)
| SHA | 메시지 |
|-----|--------|
| `2c1c62a` | Task6 fix: weights 정규화 버그 + 테스트 정정 |
| `fd1a5b5` | Task7: Supabase 업로더 |
| `b487c49` | Task8: 라이선스 조회 + 업로드 오케스트레이션 |
| `436c181` | .env.sandbox gitignore |
| `0a8d0d0` | service_role GRANT 마이그레이션 |
| `33bf12a` | httpx 로그 API 키 노출 억제 |
| `a20641d` | PR #7 리뷰: 라이선스 실패 시 업로드 보류 + published 이중 강제 + 업로드 방어 |
| `81e325a` | PR #7 Should-fix: 라이선스 실패 시 산출물 미생성 + status Literal |

---

## 결정 사항 (Decisions)

| # | 결정 | 근거 |
|---|------|------|
| 1 | FontAgit 전용 신규 Supabase 프로젝트(ref `zgxtfcpiokhkcrywlxmc`, ap-southeast-2) | ollidam 공유 아님 → prod 데이터 우려 소멸. psql pooler=`aws-0-ap-southeast-2.pooler.supabase.com` |
| 2 | 라이선스 조회 실패 시 업로드 보류 + 산출물 미생성 `return 3` | GitHub 실패 시 published 전량 draft 덮는 데이터 손실 방지(PR #7 Must-fix) |
| 3 | published 규칙 validator + DB CHECK 이중 강제 | 방어 심화(PR #7 Should-fix) |
| 4 | 머지 방식 merge(일반), develop 유지 | develop은 장기 브랜치(다음 Slice 1) |
| 5 | 후속 개선은 이슈 #8 백로그로 분리 | 원자성 등 큰 변경은 이 PR 범위 밖 |

---

## 블로커 - 미해결 이슈 (Blockers)

**없음** — Slice 0 완료-머지. 아래는 미결이 아니라 후속 개선(이슈 #8).

⚠️ 참고(운영): 파이프라인에 `GITHUB_TOKEN` 미설정 → 라이선스 판별이 비인증 GitHub API(60req/hr). 재실행 잦으면 rate limit → 라이선스 실패로 업로드 중단됨(데이터는 보존). 토큰 설정 권장(이슈 #8 NICE).

---

## 다음 단계 (Next) — 이슈 #8

🔴 **MUST**: 없음 (차단 이슈 없음).

🟡 **SHOULD** (품질-완성도, 이슈 #8):
- [ ] 업로드 원자성 — `fonts` upsert 후 `aliases` upsert 별도 요청, 중간 실패 시 불일치. Supabase RPC 트랜잭션으로 묶기. (`apps/pipeline/src/fontagit_pipeline/uploader.py` upload_records)
- [ ] stale alias 동기화 — 폰트명/규칙 변경 시 과거 alias 잔존. font_id 기존 alias 삭제 후 재삽입 또는 active 컬럼. (`uploader.py`)
- [ ] licenses.py GitHub 응답 방어 — `parse_license_map`의 `entry["path"]` 직접 접근 KeyError. `entry.get` + JSON 구조 오류도 `LicenseFetchError`로. (`apps/pipeline/src/fontagit_pipeline/licenses.py`)

🟢 **NICE-TO-DO** (이슈 #8):
- [ ] `license`/`license_type` 필드 통합 (models.py/transform.py, license는 항상 None)
- [ ] 파이프라인 `GITHUB_TOKEN` 설정 (rate limit 방지)

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 이슈 | https://github.com/jojo3420/fontagit/issues/8 |
| Plan | `docs/superpowers/plans/2026-07-14-slice-0-data-pipeline-upload.md` |
| 리뷰 리포트 | `docs/review/pr-review-7-dual-20260715-091549.md` |
| 업로더 | `apps/pipeline/src/fontagit_pipeline/uploader.py` |
| 라이선스 | `apps/pipeline/src/fontagit_pipeline/licenses.py` |
| 모델/변환 | `apps/pipeline/src/fontagit_pipeline/models.py`, `transform.py` |
| 오케스트레이션 | `apps/pipeline/src/fontagit_pipeline/__main__.py` |
| 마이그레이션 | `supabase/migrations/0001_fontagit_schema.sql` |
| 핸드오프(이 파일) | `docs/superpowers/handoff/2026-07-15-1109-pipeline-backlog-issue8.md` |

---

## 검증 상태 (Slice 0 기준)

| 항목 | 상태 | 비고 |
|------|------|------|
| 단위 테스트 | ✅ 69 passed | `cd apps/pipeline && uv run pytest -q` |
| ruff / mypy(strict) | ✅ 그린 | 0 errors |
| 통합 실행 | ✅ 수집 1951→업로드 136(공개 130) | 멱등성 2회 동일 |
| Supabase 연결 | ✅ 인증+스키마노출+service_role 권한 | psql/REST 실증 |
| PR #7 | ✅ MERGED | develop→main |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-15-1109-pipeline-backlog-issue8.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. GitHub 이슈 #8(gh issue view 8)과 리뷰 리포트 docs/review/pr-review-7-dual-20260715-091549.md를 읽는다
3. Plan(docs/superpowers/plans/2026-07-14-slice-0-data-pipeline-upload.md) 참조
4. git status, git log --oneline -12로 현재 상태 확인
5. 핸드오프 "다음 단계 → SHOULD"(이슈 #8)부터 시작 — 업로드 원자성부터
6. 사용자 제약-금지 준수: fontagit 스키마 격리, 라이선스 정직성, secret 미노출, 서브워커 diff 직접 검증, apps/pipeline+supabase만 건드림
7. 결정 사항 표는 뒤집지 않음(변경 시 사용자 확인). develop에 UI 세션 커밋 병존 주의.

진행 전에 핸드오프를 읽었음을 확인하고, 이슈 #8의 어느 항목부터 시작할지 한 줄로 보고해주세요.
```

---

✅ 핸드오프 메모 작성 완료. 다음 세션은 위 재개 프롬프트로 시작.
