# Task 7 결과: 정방향·역방향 manifest와 원자 적용 RPC

## 구현

- 승인된 finding만 allowlist로 묶어 정방향/역방향 manifest와 SHA-256을 생성한다.
- `official_url`, `slug`, `fonts.status`는 Python과 SQL 모두 변경 목록에서 거부한다.
- evidence는 dev `font_id` 대신 `(provider, provider_record_id)` 안정키로 이식한다. raw 보관 비승인 원문은 `raw_text=null`이며 hash와 위치 정보는 유지한다.
- 0018 RPC는 service role, SHA, schema, entry 수, 안정키, before, updated_at을 먼저 확인한다. 예외는 한 transaction 전체를 되돌린다.
- bootstrap RPC는 `font_sources`만 추가하며 공개 `fonts` 값은 바꾸지 않는다.
- CLI `font-audit-manifest apply`는 파일 SHA와 `--confirm-hash`를 대조한다. prod는 대화형 `yes`도 요구한다. 이번 작업에서는 dev/prod RPC를 실행하지 않았다.

## TDD·검증 증거

- RED: `uv run pytest tests/test_audit_manifest.py -q`에서 `ModuleNotFoundError: fontagit_pipeline.audit_manifest` 확인.
- GREEN: `uv run pytest tests/test_audit_manifest.py tests/test_main.py -q` → `10 passed`.
- 전체 pipeline: `uv run pytest -q` → `184 passed`.
- scoped lint/type: `uv run ruff check src/fontagit_pipeline/audit_manifest.py src/fontagit_pipeline/__main__.py tests/test_audit_manifest.py` 및 `uv run mypy src/fontagit_pipeline/audit_manifest.py src/fontagit_pipeline/__main__.py` 통과.

## 로컬 PostgreSQL 17 (임시 포트 55437)

- 0001~0017 뒤 0018 적용 성공. 원격 dev/prod에는 migration이나 쓰기를 하지 않았다.
- `supabase/tests/font_audit_manifest_test.sql` → `ALL PASS`.
  - 정상 manifest: 2건 모두 `needs_review` + `license_verified=false` 적용.
  - 한 행 before 불일치: 예외 뒤 snapshot 수와 다른 행 변경 0.
  - reverse: forward after와 일치한 2건이 pending/원래 download 값으로 복원.
  - bootstrap 정상: 2건 `font_sources` 연결, 공개 `fonts` 변경 0.
  - provider 충돌: 예외 뒤 충돌 키 1건 유지, 부분 insert 0.

## 남은 외부 단계

- dev 원격 migration/RPC 검증은 dev 자격증명과 별도 승인 뒤 수행한다.
- prod migration·manifest 적용은 사용자 명시 승인 뒤의 별도 작업이다.
