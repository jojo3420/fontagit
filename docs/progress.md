# Progress

> 작성 규칙: 각 진행 기록은 1~2줄로만 쓴다(사람이 빠르게 읽는 용도). 세부 내용은 `docs/progress/progress-[코드번호].md`(예: `docs/progress/progress-001.md`)에 기록하고, 여기서는 결과 한 줄 + 커밋/PR + 상세 파일 링크만 남긴다.

## 프로젝트 소개

FontAgit(폰트 아지트)는 국내외 무료-유료 폰트를 검색-비교하고 공식 다운로드/구매 페이지로 연결해 주는 폰트 아카이브 웹사이트입니다. 폰트 파일을 직접 호스팅하지 않고 공식 페이지로 안내하며, 검색 유입과 광고를 수익 모델로 합니다. 검색으로 들어오는 일반 사용자, 디자이너, 마케터, 학생이 주 사용자입니다.

## 주요 기능

- 폰트 목록/상세(서체 견본, 문장 미리보기, 상업 이용 여부, 공식 링크)
- 폰트 검색(/search): 한/영/띄어쓰기/오타 흡수 별칭 검색 + 헤더 실시간 자동완성 드롭다운(초성 'ㅈㅁㅋ' 포함)
- 홈/트렌드 TOP 10: 익명 '이동' 클릭 집계 인기 랭킹(데이터 없으면 최신 등록 폴백)
- 폰트 비교(최대 3종), 타입 캔버스, 테마 컬렉션, 등록 신청 폼, 유료 폰트 무료 대안, 다크모드
- 폰트 데이터 자동 수집→라이선스 판별→Supabase 적재 파이프라인
- 웹 화면 Supabase 실데이터 정적 페이지 + 검색엔진 메타/사이트맵

## 진행 기록

## 2026-07-18 - 검색·색인 설계 적대적 리뷰
검색·색인 설계를 자체 적대적 리뷰와 Claude Code Opus 리뷰로 보강해 Task 4A(1,000행 절단·canonical 집합·clean main 배포)를 운영 배포 선행 게이트로 확정. 커밋 `9de97d6`, 원격 `codex/search-index-doc-hardening`, 상세: `docs/review/review-result-20260718-072911.md`

## 2026-07-17 - prod SSG 빌드 안정화 + 검색 자동완성 신뢰성 수정
prod(ollidam) 정적 export 빌드를 막던 3함정 해결(URL /rest/v1 중복=PGRST125, PostgREST fontagit 스키마 미노출→0010, getAllFonts aliases 거대 in-list→게이트웨이 502=청크 조회) → 빌드 그린(폰트130+컬렉션3 정적 생성). 이어 F-19 웹계층 Codex 리뷰로 실재 버그 3건(빈쿼리 stale 레이스/dev Strict Mode 멈춤/무음 실패) 수정. 커밋 `48dcf6d`, `02b541d`, `b90f115`, PR #19 MERGED. 주의: 공유 워킹트리 병렬 작업으로 브랜치가 develop으로 바뀐 채 b90f115가 develop 직접 커밋됨. 남은: prod 폰트 적재, Kong rate limit(공유 게이트웨이), F-19 Should-fix(테스트 보강). 상세: 메모리 `ref-ollidam-ssg-pitfalls`, `docs/review/pr-review-19-*`

