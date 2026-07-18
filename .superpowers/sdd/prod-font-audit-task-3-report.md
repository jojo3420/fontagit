# Prod font audit Task 3 보고

## RED

- 명령: `cd apps/pipeline && uv run pytest tests/test_audit_bootstrap.py -q`
- 결과: `ModuleNotFoundError: No module named 'fontagit_pipeline.audit_bootstrap'`
- 이유: 안정 출처키 bootstrap 모듈이 아직 없었음.

## 구현

- Tier A는 `name_en + slug + 기존 Google URL` 완전 일치 시 Google family key를 연결한다.
- Tier B는 `source_page` 전체가 `https://noonnu.cc/font_page/<숫자>` 형식일 때만 페이지 번호를 연결한다. 페이지 ID가 없거나 모호하면 검수 대상으로 남긴다.
- bootstrap manifest의 `public_updates`는 항상 빈 객체다. 공개 폰트값은 변경하지 않는다.
- JSON과 동반 `.sha256` 파일은 임시 파일 후 원자적으로 교체한다.
- `font-audit-export-baseline`은 anon key와 `fontagit` 읽기 스키마만 사용한다.

## GREEN / 검증

- `uv run pytest tests/test_audit_bootstrap.py -q` → `3 passed`
- `uv run pytest tests/test_audit_policy.py tests/test_config.py tests/test_audit_bootstrap.py -q` → `14 passed`
- `uv run pytest -q` → `160 passed`
- `uv run ruff check src/fontagit_pipeline/audit_bootstrap.py src/fontagit_pipeline/__main__.py tests/test_audit_bootstrap.py` → 통과
- `uv run mypy src/fontagit_pipeline/audit_bootstrap.py src/fontagit_pipeline/__main__.py` → 통과
- 실제 `tier-a.json` / `tier-b-noonnu-seed.json` 형식을 읽는 CLI smoke: Tier A 1건 기준선 → `matched=1, unmatched=0, conflicts=0`, SHA 파일 생성 확인.

## 남은 위험

- 실제 prod 공개 기준선 export와 전수 bootstrap은 아직 실행하지 않았다. prod 쓰기·마이그레이션·배포는 수행하지 않았다.
- 공개 기준선 명령은 `SUPABASE_URL`, `SUPABASE_ANON_KEY`가 prod 공개 프로젝트를 가리킬 때만 실행해야 한다.

## Commit

- `cdaa713 feat: bootstrap font audit baseline`

## 리뷰 보완 (Changes requested 해결)

- `foundry`가 `null`이 아닌 prod 행은 후보가 정확히 하나여도 자동 manifest entry를 만들지 않고 `foundry_precondition_not_null` 검수 대상으로 보낸다.
- bootstrap CLI는 기준선의 `record_count`, 1,240건 기본 계약, slug 정렬·중복, `baseline_content_sha256`, 동반 `.sha256`의 최종 `file_sha256`을 모두 확인한다. 테스트만 `expected_record_count` 인자로 작은 fixture를 허용한다.
- 기준선 JSON 본문 해시는 `baseline_content_sha256`, 최종 파일 해시는 `file_sha256`으로 CLI 로그와 sidecar에서 구분한다.

### 보완 검증

- RED: `load_prod_baseline` import 실패를 확인한 뒤 테스트를 추가했다.
- `uv run pytest tests/test_audit_bootstrap.py tests/test_config.py tests/test_audit_policy.py -q` → `18 passed`
- `uv run pytest -q` → `164 passed`
- `uv run ruff check src/fontagit_pipeline/audit_bootstrap.py src/fontagit_pipeline/__main__.py tests/test_audit_bootstrap.py` → 통과
- `uv run mypy src/fontagit_pipeline/audit_bootstrap.py src/fontagit_pipeline/__main__.py` → 통과
- 실제 `tier-a.json`/`tier-b-noonnu-seed.json`을 읽는 로컬 fixture CLI smoke: 1,240건 임시 기준선에서 `matched=1, unmatched=1239, conflicts=0`, bootstrap sidecar SHA-256 검증 성공. prod 요청·쓰기는 하지 않았다.
