# progress-005: prod 폰트 데이터 감사 파이프라인 병합 + 배포 스크립트 확장 (2026-07-19)

## 맥락 (이 작업이 왜 필요했나)
눈누(noonnu) 등 외부 출처 메타데이터를 신뢰해 라이선스-한글지원 정보를 발행해온 기존 파이프라인은 부정확할 수 있어, 실제 폰트 파일(cmap)을 열어 한글 글리프 지원을 검증하는 감사 파이프라인이 별도 세션에서 설계-구현됨(`docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md`, plan 1928줄). 이번 세션은 그 구현(PR #76, 공유 워킹트리에서 다른 세션이 진행 중이던 작업)을 검증-병합하고, main/develop 동기화, 배포까지 마무리했다.

## 구현 요약 (무엇을 어디에)
- **DB 스키마**(`supabase/migrations/0017_font_audit_schema.sql`, `0018_apply_font_audit_manifest.sql`): `fontagit.fonts`에 `script_status`/`download_status`/`license_status` 등 컬럼 추가(전부 `add column if not exists`, 기본값 `pending`), 신규 테이블 `font_sources`/`font_audit_runs`/`font_source_snapshots`/`font_link_observations`/`font_audit_findings`. `apply_font_audit_manifest()` RPC는 `service_role` 전용, `reviewed_by`+`reviewed_at` 승인 메타데이터 없는 finding은 거부.
- **pipeline**(`apps/pipeline/src/fontagit_pipeline/audit_metadata.py` 신규, `audit_runner.py`에 `run_metadata_audit`/`_collect_metadata_evidence` 추가): fonttools로 폰트 파일을 열어 cmap 읽고 한글 글리프 실지원 여부(`script_status`) 판정. `--stage metadata`는 `sys.platform.startswith("linux")` 하드 게이트로 macOS/Windows에서 dry-run 외 실행 불가(CI도 legal/links용만 있고 metadata용 없음, `.github/workflows/`).
- **web**(`apps/web/lib/specimen.ts`, `LicenseSummaryCard.tsx`, `ClientFontFilters.tsx` 등): `isKoreanFont`가 `sourceTier` 휴리스틱(PR #75) 대신 `scriptStatus`(cmap 실검증) 기준으로 교체, 미검증 폰트는 한글+영문 혼합 확인 문구(`가나다 ABCabc 12345`) 표시. `LicenseSummaryCard`가 `licenseAudit.status`(verified/needs_review)에 따라 감사 권한 또는 "라이선스 재확인 필요" 표시.

## 시도와 실패 (원인 포함)
- **공유 워킹트리 rebase 충돌**: 로컬 `develop`에 origin에 없는 6개 커밋(설계문서 5개+`feat: add font audit schema`)이 있어 `git pull --rebase`가 충돌. 8개 파일 중 7개가 origin/develop과 바이트 단위 동일, 1개(plan.md)는 진행 체크박스만 오래된 버전임을 확인 후 `git rebase --abort` + `git reset --hard origin/develop`로 정리(유실 없음, reflog 보존).
- **적대적 코드 리뷰 오탐**: PR76 1차 코드리뷰가 CRITICAL 2건(IPv6 SSRF 우회, dev 자격증명 스푸핑) 제기했으나 실제 코드 확인 결과 이미 방어 로직 존재(오탐). 신규 기능 리뷰가 제기한 CRITICAL 1건(`fetcher(file_url)`에 `max_bytes` 누락 → 기본 1MB 제한 적용, 32MB 검사 무의미)은 실제 버그로 확인해 수정(`audit_runner.py`).
- **deploy.sh 실행 중 main이 다른 워크트리(`.worktrees/cleanup-test-build-warnings`)에 체크아웃돼 있어 root에서 체크아웃 실패**: 해당 워크트리의 미커밋 변경을 stash로 대피 → 원래 브랜치(`codex/cleanup-test-build-warnings`)로 되돌리고 stash pop → root에서 main 체크아웃 가능하게 정리.
- **`/fonts` 화면에 내부 데이터 출처 노출 회귀**: PR76에서 추가된 `ClientFontFilters.tsx`의 "출처" 필터가 `Google Fonts`/`눈누 수집`/`직접 등록` 라벨+건수를 그대로 노출. 사용자 발견 후 섹션 전체 제거(PR #79). sourceTier는 내부 데이터 수집 분류이므로 사용자 대체 필터 기준(카테고리/가격 등은 이미 존재)으로도 부활시키지 않기로 결정.

## 결정 근거와 기각된 대안
- **PR #77(main→develop, PR75 동기화) 폐기**: PR76이 이미 PR75의 sourceTier 휴리스틱보다 안전한 cmap 기반 로직으로 대체해 develop에 반영했으므로, PR77을 강행 병합하면 구버전 로직이 재도입되는 퇴행이 됨 — 병합 대신 close.
- **develop→main 승격 시 충돌 파일(specimen 관련 3개)은 develop 쪽(`--ours`) 채택**: main의 PR75 버전은 이미 develop의 cmap 버전보다 구식이므로.
- **prod `fonts` 테이블 실반영은 이번 세션에서 실행하지 않음**: 사용자가 설계 단계에서 직접 정한 결정 #8("prod 반영은 별도 승인 게이트 — 전수조사-rollback 검증 후에만 쓰기")이 문서(`docs/handoff/2026-07-18-1436-prod-font-data-audit.md`)에 명시돼 있고, `apply_font_audit_manifest` RPC 자체가 `reviewed_by`/`reviewed_at` 없이는 기술적으로 거부하도록 설계됨. 사용자가 채팅에서 "검수 생략, prod 바로 반영"을 즉흥적으로 요청했으나, 문서화된 결정과 충돌해 실행하지 않고 사용자에게 재확인 요청함.
- **deploy.sh 확장(브랜치/태그/위치인자 자동판별)**: `--branch <name>` 허용은 기존에 "main만 배포 가능"하던 안전장치를 의도적으로 완화한 것 — 어떤 브랜치든 clean+pushed 상태면 prod에 직접 배포 가능해짐(PR 리뷰 게이트 우회 가능). 사용자가 명시적으로 요청한 기능이라 구현했으나 리스크로 인지해둘 것.

## 재현-검증 명령어
```bash
# pipeline
cd apps/pipeline && uv run pytest -q && uv run ruff check . && uv run mypy src/fontagit_pipeline/audit_runner.py
# web
cd apps/web && npx vitest run && npx tsc --noEmit
# deploy.sh 문법/인자파싱만 검증(실배포 없이)
bash -n scripts/deploy.sh
```

## 미완료: 눈누/prod 데이터 실수집
`apps/pipeline/.env`에 `SUPABASE_URL`/`SUPABASE_ANON_KEY`(prod 공개 anon key)가 파이프라인이 요구하는 형태로 없어 `font-audit-export-baseline` 실행이 즉시 실패. 사용자가 값 채운 뒤 `font-audit-export-baseline` → `font-audit-bootstrap` → `font-audit-run --stage legal`(dev 저장, prod는 읽기 전용) 순으로 이어가면 됨. `--stage metadata`(cmap 한글 실검증)는 Linux 환경 필요(현재 macOS 세션에서 불가, CI 워크플로우도 미신설).