## 2026-07-17 - 검색어 자동완성(F-19) + 초성 검색(F-16) 완성
헤더 검색바 실시간 드롭다운 자동완성(키보드/IME/하이라이트) + 초성 검색을 DB 엔진(0009 초성함수/생성컬럼/RPC)부터 화면까지 완성(PR #19 `05f9142`, dev C1~C9 통과). spec/plan을 실제 구현(정적 export라 서버라우트 대신 훅에서 RPC 직접 호출)에 동기화(PR #20 `a855df3`). 주의: 이번 세션은 작업 전 `git fetch` 누락으로 이미 병합된 PR #19를 중복 재구현했다 폐기 — 착수 전 원격/PR 확인 필수(메모리 feedback-fetch-before-rework). 상세: 없음(`plans`/`specs` 2026-07-17-search-autocomplete)

## 2026-07-17 - feat/search-alias-f04 → develop 병합
슬라이스2 검색 브랜치를 develop에 병합, 문서 충돌 3건 전부 develop(상위 집합) 채택. 커밋 `6837594`(origin 반영). 남은: 자동완성(F-19)은 계획 문서만 — `plans/2026-07-17-search-autocomplete.md`. 상세: 없음

## 2026-07-17 - 클릭 rate limiting DB 최후방어 (슬라이스3 후속)
클릭 기록 봇 어뷰징 방어를 DB 계층(폰트별 10초 20건 상한 + try advisory lock)으로 구현. PR #18 MERGED(`496361b`, 마이그레이션 0008). prod fontagit 0005~0008 스키마 적용 완료(supabase_admin+SSH docker exec, `postgres`는 권한 없음). 남은: prod 폰트 적재 + Kong rate limit(공유 게이트웨이), 배포 전 부하 테스트. 상세: 없음(`specs/plans` click-rate-limiting, handoff `2026-07-17-1455`)

## 2026-07-17 - Top10 이동 클릭 집계 완성 (슬라이스3, F-03)
공식 링크 '이동' 클릭을 익명 집계해 홈/트렌드 TOP 10을 실측 인기순 표시(데이터 0건이면 '최신 등록' 폴백). PR #17 MERGED(`bfe2632`). 남은: 일별 롤업 cron, prod 0007 적용. 상세: 없음(`plans/2026-07-16-slice3-click-tracking.md`)

## 2026-07-16 - 알리아스 검색 기능 완성 (슬라이스2, F-04)
한/영/띄어쓰기/오타 흡수 폰트 검색(/search)을 DB `search_fonts` RPC부터 화면까지 완성 + 오류 UI-URL 동기화 이연분(PR #16). PR #15/#16 MERGED(`0eeae9b`). 상세: `docs/progress/progress-003.md`

## 2026-07-16 - 마스터플랜 적대적 리뷰 + 정공법 전환
마스터플랜 v3.0을 적대적 리뷰로 재편(포지셔닝 '정공법 품질 우위' 전환, 킬링 포인트 7) + 30일 그로스 플랜 신설. 커밋 `e864f87`. 상세: 없음(`fontagit-master-plan-v3.0.md` 3장, `fontagit-growth-plan-30d.md`)

## 2026-07-16 - 한글 이름-별칭 적재 + Tier A 전수 동기화 (슬라이스 0.5)
구글폰트 한글 이름-별칭 적재(name_ko 31, 별칭 32) + 인기 밖 폰트를 draft로 내리는 Tier A 전수 동기화. PR #14 MERGED(`f888f02`, 마이그레이션 0005). 상세: 없음(`specs` korean-aliases / tier-a-stale-font-sync)

## 2026-07-16 - 웹 실데이터 연동 (슬라이스1)
웹 화면을 목업 대신 Supabase 실데이터(공개 폰트 130종+컬렉션 3종) 정적 페이지로 연동 + 메타/사이트맵. PR #13 MERGED(`8d87b97`). 상세: 없음(`specs/2026-07-15-web-data-integration-design.md`)

## 2026-07-15 - 디자인 정합 슬라이스 4~8 (트렌드/비교/캔버스/컬렉션/등록)
트렌드 화면(/trends)을 목업 맞춰 주간 카드형 재구성, 나머지 4개 화면은 정합 확인만. 커밋 `962850d`. 남은: develop→main PR, 등록폼(/submit) 제출 로직 미구현(백로그). 상세: 없음(`.superpowers/sdd/progress.md`)

## 2026-07-15 - 파이프라인 업로드 원자성-stale alias 개선 (이슈 #8)
폰트 업로드를 폰트별 단일 트랜잭션(RPC)으로 묶고 이름 규칙 변경 시 남던 옛 별칭 제거. 커밋 `6bf73be`. 부분 완료(실업로드 재검증-PR 미완). 상세: 없음(`handoff/2026-07-15-1348-upload-atomicity-issue8.md`)

## 2026-07-15 - 데이터 파이프라인 Supabase 업로드 완성 (Slice 0)
구글폰트 수집→라이선스 판별→Supabase 자동 적재 파이프라인 완성(폰트 136 적재/130 공개, 멱등 검증). PR #7 main 머지. 상세: 없음(`.superpowers/sdd/progress.md`)

## 2026-07-14 - 웹 화면 진입점 추가 (캔버스/비교 nav)
타입 캔버스-비교 화면으로 가는 nav 진입점을 추가해 '진입점 고립' 해소. PR #6 main 머지(후속 `ec59e72`). 상세: 없음

## 2026-07-13 - 웹 Phase 3-4 확장 화면 + 마감
확장 화면 5개(캔버스/비교/컬렉션/등록/빈상태) + 마감 3개(모바일 탭바/다크모드/OG) 구현. PR #5 main 머지(`529a1ec`). 상세: `docs/progress/progress-002.md`

## 2026-07-13 - 웹 프론트엔드 토대 + 핵심 화면 구축 (Phase 1-2)
웹사이트 화면(apps/web) 신규 구축 — 홈/목록/상세/트렌드/404를 디자인 95% 재현(목업 데이터). PR #4 MERGED(`4fe1da5`). 상세: `docs/progress/progress-001.md`
