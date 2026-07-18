# Prod font audit Task 8 report

## 결과

예전 Noonnu 경로가 `fonts` 공개값을 다시 덮어쓰지 못하게 차단했다.

- `noonnu-enrich`: 눈누 구조화 snapshot과 `font_audit_findings` 후보만 저장한다. `fonts` 업데이트와 `license_proposals` 저장을 제거했다.
- 눈누는 참고 출처라서 모든 후보는 `needs_review`, `confidence=reference`, `auto_applicable=false`로 남긴다.
- `noonnu-review approve/reject`: exact finding ID와 `status=proposed`를 둘 다 조건으로 사용한다. `reviewed_by`, `reviewed_at`만 바꾸며 `fonts`나 legacy proposal을 수정하지 않는다.
- `noonnu-review unpublish`: 역방향 `font-audit-manifest apply` 안내와 함께 항상 차단한다.
- `noonnu-publish`: dry-run 대상 수만 제공한다. `--confirm` 포함 모든 실제 쓰기는 `RuntimeError`로 차단하고 `font-audit-manifest apply`를 안내한다.
- CLI 도움말에 deprecated 상태와 새 적용 경로를 표시했다.

## TDD 증거

- RED: 핵심 회귀 4개 모두 의도대로 실패했다.
  - enrich는 legacy proposal 경로로 빠져 `(0, 0, 1)`
  - review는 exact finding/reviewer API가 없어 `TypeError`
  - publish는 non-dry-run을 허용
- GREEN: 가능성이 큰 행복 경로 1개와 치명적 예외 1~2개만 남겼다.
  - 관련 3개 테스트 파일: `34 passed`
  - Task 8 source/test scoped Ruff: pass
  - Task 8 source scoped mypy: pass

## 전체 검증

- 전체 pipeline: `168 passed, 2 failed`
- 실패 2개는 동시에 다른 작업이 수정 중인 `tests/test_config.py`와 현재 `config.py` 불일치다. Task 8 파일은 아니다.
- 해당 동시 수정 테스트를 제외한 pipeline: `164 passed`
- 전체 Ruff: pass
- 전체 mypy: 기존 `noonnu_seed.py`, `noonnu_import.py` 6건 실패. Task 8 scoped mypy는 pass다.

## writer 전수 확인과 남은 위험

- Task 8 대상 `noonnu_enrich.py`, `noonnu_review.py`, `noonnu_publish.py`에는 `fonts.update/upsert/insert/delete` 경로가 0개다.
- 외부 네트워크, 실제 Supabase, prod/dev DB 쓰기, migration, deploy는 실행하지 않았다.

## 재리뷰 보완: import race 제거

- RED: `upsert_noonnu_draft` RPC 실패 후에도 예외 없이 slug 조회와 `fonts.update/insert` fallback이 실행됐다.
- GREEN: direct fallback을 전부 제거했다. 안전 RPC가 실패하면 쓰기 0건 상태로 `NoonnuImportError`를 반환한다.
- 이제 Noonnu import의 writer는 published 경계를 DB 안에서 원자적으로 검사하는 `upsert_noonnu_draft` RPC 하나다. 조회 후 published 전환 race로 slug-only update가 덮어쓰는 경로가 없다.
- 전체 writer rg: Noonnu 모듈의 `fonts` 접근은 enrich/review/publish 조회만 남았고, import 쓰기는 안전 RPC만 남았다.
- 최종 관련 테스트: `35 passed`; 전체 pipeline: `171 passed`; 전체 Ruff: pass.
- 수정 파일 scoped mypy: pass. 전체 mypy는 기존 `noonnu_seed.py` 1건만 남았다.
