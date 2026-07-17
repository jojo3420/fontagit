# Progress

## 프로젝트 소개

FontAgit(폰트 아지트)는 국내외 무료-유료 폰트를 검색-비교하고 공식 다운로드/구매 페이지로 연결해 주는 폰트 아카이브 웹사이트입니다. 폰트 파일을 직접 호스팅하지 않고 공식 페이지로 안내하며, 검색 유입과 광고를 수익 모델로 합니다. 검색으로 들어오는 일반 사용자, 디자이너, 마케터, 학생이 주 사용자입니다.

## 주요 기능

- 폰트 목록 탐색과 폰트별 상세 페이지(실제 서체 견본, 원하는 문장 미리보기 입력, 상업적 이용 가능 여부, 공식 페이지 링크)
- 유료 폰트 상세에서 비슷한 무료 대안 추천
- 인기 폰트 트렌드(주간/월간 TOP)
- 홈 히어로 + 이번 주 TOP 10, 다크모드
- 폰트 데이터 자동 수집-라이선스 판별-Supabase 적재 파이프라인(구글폰트 OFL/Apache/UFL 자동 공개, 서버 배치)
- 폰트 비교(최대 3종 나란히 미리보기), 타입 캔버스(한 글자를 전체 폰트로), 테마별 컬렉션, 폰트 등록 신청 폼
- 웹 화면이 Supabase 실데이터(공개 폰트 130종+컬렉션)를 정적 페이지로 표시(목업에서 실데이터로 연동 완료) + 검색엔진용 메타/사이트맵
- 폰트 검색(/search): 한글-영문-띄어쓰기-오타를 흡수하는 별칭 검색 (예: '본고딕', '본 고딕', 오타 '본고딩' → 노토 산스 KR)
- 홈/트렌드 TOP 10 실측 인기 랭킹: 공식 링크 '이동' 클릭을 익명으로 집계해 표시(클릭 데이터가 없으면 '최신 등록'으로 정직하게 폴백)

## 진행 기록

## 2026-07-17 - 클릭 rate limiting DB 최후방어 (슬라이스3 후속)

