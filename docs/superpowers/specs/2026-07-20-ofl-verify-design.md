# OFL 표준 라이선스 공식 확인 엔진 (설계)

작성일: 2026-07-20
상태: 승인됨 (구현 대기)
관련: 하이브리드 검수 2단계, progress-007.md, 폰트 감사 거버넌스(PR #76)

## 목표

dev fonts의 `license_type='OFL'` 132종을 **google/fonts 공식 저장소로 확인**하여, 확인된 폰트에 OFL 표준 권한과 `license_status=verified`를 채운다. 현재 이 132종은 `allow_*` 권한이 전부 NULL이라 상용 가능 여부 표기가 비어 있다.

## 배경-제약

- OFL 폰트 132종은 전부 `source_tier='A'`(Google Fonts 출처), `name_en`이 로마자(Jua, Do Hyeon, Gowun Batang...)라 정규화 매칭이 가능하다. `license_source_url`은 NULL이지만 확인은 URL이 아니라 저장소 트리로 한다.
- 거버넌스: "공식출처 최우선, 눈누 참고용". `license_type='OFL'` 값 자체는 눈누 임포트에서 온 참고 정보이므로 그대로 신뢰하지 않고, google/fonts 저장소 확인을 verified 게이트로 삼는다.
- 눈누 크롤 흐름(`classify_license`)은 Tier B 스냅샷 전용이라 OFL(Tier A, 스냅샷 없음)에 쓸 수 없다. 별도 경량 경로가 필요하다.

## 접근 (단순 스크립트)

새 파일 1개 `apps/pipeline/src/fontagit_pipeline/ofl_verify.py`. `__main__.py`는 건드리지 않는다.

실행: `uv run python -m fontagit_pipeline.ofl_verify` (기본 dry-run) / `--apply` (dev 쓰기).

기존 자산 재사용:
- 확인 출처: `licenses.py`의 `fetch_license_map()`(google/fonts `ofl`/`apache`/`ufl` 트리) + `resolve_license_type(name_en, map)`.
- 접속: `config.load_audit_settings().dev_write_credentials()`, REST 헤더 `Accept-Profile: fontagit`.

## 데이터 흐름

1. dev fonts에서 `license_type='OFL'` 조회 → id, name_ko, name_en, updated_at, 현재 권한 필드.
2. `fetch_license_map()`으로 google/fonts 맵 로드. **실패 시 즉시 중단(쓰기 0)**.
3. 폰트별 `resolve_license_type(name_en, map)` 판정:
   - 결과가 `"OFL"` → 확인 성공. 아래 권한을 제안값으로 계산(현재값과 다른 필드만 변경 대상).
   - `"OFL"이 아니거나 None`(맵에 없음/타 라이선스) → 미확인. 리포트에만 기록, 쓰기 없음.
4. dry-run: 확인/미확인 건수 + 폰트별 before→after 표를 stdout + 리포트 JSON(`output/audit/ofl-verify-report.json`)으로 출력.
5. `--apply`: 확인된 폰트만 dev fonts에 PATCH(by id). 값이 이미 같으면 no-op(멱등).

## 기록값 (SIL OFL 1.1 원문 대조 완료)

확인된 폰트에 쓰는 필드:

| 필드 | 값 | 비고 |
|---|---|---|
| license_status | verified | pending → verified |
| license_verified | true | 유지 |
| is_commercial_free | true | 유지 |
| allow_commercial | allowed | |
| allow_modify | allowed | |
| allow_redistribute | allowed | |
| allow_embedding | allowed | |
| allow_font_sale | denied | OFL 단독 판매 금지 |
| attribution_requirement | required | 저작권-라이선스 고지 필수 |
| license_source_kind | official | 증거: google/fonts |
| license_source_url | https://github.com/google/fonts/tree/main/ofl/&lt;dir&gt; | 확인된 공식 경로 |
| license_checked_at | 실행 시각(UTC) | 확인 시점 |
| auto_approved | true | 자동 확인임을 정직하게 기록 |

## 오류 처리-엣지

- google/fonts fetch 실패 → 예외로 중단, verified 0건. 부분 성공을 verified로 위장하지 않는다.
- name_en 매칭 실패/모호 → 미확인으로 안전하게 분류(오분류 아님, needs_review 성격).
- `--apply` 중 개별 PATCH 실패 → 해당 폰트 실패로 집계-로그, 나머지 계속. 최종 요약에 성공/실패 수 보고.
- prod는 이 슬라이스 범위 밖. dev만 대상.

## 범위 밖 (후속)

- prod 적용(사람 게이트 후속).
- custom-free 1,110종-None 50종-google/fonts 미확인 OFL 후보 → 사람 검수 대상.
- errors 22종 재크롤링(별건).

## 테스트 (TDD, 핵심만)

1. `resolve` 결과 'OFL' → 제안값이 위 표와 정확히 일치.
2. `resolve` 결과 None/타 라이선스 → 변경 대상에서 제외(쓰기 없음).
3. `fetch_license_map` 실패 → 스크립트 중단, 쓰기 0건.
4. 이미 verified+권한이 채워진 폰트 재실행 → no-op(멱등).
5. 리포트 JSON에 확인/미확인 건수와 폰트별 diff가 담긴다.

## 완료 기준

- dry-run이 132종의 확인/미확인 분류와 변경 미리보기를 출력한다.
- `--apply` 후 확인된 폰트의 `license_status=verified` + OFL 권한이 dev에 반영된다(쓰기→읽기 재검증 로그).
- 미확인 폰트는 손대지 않는다.
