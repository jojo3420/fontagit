# PR #99 리뷰 최종 리포트 (Codex + Claude 크로스 리뷰)

> 생성: 2026-07-23 - PR: https://github.com/jojo3420/fontagit/pull/99 - develop ← feature/collections-task23-prep
> Codex 원문: `pr-review-99-codex-run.md` - Codex 종합점수 5/10(Must-fix 존재)

## 크로스 리뷰 판정 (Codex Must-fix 4건 — 모두 diff/코드로 확인, 전부 동의)

| # | Codex Must-fix | Claude 판정 | 근거(실측) | 조치 |
|---|---|---|---|---|
| MF1 | Docker `-v $(pwd):/repo` 마운트가 `/repo/apps/pipeline/.venv`를 가려 파이프라인 깨짐 | 동의 | dry-run에서 직접 재현. 컨트롤러가 앞서 동일 문제 확인 | Dockerfile venv를 `/opt/venv`로 이전(`558215d`) — 마운트 有無 모두 import=linux 검증. REVISED plan Step 3에 마운트-venv 주의 노트 추가 |
| MF2 | `backoff_delay = float(retry_after)`에 상한 없음 → 악성 Retry-After로 초장기 sleep / `-1`이면 `time.sleep` 예외 | 동의 | `audit_http.py` 재시도 루프에서 Retry-After만 `_RETRY_MAX_BACKOFF` 미적용 확인 | `min(max(float(retry_after),0.0), _RETRY_MAX_BACKOFF)`로 클램프(`66d1d6b`) + 상한/음수 테스트 보강. pytest 19/19 |
| MF3 | 정정 전 원본 plan이 실행 지침으로 남아 잘못된 명령 유도 | 동의 | 원본 plan에 `--bootstrap tier-b-noonnu-seed.json`/`build --report` + "구현하라" 지시 잔존 | 원본 plan에 SUPERSEDED 배너 + progress/handoff 상태 정정(도커-backoff는 PR#99로 완료 명시) |
| MF4 | REVISED의 `approve_finding`이 어떤 finding이든 일괄 approved → 검수 게이트 우회 | 동의 | REVISED plan 갭4 설계가 `auto_applicable=False` 검수 게이트/거버넌스와 충돌 | REVISED plan 갭4를 명시적 per-finding 검증 승인(stage/field=tags-weights/needs_review→approved 조건부, `--reviewed-by` 실검수자)으로 재설계 |

## Should-fix 반영/판정
- backoff 상한 테스트 이름-검증 불일치 → MF2 수정에 실제 상한 테스트 포함(동의-반영).
- gap-3 assert_safe 50% 상향안 결함(needs_review 80~100%라 무의미) → REVISED plan에서 "metadata는 needs_review 비율 게이트 SKIP, broken 비율로 판정"으로 교정(동의-반영).
- timeout/네트워크 오류 재시도 미포함 → **의도적 스코프 결정(429/503만, YAGNI)**. Task C brief에서 명시 제외했으므로 pass(비동의). 필요 시 후속.
- Dockerfile 비root/버전 digest 고정 → 유효한 개선이나 로컬 감사 실행용 이미지 범위에서 후속(Nice-to-have).

## 머지 결정: ✅ 머지 가능
- 동의한 Must-fix 4건 전부 조치 완료(코드 2 커밋 + 문서 정정). 남은 Must-fix 0건.
- 검증: pytest 19/19, Docker build + run(no-mount/mount) OK, editable 확인.
- 사용자 사전 승인("동의 시 수정 후 머지")에 따라 squash 머지 진행.
