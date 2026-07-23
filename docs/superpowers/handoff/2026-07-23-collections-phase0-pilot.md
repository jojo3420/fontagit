# 핸드오프: 컬렉션 0단계 파일럿 단계 (2026-07-23)

> **모드**: superpowers-plan (subagent-driven-development)
> **Feature**: collections-expansion 0단계 — manifest 조립 파이프라인 코드(Task1~4) 완료, 파일럿(approve CLI + Task5) 미실시

## 한 줄 상태
눈누 tags/weights를 감사 파이프라인으로 dev fonts에 채우는 데 필요한 **코드가 전부 완성**됐다(assert_safe 게이트, approve_finding, DB 조립 헬퍼, build CLI). 남은 건 (1)metadata approve CLI 구현(거버넌스 결정 필요) (2)Task5 라이브 파일럿(dev 쓰기+눈누 크롤, 하드 게이트).

## 완료 (이번+직전 세션)
- **PR #99**(develop 머지): 준비 인프라(Docker 이미지 `fontagit-pipeline:local`, 크롤 429/503 backoff) + REVISED plan + codex Must-fix 4건.
- **exec 브랜치**(feature/collections-phase0-exec, PR 예정/완료): Task1~4
  - Task1: `assert_safe` metadata stage 교정(needs_review 비율 SKIP, broken 비율 판정) + `run_metadata_audit` broken_count 산출. `audit_runner.py`.
  - Task2: `SupabaseAuditStore.approve_finding(finding_id, *, reviewed_by, stage)`(:496) — 검증(존재/field∈{tags,weights}/stage/status=needs_review)+조건부 UPDATE. `audit_store.py`.
  - Task3: `get_run`/`get_approved_findings`/`get_current_fonts_with_snapshots`(:764~) — build_manifest 정합 실증(통합테스트). `audit_store.py`.
  - Task4: `font-audit-manifest build --run-id --out`(`main_audit_manifest_build:646`). `__main__.py`.

## 다음 단계 A: metadata approve CLI (코드, dev 불필요)
**갭**: `noonnu-review approve`(`__main__.py:274`)는 legal 전용 `approve(schema,...)` 함수 호출 — Task2의 `SupabaseAuditStore.approve_finding`(stage 필수)로 미연결. metadata finding 승인 CLI가 없다.
**⚠️ 거버넌스 결정 필요**(착수 전 사용자 확인):
- 엄격 per-finding: `--finding-id`씩 승인(자동 일괄승인 금지 원칙 충실, 파일럿에 번거로움).
- 파일럿 batch: `--run-id --reviewed-by [--limit]`로 run의 needs_review metadata finding을 일괄 승인(각 건 field/status 검증은 유지, 운영자가 명시 트리거). MF4(codex)가 "일괄=게이트 우회" 경고했으므로 결정 필요.
**구현 위치**: `noonnu-review approve`를 metadata로 확장하거나 신규 서브커맨드. `store.approve_finding(finding_id, reviewed_by=, stage="metadata")` 호출.

## 다음 단계 B: Task5 파일럿 (dev 쓰기 + 눈누 라이브 크롤 = 하드 게이트, 사용자 확인 필수)
6단계 순서(REVISED plan `docs/superpowers/plans/2026-07-22-collections-phase0-execution-REVISED.md`):
1. **prod 기준선 스냅샷**: `font-audit-...`(`__main__.py:395` `--source prod-public`) → prod 공개행 → JSON. (prod 읽기, 쓰기 아님)
2. **bootstrap-manifest**: `font-audit-bootstrap --prod-snapshot <1의산출> --out output/audit/bootstrap-manifest.json`(입력: prod스냅샷 + output/tier-a.json + output/tier-b-noonnu-seed.json).
3. **감사 실행**: `font-audit-run --stage metadata --bootstrap output/audit/bootstrap-manifest.json --limit 50 --out ...`. **도커 필수**(Linux). dev에 needs_review finding 저장. env `-e SUPABASE_DEV_URL -e SUPABASE_DEV_SECRET_KEY`(apps/web/.env.local). Task1 게이트 교정 덕에 needs_review 비율로 안 막힘.
4. **승인**: 단계 A의 approve CLI로 metadata finding 승인(run_id 기준).
5. **build**: `font-audit-manifest build --run-id <run> --out output/audit/manifest`. forward/reverse sha256 로그 확보.
6. **apply**: `font-audit-manifest apply`(`:589`) — `--confirm-hash`에 5의 sha256. dev fonts에 tags/weights UPDATE(RPC).

## 제약 (반드시 준수)
- fonts 쓰기 = apply RPC(6단계)만. 감사(3)는 감사테이블만 write(fonts는 select). published status 불변. prod는 dev 검증 후 별도 게이트.
- dev 조회 Accept-Profile / 쓰기 Content-Profile: fontagit(client.schema("fontagit")로 처리됨).
- 도커 실행: 이미지 venv가 `/opt/venv`라 `-v $(pwd):/repo` 마운트 안전(PR#99 수정). metadata 감사는 Linux 전용.

## 확인 필요 / 리스크
1. supabase-dev MCP가 이 세션 미연결이었음 — 다음 세션에서 dev 조회 도구 확인(스키마 드리프트/실데이터 검증).
2. Task3 헬퍼는 마이그레이션 스키마로 정합 실증했으나 **실데이터 미검증**(source_key 실제 populate, computed field). Task5 3~5단계에서 실 데이터로 확인.
3. `get_current_fonts_with_snapshots` select("*") 전체 로드 — 파일럿 규모(50)엔 무방, 전체(1,110)엔 최적화 고려.
4. 1단계 prod 기준선 명령의 정확한 이름/인자 미확정(REVISED "확인 필요") — `__main__.py:395` 부근 확인.

## 재개 프롬프트
"docs/superpowers/handoff/2026-07-23-collections-phase0-pilot.md 읽고 이어받기. feature/collections-phase0-exec 기반(PR 머지됐으면 develop). 먼저 metadata approve CLI 거버넌스 결정(AskUserQuestion) 후 구현→리뷰. 그다음 Task5 파일럿은 dev 쓰기 직전 사용자 확인. supabase-dev MCP 연결 확인. SDD ledger=.superpowers/sdd/progress.md."
