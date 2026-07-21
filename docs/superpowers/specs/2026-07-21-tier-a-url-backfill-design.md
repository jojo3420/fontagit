# Tier A(Google Fonts) 폰트 URL 백필 설계 (#89)

> 작성일: 2026-07-21
> 상태: 초안 (적대적 검증 반영, 사용자 리뷰 대기)
> 관련: 이슈 #89, [[project-font-audit-governance]], OFL verified 트랙(#88)

## 배경

prod 폰트 감사(legal 스테이지)에서 `provider=google-fonts`인 Tier A 약 128종이 `download_url`-`license_source_url`-`foundry`가 모두 null이라 검증 후보가 생성되지 않아 `pending`(판정 보류)으로 남는다. legal 감사의 후보 생성 로직(`audit_runner.py`의 `_all_candidates`)은 URL이 있는 항목만 후보로 만들기 때문에, "검증 실패"가 아니라 "검증할 데이터가 없어 보류" 상태다.

Google Fonts는 메타데이터를 공개 Web API(`webfonts/v1/webfonts`)로 확보할 수 있고, 시드에 쓰던 `GOOGLE_FONTS_API_KEY`와 기존 유틸(`client.py::fetch_webfonts`)을 재사용할 수 있다.

## 적대적 검증으로 확정된 전제 (원설계 수정)

이 설계는 초기 가정을 코드로 적대적으로 검증한 뒤 수정됐다. 검증 근거는 `audit_runner.py`, `models.py`, `__main__.py` 실코드다.

1. **URL 백필만으로 `verified`에 도달하지 못한다.** `audit_runner.py:1642` 근처에서 license 후보가 `source not in {"official","public"}`이면(백필로 채운 URL은 `source="existing"`) 무조건 `needs_review`로 강제된다. 따라서 백필의 현실적 도달점은 `pending → needs_review`이며, `verified`는 후속 단계(사람 검수 또는 registry 전략)가 필요하다.
2. **prod 쓰기 경로가 아직 없다.** `google_fonts_backfill` CLI와 fonts 테이블 PATCH 로직은 미구현이다. prod 쓰기는 현재 Tier B 전용 `noonnu_publish`만 있고, prod service-role 키 설정도 없다. 신규 구현이 필요하다.
3. **Tier A 128종의 라이선스 분포가 미검증이다.** 전부 OFL이라는 보장이 없다. Apache-2.0/UFL이 섞이면 `license_source_url` 단일 규칙이 깨진다. 설계 확정 전 사전 검증이 필요하다.
4. **검증된 사실**: `GoogleFontRaw.files["regular"]`(`models.py:8-19`, `test_client.py:29`)로 `download_url` 생성 가능. legal 감사는 macOS 실행 가능(`__main__.py:485`의 Linux 게이트는 metadata 스테이지 전용).

## 목표 (재정의)

