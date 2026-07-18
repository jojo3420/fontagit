# Task 6 구현 보고서: append-only 저장과 50종 파일럿

## 범위

- 추가: `audit_store.py`, `audit_runner.py`, `test_audit_runner.py`
- 수정: `__main__.py`의 `font-audit-run` 명령
- 제외: prod URL·prod key·prod 쓰기·migration·deploy와 실제 dev DB 쓰기

## RED → GREEN

1. RED: `uv run pytest tests/test_audit_runner.py -q`
   - `ModuleNotFoundError: fontagit_pipeline.audit_runner`로 예상 실패를 확인했다.
2. GREEN: 결정론 50종 선택(흰꼬리수리·횡성한우체 포함), snapshot/finding 멱등성,
   dry-run DB 미호출의 핵심 3개 테스트가 통과했다.
3. applied finding 불변 경계도 `mark_applied` 부재로 RED를 확인한 뒤, 같은 finding은
   재사용하고 applied 뒤에는 새 finding을 남기도록 GREEN 처리했다.

## 구현 결과

- `AuditStore`는 실행·snapshot·observation·finding·완료 저장 계약을 제공한다.
  `SupabaseAuditStore`는 dev URL/service key만 받으며 공개 `fonts` 테이블을 변경하지 않는다.
- 동일 snapshot은 안정 키로 기존 ID를 돌려주고, applied finding은 덮어쓰지 않는다.
- 파일럿은 신고 폰트를 먼저 포함한 뒤 `source_tier → 제작사 → 도메인 → slug` 순으로
  같은 입력에 같은 50건을 고른다.
- dry-run은 `InMemoryAuditStore`도 호출하지 않고 JSON, Markdown, JSON SHA-256을 원자 저장한다.
- 현재는 외부 문서를 요청하지 않으므로, 눈누/기존 reference는 discovery finding과 pending으로만
  남긴다. 자동 승인·공개값 변경은 없다.

## 검증

- focused: `uv run pytest tests/test_audit_runner.py -q` → **3 passed**
- 전체 pipeline: `uv run pytest -q` → **182 passed**
- scoped: Task 6 파일 ruff, mypy → **통과**
- dry-run:
  `font-audit-run --stage legal --limit 50 --require-slug 흰꼬리수리 --require-slug 횡성한우체 --out output/audit/pilot-task6-dry --dry-run`
  - JSON/Markdown/SHA 생성 및 SHA 일치 확인
  - 종료 코드 **3**: 50건 모두 pending이라 안전 게이트가 의도대로 차단
  - DB 자격증명·DB 쓰기 0회

## 기준선 오류 (이번 범위 밖)

- 전체 `ruff check src tests`: 기존 테스트 unused import 5건
  (`test_noonnu_enrich.py`, `test_noonnu_publish.py`, `test_noonnu_review.py`).
- 전체 `mypy src`: 기존 Noonnu 모듈 7건
  (`noonnu_seed.py`, `noonnu_import.py`, `noonnu_review.py`).

## 남은 위험

- 이 단계는 안전한 검수 큐 생성만 한다. 실제 공식/공공 원문을 수집해 pending을 해소하는
  작업은 다음 수집 단계와 사람 검수가 필요하다.
- dev DB 저장 경로는 구현했지만 이번 작업에서는 실행하지 않았다.

## 리뷰 보완: 실행 경계와 후보 안전성

- RED: 실행 ID를 finding 키에서 빼면 서로 다른 두 실행이 같은 finding을 재사용했고, 일반 `SUPABASE_*` 값만으로 감사 쓰기 경계를 통과할 수 있었다. 필수 신고 폰트도 표시명이 아닌 slug로 고정해야 한다는 회귀를 추가했다.
- GREEN: finding 키를 `(run_id, font_id, field_name)`으로 고정했다. 같은 run은 applied 여부와 무관하게 기존 finding을 반환해 값을 바꾸지 않고, 새 run은 별도 finding을 만든다. dry-run ID도 finding ID에 포함한다.
- dev 쓰기는 `SUPABASE_DEV_URL`, `SUPABASE_DEV_SECRET_KEY`, 명시 allowlist만 허용한다. prod와 URL/project ref 또는 service key가 같으면 중단하며 일반 `SUPABASE_URL`/`SUPABASE_SECRET_KEY`는 fallback으로 쓰지 않는다.
- 파일럿 필수 대상은 흰꼬리수리·횡성한우체 slug가 각각 정확히 한 건인지 검사한다. slug와 provider 안정키 중복, 중복 `--require-slug`, 0건 gate를 모두 오류로 막는다.
- 후보는 승인 제작사 → 승인 공공기관 → 의미 있는 눈누 CTA → 승인된 기존 주소 순으로 고른다. 이름·제작사·문서 역할이 맞지 않으면 discovery만 남기며 홈페이지·다운로드·라이선스는 각자 finding으로 저장한다. 다운로드 2xx만으로 verified가 되지 않는다.
- dry-run은 fetcher와 AuditStore를 호출하지 않는다. `/tmp/fontagit-task6-fix/pilot.json` SHA-256은 `1581cc704a2672e599d9aafb12d0ab68ef54579d57c9abd85ad3760d19055e26`이며 pending gate로 종료 코드 3이 정상 발생했다.

