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

## 보안 재검토 수정 (2026-07-18)

- RED: 중첩 `after`의 알 수 없는 필드와 배열 형태의 `reviewed_by`를 넣은 Python 계약 테스트가 기존 구현에서 실패했다. 기존 SQL 테스트도 finding이 빈 문서를 넣어 새 필수 근거 검증에서 실패했다.
- GREEN: manifest의 run·entry·snapshot·finding을 폐쇄 스키마로 검증하고, 각 변경 필드를 같은 source key·snapshot·사람 승인 finding에 정확히 연결했다. 역방향은 원래 finding의 before/after를 반대로 대조한다.
- 0018은 before/after의 동일 allowlist 전 필드를 실제 DB 값과 비교하고, UUID 재사용 시 run/snapshot/finding의 저장 내용 충돌을 거부한다. bootstrap도 최상위·entry 키와 중복 key를 사전 거부한다.
- 로컬 임시 PostgreSQL 17 포트 55438에서 0001~0018을 적용한 뒤 SQL `ALL PASS`: 정상 2건, 역방향 전체 복원, missing finding, snapshot UUID 내용 충돌, bootstrap duplicate 모두 부분 반영 0을 확인했다.
- Python: focused `2 passed`, 전체 `184 passed`; scoped ruff/mypy 통과. 원격 dev/prod migration·RPC·데이터 쓰기는 실행하지 않았다.

## 승인 게이트·SQL 테스트 후속 보강

- missing finding 테스트가 자체 sentinel 예외까지 삼키던 문제를 고쳐, 예상 RPC 오류가 실제 발생해야만 통과한다.
- bootstrap은 정상 2건 전량 적용과 `첫 entry 신규 + 둘째 기존 provider 충돌` 시 신규 0건을 별도 사례로 검증한다.
- prod CLI는 전체 해시 2회 확인(`--confirm-hash`, `--approved-hash`), 승인 ID, `FONTAGIT_PROD_MANIFEST_ENABLED=true`, 대화형 `yes`를 모두 요구한다. manifest 파일은 한 번 읽은 동일 바이트로 해시·파싱·RPC 전송한다.
- 로컬 PostgreSQL 17 포트 55437 SQL `ALL PASS`, focused `10 passed`, 전체 pipeline `184 passed`, scoped ruff/mypy 통과. 원격 DB와 네트워크는 사용하지 않았다.

## 재검토 2차 수정 (2026-07-18)

- SQL RED: `reviewed_at=null`, `reviewed_by=[]`, orphan snapshot, 잘못된 top-level baseline SHA, bootstrap `matched` 불일치 문서를 추가했다. 기존 함수는 승인 메타데이터/정확 집합 검증 전에 다른 충돌로 진행하거나 잘못된 입력을 허용했다.
- GREEN: `reviewed_by`는 JSON string + 공백 제거 후 비어 있지 않음, `reviewed_at`은 timezone이 있는 JSON string과 안전한 timestamp cast를 요구한다. status도 JSON string `approved`만 허용한다.
- entry가 가리키는 snapshot/finding ID 집합과 bundle 집합이 정확히 같아야 하며, top/run baseline SHA는 64자리 소문자 hex와 동일값을 요구한다. bootstrap은 non-negative 정수 집계와 `entries`·`review_rows` 수의 계약을 확인한다.
- 로컬 임시 PostgreSQL 17에서 0018 재적용과 SQL `ALL PASS`를 확인했다. Python focused 2 passed, 전체 184 passed, scoped ruff/mypy 통과. 원격 dev/prod 적용은 하지 않았다.