- **1차 목표**: Tier A 128종의 `download_url`-`license_source_url` 백필로 legal 감사가 검증 후보를 생성하게 해 `pending`을 탈출시킨다. 도달점은 `needs_review`(검증 후보 존재).
- **2차 목표(후속)**: `needs_review`가 된 Tier A를 `verified`로 승격. OFL 폰트는 기존 `ofl_verify.py`(#88) 트랙과 연계하거나 사람 검수(거버넌스 게이트)로 처리.
- **비목표**: 백필 단계에서 자동 `verified` 부여(거버넌스의 자동승인 금지 위반). `foundry` 필드(후보 생성과 무관).

## Phase 0: 사전 검증 (설계 확정 조건 — 구현 전 필수)

구현 착수 전에 아래를 확인해 설계 위험을 제거한다.

1. **Tier A 라이선스 분포**: `bootstrap-manifest.json`의 Tier A 128종을 google/fonts로 확인해 OFL/Apache/UFL 비율 파악. 단일 규칙 가능 여부 판정.
2. **OFL verified 트랙과의 중복**: #88의 OFL verified 132종과 Tier A pending 128종이 겹치는지 확인. 이미 verified된 폰트는 백필 대상에서 제외(범위 축소 가능성).
3. **`needs_review → verified` 경로 확정**: 백필 후 needs_review가 된 폰트를 verified로 올리는 실제 경로(ofl_verify 재사용 vs registry에 google-fonts를 official/public 등록 vs 사람 검수)를 결정.
4. **prod service-role 키**: prod DB 쓰기 인증(키 위치, config 필드명)을 확인. env SSoT 구조([[ref-env-file-ssot]]) 기준.

## 구현 설계

### CLI: `google_fonts_backfill`

`apps/pipeline`에 독립 CLI 추가(`font-audit-crawl-all` 계열). 일회성 작업이라 감사 파이프라인과 분리.

```
python -m fontagit_pipeline google-fonts-backfill --target dev [--apply] [--limit N]
```

- `--target dev|prod` (기본 dev), `--apply` 없으면 dry-run(변경 미적용, 리포트만)
- 흐름:
  1. 대상 DB에서 `provider='google-fonts'` AND (`download_url` IS NULL OR `license_source_url` IS NULL) 폰트 조회 (dev 조회 시 `Accept-Profile: fontagit`)
  2. `fetch_webfonts(api_key)`로 Google Fonts 전체 조회(약 1500+종), family name 정규화 후 매칭
  3. 필드 매핑(아래), 매칭 실패분은 리포트에 남김(무음 스킵 금지)
  4. `--apply` 시 fonts 테이블 PATCH(`Content-Profile: fontagit`). dev는 service-role, prod는 별도 prod service-role 키
  5. 결과 리포트: 백필 N종, 매칭 실패 M종(사유 포함)

### 필드 매핑

- `download_url` ← `GoogleFontRaw.files["regular"]`(regular 없으면 첫 variant). 검증됨.
- `license_source_url` ← **Phase 0 결과에 따라 결정.** 후보: `https://fonts.google.com/specimen/{family}/license`(family 정규화: 공백→하이픈) 또는 `github.com/google/fonts/.../OFL.txt`. 라이선스 분포가 OFL 단일이 아니면 라이선스별 분기. (⚠️ 규칙이 코드에 없어 하드코딩 필요 — Phase 0에서 확정)
- `foundry`: 이번 범위 제외.

### dev → prod 2단계 (#90 OFL 승격과 동일 패턴)

1. `--target dev --apply` 백필
2. `font-audit-run --stage legal`(macOS 가능) 재실행 → pending 카운트 감소(needs_review 증가) 확인
3. 사람 검토(백필 정확도 + 매칭 실패분)
4. `--target prod --apply` 승격 (수동 게이트, prod service-role 필요)

## 검증 방법

- 백필 전/후 pending-needs_review 카운트 비교(감사 리포트)
- family name 정규화 매칭 단위 테스트(공백/대소문자/한글 별칭 케이스)
- dry-run 리포트로 매칭 실패 폰트 육안 확인 후 `--apply`

## 리스크

- **family name 매칭 실패**: DB `name_en` vs API `family` 불일치(공백-대소문자-별칭). 정규화 + 실패 리포트로 대응, 무음 스킵 금지.
- **라이선스 규칙 분기**: OFL 외 라이선스 섞이면 license URL 규칙 복잡화. Phase 0에서 선제 확인.
- **prod 쓰기 사고**: prod service-role로 fonts 테이블 직접 PATCH는 되돌리기 어려움. dry-run 필수 + 사람 게이트 + 백필 전 스냅샷 권장.
- **needs_review 적체**: 128종이 needs_review로 몰리면 사람 검수 부담. ofl_verify 연계로 OFL 자동 처리 가능한지 Phase 0에서 판단.

## 확인 필요 (미해결 — 사용자/후속 결정)

1. `license_source_url` 최종 URL 형식(specimen license vs github OFL.txt) — Phase 0 라이선스 분포 확인 후 확정
2. `needs_review → verified` 승격 경로 — ofl_verify 재사용 vs registry 등록 vs 사람 검수
3. OFL verified 트랙(#88)과 Tier A pending 중복 범위 — 실제 백필 대상 수 확정
4. prod service-role 키 위치/config 필드명

## 범위 요약

- 신규: `google_fonts_backfill` CLI 1개, family 정규화 유틸, 매칭 단위 테스트
- 재사용: `fetch_webfonts`(client.py), fonts 테이블 조회/PATCH 패턴
- Phase 0(사전 검증) 완료 후 구현 착수. 미완료 시 착수 금지.
