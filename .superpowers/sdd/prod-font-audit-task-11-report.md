# Task 11 구현 보고

## 결과

- KS X 1001 한글 2,350자 exact 판정과 Basic Latin 52자 판정을 구현했다.
- 같은 family·weight·style 분할 파일은 cmap 합집합 후 판정한다.
- 일부 한글, 빈 cmap, family/face 충돌, 부분 파일은 `needs_review`로 보낸다.
- 공식·공공기관 파일만 굵기·이탤릭 자동 후보가 될 수 있다.
- 눈누 `@font-face` 파일은 문자 지원 근거로만 사용한다.
- `font-audit-run --stage metadata`를 연결했다.

## 안전 경계

- 입력 파일 최대 32 MiB, WOFF/WOFF2 선언 해제 크기 최대 128 MiB
- 일반 페이지 응답은 1 MiB, 승인된 폰트 파일 요청만 명시적으로 32 MiB 허용
- TTF/OTF/TTC/WOFF/WOFF2 signature allowlist
- fontTools 파싱은 격리 spawn 프로세스에서 실행하며 8초 후 terminate/kill
- Linux worker는 메모리와 CPU 제한 실패 시 안전하게 중단
- Windows는 격리 보장을 확인할 수 없어 자동 분석하지 않고 `needs_review` 처리
- 모든 외부 요청은 기존 `audit_http` SSRF·DNS·리다이렉트·TLS 경계를 재사용
- 원본 파일을 한 번만 열어 검사하고, 전체 SHA-256을 계산한 비공개 복사본만 파싱
- 원본 변경 여부를 다시 확인하며 모든 종료 경로에서 임시 파일과 worker를 정리
- DB에는 바이너리·응답 본문 없이 SHA-256과 구조화 값만 저장
- discovery/legacy URL은 폰트 파일로 다운로드하지 않음
- TTC는 face 구성이 같아도 항상 `needs_review` 처리

## 검토 보강

- 모든 자동 제안은 현재 DB 값을 `before_value`로 저장한다.
- 모든 발견 항목은 저장된 증거 snapshot ID와 연결한다.
- 공식·공공기관 증거만 굵기·변형·분류·태그 자동 후보로 허용한다.
- 눈누 자료는 `font-file-script` 역할과 `reference` 신뢰도로 문자 지원 범위에만 사용한다.
- 위 정책을 Python 검증기와 SQL 적용 함수에 동일하게 반영했다.
- OS/2 `fsSelection`의 이탤릭 비트도 판정에 포함했다.

## TDD 및 검증

- RED: 현재값·증거 연결, TTC, 이탤릭, HTTP 상한, 눈누 정책 실패를 먼저 재현
- focused: 관련 Python 테스트 24개 통과
- SQL: 기존 정책에서 실패를 재현한 뒤 로컬 임시 DB에서 `ALL PASS`
- full: pipeline 테스트 183개 통과
- Ruff: 전체 통과
- scoped mypy: metadata, HTTP, manifest, runner 통과
- full mypy: 기존 `noonnu_seed.py:346` 오류 1건만 재현

## 실행 제한과 남은 리스크

- 실제 네트워크·dev DB·prod DB는 실행하지 않았다.
- macOS는 운영체제의 메모리 제한 적용이 실패할 수 있어 부모 프로세스의 강제 시간 제한을
  기본 방어선으로 사용한다. Linux 운영 환경에서는 제한 적용 실패 시 분석을 중단한다.
- 2,350자 기준은 통과율을 위해 자동 완화하지 않는다.
