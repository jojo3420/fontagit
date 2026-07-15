# 업로드 원자성 + stale alias 동기화 Design (이슈 #8 SHOULD)

> 작성: 2026-07-15 - 출처: GitHub 이슈 #8, PR #7 듀얼 리뷰(`docs/review/pr-review-7-dual-20260715-091549.md`)
> 범위: `apps/pipeline` + `supabase`만. `fontagit` 스키마 격리 유지. 결정 표 불변.

## 문제

현재 `uploader.py:upload_records`는 폰트마다 `fonts` upsert와 `aliases` upsert를 **별도 요청 2회**로 실행한다. 두 정합성 구멍:

1. **비원자성** — 폰트의 `fonts`는 저장됐는데 뒤이은 `aliases` 요청이 실패하면 "별칭 없는 폰트" 불일치. 루프 중간 실패 시 일부 폰트만 반영.
2. **stale alias** — `aliases`는 upsert만 하므로 수집 목록에서 빠진 옛 별칭이 DB에 잔존.

`supabase-py`는 클라이언트 트랜잭션 미지원 → Postgres 함수(RPC) 안에서 묶는 것이 유일한 현실 경로.

## 결정 (사용자 확정)

| 항목 | 결정 | 근거 |
|------|------|------|
| 원자성 범위 | **폰트별 원자** (RPC 1회 = 폰트 1개) | 파이프라인이 멱등 재실행이라 전체 롤백 불필요. 핵심 불일치(fonts/aliases 짝 깨짐)를 함수 단순하게 해결 |
| stale alias | **삭제 후 재삽입** | 별칭은 폰트 파생 조회 데이터라 이력 보존 불필요. `aliases` 참조 FK 없어(0001 확인) id 변동 무해 |

## 설계

### 1. `supabase/migrations/0002_upsert_font_rpc.sql`

`fontagit.upsert_font(p_font jsonb, p_aliases jsonb) returns uuid` 함수 신설. 함수 본문이 단일 트랜잭션이라 아래 3동작이 폰트당 원자적:

- `fonts`를 `slug` 기준 upsert(on conflict do update) → `font_id` 확보
- 그 `font_id`의 기존 `aliases` 전량 `delete` (stale 제거)
- `p_aliases`(jsonb 배열, 각 `{alias, alias_norm}`)를 insert

보안: `security definer` + `set search_path = fontagit, pg_temp` 고정(search_path 조작 차단). 호출은 secret key(service_role) 전용.

### 2. `uploader.py` 재작성

- `upload_records`: 폰트당 두 요청 → **RPC 1회**(`client.schema("fontagit").rpc("upsert_font", {"p_font": ..., "p_aliases": ...})`).
- `build_alias_rows`: `font_id`를 앱이 정하지 않으므로 시그니처에서 `font_id` 제거, `{alias, alias_norm}`만 반환. DB 함수가 id 채움.
- `build_font_row`는 그대로 재사용(slug 포함, id 제외).

### 3. `licenses.py` 방어 (독립 소작업)

`_get_tree_sha`/`fetch_license_map`/`parse_license_map`의 `r.json()["tree"]`, `entry["path"]`, `entry["type"]` 직접 인덱싱을 `.get()` 기반으로. 응답 구조 이상 시 `KeyError` 대신 안전 스킵 또는 `LicenseFetchError`로 감쌈.

## 에러 처리

RPC 실패 시 해당 폰트만 실패, 앞서 커밋된 폰트는 유지(폰트별 원자). `__main__.py` 기존 업로드 실패 경로(`return 3`) 재사용.

## 테스트

- `build_alias_rows` 시그니처 변경(font_id 제거) 단위 테스트 갱신.
- `upload_records`가 폰트당 RPC를 올바른 payload로 호출하는지 mock 검증.
- `licenses.py` 방어: 깨진 응답 입력 시 죽지 않음.
- RPC 원자성-stale 삭제는 통합 실행(psql 쓰기→읽기 재검증)에서 확인.

## 범위 밖

`fontagit` 외 스키마, UI, `apps/pipeline`-`supabase` 외 디렉터리. NICE-TO-DO 2건(license 필드 통합, GITHUB_TOKEN)은 별도.
