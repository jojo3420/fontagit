# progress-008: OFL 표준 라이선스 google/fonts 공식 확인 자동 verified (2026-07-20)

## 맥락 (왜 필요했나)
하이브리드 검수 2단계 = 표준 라이선스 자동 verified. 눈누 전수 크롤링(1단계) 후, 표준 라이선스는 자동 확정하고 나머지는 사람 검수하는 방향. 이번 세션은 그 중 OFL만 범위로 잡아 엔진을 구축.

## 핵심 사실 정정 (1단계 분석 오류)
- 1단계(progress-007)는 `fonts.license_source_url` 도메인으로 OFL을 집계(github 43+google 11=54종)했으나 **부정확**.
- 진짜 OFL 집합은 **`fonts.license_type='OFL'` 컬럼 = 132종**. 전부 source_tier='A'(Google Fonts 출처), name_en이 로마자(Jua, Do Hyeon, Gowun Batang...). license_source_url은 전부 NULL.
- license_type 분포(dev fonts 1,294행): custom-free 1,110 / OFL 132 / None 50 / Apache-2.0 1 / UFL 1.
- github 도메인엔 custom-free 폰트(도스명조 등)도 있어 도메인=라이선스 매핑은 불가.

## 결정 근거와 기각된 대안
- 범위: OFL만(권한 단일-확정적). KOGL은 유형(제1~4)별 상업/변경 권한이 달라 도메인만으론 판정 불가 → 후속.
- 증거 수준: "공식 출처 확인"(B안). 눈누 라벨(license_type) 그대로 신뢰(A안)는 거버넌스 "공식출처 최우선" 위반이라 기각.
- 적용 방식: 감사 findings+매니페스트 절차(정식) 기각, **경량 스크립트 1개**(dry-run→--apply) 채택(사용자가 복잡도 낮추길 요청). 잃는 것=DB 감사 이력, 리포트 JSON으로 대체.

## 구현 요약 (무엇을 어디에)
- 신규: `apps/pipeline/src/fontagit_pipeline/ofl_verify.py` (+ `tests/test_ofl_verify.py` 14개).
- 실행: `uv run python -m fontagit_pipeline.ofl_verify` (dry-run 기본) / `--apply` (dev 쓰기). `__main__.py` 미수정.
- 공식 확인: `licenses.fetch_license_map()`(google/fonts 저장소 `ofl`/`apache`/`ufl` 트리) + `resolve_license_type(name_en, map)`. name_en 정규화(`normalize_family_dir`)가 `ofl/<dir>`와 매칭되면 확인.
- 순수함수 `plan_font_update(font, license_map, checked_at)`: 확인 시 제안 dict, 미확인 시 None → 테스트 용이.
- 쓰기: dev REST PATCH. **`Content-Profile: fontagit` 헤더 필수**(fontagit 스키마 대상). 읽기는 `Accept-Profile: fontagit`.
- 기록값(SIL OFL 1.1 원문 대조): license_status=verified, allow_commercial/modify/redistribute/embedding=allowed, allow_font_sale=denied(단독판매 금지), attribution_requirement=required, license_source_kind=official, license_source_url=`https://github.com/google/fonts/tree/main/ofl/<dir>`, license_checked_at=UTC, auto_approved=true.

## 시도와 실패 (재발 방지)
- 워커 초기 구현이 PATCH에 `Content-Profile: fontagit` 누락 → public 스키마로 오작동(--apply에서만 터짐, DB mock 단위테스트로는 못 잡음). 적용 전 코드리뷰로 발견-수정. 교훈: raw PostgREST 비-public 스키마 쓰기는 Accept-Profile(읽기)과 별도로 Content-Profile(쓰기)이 필수. 기존 코드는 supabase-py `.schema()`를 써서 참고 패턴 없었음.

## 재현-검증 명령어
- dry-run: `cd apps/pipeline && uv run python -m fontagit_pipeline.ofl_verify` → confirmed/unconfirmed 카운트 + `output/audit/ofl-verify-report.json`.
- 테스트: `uv run pytest tests/test_ofl_verify.py -q` (14 passed).
- dev 재검증(읽기): fonts에서 `license_type=eq.OFL` 조회 → license_status=verified 132, allow_commercial=allowed 132 확인.
- dev 조회 헤더: `Accept-Profile: fontagit`, creds=`config.load_audit_settings().dev_write_credentials()`.

## 실행 결과
- dry-run/apply 모두 confirmed=132, unconfirmed=0. --apply 성공=132/실패=0. 쓰기→읽기 재검증으로 132행 반영 확인.
