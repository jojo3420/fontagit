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

## 최종 근거 권한 보강

- 내부 SQL helper는 PUBLIC·anon·authenticated·service_role 모두 직접 실행할 수 없고, service role은 공개 RPC 두 개만 실행할 수 있다.
- 다운로드·라이선스·일반 메타데이터·문자 지원 근거의 문서 역할을 분리했다. 공개 확정 근거는 official/public만 허용하며 Noonnu는 승인 근거로 사용할 수 없다.
- entry별 `evidence_ids`는 해당 entry의 승인 finding이 실제 참조하는 snapshot ID 집합과 정확히 같아야 한다.
- bootstrap 충돌 테스트는 첫 entry `2003` 신규, 둘째 `2001` 기존 충돌 순서를 고정하고 `2003`이 0건인지 확인한다.
- 로컬 PostgreSQL 17 포트 55517에서 0001~0018과 SQL 5개 사례 `ALL PASS`. Python focused `11 passed`, 전체 `185 passed`, scoped ruff/mypy 통과. 원격 DB·prod·네트워크는 사용하지 않았다.

## 재검토 2차 수정 (2026-07-18)

- SQL RED: `reviewed_at=null`, `reviewed_by=[]`, orphan snapshot, 잘못된 top-level baseline SHA, bootstrap `matched` 불일치 문서를 추가했다. 기존 함수는 승인 메타데이터/정확 집합 검증 전에 다른 충돌로 진행하거나 잘못된 입력을 허용했다.
- GREEN: `reviewed_by`는 JSON string + 공백 제거 후 비어 있지 않음, `reviewed_at`은 timezone이 있는 JSON string과 안전한 timestamp cast를 요구한다. status도 JSON string `approved`만 허용한다.
- entry가 가리키는 snapshot/finding ID 집합과 bundle 집합이 정확히 같아야 하며, top/run baseline SHA는 64자리 소문자 hex와 동일값을 요구한다. bootstrap은 non-negative 정수 집계와 `entries`·`review_rows` 수의 계약을 확인한다.
- 로컬 임시 PostgreSQL 17에서 0018 재적용과 SQL `ALL PASS`를 확인했다. Python focused 2 passed, 전체 184 passed, scoped ruff/mypy 통과. 원격 dev/prod 적용은 하지 않았다.

## 동시 작업 통합·거부 경로 증명 (2026-07-18)

- 작업 중 다른 작업자가 남긴 dirty 변경(`verify_manifest_bytes`, 한 번 읽은 bytes 재사용, prod enable·승인 ID·승인 SHA gate)을 확인해 의도대로 보존·통합했다. 누가 만들었는지는 Git 작업 트리에 기록돼 있지 않아 특정할 수 없다.
- Python 핵심 테스트는 같은 bytes로 hash·파싱을 확인하고, prod에서 enable 또는 승인 SHA가 빠지면 입력창·RPC 전에 중단하며 manifest 본문을 실행당 한 번만 읽는 것을 검증한다. RPC의 `p_schema_version`은 정수다.
- SQL 거부 테스트는 null `reviewed_at`, 배열 `reviewed_by`, orphan snapshot, 잘못된 top baseline, top/run baseline 불일치가 snapshot/finding/font 변경 없이 거부되는지 확인한다. bootstrap matched 불일치 뒤 `font_sources` 전체 행 수도 변하지 않는다.
- 검증: 로컬 임시 PostgreSQL 17 migration + SQL `ALL PASS`; Python focused 11 passed, 전체 185 passed, scoped ruff/mypy 통과. 원격 dev/prod에는 접근하거나 적용하지 않았다.

## PR 전 evidence-role 보강 (2026-07-18)

- 동시 작업으로 들어온 evidence 역할 검증, helper 함수 execute 권한 회수, bootstrap 충돌 fixture 순서 고정을 보존했다.
- 추가로 한 entry 안의 `evidence_ids`와 `finding_ids`는 각각 배열 길이와 distinct UUID 수가 같아야 한다. 중복 ID는 before/evidence import/font update 이전에 거부한다.
- SQL은 동일 evidence UUID를 entry에 두 번 넣은 문서를 거부하고 snapshot·finding 수와 fonts 값이 변하지 않는지 확인했다.
- 검증: 로컬 임시 PostgreSQL 17 migration + SQL `ALL PASS`; Python focused 2 passed, 전체 185 passed, scoped ruff/mypy 통과. 원격 dev/prod 적용은 하지 않았다.

## Claude High H1~H3 수정 (2026-07-18)

- RED: `test_config.py`의 managed dev 무-prod-secret·자체 호스팅 origin 사례가 기존 구현에서 각각 `SUPABASE_PROD_SECRET_KEY` 강제와 `.supabase.co` 전용 파싱 때문에 실패했다.
- GREEN: service-role SQL 검사는 최신 `request.jwt.claims` JSON의 `role=service_role`을 우선 확인한다. JSON이 없을 때만 구형 `request.jwt.claim.role` 호환 경로를 쓴다. anon·손상 JSON은 모두 거부한다.
- `dev_write_credentials()`는 prod URL만 받아 scheme/host/effective-port origin을 비교하고 prod secret을 요구·비교하지 않는다. managed dev는 기존 ref allowlist, 자체 호스팅 dev는 `SUPABASE_ALLOWED_DEV_ORIGINS`의 명시 origin allowlist를 요구한다.
- bootstrap source insert는 `row_count <> 1`이면 예외로 중단한다.
- 검증: focused config/manifest/main `17 passed`, 전체 pipeline `170 passed`, scoped ruff/mypy 통과. 로컬 PostgreSQL 17 포트 55439에 0018을 적용하고 SQL `ALL PASS`(JSON service_role 허용, anon·손상 claims 거부) 확인. 원격 DB·외부 요청·prod 적용은 하지 않았다.
