# Tier A OFL prod 승격 설계 (#89 재편)

> 작성일: 2026-07-21 (Phase 0 실측 후 재편)
> 상태: 승인됨
> 관련: 이슈 #89, OFL verified 트랙(#88), [[project-font-audit-governance]]

## 배경 — Phase 0 실측으로 원 설계 폐기

원 설계(새 `google_fonts_backfill` CLI로 URL 백필 → needs_review)는 실측과 어긋나 폐기.

dev/prod 직접 조회 실측 (2026-07-21, prod는 읽기만):

| 구분 | prod (136종) | dev (140종) |
|---|---|---|
| license_status | 전부 pending | OFL 132 verified, 8 pending |
| license_type | OFL 128, Apache-2.0 1, UFL 1, null 6 | OFL 132, Apache-2.0 1, UFL 1, null 6 |
| license_source_url null | 136 (전부) | 8 |
| download_url null | 136 (전부) | 140 (전부) |

핵심 발견:
- OFL 폰트의 license_source_url + verified 승격은 기존 `ofl_verify.py`가 dev에서 이미 해결(132종). prod만 미반영.
- `config.py`에 prod 쓰기 경계 메서드 없음(`supabase_prod_secret_key` 필드만 존재). env에 `SUPABASE_PROD_SECRET_KEY`는 실존, prod REST 읽기 HTTP 200 확인.
- manifest(bootstrap-manifest.json)는 prod 스냅샷(google-fonts 128 + noonnu 1110).

## 결정 사항

| # | 결정 | 근거 |
|---|---|---|
| 1 | 범위 = OFL prod 승격만 | 사용자 선택(최소 범위). 비-OFL 8종, download_url, foundry는 후속 이슈 분리 |
| 2 | 새 CLI 없이 `ofl_verify.py` 확장 | dev에서 검증된 트랙 재사용이 최단-최안전 |
| 3 | 자동 verified 허용 (기존 "자동승인 금지" 갱신) | 사용자 지시(2026-07-21): 검수 시간 부족, 예외 기반 검수로 전환. 근거는 google/fonts 공식 확인 |
| 4 | 이중 게이트 B안 | 공식 확인 + dev 교차. 사용자 선택 |
| 5 | prod --apply 전 go/no-go 1회 | 건별 검수 없음. 실행 승인만 |

## 설계

기존 `ofl_verify.py` 구조(fetch → plan → report → apply, base/headers 주입형 순수 함수) 유지.

1. **`--target dev|prod`** (기본 dev, 기존 동작 무변경). prod 시 이중 게이트 활성화.
2. **`config.py::prod_write_credentials()`** 신규: `dev_write_credentials()` 패턴 미러. `SUPABASE_PROD_URL` + `SUPABASE_PROD_SECRET_KEY` 반환, 신규 env 키 `SUPABASE_AUDIT_PROD_ALLOWLIST` 승인 없으면 ValueError. dev/prod origin 상이 검증 유지.
3. **이중 게이트** (prod 전용):
   - 게이트 1(기존): google/fonts 공식 라이선스 목록(fetch_license_map)에서 OFL 확인
   - 게이트 2(신규): dev에서 `license_type=OFL & license_status=verified` 목록 조회, `name_en` 일치 확인
4. **판정**: 둘 다 통과 → confirmed(PATCH 대상) / 하나라도 실패 → 예외 리포트(사유 포함), DB pending 유지(fail-closed).
5. **흐름**: dry-run(기본) → confirmed N/예외 M 리포트 → go/no-go 1회 → `--apply` PATCH. 필드는 dev와 동일: `OFL_FIELDS` + `license_source_url`(github.com/google/fonts/ofl/{family}) + `license_checked_at`.

## 검증

- 게이트 2 매칭 단위 테스트: 일치 / 불일치 / 이름 정규화 케이스
- prod dry-run 실측: confirmed=128 예상치 확인
- apply 후 prod 재조회: pending 136→8 확인 (쓰기→읽기 재검증)

## 범위 제외 (후속 이슈 등록)

- 비-OFL 8종: Roboto Slab(Apache-2.0), Ubuntu(UFL), Google Sans + Material Icons/Symbols 계열 6종(license_type null) — 개별 검수
- `download_url` 백필: dev/prod Tier A 전체 null. published 상태로 서빙 중이므로 영향 별도 확인 필요
- `foundry` 백필

## 리스크

- prod 실서비스 DB PATCH: go/no-go 승인 + 실패 건 로그 + fail-closed로 완화
- dev/prod `name_en` 불일치 시 예외 증가 가능: 실측상 분포 동일해 가능성 낮음. 발생 시 예외 리포트로 드러남
- prod는 자체 호스팅(OCI VM2) REST: 쓰기 시 `Content-Profile: fontagit` 헤더 필수(기존 apply_update에 이미 존재)
