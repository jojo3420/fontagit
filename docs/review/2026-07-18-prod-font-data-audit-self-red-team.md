# prod 폰트 데이터 전수 조사 설계 — 자체 적대적 리뷰

> 대상: `docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md`
> 모드: superpowers 단일 설계 문서, 구현 전 Critical 중심

## 종합 점수: 63/100

- 완성도: 17/25
- 일관성: 13/25
- 실현 가능성: 11/20
- 엣지케이스·리스크: 12/15
- 코드·DB 추적성: 10/15

방향은 맞지만 환경 간 식별자, 기존 필드 호환, 원자적 prod 반영이 구체화되지 않아 그대로 구현하면 다른 폰트를 수정하거나 prod 일부만 바뀔 수 있다.

## 🔴 반드시 보강

### 1. dev·prod 사이의 안정 식별자가 없다

- 위치: 설계 165~172행
- 현재: DB 폰트 ID와 제공자 ID를 함께 쓴다고만 되어 있다.
- 문제: 현재 prod 발행기는 ID를 복사하지 않고 slug로 upsert한다(`noonnu_publish.py:96~101`). dev와 prod의 UUID가 같다는 보장이 없고 slug도 단독 근거로 금지했다.
- 보강: 환경 공통의 `font_sources(provider, provider_record_id)`를 만들고 manifest는 이 키로 대상을 찾는다. 한 출처 ID가 둘 이상 폰트에 연결되면 자동 반영을 중단한다.

### 2. `official_url` 의미 변경이 기존 화면을 즉시 깨뜨린다

- 위치: 설계 75~81행
- 현재: `official_url`을 제작사 홈페이지로 재정의한다.
- 문제: 웹은 이 값을 다운로드 CTA로 직접 사용한다(`mappers.ts:36`, `LicenseSummaryCard.tsx` 호출부). 의미만 바꾸면 버튼이 다운로드 페이지가 아닌 제작사 홈으로 이동한다.
- 보강: `foundry_url`을 새로 추가하고 `official_url`은 legacy 필드로 동결한다. UI·파이프라인 전환 후에도 한 릴리스 이상 삭제하지 않는다.

### 3. 기존·신규 라이선스 필드의 불변식이 없다

- 위치: 설계 84~95행
- 현재: `license_status`, `allow_commercial`을 추가하지만 기존 `license_verified`, `is_commercial_free`와의 관계가 없다.
- 문제: 검색 RPC와 웹 여러 경로가 기존 boolean을 계속 사용한다. 서로 다른 값이 동시에 공개될 수 있다.
- 보강: backfill 기간의 dual-write 규칙과 DB CHECK를 정의한다. `verified`가 아니면 검증된 라이선스 문구를 공개하지 않고, `allow_commercial`에서 기존 boolean을 파생한다.

### 4. prod manifest가 부분 반영과 동시 수정에 취약하다

- 위치: 설계 273~296행
- 현재: manifest와 역방향 manifest만 언급한다.
- 문제: 현재 발행기는 행별 upsert라 중간 실패 시 일부만 반영된다(`noonnu_publish.py:96~106`). 조사 이후 다른 작업이 값을 바꾸면 오래된 manifest가 새 값을 덮어쓸 수 있다.
- 보강: manifest에 before 값·`updated_at`·근거·스키마 버전·해시를 넣는다. service-role 전용 DB RPC가 모든 precondition을 검사한 뒤 한 트랜잭션으로 전량 적용하거나 전량 거부한다.

### 5. 공개 화면이 요구하는 출처 종류를 저장하지 않는다

- 위치: 설계 77~93행, 223~234행
- 현재: 화면에는 출처 종류를 표시한다고 했지만 `fonts`에는 다운로드·라이선스 출처 종류가 없다.
- 보강: `download_source_kind`, `license_source_kind`와 선택 근거 snapshot 연결을 추가한다. `verified`는 공식·공공기관 근거가 있을 때만 허용한다.

### 6. 공식 출처를 “찾는” 방법과 공공기관 허용 범위가 없다

- 위치: 설계 161~163행, 174~183행
- 현재: 공식 출처와 공공기관 출처를 찾는다고만 적었다.
- 문제: 임의 웹검색 결과를 자동 확정하면 같은 오염이 반복된다.
- 보강: 후보는 눈누의 의미 있는 링크, 기존 링크, 제작사 매핑, 승인된 공공기관 레지스트리에서만 만든다. 일반 검색 결과는 검수 후보로만 쓴다.

### 7. 상태 전이·중복 방지·링크 재확인 시간이 불명확하다

- 위치: 설계 84~85행, 123~132행, 185~195행
- 현재: 최초 상태와 finding 유일성, “시간 간격”이 정의되지 않았다.
- 보강: `pending → verified|needs_review`, `needs_review → broken` 전이를 정의한다. 첫 404·410은 needs_review, 24시간 이상 지난 독립 검사에서 다시 확인될 때만 broken으로 바꾼다. finding은 `(run_id, font_id, field_name)` 유일성을 갖는다.

### 8. 기존 파이프라인이 보정 필드를 다시 오염시킬 수 있다

- 위치: 설계 197~210행
- 현재: 새 감사 파이프라인의 자동 보정 조건만 정의하고 기존 `noonnu_enrich`·uploader의 쓰기 권한은 제한하지 않았다.
- 문제: 현재 enrich는 제안 분류 직후 `fonts`의 라이선스·출처·status를 직접 갱신한다. 전수 보정 뒤 재실행하면 예전 규칙으로 값을 덮을 수 있다.
- 보강: 검증 필드의 단일 writer를 전용 audit apply 경로로 제한한다. 기존 import/enrich는 원본·후보·finding만 만들고 검증 필드를 직접 쓰지 못하게 한다.

## 자기 비평 라운드

- 1차 지적: 13건
- 유지: Critical 8건
- Warning으로 약화: 원문 저장 용량, GitHub Actions 비활성 가능성, 예약 시간대
- 제거: UI Loading 상태, 신규 API 응답 포맷 — 이번 설계는 정적 상세 페이지와 CLI 중심이라 구현 차단 근거가 약함

## 적용 방침

사용자가 적대적 리뷰 후 문서 보강을 명시했으므로 위 Critical 8건을 설계 문서에 먼저 반영한다. 이후 보강본을 Claude Opus에 전달해 과잉 설계·추가 누락을 다시 검증한다.
