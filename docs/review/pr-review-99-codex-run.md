### 종합 평가
- 전체 점수: 5/10
- 한줄 총평: SSRF 방어와 재시도 횟수 계산은 안전하지만, 실제 Docker 실행 경로가 깨지고 외부 서버가 재시도 대기 시간을 무제한 조종할 수 있습니다.
- 머지 권고: Must-fix 해결 전 불가

### 관점별 리뷰 (표)

| 관점 | 평가 | 핵심 지적 |
|---|---|---|
| 정합성 | Critical | Docker 실행 명령이 이미지 내부 가상환경을 가리며, 두 실행 계획도 서로 충돌합니다. |
| 영향도 | High | 기본값 기준 요청이 리다이렉트 단계마다 최대 4회로 증가합니다. |
| SOLID/SRP | Medium | 재시도 정책·대기 계산·로그가 한 함수에 섞였습니다. |
| 선제 위험 | Critical | `Retry-After` 하나로 작업이 장시간 멈추거나 즉시 실패할 수 있습니다. |
| 방어적 입력 | Critical | 음수·초대형 `Retry-After`, 비정수·과도한 `max_retries`를 막지 않습니다. |
| 보안 | Critical | DNS 고정 SSRF 방어는 유지됐지만, 가용성 공격과 URL 로그 노출 위험이 생겼습니다. |
| Silent Failure | High | 재시도 소진 후 별도 실패 로그 없이 429/503 결과를 반환합니다. |
| 테스트 | High | “30초 상한” 테스트가 실제로 30초 상한을 한 번도 검증하지 않습니다. |
| 스타일/가독성 | Medium | 429와 503 로그 코드가 중복됩니다. |
| 머피의 법칙 | Critical | 실제 파일럿 실행 시 가상환경이 사라지거나 첫 악성 헤더에서 전체 작업이 중단될 수 있습니다. |

### Critical - Must-fix (머지 차단)

| 파일:라인 | 문제 | 근거(diff 인용) | 제안 |
|---|---|---|---|
| `apps/pipeline/Dockerfile:4-11`, `docs/superpowers/plans/2026-07-22-collections-phase0-execution-REVISED.md:68-79` | 실제 런북대로 실행하면 이미지에 설치한 가상환경이 가려집니다. | Dockerfile은 `/repo/apps/pipeline/.venv`에 설치하지만 런북은 `-v $(pwd):/repo`로 `/repo` 전체를 덮습니다. 호스트 `.venv`가 없으면 의존성이 사라지고, 있으면 mac용 가상환경을 Linux가 읽을 수 있습니다. | 가상환경을 `/opt/venv`처럼 마운트 밖에 만들고 `PATH`도 그곳으로 지정하세요. 또는 저장소 전체가 아닌 필요한 입력·출력 디렉터리만 마운트하세요. 같은 마운트 조건으로 import 테스트도 해야 합니다. |
| `apps/pipeline/src/fontagit_pipeline/audit_http.py:365-394` | 외부 서버가 대기 시간을 무제한 조종하거나 크롤러를 즉시 중단시킬 수 있습니다. | `backoff_delay = float(retry_after)`에는 상한·하한이 없습니다. `Retry-After: -1`은 `time.sleep()`에서 예외가 나고, 매우 큰 값은 장시간 정지 또는 `OverflowError`를 유발합니다. `_RETRY_MAX_BACKOFF`는 헤더가 없을 때만 적용됩니다. | 파싱 결과를 `0~30초` 등 허용 범위로 제한하세요. 비정상 값은 기본 backoff로 대체하고, 표준 HTTP-date 형식도 처리하거나 명시적으로 거부하세요. |
| `docs/superpowers/plans/2026-07-22-collections-phase0-task23-execution-prep.md:78-118,173-185` | 정정 전 계획이 여전히 실행 가능한 지침으로 남아 있습니다. | 기존 plan은 `--bootstrap output/tier-b-noonnu-seed.json`, `build --report ...`를 지시하지만 REVISED 문서는 각각 실제 배선과 맞지 않는다고 밝힙니다. 상단에는 여전히 작업자가 이 plan을 구현하라는 지시도 있습니다. | 기존 plan 최상단에 `SUPERSEDED`를 명확히 표시하고 잘못된 명령을 제거하세요. progress·handoff의 “Docker/backoff 미구현” 상태도 현재 PR 기준으로 갱신하세요. |
| `docs/superpowers/plans/2026-07-22-collections-phase0-execution-REVISED.md:149-225` | 제안된 승인 방식이 사람 검수 게이트를 사실상 우회합니다. | `approve_finding(finding_id)`가 어떤 finding이든 `status="approved"`로 바꾸고 `reviewed_by="system-metadata-approval"`을 기록합니다. 뒤에서는 모든 approved finding을 조회합니다. 이는 `auto_applicable=False`, “검수 후 apply” 원칙과 충돌합니다. | 명시적으로 선택된 finding ID만 승인하고, 실제 검수자·run·stage·허용 필드(tags/weights)·현재 상태를 검증하세요. `needs_review → approved` 조건부 갱신과 dev 환경 강제도 필요합니다. 자동 승인이라면 reviewed로 기록하면 안 됩니다. |

### High - Should-fix

