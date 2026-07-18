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
- TTF/OTF/TTC/WOFF/WOFF2 signature allowlist
- fontTools 파싱은 격리 spawn 프로세스에서 실행하며 8초 후 terminate/kill
- Linux worker는 512 MiB 주소 공간과 CPU 제한을 추가 적용
- 모든 외부 요청은 기존 `audit_http` SSRF·DNS·리다이렉트·TLS 경계를 재사용
- 임시 파일은 명시적 경로로 만들고 파싱 직후 제거
- DB에는 바이너리·응답 본문 없이 SHA-256과 구조화 값만 저장
- discovery/legacy URL은 폰트 파일로 다운로드하지 않음

## TDD 및 검증

- RED: 신규 모듈 부재로 `ModuleNotFoundError` 확인
- GREEN: 신규 핵심 테스트 5개 통과
- focused: metadata + runner 테스트 11개 통과
- full: pipeline 테스트 180개 통과
- Ruff: 전체 통과
- scoped mypy: 신규 모듈, runner, CLI 통과
- full mypy: 기존 `noonnu_seed.py:346` 오류 1건만 재현
- CLI: `font-audit-run --stage {legal,metadata}` help 확인

## 실행 제한과 남은 리스크

- 실제 네트워크·dev DB·prod DB는 실행하지 않았다.
- 기존 `audit_http` 응답 상한 1 MiB가 32 MiB 입력 상한보다 더 엄격하다. 큰 폰트는
  자동 실패가 아니라 `needs_review`가 되며, 파일럿에서 비율을 확인한 뒤 별도 승인으로
  HTTP 상한 조정을 검토해야 한다.
- 2,350자 기준은 통과율을 위해 자동 완화하지 않는다.
