# 핸드오프: 컬렉션 0단계 실행 단계 (2026-07-22 23:30 KST)

> **모드**: superpowers-plan (subagent-driven-development)
> **Feature**: collections-expansion 0단계 — 준비(A/C) harvest 완료, 실행(Task1~5) 미착수

## 한 줄 상태
준비 인프라(Docker 이미지 + 크롤 backoff)를 PR #99로 거뒀고, 실행 경로를 실코드로 정정한 REVISED plan을 확정했다. 다음은 REVISED plan의 갭 해결 Task1~5 실행(대부분 dev DB 통합 + dev 쓰기 게이트).

## 완료 (이번 세션)
- **PR #99** (develop 대상, 브랜치 feature/collections-task23-prep): https://github.com/jojo3420/fontagit/pull/99
  - Task A: Docker 이미지 `fontagit-pipeline:local` (uv 2단계 캐시) — 커밋 bc1af3e..ff49c9f
  - Task C: `audit_http.py` 429/503 지수 backoff + Retry-After, SSRF 보존, 17 passed — c55bdb6
  - REVISED plan + 계획문서 — af6420b
  - final-review: Ready to merge Yes (Critical/Important 0). codex 리뷰는 사용자가 직접.

## 실행 plan (SSoT)
`docs/superpowers/plans/2026-07-22-collections-phase0-execution-REVISED.md` — 6단계 파이프라인 + 갭 3종 해결설계 + Task1~5.

6단계: ①prod기준선 스냅샷(`main_audit_export_baseline` __main__.py:395) → ②bootstrap-manifest(`main_audit_bootstrap`:429) → ③감사(`main_audit_run`:465 --stage metadata, 도커/Linux) → ④metadata approve → ⑤manifest 조립 → ⑥apply(:589).

## 다음 단계 (실행 Task, REVISED 기준)
- **Task 1: assert_safe 게이트** (`audit_runner.py:226`) — ⚠️ **REVISED의 50% 임계값안은 결함**. metadata needs_review는 80~100% 예상이라 50%로도 막힘. 교정: metadata stage는 **비율 게이트 SKIP**(target>0/pending 체크는 유지). 추가로 auto_applicable=False finding이 "pending"인지 "needs_review"인지 실제 status 흐름 확인(pending이면 `pending_count` 체크도 걸림). 순수 코드+단위테스트, dev 불필요.
- **Task 2: `SupabaseAuditStore.approve_finding`** 추가(`audit_store.py`) — InMemory에만 있음(:144). metadata finding을 approved로 UPDATE. reviewed_by/reviewed_at 부여.
- **Task 3: DB 조회 헬퍼**(`audit_store.py`) — `get_run_for_manifest`/`get_approved_findings_for_run`/`get_current_fonts_with_snapshots`. ⚠️ evidence_snapshots 조인 SQL 미확정(확인 필요). build_manifest의 current_rows 형식(evidence_snapshots 각 id/run_id/font_id/provider/provider_record_id/raw_sha256/normalized_sha256)에 정확히 맞춰야 함. dev DB 통합 필요.
- **Task 4: `font-audit-manifest build` CLI**(`__main__.py`) — Task2/3 조합해 build_manifest→write_manifest_bundle. Task3 의존.
- **Task 5: 파일럿 실행** — 도커에서 6단계 end-to-end(prod기준선→bootstrap→감사→approve→build→apply) 50종. ⚠️ **dev 쓰기 게이트: 실행 직전 사용자 확인.**

## 제약 (준수)
- fonts 쓰기 = apply RPC(⑥)만. 감사(③)는 감사테이블만 write(fonts는 select). published 불변. prod는 dev 검증 후 별도 게이트.
- dev 조회 Accept-Profile / 쓰기 Content-Profile: fontagit 필수.
- metadata 감사는 Linux 전용 → 도커(`fontagit-pipeline:local`) 필수. dev 쓰기 시 `-e SUPABASE_DEV_URL -e SUPABASE_DEV_SECRET_KEY`. 자격증명 apps/web/.env.local.
- dev DB 소스변경 반영: 이미지 재빌드(캐시로 빠름) 또는 볼륨마운트. 단, `-v $(pwd):/repo`는 baked .venv를 가리므로 재빌드가 안전(dry-run 검증 완료).

## 확인 필요 (REVISED)
1. `get_current_fonts_with_snapshots` evidence_snapshots 조인 방식(RPC vs 다중 select) — dev SQL 미확정.
2. auto_applicable=False finding의 실제 status(pending vs needs_review) — Task1 게이트 교정에 직결.
3. Docker dev secret 주입 방식(--env-file vs export).

## 재개 프롬프트
"REVISED plan(docs/superpowers/plans/2026-07-22-collections-phase0-execution-REVISED.md)의 Task1부터 subagent-driven-development로 실행. Task1은 핸드오프의 교정(metadata 비율게이트 SKIP + status흐름 확인)을 반영. Task3~5는 dev DB 통합/쓰기라 게이트 준수. 브랜치는 develop에서 새로 분기(feature/collections-phase0-exec)."
