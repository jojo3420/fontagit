# Task 5 완료 보고: 눈누 상세 추출과 라이선스 신뢰 판정

- Commit: `bfc2f95 feat: extract and classify font license evidence`
- 변경 파일: `audit_noonnu.py`, `audit_license.py`, `license_rules.json`, 신규 핵심 테스트 2개, 최소 상세 HTML fixture 2개

## TDD 증거

- RED: `uv run pytest tests/test_audit_noonnu.py tests/test_audit_license.py -q`
  - 결과: `ModuleNotFoundError`로 실패. 새 모듈이 없어서 의도대로 실패했다.
- GREEN: 같은 명령 결과 `4 passed`.

## 검증

- 신규 focused: `4 passed`
- 기존 noonnu seed/enrich 회귀: `42 passed`
- 전체 pipeline pytest: `176 passed`
- Task 5 scoped ruff: 통과
- Task 5 scoped mypy: `Success: no issues found in 2 source files`
- 전체 `ruff check src tests`: 기존 test 파일의 미사용 import 5건으로 실패했다. Task 5 파일과는 무관하며 수정하지 않았다.

## 안전성

- 눈누 상세 `data-font-detail`/article 내부만 추출한다. footer/nav/SNS/광고 링크는 후보에 넣지 않는다.
- 기본 보관은 structured-only다. `raw_text`는 항상 `None`이고 SHA-256과 selector 위치만 남긴다.
- 다운로드 CTA는 검증 전 `needs_review`다. 횡성한우체 URL은 사용자가 404를 제보했지만 단일 관찰만으로 `broken`을 확정하지 않는다.
- `verified`는 결정론적 추출 + 정확한 표준 fingerprint, 승인된 출처의 제작사 template fingerprint, 또는 승인자·승인시각이 있는 사람 검수에만 허용한다. LLM·custom·불일치 원문은 권한을 채우지 않고 `needs_review`다.
- 라이선스 사용자 요약은 여섯 권한과 제한 문구만 사용하며, 원문 페이지는 `source_url`로 별도 연결한다.

## 남은 불확실성

- `license_rules.json`은 안전한 빈 규칙 구조만 만들었다. 실제 표준/제작사 원문 fingerprint는 공식 원문 수집 및 사람 승인 후에만 추가해야 한다.
- 이 Task는 네트워크를 호출하거나 prod에 쓰지 않았다.

## 리뷰 보완: 근거 우회 차단

- RED: `uv run pytest tests/test_audit_noonnu.py tests/test_audit_license.py -q` 결과 7 failed, 4 passed. 승인 근거 없는 registry mapping, 공백 승인자·임의 시각·권한 없는 사람 검수, fallback evidence selector, 비폰트 `@font-face` URL, 첫 article 오선택이 각각 재현됐다.
- GREEN: 같은 명령 결과 11 passed.
- registry mapping은 이제 `SourceRegistry.model_validate()`를 거친다. 승인 근거가 빠진 official/public entry는 예외로 중단되고 discovery는 제작사 template verified에 쓰이지 않는다.
- 사람 검수는 `reviewed_by` 공백 제거, timezone 있는 ISO datetime 검증, 유효 권한 또는 `review_evidence_id`를 요구한다. 근거 ID만 있는 경우는 verified 근거로 남기되 적용 권한이 없어 `auto_applicable=false`다.
- parser는 data 속성 없는 값에 실제 `h1`, `dt + dd` selector를 증거 위치로 기록한다. font file 후보는 HTTP(S)와 path 확장자 `.woff/.woff2/.ttf/.otf`만 허용한다.
- `[data-font-detail]`이 없으면 이름과 두 개 이상의 상세 신호를 가진 article이 정확히 하나여야 하며, 없거나 여러 개면 `ValueError("font detail article is missing or ambiguous")`로 검수 큐로 넘길 수 있게 했다.

## 최종 검증

- focused: `11 passed`
- 기존 noonnu seed/enrich: `42 passed`
- 전체 pipeline pytest: `183 passed`
- scoped ruff: 통과
- scoped mypy: `Success: no issues found in 2 source files`
