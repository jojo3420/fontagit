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