- 상태: 완료 (PR #18 생성, 리뷰 대기 — 미머지)
- 완료한 일: 클릭 기록(record_click)의 어뷰징 방어를 DB 계층에 구현. 같은 폰트를 짧은 시간에 대량 클릭(봇 연타)하면 조용히 무시하도록 폰트별 10초 20건 상한을 걸고, 동시 요청이 상한을 우회하는 경합(race)을 advisory lock으로 차단. IP 기반 정밀 차단(Kong 게이트웨이)은 자체호스팅 prod 인프라 작업이라 설계 문서로 인계.
- 커밋/PR: `8d34c14`(마이그레이션 0008), `e9d6d56`(SQL 테스트), `83ff5b0`/`a8c6914`(설계-계획-리뷰 문서). PR #18 (https://github.com/jojo3420/fontagit/pull/18). dev psql 실측: RED(0007 상태 상한없음 노출)→0008 적용→GREEN(click_rate_limit_test ALL PASS)→회귀(font_clicks_test ALL PASS). 최종 리뷰(Opus) Ready to merge YES, Critical 0.
- 결정사항: rate limit 마이그레이션=0008, 등록 신청=0009로 재배치(순번 연속성). B(DB)는 폰트별 전역 상한(IP 미사용), A(Kong)는 IP당 분당 30건 인계(real IP/route 플러그인 상속 주의). dev MCP self-signed 인증서 블로커는 psql `sslmode=require`로 우회 가능(실증됨). Codex 듀얼리뷰 Must 3건(race/Kong IP/route 상속)+Should 3건 설계 반영.
- 남은 일: (1) prod에 0008 적용(명시 승인 — prod는 0007도 미적용이라 배포 트랙에서 함께). (2) Kong IP 제한 적용(설계 5장). (3) 배포 전 병렬 부하 테스트(R4 동시성 실증, wrk/ghz). (4) PR #18 리뷰-머지.
- 관련 문서: `docs/superpowers/specs/2026-07-17-click-rate-limiting-design.md`, `docs/superpowers/plans/2026-07-17-click-rate-limiting.md`, `docs/review/review-result-dual-20260717-125336.md`
- 상세 히스토리: 없음

## 2026-07-17 - Top10 이동 클릭 집계 완성 (슬라이스3, F-03)

- 상태: 완료 (PR #17 MERGED)
- 완료한 일: 공식 링크 '이동' 클릭을 익명(IP/식별자 미저장)으로 기록하고 홈/트렌드 TOP 10을 실측 클릭순으로 표시. 클릭 데이터가 없으면 "최신 등록"으로 폴백하고 라벨도 정직하게 전환(인기 사칭 금지). 이중 코드리뷰(code-reviewer Opus + Codex gpt-5.6-sol 교차)로 검증한 뒤 저비용 개선 3건 반영.
- 커밋/PR: PR #17 MERGED (https://github.com/jojo3420/fontagit/pull/17, squash `bfe2632`). 교차리뷰 반영 `1007f0c`(클릭 기록 동기예외 방어, 트렌드 RPC 비정상응답 throw, SQL C5 랭킹순서 검증). 머지 게이트: 깨끗한 env에서 117개 테스트 green 직접 실측.
- 결정사항: 익명 쓰기는 RPC-only(원본 테이블 REVOKE+RLS), RPC는 SECURITY DEFINER+search_path 고정. 데이터 0건 폴백=source:'latest'이며 폴백 화면에 "인기" 표기 금지(정직성 게이트). getTrends는 RPC 오류/비정상 응답을 throw(조용한 폴백 은폐 금지). Codex가 Must-fix로 올린 2건(정직성 문구, rate limit)은 실코드 검증 결과 머지 차단 아님으로 강등.
- 남은 일: (1) 일별 롤업 cron(font_clicks→font_click_daily, 현재 스키마만 존재) 설계-구현. (2) prod에 마이그레이션 0007 적용(명시 승인 + rate limit 배포조건). (3) 트렌드 폴백 lead 문구의 "인기 순위" 표현 다듬기(취향 판단, 미반영). (4) 클릭 남용 방지 rate limiting(Supabase 게이트웨이 등 인프라 레벨).
- 관련 문서: `docs/superpowers/plans/2026-07-16-slice3-click-tracking.md`, `docs/review/pr-review-17-20260717-085623.md`
- 상세 히스토리: 없음

## 2026-07-16 - 알리아스 검색 기능 완성 (슬라이스2, F-04)

- 상태: 완료 (PR #15 Codex 리뷰 반영 완료, 머지 진행)
- 완료한 일: 한글/영문/띄어쓰기/오타를 흡수하는 폰트 검색을 백엔드부터 화면까지 완성. DB 검색 함수(`search_fonts` RPC — 별칭 정확일치 100점 > 부분일치 50점 > 오타 유사도 0~50점, 공개 폰트만 최대 20건)와 정규화 함수(NFC → 공백제거 → 소문자, 파이프라인과 동일 규칙)를 만들고 검색 페이지(/search)와 상단 검색 버튼을 연결. dev 실측: '본고딕' → 노토 산스 KR 100점, 오타 '본고딩'도 매칭, 와일드카드(%/_)-101자 입력 차단.
- 커밋/PR: `4ce6782`(계획 v1.1)~`0eeae9b` 총 11커밋, PR #15 (https://github.com/jojo3420/fontagit/pull/15). Codex PR 리뷰(6.5/10, Must-fix 0) Should 5건 중 3건 반영 `0eeae9b`(무한 로딩 버그, RPC 서버측 입력 방어 + LIKE 와일드카드 이스케이프, pg_trgm 설치 스키마 가드, 정렬 안정화), 2건 이연.
- 결정사항: 검색 매칭은 전부 정규화된 별칭(alias_norm) 기준(원문 이름 ILIKE 제거 — 공백 포함 이름과 정규화 쿼리 미스매치 해소). pg_trgm 함수는 public 스키마 한정 호출(SECURITY DEFINER의 search_path에 public을 넣지 않음). RPC 오류 시 빈 배열 반환은 계획 명시 동작이라 유지.
- 남은 일: (1) 슬라이스3 클릭 집계(마이그레이션 0007). (2) prod 배포 시 0006 적용 + SQL 테스트 실행. (3) 슬라이스 0.5 이연분(Codex Medium 4건)은 별도 처리.
- 후속(같은 날): 검색 이연분을 PR #16으로 반영 — 오류 상태 UI 구분(장애를 "결과 없음"으로 오인 방지), URL q 동기화(공유 가능), SQL 통합 테스트 10케이스(dev ALL PASS), aria-live. Codex 리뷰(7/10, Must 0) Should 4건 반영(URL 정리 버그, 실패 시 이전 결과 제거, 오류 로깅, 테스트 보강 — 최종 96/96).
- 관련 문서: `docs/superpowers/plans/2026-07-16-slice2-alias-search.md`(v1.1), `docs/review/pr-review-15-20260716-201537.md`
- 상세 히스토리: progress-003.md

## 2026-07-16 - 마스터플랜 적대적 리뷰 + 정공법 전환 + 30일 그로스 플랜

- 상태: 완료
- 완료한 일: 기획서(마스터플랜 v3.0)를 적대적 리뷰 2건(Opus 심층 + Codex 독립)으로 검증하고 재편. 포지셔닝을 "눈누 정면 회피"에서 "정공법 품질 우위"(광고는 더 가볍게, 정보-편리성-보유량-검색은 동등 이상)로 전환, 킬링 포인트 7개로 재편, 사실 오류 정정(눈누마켓이 실재해 유료폰트 틈새를 "정보 포지션"으로 재정의). 트래픽 0 탈출용 30일 그로스 플랜 문서 신설 후 Codex 문서 리뷰(6.5/10)의 Must 4건 + Should 5건 반영.
- 커밋/PR: `db14f71`(3장 1차 보강), `9e503e6`(정공법 전환 + 그로스 플랜 신설), `e864f87`(리뷰 반영 + 리뷰 리포트). PR 없음.
- 결정사항: 로드맵(S0~S4) 유지. 성공 기준 = 공개 후 30일 GA4 신규 사용자 누적 1,000명(UTM 의무). 제약 = 예산 0원, 익명 활동, 마케팅 주 5시간. 공개 데드라인 = D-30 기점 45일 내 강제 공개. 클릭 집계 완료 전 "인기" 표기 배포 금지(정직성 게이트). 성장기 광고 0~1개(광고 라이트).
- 남은 일: (1) 트랙 A: 슬라이스2 검색 완료 → 슬라이스3 클릭 집계. (2) 트랙 B W1: 시딩 리스트 60곳 작성(창업자 작업). (3) 눈누 폰트 총수 실측 → 카탈로그 패리티 30/90일 목표 확정.
- 관련 문서: `docs/fontagit-master-plan-v3.0.md`(3장), `docs/fontagit-growth-plan-30d.md`, `docs/review/review-result-20260716-181415.md`
- 상세 히스토리: 없음 (결정 근거는 마스터플랜 3-2절과 그로스 플랜 1장에 기록됨)

## 2026-07-16 - 한글 이름-별칭 적재와 Tier A 전수 동기화 완료
- 상태: 슬라이스 0.5 전체 완료(Task 1~5)
- 완료한 일: 구글폰트 38종의 한글 이름-별칭을 선별해 적재. `name_ko` 31종, 한글 별칭 32종을 반영하고 유니코드 NFC 정규화를 적용. 현재 인기 100종에서 빠진 폰트는 `draft`로 내리고 새로 들어온 폰트는 공개하는 전수 동기화도 추가.
- 안전장치: 수집 결과가 100종 미만이거나 한 번에 비공개 전환할 폰트가 5종을 넘으면 작업을 중단. 일반 업로드와 전수 동기화 함수를 분리해 오작동 범위를 제한.
- 커밋/DB: `c7cfc7f`(동기화 DB 함수), `6492c73`(업로더 핵심 로직-테스트), `bda2729`(실행 명령 연결). dev에 마이그레이션 `0005` 적용. prod 쓰기 없음.
- 커밋/PR: PR #14 MERGED (https://github.com/jojo3420/fontagit/pull/14, squash `f888f02`). Codex PR 리뷰(5.5/10) High 2건 반영 `6c83a74`(전체 동기화 경로 변환 실패 시 즉시 중단 strict, 스냅샷 한글 30/라틴 90 하한 분리 검증).
- 검증: 파이프라인 재실행 성공(exit 0), 테스트 90건-Ruff-mypy 통과. dev DB는 전체 137종/공개 130종이며 `urbanist`는 draft, `geist`는 published. 현재 수집 결과와 DB 공개 Tier A 차이 0건, 한글 데이터 차이 0건, 기존 Tier B/C 변경 0건.
- 결정사항: 마이그레이션 번호는 Tier A 동기화 `0005`, 검색 `0006`, 클릭 집계 `0007`, 등록 신청 `0008` 순서로 사용. Codex High(137건 upsert+동기화 단일 트랜잭션화)는 아키텍처 변경이라 다음 PR로 이연.
- 다음 단계: 슬라이스2 검색(F-04, `pg_trgm` + `search_fonts` RPC) 구현 재개. Codex Medium 이연분: 산출물 쓰기 순서(임시파일 후 교체), sources URL 형식 검증, 매핑 JSON 최상위 배열 가드, 동기화 통합 테스트, 슬라이스2 계획 문서 갱신(NFC/similarity 버그/지마켓 테스트 교체).
- 관련 문서: `docs/superpowers/specs/2026-07-16-slice0.5-korean-aliases-design.md`, `docs/superpowers/specs/2026-07-16-tier-a-stale-font-sync-design.md`, `docs/superpowers/plans/2026-07-16-tier-a-stale-font-sync.md`

## 2026-07-16 - 웹 실데이터 연동 슬라이스1 완료 + 검색 슬라이스2 착수
- 상태: 슬라이스1 완료(main 머지) / 슬라이스2 계획 단계
- 완료한 일: 웹 화면이 목업 대신 Supabase 실데이터(공개 폰트 130종+컬렉션 3종)를 정적 페이지로 보여주도록 연동. 데이터 접근 계층(lib/db) 신설, 폰트 미리보기는 시스템폰트 폴백, 검색엔진용 메타-사이트맵 추가. 정적 빌드 276페이지 성공.
- 커밋/PR: `8d87b97` 슬라이스1(PR #13 MERGED, https://github.com/jojo3420/fontagit/pull/13). 슬라이스2 브랜치 feat/search-alias-f04 `acd392c`(마이그레이션 번호 정정).
- 결정사항: dev로 개발 계속, prod 폰트 적재는 마지막(현재 prod 폰트 0건). 트렌드는 임시 최신등록순인데 UI는 "인기" 표기 유지 -> prod 배포 전 슬라이스3(클릭집계) 완료 필수(정직성). 마이그레이션 번호는 Tier A 동기화0005/검색0006/클릭0007/등록0008.
- 남은 일: (1) 슬라이스2 검색(F-04, pg_trgm+search_fonts RPC) 계획 검증->구현 (2) 슬라이스3 클릭집계 (3) 슬라이스4 등록폼 제출 (4) prod 폰트 적재+컬렉션 시드 (5) name_ko 전부 null 파이프라인 보강
- 관련 문서: `docs/superpowers/specs/2026-07-15-web-data-integration-design.md`(v1.1), `docs/superpowers/plans/2026-07-15-slice1-realdata-integration.md`, `docs/review/pr-review-13-20260716-100323.md`
- 상세 히스토리: 없음 (스펙/계획/리뷰 문서에 상세 기록)

## 2026-07-15 - 디자인 정합 슬라이스 4~8 (트렌드/비교/캔버스/컬렉션/등록)

- 상태: 완료 (디자인 목업 대비 정합 슬라이스 1~8 전체 완료)
- 완료한 일: 트렌드 화면(/trends)을 목업과 맞춰 "이번 주 인기 폰트" 단일 주간 리스트 카드형으로 재구성. 비교-캔버스-컬렉션-등록 4개 화면은 이미 목업과 일치해 코드 변경 없이 시각검증만 수행(각 데스크톱/모바일/다크 3종 90점+ 확인).
- 커밋/PR: `6e62212`(TrendRankRow 카드행), `962850d`(/trends 재조립+TrendTable 제거), `b9aa339`(슬라이스4 계획). PR ⚠️ 준비 중(develop→main).
- 결정사항: 슬라이스 5~8은 기존 구현이 이미 정합이라 재작성 안 함(요청 최소 변경). 월간 트렌드 탭은 시각만(데이터는 보존). 등록 폼 광고 영역은 제외(수용한 차이).
- 남은 일: (1) develop→main PR 생성. (2) ⚠️기술부채: 등록 폼(/submit) 제출-검증 로직 미구현(무동작) → 백로그 이슈. (3) 비교/캔버스/등록 폼 컴포넌트 테스트 부재.
- 관련 문서: `docs/superpowers/plans/2026-07-15-design-fidelity-slice4-trends.md`, `docs/superpowers/specs/2026-07-15-design-fidelity-v2-design.md`, `.superpowers/sdd/progress.md`(SDD 원장)
- 상세 히스토리: 없음 (SDD 원장에 태스크별 dense 기록)

## 2026-07-15 - 파이프라인 업로드 원자성-stale alias 개선 (이슈 #8)

- 상태: 부분 완료 (코드 완료 + sandbox DB 함수 적용, 실제 업로드 재검증-PR 미완)
- 완료한 일: 폰트 업로드를 폰트 1건당 단일 트랜잭션(DB 함수 RPC)으로 묶어 "폰트는 저장됐는데 별칭이 없는" 불일치와, 이름 규칙 변경 시 남던 옛 별칭(stale alias)을 제거. 구글폰트 라이선스 조회 응답이 이상해도 죽지 않도록 방어 추가. 전체 테스트 75건 통과, sandbox Supabase에 DB 함수 적용 완료.
- 커밋/PR: `060e827`(licenses 방어), `bfd1320`(upsert_font RPC + 실행권한 제한), `6bf73be`+`0227e2e`(업로더 RPC 재작성 + 테스트). PR ⚠️ 미생성.
- 결정사항: 원자성=폰트별(전체 배치 아님), stale alias=삭제 후 재삽입(active 컬럼 아님). DB 함수는 SECURITY DEFINER라 실행 권한을 service_role로 제한(anon/authenticated 쓰기 차단).
- 남은 일: (1) 실제 파이프라인 실행으로 멱등/stale/롤백 재검증. (2) PR 생성. (3) 이슈 #8 NICE 2건(license 필드 통합, GITHUB_TOKEN 설정).
- 관련 문서: `docs/superpowers/plans/2026-07-15-upload-atomicity-alias-sync.md`, `docs/superpowers/specs/2026-07-15-upload-atomicity-alias-sync-design.md`, `docs/superpowers/handoff/2026-07-15-1348-upload-atomicity-issue8.md`
- 상세 히스토리: 없음 (design/handoff/ledger에 dense 기록)

## 2026-07-15 - 데이터 파이프라인 Supabase 업로드 완성 (Slice 0)

- 상태: 완료
- 완료한 일: 구글폰트 수집 데이터를 라이선스 판별 후 Supabase(폰트 DB)에 자동 적재하는 파이프라인 완성. 실제 폰트 136개 적재(공개 가능 130개), 여러 번 실행해도 중복 없이 동일(멱등) 검증. 공개는 OFL/Apache/UFL처럼 라이선스가 확인된 폰트만 자동 게시. PR #7 듀얼 리뷰(Codex)에서 라이선스 조회 실패 시 공개 폰트가 전부 비공개(draft)로 덮이는 데이터 손실 경로를 발견-수정한 뒤 main에 머지.
- 커밋/PR: `2c1c62a`(변환 버그+테스트 정정), `fd1a5b5`(Supabase 업로더), `b487c49`(오케스트레이션), `436c181`(비밀파일 gitignore), `0a8d0d0`(DB 권한), `33bf12a`(API키 로그 억제), `a20641d`+`81e325a`(PR #7 리뷰 반영: 라이선스 실패 시 업로드 보류-published 규칙 강제-status Literal). PR #7 develop→main 머지 완료(https://github.com/jojo3420/fontagit/pull/7).
- 결정사항: FontAgit 전용 신규 Supabase 프로젝트(ref zgxtfcpiokhkcrywlxmc, 서울 리전) 사용 — ollidam 공유 인스턴스 아님. license_verified=true인 폰트만 공개(라이선스 정직성).
- 남은 일: (1) Slice 1 웹 실데이터 연동(Plan B). (2) 파이프라인 후속 개선 백로그 — 업로드 원자성-stale alias-GitHub 응답 방어 등(GitHub 이슈 #8).
- 관련 문서: `docs/superpowers/plans/2026-07-14-slice-0-data-pipeline-upload.md`, `.superpowers/sdd/progress.md`(태스크별 상세)
- 상세 히스토리: 없음 (.superpowers/sdd/progress.md에 태스크별 dense 기록)

## 2026-07-14 - 웹 화면 진입점 추가 (캔버스/비교 nav)

- 상태: 완료 (PR #6 main 머지)
- 완료한 일: 만든 화면(타입 캔버스 `/playground`, 비교 `/compare`)으로 가는 메뉴 진입점을 추가해 "진입점 고립"(nav 링크가 없어 사용자가 화면을 못 찾던 문제)을 해소. 데스크톱 헤더 nav에 캔버스-비교 링크 추가, 모바일은 하단 탭바에 비교 탭 추가. 헤더 nav가 모바일에서도 보이는 구조라 좁은 폰 넘침 방지를 위해 두 링크는 모바일 상단 nav에서만 숨김.
- 커밋/PR: `bc73261`(nav 링크), `68ad6b4`(스크린샷 기준 이미지 22개 갱신), `f02955b`(리뷰 반영-모바일 탭 선택 판정 정확화). PR #6 main 머지 완료(https://github.com/jojo3420/fontagit/pull/6). 후속 `6027218`(smoke 테스트 강화 - viewport await + href 앵커 + 390px 모바일 검증, Codex Medium 후속). 후속분은 `ec59e72`(develop→main 머지 커밋)로 main 반영 완료.
- 결정사항: 진입점 위치는 헤더 nav 확장 방식으로 확정(대안이던 홈 배너 스펙 9a 미채택). Codex 리뷰는 Critical-High 0, Medium 3 - 모바일 탭 active 정확 매칭은 PR #6에, 나머지 2건(smoke 테스트 await/href 앵커 + 모바일 검증)은 후속 커밋 `6027218`에 모두 반영(e2e 64 pass). main과 develop은 PR 머지 커밋 때문에 분기 상태라 develop→main은 fast-forward 불가, `--no-ff` 머지 커밋으로 합침.
- 남은 일: 승계 - 배포 도메인 확정 후 `metadataBase` 설정, 필터/검색/등록폼 실동작화, 실데이터 파이프라인 연동.
- 관련 문서: `tobyteam/cpr-review-6.md`(PR #6 Codex 리뷰 + 크로스 리뷰)
- 상세 히스토리: 없음

## 2026-07-13 - 웹 Phase 3-4 확장 화면 + 마감

- 상태: 완료 (PR #5 main 머지)
- 완료한 일: Phase 1-2 토대 위에 확장 화면 5개(타입 캔버스 `/playground`, 비교 `/compare`, 컬렉션 목록-상세 `/collections`, 창작자 등록 `/submit`, 빈 상태 `EmptyState`)와 마감 3개(모바일 하단 탭바 `MobileTabBar` + safe-area, 다크모드 토글 `ThemeToggle`, 파비콘 + OG 이미지)를 디자인 95% 재현으로 구현. 헤더 nav 404 블로커 해소, 컬렉션 빌드타임 무결성 검증 추가.
- 커밋/PR: 웹 커밋 17개(`63332e2`..`ea8bef1`). PR #5 main 머지 완료(merge `529a1ec`, https://github.com/jojo3420/fontagit/pull/5). PR Codex 리뷰 후 후속 수정(`ea8bef1`: iPhone safe-area `viewport-fit` + 컬렉션 중복 fontSlug 무결성).
- 결정사항: Phase 1-2 결정 승계(CSS Modules, 정적 export, 목업 데이터, 인터랙션 핵심만 동작). 비교는 폰트 슬롯 3개 고정 + select 교체. OG는 satori에 한글 폰트(Pretendard-Bold.otf) 임베드(미임베드 시 한글이 네모로 깨짐). 다크 토글은 `useSyncExternalStore`로 FOUC 스크립트가 설정한 `data-theme`를 구독(setState-in-effect 회피).
- 남은 일: (1) 캔버스/비교 화면 진입점 추가 - `/compare`는 nav 링크가 없어 고립, `/playground`는 모바일 탭에만(Codex PR 리뷰 지적, 진입점 위치는 디자인 결정 필요). (2) 배포 도메인 확정 후 `layout.tsx`에 `metadataBase` 설정(og:image가 현재 localhost). (3) 필터/검색/등록폼 비동작 목업 - 백엔드 연동 시 실동작. (4) 실데이터 파이프라인 연동.
- 관련 문서: `docs/superpowers/plans/2026-07-13-fontagit-web-phase3-4.md`, `docs/review/review-result-20260713-145158.md`(계획 Codex 리뷰), `docs/review/pr-review-5-20260713-173152.md`(PR Codex 리뷰 + 크로스 리뷰)
- 상세 히스토리: progress-002.md

## 2026-07-13 - 웹 프론트엔드 토대 + 핵심 화면 구축 (Phase 1-2)

- 상태: 완료
- 완료한 일: 웹사이트 화면(apps/web)을 새로 구축. 홈, 폰트 목록, 폰트 상세(무료/유료 구분 + 무료 대안), 트렌드, 없는 페이지(404)를 디자인과 95% 동일하게 구현. 내용은 임시 목업 데이터로 채움.
- 커밋/PR: 웹 커밋 다수(`3634686`..`148d770`), PR #4 머지 완료(`4fe1da5`). https://github.com/jojo3420/fontagit/pull/4
- 결정사항: 스타일은 CSS Modules + CSS 변수 토큰(Tailwind 제거), 배포는 정적 사이트 생성(`output: 'export'`), 폰트는 앱에 self-host(next/font + Pretendard), 화면 데이터는 목업(추후 파이프라인 실데이터로 교체 예정).
- 남은 일: Phase 3-4 화면(타입 캔버스, 비교, 컬렉션, 창작자 등록, 모바일 정밀화, 다크모드 토글 UI, 런칭 자산 OG). 헤더의 컬렉션-등록 링크는 아직 대상 페이지가 없어 클릭 시 404. 필터/검색은 현재 목업(비동작). README와 중복 pnpm-workspace 경고 정리.
- 관련 문서: `docs/superpowers/specs/2026-07-12-fontagit-web-screens-design.md`, `docs/superpowers/plans/2026-07-12-fontagit-web-foundation-and-core.md`, `docs/review/pr-review-4-dual-20260713-120348.md`
- 상세 히스토리: progress-001.md