| 파일:라인 | 문제 | 근거(diff 인용) | 제안 |
|---|---|---|---|
| `apps/pipeline/src/fontagit_pipeline/audit_http.py:307-316,356-359` | timeout과 일시적 전송 오류는 재시도하지 않습니다. | `_fetch_once()`가 `FetchTimeoutError` 또는 `NetworkFetchError`를 던지면 재시도 루프가 즉시 종료됩니다. 준비 plan은 `429/503/타임아웃` 재시도를 요구합니다. | timeout과 재시도 가능한 전송 오류만 제한적으로 재시도하세요. SSRF 차단·본문 크기 초과·영구 오류는 재시도하면 안 됩니다. |
| `apps/pipeline/src/fontagit_pipeline/audit_http.py:329,343-356` | `max_retries` 입력 검증이 부족합니다. | 검사는 `max_retries < 0`뿐입니다. 실수는 `range()`에서 실패하고, 지나치게 큰 정수는 `2 ** attempt` 계산 비용과 요청 폭증을 만듭니다. | 정수 여부와 작은 상한을 검증하세요. 외부 설정이 필요 없다면 공개 인자 대신 내부 상수로 고정하는 편이 안전합니다. |
| `apps/pipeline/tests/test_audit_http.py:437-끝` | backoff 상한 테스트 이름과 검증 내용이 다릅니다. | `test_fetch_public_url_backoff_capped_at_30_seconds`가 확인하는 값은 `[1.0, 2.0, 4.0]`뿐이며 주석도 `not capped`라고 적혀 있습니다. | 32초가 계산되는 시도까지 진행해 실제 결과가 30초인지 확인하세요. 큰·음수 `Retry-After`, timeout, 404 무재시도, 재시도 후 redirect도 함께 검증해야 합니다. |
| `docs/superpowers/plans/2026-07-22-collections-phase0-execution-REVISED.md:104-143,257-278` | metadata 게이트를 50%로 바꾸는 설계가 근거도 없고 문제도 해결하지 못합니다. | 문서 자체 예상치는 needs_review 80~100%인데 해결안은 50%입니다. 한 폰트에서 tags와 weights finding이 각각 나오면 분자가 대상 폰트 수보다 커질 수도 있습니다. | 임의 비율 완화 대신 “예상된 수동 검수 finding”과 “수집 실패·비정상 finding”을 분리하세요. 게이트는 실패 대상 비율처럼 실제 위험 지표를 검사해야 합니다. |
| `apps/pipeline/Dockerfile:1-11` | 공급망 재현성과 최소 권한 원칙이 부족합니다. | `python:3.12-slim-bookworm`과 `pip install uv` 버전이 고정되지 않았고 컨테이너가 root로 실행됩니다. dev 비밀키와 쓰기 가능한 저장소도 함께 사용합니다. | `uv` 버전을 고정하고 비root 사용자를 추가하세요. 가능하면 베이스 이미지 digest도 고정하세요. |

### Medium

| 파일:라인 | 문제 | 근거(diff 인용) | 제안 |
|---|---|---|---|
| `apps/pipeline/src/fontagit_pipeline/audit_http.py:372-391` | 전체 URL을 로그에 기록합니다. | `extra={"url": target.url}`은 쿼리 문자열의 서명·토큰까지 로그로 남길 수 있습니다. | scheme·host·path만 기록하고 userinfo와 query는 제거하세요. |
| `apps/pipeline/src/fontagit_pipeline/audit_http.py:352-397` | redirect와 retry가 곱해져 요청량이 커집니다. | 기본값이면 각 redirect 단계에서 최대 4번 요청할 수 있습니다. 5회 redirect라면 최대 24회 요청과 여러 번의 본문 다운로드가 가능합니다. | 전체 요청 횟수 또는 전체 경과 시간에도 별도 상한을 두고, backoff에 작은 무작위 지연을 추가하세요. |
| `apps/pipeline/src/fontagit_pipeline/audit_http.py:360-394` | 재시도 소진 상태가 명확히 기록되지 않습니다. | 재시도 전 로그만 있고 마지막 429/503 반환 시 별도 경고가 없습니다. | 마지막 실패에 URL을 정제해 warning 로그를 남기고 호출자가 실패 목록에 포함하도록 계약을 명확히 하세요. |
| `apps/pipeline/src/fontagit_pipeline/audit_http.py:372-391` | 429/503 로그 코드가 중복됩니다. | 메시지만 다르고 `extra` 필드는 동일합니다. | 상태별 메시지만 계산한 뒤 한 번만 로그하세요. |
| `docs/progress/progress.md:21-27`, `docs/superpowers/handoff/2026-07-22-2100-collections-phase0.md:94-116` | 같은 PR 안에서 현재 상태와 과거 상태가 충돌합니다. | 문서는 Docker와 backoff가 미착수라고 기록하지만 이 PR에는 두 변경이 포함됩니다. | 역사 기록임을 표시하거나 현재 상태를 갱신해 다음 작업자가 잘못 재구현하지 않게 하세요. |

### 긍정적 관찰

- 재시도 전에 `_resolve_public_target(current_url)`을 거치고, 재시도 동안 검증된 `_PublicTarget`을 그대로 사용합니다. DNS 고정 기반 SSRF 방어를 우회하지 않습니다.
- redirect는 기존 바깥 루프에서 새 URL을 다시 검증하므로 redirect를 통한 사설 IP 접근 방어도 유지됩니다.
- 신규 재시도 루프는 `range(max_retries + 1)`이라 기본값 기준 최초 요청 1회와 재시도 3회가 정확합니다. 신규 코드 자체의 무한루프는 없습니다.
- curl 전송 실패를 HTTP 성공으로 오인하지 않는 기존 검사도 유지됩니다.
- 마지막 HTTP 헤더 블록을 역순으로 찾고 헤더 이름을 대소문자 구분 없이 처리한 점은 좋습니다.
- Dockerfile의 `--no-install-project → 소스 복사 → 최종 sync` 구조는 의존성 레이어 캐시에 적절합니다.
- `--frozen`, `--no-install-recommends`, apt 목록 삭제, `.dockerignore` 적용은 좋은 기본 설정입니다.