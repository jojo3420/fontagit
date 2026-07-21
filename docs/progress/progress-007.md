# progress-007: 눈누 전수 크롤링 + 하이브리드 검수 1단계 (2026-07-20)

## 맥락 (다음 세션 2단계 재개용)
눈누 라이선스 출처를 dev에 전수 크롤링 완료. 하이브리드 검수(표준 라이선스 자동 verified + 나머지 사람 검수)의 1단계(출처 분석)까지 마침. 2단계(표준 라이선스 자동 판정 구현)가 다음 세션 재개점.

## 이번 세션 구현 (커밋됨)
- 요청당 1.5초 딜레이: `audit_http.py` `fetch_public_url(delay_seconds)` + `audit_runner.py` `_CRAWL_DELAY_SECONDS=1.5`를 legal/metadata/scan fetcher wrapper에 주입.
- 전수 배치 크롤링 CLI: `font-audit-crawl-all` (`__main__.py` `main_audit_crawl_all` + `audit_runner.py` `run_batch_crawl`).
  - 대상: `load_bootstrap_targets` → source_tier=="B"(눈누) 필터.
  - 배치: `--batch-size`(기본 100)씩 `run_legal_audit` 순차 실행. 게이트(`assert_safe`) 미호출.
  - 재개: 체크포인트 파일(`--checkpoint`, completed_font_ids)로 중단 지점부터 skip.
  - 실행 예: `uv run python -m fontagit_pipeline font-audit-crawl-all --stage legal --batch-size 100 --out output/audit/crawl-all-result.json --checkpoint output/audit/crawl-all-progress.json`

## 크롤링 결과 (dev, 실제 실행)
- 눈누 1,110종 12배치 완주. needs_review 1,109 / pending 1 / broken 0 / errors 22.
- errors 22 = 개별 URL 실패(UnsafeAddressError=SSRF 방어, ResponseTooLargeError, NetworkFetchError, FetchTimeoutError). 크롤링 실패 아님, 해당 종만 재시도 대상.
- 적재: 폰트별 다운로드/라이선스 출처 URL finding + 증거 snapshot(noonnu/metadata + noonnu/download). confidence=reference, auto_applicable=False, status=proposed.
- 배치별 별도 run 생성(12개). font_audit_runs.review_count로 배치별 needs_review 확인 가능.

## 하이브리드 1단계: 출처 분포 (dev fonts.license_source_url, 눈누 1,154종)
- 공공기관(.go.kr/.or.kr) 전체: 271종 (keris 69, gongu 35, mapo 9, taebaek 7 등) - 공공누리(KOGL) 표준 다수
- OFL(github 43 + google 11): 54종
- 표준 자동 규칙 후보 합계: 약 325종(28%) → 자동 처리 시 검수 대상 1,154 → 약 829종 축소
- 제작사(uhbeefont 77, ownglyph 36, cafe24 33, griun 32 등): 개별 약관, 제작사별 규칙 또는 검수
- 규칙 어려움(검수 대상): instagram 172, blog.naver 61, 출처없음 44 등

## 2단계 구현 방향 (재개점) - 핵심 제약
verified 자동 판정의 구조적 미싱 링크(progress-006 참조):
- `classify_license`(audit_license.py:49) verified 경로: extractor=="deterministic" → (a)human_review(reviewed_permissions) 또는 (b)standard/template fingerprint 매칭.
- 문제: 크롤링 파서(`_parse_candidate`→`extract_noonnu_font`)가 `license_id`/`license_version`을 안 채움 → standard_licenses fingerprint 매칭 불가. reviewed_* 주입 경로도 미구현.
- 2단계 선택지:
  - A. 도메인 기반 판정: registry/규칙에 도메인→라이선스유형 매핑(gongu→공공누리, github/OFL 등) 추가, 크롤링 문서 도메인이 매칭되면 해당 유형으로 verified. classify_license 확장 필요. fingerprint 취약성 회피.
  - B. 라이선스 파서 신규: 공공누리/OFL 문서에서 license_id/version 추출 파서 + license_rules.json 등록.
- 무검수 일괄 승인은 배제(사용자 결정): allow_commercial 등 세부 권한 None이라 오표기 리스크.

## dev 감사 데이터 조회법 (재현)
- config: `from fontagit_pipeline.config import load_audit_settings; url,key = settings.dev_write_credentials()`
- REST 헤더에 **`Accept-Profile: fontagit`** 필수(감사 테이블은 fontagit 스키마).
- 테이블: font_audit_runs(target_count/verified_count/review_count/broken_count), font_audit_findings(field_name/proposed_value/confidence/status), font_source_snapshots(provider/document_kind).
- fonts 테이블 라이선스 컬럼: status/license_status/license_verified/is_commercial_free/allow_commercial/allow_modify/allow_embedding/license_source_url.
- 분석 스크립트: scratchpad/analyze_sources.py, check_dev_data.py, check_fonts_status.py

## 현재 상태 (dev fonts, 눈누)
- status: published 다수(이미 서비스 중), license_status: pending(감사 결과 미apply), allow_commercial: None(세부 권한 미확인)
- 발행은 이미 됨 - 2단계는 "발행"이 아니라 라이선스 권한 확정(검수) 작업.