## 최종 검증

- focused: `uv run pytest tests/test_audit_runner.py tests/test_config.py -q` → `8 passed`
- full pipeline: `uv run pytest -q` → `182 passed`
- scoped ruff/mypy → 통과

## 재리뷰 보완: dry-run 키와 눈누 CTA

- RED: dry-run finding UUID가 `proposed_value`에 따라 달라졌고, dev 쓰기 설정은 prod URL/key가 없는 상태도 통과했다.
- GREEN: dry-run finding UUID는 `(run_id, font_id, field_name)`만 사용한다. 같은 키의 proposal 본문이 달라도 같은 UUID다.
- 눈누 상세는 injected fetcher로만 읽어 `extract_noonnu_font`의 이름·제작사·다운로드 CTA를 구조화한다. 대상 이름과 제작사가 상세값과 모두 맞아야 CTA 후보를 만든다. CTA 목적지는 승인 registry와 다시 대조한다.
- dev 감사 쓰기는 `SUPABASE_DEV_URL`, `SUPABASE_DEV_SECRET_KEY`와 별도 allowlist를 필수로 요구한다. prod URL이 설정된 경우 project ref도 달라야 한다. secret은 비교하거나 로그에 남기지 않는다.
- dry-run은 fetcher·AuditStore를 호출하지 않고 fixture 상태를 집계한다. fixture가 없으면 pending으로 남아 gate가 안전하게 실패한다.

## 재리뷰 최종 검증

- focused: `8 passed`
- full pipeline: `182 passed`
- scoped ruff/mypy: 통과

## 필수 역할·실제 bootstrap·관찰 멱등성 보완

- 다운로드와 라이선스를 필수 역할로 따로 집계한다. 둘 중 하나라도 없으면 전체 폰트는 `verified`가 될 수 없다.
- Task 3 manifest의 `before`와 선택적 `current`에서 제작사·홈페이지·다운로드·라이선스 URL을 읽는다. 역할이 없는 `official_url`은 metadata discovery로만 유지한다.
- 링크 관찰은 DB unique key `(run_id, font_id, normalized_url)`로 원자 upsert한다. 같은 URL의 여러 역할은 첫 관찰을 재사용하고 역할은 snapshot과 finding에 남긴다.
- 수집 원문은 공개값에 저장하지 않고 SHA-256만 snapshot 내부 근거로 보존한다.
- 검증: focused `3 passed`, audit/config `36 passed`, 전체 pipeline `182 passed`, scoped ruff/mypy 통과.
- 실제 prod/dev DB 쓰기, migration, deploy, 외부 네트워크 호출은 실행하지 않았다.

## 최종 리뷰 경계 검증

- RED: 빈 대상은 실행을 시작한 뒤 통과했고, `before.official_url`은 역할별 기존 후보로 확대됐으며 structured-only snapshot은 빈 문자열 해시를 만들 수 있었다.
- GREEN: 빈 대상은 `start_run` 전 `AuditInputError`로 중단한다. legacy URL은 `existing-db/metadata` 검수 후보 하나로만 보존한다. 수집 bytes SHA-256은 snapshot 저장값과 structured evidence에 함께 남긴다.
- 검증: audit/config `8 passed`, 전체 pipeline `182 passed`, scoped ruff/mypy 통과.
- CLI dry-run은 실제 bootstrap 산출물이 저장소에 없어 그 입력으로는 중단했다. 별도 50종 fixture manifest로 JSON/SHA 생성(`6c1492663df7f0f350eaa2cace57e3f5014498787b183aa7f706bbe6f674da8b`)과 pending 안전 게이트 종료 코드 3을 확인했다. 이 실행도 외부 네트워크·DB 요청 0회다.
