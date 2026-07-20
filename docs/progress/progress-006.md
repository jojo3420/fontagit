# progress-006: 감사 파일럿 결과 심층 조사 (2026-07-20)

## 맥락 (이 작업이 왜 필요했나)
dev legal 파일럿(run `23c49d23`, 50종) 결과 verified 0 / needs_review 26 / pending 24 / broken 0으로 게이트 실패(`pending remains`). Google Tier A 24종 pending 원인 조사에서 시작해 파일럿 전체의 verified=0 구조적 원인까지 규명. 코드 변경 없음(조사 세션).

## 핵심 발견 (파일:라인 근거)

### 1. Tier A(Google) pending 원인
- 파일럿 50종 = 눈누(Tier B) 26 + Google(Tier A) 24.
- bootstrap-manifest.json 집계: Tier A 128종 전부 `provider=google-fonts`, `download_url`/`license_source_url`/`foundry` 전부 **null**.
- `_all_candidates`(audit_runner.py:1395)는 URL 있는 항목만 후보로 생성(`if url:`) → download/license 후보 미생성 → `_choose_candidate` None(1315 continue) → outcome pending 유지(1312 초기값).
- 2차 잠재원인: registry에 official/public 0개라 `_approved_registry_entry` 항상 None → 설령 URL 있어도 priority=4(discovery)로 탈락(1319).

### 2. verified=0 근본 원인
- `source_registry.json`: entry 1개(네이버 clova.ai)뿐이고 `source_kind=discovery`. official/public **0개**.
- `license_rules.json`: `standard_licenses:[]`, `maker_templates:[]` 완전 비어있음. Plan line 449 "자동 확정 규칙 0건으로 시작" = 의도된 초기상태.
- verified 3경로(audit_license.py `classify_license` 49~89): (a) extractor=="deterministic" 선결(57), (b) 사람승인 human_review(60~69, `_reviewed_permissions` 190), (c) 표준/템플릿 지문 매칭(71~88, license_id+version+fingerprint 필요).

### 3. 눈누는 항상 needs_review → 게이트 구조 문제
- 게이트(audit_runner.py:227~231): target=0 / `pending>0`("pending remains") / `needs_review/target>0.10`.
- 눈누는 `source_kind=noonnu`(참고용), `_candidate_priority`(1787~1792) priority=2, auto_applicable=False(1380: official/public만). verified 불가 → 항상 needs_review.
- 파일럿 결과가 실증: 눈누 26종 100% needs_review. Tier A 제거해도 눈누-only는 needs_review 100% > 10% → 게이트 통과 불가.

### 4. human_review verified 미싱 링크 (설계 정공법의 본체)
- `_candidate_outcome`(1636) → `classify_license(parsed, registry, rules)`. `parsed`는 `_parse_candidate`(1484)→`extract_noonnu_font(html)` 크롤링 결과.
- human_review verified 조건(`_reviewed_permissions` 190~): snapshot의 `finding_status=="approved"` + `reviewed_by` + `reviewed_at` + `review_evidence_id` + `reviewed_permissions`.
- `noonnu_review.approve`(noonnu_review.py:41)는 `font_audit_findings`의 status/reviewed_by/reviewed_at/review_reason만 채움. `review_evidence_id`/`reviewed_permissions` 미기록.
- 크롤링 파서는 reviewed_* 필드를 절대 안 채움(주입 코드 코드베이스 0건). → 재판정 snapshot에 승인 데이터를 주입하는 경로가 없어 human_review verified가 **구조적으로 발생 불가**. 이 연결 고리 구현이 설계 정공법 슬라이스의 핵심.

## 파일럿 실행 사실 (로그 증거)
- pilot-legal.run.log: HTTP 요청 233줄 전부 supabase.co(POST/PATCH 182건 = snapshots/link_observations/findings/runs 실제 저장). 외부 문서(noonnu.cc/hsg.go.kr 등) fetch **0건** → 눈누 CTA 크롤링(`_discover_noonnu_cta` 1419)이 조기반환(dry_run 또는 `_is_noonnu_reference` 미통과). source-policy.json `crawl_allowed=unknown`.
- pilot-legal.md 제목 "Font audit dry-run"은 템플릿 오표기(실제는 dev 실행). fonts 테이블 직접 update 없음 → finding 판정과 fonts 반영(apply, audit_manifest.py:442/628)이 분리.

## verified 가능 데이터 (Tier B 1110종 license_source_url 도메인)
- 공공기관(public 후보): copyright.keris.or.kr 69, gongu.copyright.or.kr(공유마당) 35, mapo.go.kr 9 등.
- 제작사 공식(official 후보): uhbeefont.com 77, ownglyph.com 36, griun.co.kr 32, hangeul.naver.com 16, fonts.google.com 11 등.
- 신고 2종(흰꼬리수리-횡성한우체) 모두 tier=B provider=noonnu.

## 결정 근거와 기각된 대안
- 설계 정공법 접근법: 사람승인 경로 완성(채택) vs 표준지문 자동화(기각: 구현 크고 "자동규칙 0건 시작" 설계와 배치) vs 하이브리드.
- verified 실증 슬라이스: 공공기관 도메인 1개(gongu 추천) public 등록 + approve 보강(reviewed_permissions/evidence_id) + 재판정 주입 경로 신규 + 검증.
- 재판정 방식 미결(보류): 별도 재판정 명령(추천) vs approve 즉시 반영.
- 사용자 최종 결정: 설계 정공법 보류. 눈누 크롤링 실행 + fix PR 먼저. Tier A 재조사는 후속.

## 재현-검증 명령어
- 파일럿 산출물: `apps/pipeline/output/audit/{pilot-legal.json,pilot-legal.run.log,bootstrap-manifest.json,source-policy.json}`
- 도메인 집계: `jq -r '.entries[]|select(.current.source_tier=="B")|.current.license_source_url' bootstrap-manifest.json | sed -E 's#https?://([^/]+).*#\1#' | sort | uniq -c | sort -rn`
