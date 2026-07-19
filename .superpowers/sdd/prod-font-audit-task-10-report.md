# Task 10 구현 보고서

## 결과

- prod 공개 RLS를 anon 자격증명으로만 읽는 `font-audit-scan`을 추가했다.
- 폰트 URL 요청은 기존 `audit_http.fetch_public_url`만 사용한다.
- scan 실패·대상 0건·빈 관찰·처리하지 못한 오류가 있으면 artifact를 만들지 않는다.
- artifact는 closed schema JSON과 canonical SHA-256 sidecar만 남긴다. 원문, 응답 헤더, 자격증명은 넣지 않는다.
- `font-audit-import`는 symlink·크기·읽기 중 변경·SHA·canonical bytes·schema·타입·개수·중복 run ID를 검증한 뒤 dev append-only 감사 테이블만 쓴다.
- 다운로드 404/410은 `audit_http.classify_download`를 재사용해 서로 다른 run이 24시간 이상 떨어졌을 때만 broken으로 판정한다.
- 라이선스 본문 hash 변화는 `needs_review` finding만 만들고 공개 폰트 값 적용 수는 항상 0이다.
- 주간 다운로드 검사와 분기 라이선스 검사 workflow는 `contents: read`, frozen lock, 30분 timeout, 7일 artifact 보관, 동시 실행 제한을 사용한다. 쓰기 키 이름은 없다.

## TDD 및 검증

- RED: `ScheduledObservation` 미구현 ImportError로 테스트 수집 실패 확인.
- focused: `uv run pytest tests/test_audit_runner.py -q` → 6 passed.
- full: `uv run pytest -q` → 175 passed.
- lint: Task 10 Python 파일 scoped ruff 통과.
- types: Task 10 Python 소스 scoped mypy 통과.
- YAML: 두 workflow Ruby YAML parse 통과.
- 보안 정적 검사: workflow의 `SERVICE|SECRET_KEY|PROD_SECRET` 0건, 예약 감사 구현의 새 HTTP 우회 0건.
- CLI: scan/import `--help` 오프라인 실행 성공.

## HIGH 보완: 공개 자격증명 경계

- 일반 `SUPABASE_URL`·`SUPABASE_ANON_KEY` fallback을 제거하고 예약 scan 전용 prod 공개 URL·anon key·allowlist를 필수로 바꿨다.
- URL은 path·query·fragment·userinfo가 없는 HTTPS origin만 허용한다. Managed Supabase는 project ref 또는 전체 origin이 allowlist와 정확히 같아야 하고, self-hosted는 전체 origin이 정확히 같아야 한다.
- `sb_publishable_` 공개 키만 허용하고 `sb_secret_`는 거부한다. legacy JWT는 크기를 제한하고 중복·알 수 없는 claim을 거부한 뒤 role이 정확히 `anon`인지 형식만 확인한다. 서명 검증은 Supabase에 맡긴다.
- 공격자 URL, 일반 설정 fallback, legacy `service_role` JWT가 SDK와 fetch 전에 중단되고 키·decoded claim이 로그에 남지 않는 RED→GREEN 회귀 검사를 기존 핵심 테스트에 통합했다.
- workflow는 공개 URL·allowlist를 GitHub variables에서, anon key만 GitHub secret에서 받도록 분리했다.

## 실행하지 않은 작업과 남은 위험

- 실제 workflow, 외부 폰트 URL, dev/prod DB 네트워크는 실행하지 않았다.
- prod 공개 대상 목록 조회는 Supabase anon SDK 경계이고, 실제 폰트 링크 요청만 `audit_http` SSRF 방어를 통과한다.
- 원격에 감사 migration과 공개 RLS가 아직 없다면 첫 workflow는 안전하게 실패한다.
- 1,240건 실응답 시간이 30분을 넘는지는 첫 수동 workflow에서 확인해 timeout·분할 실행을 조정해야 한다.
- `actionlint`는 로컬에 없어 실행하지 못했고 YAML parser와 정적 검사로 대체했다.
