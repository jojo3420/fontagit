# Progress

## 프로젝트 소개
FontAgit는 한글 폰트를 찾고 라이선스-미리보기 정보를 확인하는 폰트 탐색 웹 서비스다. 눈누(noonnu)의 약점(불확실한 라이선스 고지, 약한 검색)을 겨냥해 "행동별 허용 4행 + 확인일 + 원문 링크" 신뢰 블록과 한글/영문/오타/초성 검색을 차별점으로 삼는다. 스택은 Next.js SSG(정적 사이트 생성) + Supabase, 저장소는 `apps/web`(웹) + `apps/pipeline`(데이터 수집).

## 주요 기능
- 폰트 목록/상세/트렌드/홈 등 핵심 화면 (Phase 1-2)
- Phase 3-4 확장 화면 + SSG 마감
- 알리아스 검색: 한글-영문-붙여쓰기-오타-초성 매칭 + 실시간 자동완성(F-04/F-16/F-19)
- 런칭 MUST 기능 세트(필수 문서, 측정, AdSense, 신고-문의, 목록 필터-정렬, 미리보기 폴백)는 코드 완료되어 develop에 병합됨(main 승격 대기)
- 실서비스 배포: fontagit.com이 Cloudflare Pages로 라이브(정적 export + prod ollidam 1,240종 데이터(v0.1.0)), 배포 자동화 스크립트(scripts/deploy.sh)
- 눈누 Tier B 라이선스-스타일 반자동 수집 파이프라인: 눈누 상세페이지에서 사실만 추출 → 명백히 안전한 것 자동 발행/애매하면 사람 검수. 마이그레이션 0016 + CLI 3종. **prod(ollidam)에 Tier B 1,110종 적재 + deploy.sh 리얼서버 배포 완료 → fontagit.com에 전체 1,240 published 라이브(태그 v0.1.0)**.
- prod 폰트 데이터 감사(audit) 파이프라인: fonttools로 실제 폰트 파일을 열어 cmap 기반 한글 글리프 지원을 실검증(추정이 아닌 사실 확인), 공식 출처만 자동 승인-눈누는 참고용으로만 저장. dev DB 마이그레이션 완료, 실데이터 수집은 다음 세션 과제(progress-005.md 참고).
- OFL 라이선스 자동 verified: OFL(오픈폰트라이선스) 폰트 132종을 google/fonts 공식 저장소로 확인해 라이선스 권한(상업/수정/임베딩 등)과 verified 상태를 dev에 자동 확정(`ofl_verify.py`, progress-008.md 참고).

- /fonts 용도별 섹션 계층화 + 타입 캔버스: 폰트를 용도 5섹션(본문/제목/브랜드/손글씨/장식)으로 자동 그룹화하고 에디터 추천을 앞에 노출, 상단 문구 입력창(타입 캔버스)으로 모든 견본을 실시간 미리보기(#60, PR #92) → v0.2.0으로 prod 라이브, 개요 모드 레이아웃/다크모드 버그는 v0.2.1 hotfix로 해결

## 진행 기록

## 2026-07-21 - v0.2.0/v0.2.1 prod 배포 + /fonts UI hotfix + 이슈 정리
- 상태: 완료
- 요약: (1) develop→main 승격(PR #93)으로 /fonts 섹션 계층화+OFL 검증 엔진 등을 prod 배포(태그 v0.2.0, fontagit.com 라이브). (2) 배포된 /fonts 개요 모드 UI 버그 3건 hotfix(v0.2.1, PR #94): 개요 모드가 필터용 2단 그리드(`220px minmax(0,1fr)`) 첫 컬럼(220px)에 갇혀 폭 좁음+우측 공백 과다 → `SectionedFontsView .wrapper`에 `grid-column: 1/-1`; `TypeCanvasBar` 하드코딩 색 → 테마 변수(다크모드 자동 대응); `SectionOverview`의 미정의 `--color-primary` → `--point`. (3) 열린 이슈 22→19 정리(#91 컬렉션-섹션 중복/#34/#36 닫기, #37-#62-#56 최신화). 다음 착수 후보 #28-#89는 조사 완료.
- 커밋/PR: PR #93 `6f9cc45` (https://github.com/jojo3420/fontagit/pull/93, v0.2.0), PR #94 `0e38709`/`6c9ec54` (https://github.com/jojo3420/fontagit/pull/94, v0.2.1 hotfix)
- 남은 일: #28 컬렉션 시드(폰트 200종/컬렉션 10개, 큐레이션 확정+DB 마이그레이션), #89 Tier A URL 백필(Google Fonts API로 legal 감사 pending 해소), #83 cmap 검증 CI 환경, #90 OFL prod 승격
- 관련 문서: 없음 (기존 #60 설계문서 활용)
- 상세: 없음 (⚠️ deploy.sh prod build 직후 dev 서버는 .next 캐시 충돌로 500 → `rm -rf apps/web/.next` 재시작)

## 2026-07-21 - /fonts 용도별 섹션 계층화 + 타입 캔버스 통합 (#60)
- 상태: 완료 (PR #92 squash 머지 → develop)
- 요약: /fonts를 용도 5섹션으로 자동 매핑(`lib/sections.ts::sectionOf`, category+굵기 규칙, DB 무변경)해 계층 렌더하고, 자동 매핑 위에 에디터 추천(`sectionCuration`+`orderByCuration`)을 우선 노출. 상단 타입 캔버스(문구 입력)에 입력하면 `SectionedFontsView`가 useDeferredValue로 모든 섹션 폰트 견본을 실시간 갱신(기존 LazyFontPreview 지연로딩 유지). 라우팅은 파라미터 없으면 개요/있으면 평면이며, 앱이 output:'export'(정적 export)라 서버 searchParams가 빌드에서 깨져 클라이언트 `FontsViewWrapper`(useSearchParams)로 분기(다음 세션 주의점). 컬렉션 페이지는 유지.
- 커밋/PR: PR #92 squash 머지 `cf46987` (https://github.com/jojo3420/fontagit/pull/92). 구현 17커밋(설계/계획/리뷰 문서 커밋 포함), agy 설계리뷰+task별 리뷰+Opus 최종리뷰+agy PR리뷰 4건 반영.
- 남은 일: 큐레이션 확충(#28 데이터 적재 후 각 섹션 추천 보강, 무명폰트 사람 스팟검수), 긴 미리보기 문구 레이아웃 clamp, TypeCanvasBar 하드코딩 색→디자인 토큰, `?section=invalid` 엣지 테스트. develop→main 승격 시 반영.
- 관련 문서: docs/superpowers/specs/2026-07-20-fonts-section-hierarchy-canvas-design.md, docs/superpowers/plans/2026-07-20-fonts-section-hierarchy-canvas.md
- 상세: progress-009.md

## 2026-07-20 - OFL 표준 라이선스 google/fonts 공식 확인 자동 verified (하이브리드 2단계)
- 상태: 완료 (dev 적용까지 / prod는 후속 수동 게이트)
- 요약: `license_type=OFL` 132종을 google/fonts 저장소 트리로 공식 확인 후 OFL 표준 권한(SIL OFL 1.1: 상업/수정/재배포/임베딩 allowed, 단독판매 denied, 출처표기 required) + `license_status=verified`를 dev fonts에 직접 PATCH. 신규 경량 스크립트 `ofl_verify.py`(dry-run 기본/`--apply` 쓰기), 감사 findings 절차 없이 처리(복잡도 낮추기, 사용자 결정). dev 132/132 확인-적용 완료(쓰기→읽기 재검증). 1단계 도메인 집계(54종)는 부정확 → `license_type=OFL` 132종이 정답으로 정정.
- 커밋/PR: `68bf582` feat: ofl_verify 엔진+테스트, `279554c` docs: 설계, PR #88(base=develop, https://github.com/jojo3420/fontagit/pull/88)
- 남은 일: 공공기관 KOGL/공공누리 271종(유형별 권한 상이, 유형 확정 필요), custom-free 1,110+None 50 사람검수, errors 22 재크롤, OFL prod 적용
- 관련 문서: docs/superpowers/specs/2026-07-20-ofl-verify-design.md
- 상세: progress-008.md

## 2026-07-20 - 눈누 라이선스 출처 전수 크롤링 실행 + 하이브리드 검수 1단계
- 상태: 부분 완료 (하이브리드 2단계 = 표준 라이선스 자동 판정 구현은 다음 세션)
- 요약: (1) 외부 크롤링에 요청당 1.5초 딜레이 추가 + 전수 배치 크롤링 CLI(`font-audit-crawl-all`, 배치-체크포인트 재개-게이트 비활성) 신규 구현. (2) dev 전수 크롤링 실행 완료: 눈누 1,110종 12배치, needs_review 1,109/pending 1/broken 0/errors 22(SSRF 방어-타임아웃 등 개별 URL 실패, 재시도 대상). 각 폰트의 다운로드/라이선스 출처 URL + 증거 snapshot 적재. (3) FK 위반 수정 PR #88 생성. (4) 하이브리드 1단계 출처 분포 분석: 공공기관(.go.kr/.or.kr) 271종 + OFL(github/google) 54종 = 약 325종(28%)이 표준 라이선스 자동 규칙 후보 → 자동 처리 시 검수 대상 1,154 → 약 829종 축소.
- 커밋/PR: `feat: 전수 배치 크롤링 CLI + 요청당 1.5초 딜레이` (fix 브랜치), PR #88(https://github.com/jojo3420/fontagit/pull/88, FK 수정), 이슈 #89(Tier A URL 백필)
- 남은 일: 하이브리드 2단계 - 표준 라이선스(공공누리 KOGL/OFL) 도메인 기반 자동 verified 구현(현재 license_id/version 추출 파서 부재로 자동 판정 불가, 이 구현이 본체). errors 22종 재크롤링. 나머지 약 829종 사람 검수. 무검수 일괄 승인은 라이선스 오표기 리스크로 배제(사용자 결정).
- 관련 문서: docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md
- 상세: progress-007.md

## 2026-07-20 - 감사 파일럿 결과 심층 조사: Tier A pending-게이트-verified 경로 원인 규명
- 상태: 부분 완료 (설계 정공법 착수는 사용자 판단으로 보류 → 후속 재개)
- 요약: dev legal 파일럿(50종) 결과 verified 0/needs_review 26/pending 24의 구조적 원인을 코드-데이터-로그로 규명. (1) Tier A(Google) pending은 download/license URL이 DB에 null이라 검증 후보 자체가 안 생김. (2) verified가 0인 근본 원인은 registry에 official/public 출처 0개 + license_rules.json 규칙 0건(설계상 "자동규칙 0건 시작"). (3) 눈누는 참고용(source_kind=noonnu)이라 항상 needs_review → needs_review>10% 게이트로 눈누-only 파일럿은 통과 불가. (4) 사람승인(human_review) verified 경로는 승인 데이터를 재판정 snapshot에 주입하는 "연결 고리"가 코드에 미구현. 결정: verified 실증 슬라이스(설계 정공법)는 보류하고, 눈누 크롤링 실행 + fix PR 생성 먼저 진행.
- 커밋/PR: 없음 (조사 세션, 코드 변경 없음)
- 남은 일: (1) 눈누 크롤링 승인 반영해 legal 재실행 (2) fix/audit-pilot-dev-font-id-mapping PR 생성 (후속) Tier A pending 재조사, verified 실증 슬라이스(공공기관 사람승인 경로)
- 관련 문서: docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md, docs/superpowers/plans/2026-07-18-prod-font-data-audit.md
- 상세: progress-006.md

## 2026-07-20 - 미해결 이슈-원격 브랜치 정리
- 요약: develop→main 승격(PR #87, 92278b2) 후 원격 병합 브랜치 15개 삭제(squash-aware 내용 판정). 이슈 #82(SUPABASE 설정 차단)는 PR #85로 이미 해결됨을 재현(font-audit-export-baseline exit 0, baseline 1.1MB)으로 확인 후 close. #54 close, #84 완료 항목 반영.
- 남은 일: #83(metadata cmap 스테이지는 Linux 실행환경/CI 필요), #84 잔여(deploy.sh 보강, fonts.ts 목업, 보안 MEDIUM 2건).

## 2026-07-19 - 테스트/빌드 경고 정리 main 병합 + PR #86 develop 병합
- 상태: 완료
- 요약: (1) 테스트 act 경고 및 turbopack workspace root 경고 정리분(`page.test.tsx` setTimeout→waitFor, `useDebouncedSuggestions.test.ts` act 래핑, `next.config.ts` turbopack.root)을 main에 ff 병합-push하고 작업 worktree(cleanup-test-build-warnings) 삭제. (2) PR #86(#54 /compare 제거→홈 통합)을 develop에 squash 병합 — develop 대비 문서 충돌 2건만 있었고(progress.md union, compare-home-merge-design.md 개정판 채택) 코드는 자동병합(충돌 0)이라 안전 해소.
- 커밋/PR: `6619a4c` chore: 테스트/빌드 경고 정리(main), `e2707da` PR #86 squash 병합 (https://github.com/jojo3420/fontagit/pull/86)
- 남은 일: develop→main 승격 시 #54 close(기존 미결: 폰트 상세 404 e2e 스냅샷 환경 의존성, 홈 Lighthouse 배포 전 실측).
- 관련 문서: docs/superpowers/specs/2026-07-18-compare-home-merge-design.md
- 상세: 없음

## 2026-07-19 - #54 /compare 제거 → 홈 통합 (PR #86)
- 상태: 구현 완료, PR #86(base=develop) 생성, squash 머지 대기
- 요약: 별도 라우트 `/compare`를 제거하고 폰트 비교를 홈("/") 지연 로드 섹션으로 통합. `CompareLazy`(React.lazy 코드분할 + IntersectionObserver 뷰포트 지연) 신규, 서버 `page.tsx`가 `<section id="compare">` SSG 상주, `CompareBoard` h1→h2. 데스크톱/모바일 네비 '비교'→`/#compare`(모바일 탭 유지=헤더 tool 링크 숨김이라 유일 진입점). Next 16에 `next/dynamic` 진입점 없어 프로젝트 기존 `LazyFontPreview` 패턴 채택. `not-found` 미변경. 브레인스토밍 7결정 + codex 스펙 리뷰(7/10) + 최종 whole-branch 리뷰 반영.
- 검증: 유닛 183/183, compare e2e 3경우(홈앵커-크로스페이지-직접진입) PASS, 코드분할 확인(별도 청크-홈 초기 미참조), `/compare` 활성링크 0.
- 커밋/PR: 62d26e0(SEO정리)-5a4025b(네비)-f39a9d0(CompareLazy)-027c42c(홈통합)-8a8dfb9(fix)-c048f69(스냅샷정정)-df8b7d7(직접앵커e2e)-docs. PR #86 base=develop.
- 남은 일: PR #86 squash 머지 → develop→main 승격 시 #54 close. 스코프 외 별도 이슈 권장: 폰트 상세 404-e2e 스냅샷 환경 의존성, 홈 Lighthouse 배포 전 실측.
- 사고 기록: 구현 중 서브에이전트가 worktree 대신 원본 repo main에서 커밋(cwd 오잡)→cherry-pick+reset로 복구, 이후 cwd 검증 강제.
- 관련 문서: docs/superpowers/specs/2026-07-18-compare-home-merge-design.md, docs/superpowers/plans/2026-07-18-compare-home-merge.md
- 상세: 없음

## 2026-07-19 - prod 폰트 데이터 감사 파이프라인(cmap 실검증) 병합 + 배포 스크립트 확장
- 상태: 부분 완료 (눈누/prod 실데이터 수집은 apps/pipeline/.env 설정 미비로 미실행)
- 요약: PR #76(fonttools cmap으로 실제 폰트 파일을 열어 한글 글리프 지원을 실검증하는 감사 파이프라인, PR75의 sourceTier 휴리스틱 대체)을 적대적 코드/보안 리뷰 후 실버그(폰트 다운로드 max_bytes 누락) 1건 수정해 병합. develop→main 승격(PR #78, specimen 충돌 3파일은 cmap 로직으로 해소) 및 PR #77(구식 로직) 폐기. `/fonts` 화면에 내부 데이터 출처(눈누/Google Fonts 건수) 노출 회귀를 발견 즉시 제거(PR #79). deploy.sh에 --branch/--new-tag/--tag 및 위치 인자 자동판별(PR #79, #81) 추가.
- 커밋/PR: #76 (https://github.com/jojo3420/fontagit/pull/76) merged, #77 closed(중복), #78 (https://github.com/jojo3420/fontagit/pull/78) merged, #79 (https://github.com/jojo3420/fontagit/pull/79) merged, #81 (https://github.com/jojo3420/fontagit/pull/81) merged
- 남은 일: (1) apps/pipeline/.env에 SUPABASE_URL/ANON_KEY 설정 후 legal 스테이지부터 실수집(dev 저장) (2) metadata(cmap 한글검증) 스테이지는 Linux 필요 — CI 워크플로우 신설 필요 (3) prod fonts 테이블 반영은 사용자 결정(전수조사+사람검수 후 별도 승인)에 따라 보류
- 관련 문서: docs/superpowers/specs/2026-07-18-prod-font-data-audit-design.md, docs/handoff/2026-07-18-1436-prod-font-data-audit.md, docs/runbooks/prod-font-data-audit.md
- 상세: progress-005.md

## 2026-07-18 - #75 한글 폰트 견본 팬그램 수정 + 재배포
- 상태: 완료
- 요약: /fonts에서 눈누(Tier B) 한글 폰트가 subsets 빈 배열이라 영문 팬그램으로 렌더되던 버그를, isKoreanFont가 sourceTier==="B"도 한글로 판정하도록 확장해 수정(specimen.ts + 호출부 4곳, 유닛 17 pass). 코덱스 리뷰 8.5/10 Must-fix 0. deploy.sh 재배포 스모크 200. 사용자 확인 완료.
- 커밋/PR: fix 024da4d, PR #75 (https://github.com/jojo3420/fontagit/pull/75) squash 머지.
- 남은 일: (후속 별건) 눈누 subsets 데이터 백필 + 파이프라인 수정. 참고: 이후 codex 세션이 cmap 기반 specimen 로직을 별도 병합(#78/#79).
- 관련 문서: docs/review/pr-review-75-20260718-142355.md
- 상세: 없음

## 2026-07-18 - #72 /fonts 목록 getAllFonts 페이지네이션 fix + 재배포
- 상태: 완료
- 요약: /fonts 목록의 getAllFonts()가 .range() 페이지네이션 없이 조회해 PostgREST 기본 1,000행에서 무음 절단(published 1,240 중 일부만 노출)되던 것을 getAllSlugs/getPublishedSlugs와 동일한 range 루프 + 2차 정렬 slug(대량 삽입 created_at 중복 시 offset 안정성 확보)로 전량 조회하도록 수정. fonts.test.ts에 1,001종 페이지네이션 케이스 추가(7 passed, tsc fonts 오류 0). deploy.sh 재배포 → 라이브 /fonts RSC 페이로드에 1,240종 임베드 확인(빌드 SSG 2,502페이지, verify:seo fonts=1240).
- 커밋/PR: fix de990e0, Cloudflare Pages 배포 00b54e45.fontagit.pages.dev 스모크 200, #72 close.
- 남은 일: #57 /fonts UI 페이지네이션 + 개수 메타 표시(데이터 절단은 해결, UI 잔여).
- 관련 문서: docs/handoff/2026-07-18-1018-noonnu-tierb-fonts-list-fix.md
- 상세: 없음

## 2026-07-18 - 검색-색인 설계 적대적 리뷰
검색-색인 설계를 자체 적대적 리뷰와 Claude Code Opus 리뷰로 보강해 Task 4A(1,000행 절단-canonical 집합-clean main 배포)를 운영 배포 선행 게이트로 확정. 커밋 `9de97d6`, 원격 `codex/search-index-doc-hardening`, 상세: `docs/review/review-result-20260718-072911.md`

## 2026-07-18 - 브랜치 통합(develop→main) + 한글 slug 페이지네이션 리얼서버 배포
- 상태: 완료
- 요약: `getAllSlugs`/`getPublishedSlugs`가 `.range()` 페이지네이션 없이 조회해 Supabase 기본 1000행 무음 절단 → 한글 slug 다수(1,062/1,240)가 정적 생성에서 누락(라이브 404-sitemap 누락)되던 것을 `getAllFonts`의 기존 range 루프 패턴으로 해결. 작업 브랜치 3개(`codex/search-index-task4a`=`feature/noonnu-tier-b-enrich`, `codex/fix-tier-a-font-preview`)를 develop→main으로 통합하고 fontagit.com 재배포. 라이브 한글 slug 200, sitemap fonts 1,240 전량 확인. 통합 중 task4a의 `417c15d`가 동일 slug fix의 상위집합(+sitemap 인코딩)임을 확인해 canonical로 채택.
- 커밋/PR: slug fix `7a490ee`, develop 머지 `df11ff2`-`ca68b52`, develop→main 머지 `7a17c74`, 진행기록 `27c6024`. PR 없음(직접 머지). Cloudflare Pages 배포 `f2a4e5d5.fontagit.pages.dev` 스모크 200.
- 남은 일: 검수대기 44건 noonnu-review 사람 검수, 상세페이지 라이선스 4행 렌더 UI 후속(기존 이월).
- 관련 문서: docs/superpowers/plans/2026-07-18-tier-a-dynamic-font-preview.md, docs/review/*.md
- 상세: 없음

## 2026-07-18 - 눈누 Tier B 전량 수집 → prod 적재 + 리얼서버 배포 완료
- 상태: 완료 (prod 적재-검증 + deploy.sh 리얼서버 배포까지 라이브 확정)
- 요약: 눈누 Tier B 1,157종 전량 enrich → 자동발행 1,092 / 검수대기 44 / 스킵 21(이미 발행분 멱등 스킵). prod(ollidam) upsert 적재 후 실조회로 Tier B 1,110 / 전체 1,240 published 검증. deploy.sh로 리얼서버 배포 완료 → fontagit.com에 정적 페이지 2,502개(sitemap 1,250 URL: fonts 1,240+collections 3) 라이브, Tier B 폰트 페이지+sitemap HTTP 200 확인. sitemap 한글 slug 인코딩 + getAllSlugs/publish 조회 1000행 페이지네이션 fix(무음 절단 방지, auto발행 1,092>1000이라 필수). 자동 미발행 사유는 전부 license_proposals에 기록: 34건=상업 게이트 조건부, 10건=게이트 카테고리(포장지/영상) 빈칸.
- 커밋/PR: sitemap fix `f407a77`, publish 페이지네이션 fix(origin/develop 반영), PR #67 develop→main 머지 `2e5fdb3`, 진행기록 `c936785`, 태그 `v0.1.0`(최초). pipeline 테스트 147 passed.
- 남은 일: (1) 검수대기 44건 noonnu-review 사람 검수(34=상업 게이트 조건부, 10=게이트 빈칸) (2) 상세페이지 라이선스 4행 렌더 UI 후속 (3) 로컬 feature/noonnu-tier-b-enrich 브랜치 정리(병렬 워크트리 점유 중이라 보류)
- 관련 문서: docs/superpowers/specs|plans/2026-07-18-noonnu-tier-b-enrich*
- 상세: progress-004.md

- 2026-07-18: Tier A 영어 폰트가 Pretendard로만 표시되던 문제를 동적 Google Fonts 미리보기로 수정하고 `develop`에 반영함 (`b3bde64`, 테스트 175개 통과).
- 2026-07-18: 검색 색인 Task 4A 완료 — exact count, sitemap-canonical 전수 대조, 한글 slug 404/noindex, 빈 제작사 메타, main 전용 배포 게이트를 보완하고 177 tests-lint-2,502페이지 build-1,250 URL SEO 검증 통과.

## 2026-07-18 - 눈누 Tier B 라이선스-스타일 반자동 수집 파이프라인
- 상태: 부분 완료 (코드 develop 병합 완료. 실데이터 파이프라인은 dev 0016 마이그레이션 적용 후 실행 — 사용자 몫)
- 요약: 눈누 상세페이지에서 라이선스 허용표-굵기/이태릭을 결정론(LLM 없이) 사실만 추출 → 상업 4카테고리 전부 허용+무료(price 0)면 자동 발행, 애매하면 검수 큐(license_proposals)로 사람 승인. 마이그레이션 0016(라이선스 세부 컬럼+발행 제약 완화+검수 큐), CLI 3종(noonnu-enrich/review/publish). 결정: 눈누 사실만+발행 전 제작사 교차확인(문구 복제 금지), 재배포/수정은 눈누에 없어 항상 unknown(추정 금지), 임베딩은 자동 게이트 제외. 자체 적대적 리뷰(opus)+codex 리뷰로 슬러그 불일치/OFL 오판/가격 절삭/승인 컬럼버그 잡아 수정.
- 커밋/PR: PR #65 (merged→develop, 머지 `3d70f89`). 커밋 `dc7299c`(0016 마이그레이션)~`394d6b3`(codex fix). 테스트 140 passed.
- 남은 일: (1) 사용자: dev 0016 psql 적용 (2) noonnu-enrich --limit 20 정확도 확인 → 전량 (3) noonnu-review 검수 + audit-sample 5% (4) prod 0016 적용 + noonnu-publish --confirm (5) /deploy는 prod 적재 후 (6) 상세페이지 라이선스 4행 렌더 UI는 후속 별도
- 관련 문서: docs/superpowers/specs/2026-07-18-noonnu-tier-b-enrich-design.md, docs/superpowers/plans/2026-07-18-noonnu-tier-b-enrich.md
- 상세: progress-004.md

## 2026-07-18 - #62 이슈트래킹 실행 계획 문서 + CWV 실측 + codex 리뷰 2회
- 상태: 완료
- 요약: #25 CWV(Core Web Vitals, 핵심 웹 성능 지표) prod 실측 통과(Lighthouse mobile: Performance 96, LCP 2.1s, CLS 0, TBT 40ms). #62 로드맵 남은 이슈의 통합 실행 계획 문서 작성. codex 계획 리뷰 2회(5/10→7/10) + Claude 크로스 리뷰로 보완. 결정: #28 시드 목표 종수는 유연(완료 판정은 품질 게이트=중복0/결측0/컬렉션10), dev DB 조회 장애(B1)는 시드 비차단, 공유 워킹트리 충돌 방지로 기능 브랜치+병합 담당 세션 원칙.
- 커밋/PR: `e70b485`, `fd4e45c` (develop 직접, PR 없음). #25 실측은 이슈 #25 코멘트로 기록(close는 main 병합 정책 존중해 보류).
- 남은 일: B1(dev DB cert) 진단 → #28 시드 실행(다른 세션 조율), #57(/fonts 페이지네이션)-#53(검색 통일) 설계 착수(worktree 격리), 계획문서 Should(시드 트랜잭션/실제 롤백 상세)
- 관련 문서: docs/superpowers/plans/2026-07-18-issue-62-tracking-execution.md, docs/review/review-result-20260718-003906.md, docs/review/review-result-20260718-010244.md
- 상세: 없음


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

## 2026-07-17 - fontagit.com 실서비스 배포 (Cloudflare Pages)
- 상태: 완료
- 요약: 정적 export 웹을 Cloudflare Pages(프로젝트 fontagit)로 실서비스 배포 — fontagit.com 라이브, www→apex/http→https 301, prod ollidam 실데이터(published 130종). 배포 자동화 scripts/deploy.sh(+make deploy) 추가. 정정: 핸드오프의 "prod 폰트 미적재"는 오류, ollidam엔 이미 130종 적재됨.
- 커밋/PR: `ee55306` chore: 프로덕션 배포 스크립트 및 Cloudflare Pages 런북 추가 (develop 직접, PR 없음). 도메인-DNS-리다이렉트는 Cloudflare API로 세팅(git 외부).
- 남은 일: GA4/서치콘솔/서치어드바이저, 필수문서 4종, AdSense, CWV 정식 통과, 일별 롤업 cron, Kong rate limit (마스터 15장 S3)
- 관련 문서: docs/superpowers/specs/2026-07-17-prod-deploy-cloudflare-pages-design.md
- 상세: 없음

## 2026-07-17 - GitHub 이슈 계층화 + 우선순위 라벨 체계
- 상태: 완료
- 요약: 개별로 흩어진 열린 이슈 28개를 마스터 로드맵(#62) 아래 4개 영역(런칭/탐색경험/검색/기술부채)으로 계층화. 기획서 MUST/SHOULD 등급 + PR 병합 실측에 맞춰 priority 라벨(high/medium/low) 정비. 결정: #60을 "폰트 탐색 경험" 에픽 부모로, #56은 컬렉션 페이지 고도화로 범위 축소(시드는 #28로 일원화).
- 커밋/PR: 없음 (코드 변경 없이 GitHub 이슈 #56/#60/#62 본문 + 라벨 직접 편집). 신규 이슈 #60(기능 고도화), #62(로드맵) 생성.
- 남은 일: (1) main 리베이스 완료 후 런칭 MUST 이슈 자동 close 확인 (2) #25 CWV 실측, #28 시드 200/컬렉션10 (런칭 잔여 MUST) (3) 계층화가 마크다운 스냅샷이라 부패 위험 → 필요 시 GitHub 네이티브 sub-issue 전환 검토
- 관련 문서: docs/review/issue-hierarchy-worklog-20260717.md(리베이스 중 유실), docs/review/review-result-dual-20260717-225108.md(듀얼 리뷰)
- 상세: 없음


## 2026-07-16 - 마스터플랜 적대적 리뷰 + 정공법 전환
마스터플랜 v3.0을 적대적 리뷰로 재편(포지셔닝 '정공법 품질 우위' 전환, 킬링 포인트 7) + 30일 그로스 플랜 신설. 커밋 `e864f87`. 상세: 없음(`fontagit-master-plan-v3.0.md` 3장, `fontagit-growth-plan-30d.md`)

## 2026-07-16 - 한글 이름-별칭 적재 + Tier A 전수 동기화 (슬라이스 0.5)
구글폰트 한글 이름-별칭 적재(name_ko 31, 별칭 32) + 인기 밖 폰트를 draft로 내리는 Tier A 전수 동기화. PR #14 MERGED(`f888f02`, 마이그레이션 0005). 상세: 없음(`specs` korean-aliases / tier-a-stale-font-sync)

## 2026-07-16 - 웹 실데이터 연동 (슬라이스1)
웹 화면을 목업 대신 Supabase 실데이터(공개 폰트 130종+컬렉션 3종) 정적 페이지로 연동 + 메타/사이트맵. PR #13 MERGED(`8d87b97`). 상세: 없음(`specs/2026-07-15-web-data-integration-design.md`)

## 2026-07-16 - 알리아스 검색 슬라이스2
- 상태: 완료
- 요약: 한글-영문-오타 매칭 검색(F-04) 구현. pg_trgm 기반 `search_fonts` RPC + `/search` 화면 4상태 UI.
- 커밋/PR: PR #38 계열(develop)
- 남은 일: 없음
- 관련 문서: 없음
- 상세: progress-003.md


## 2026-07-15 - 디자인 정합 슬라이스 4~8 (트렌드/비교/캔버스/컬렉션/등록)
트렌드 화면(/trends)을 목업 맞춰 주간 카드형 재구성, 나머지 4개 화면은 정합 확인만. 커밋 `962850d`. 남은: develop→main PR, 등록폼(/submit) 제출 로직 미구현(백로그). 상세: 없음(`.superpowers/sdd/progress.md`)

## 2026-07-15 - 파이프라인 업로드 원자성-stale alias 개선 (이슈 #8)
폰트 업로드를 폰트별 단일 트랜잭션(RPC)으로 묶고 이름 규칙 변경 시 남던 옛 별칭 제거. 커밋 `6bf73be`. 부분 완료(실업로드 재검증-PR 미완). 상세: 없음(`handoff/2026-07-15-1348-upload-atomicity-issue8.md`)

## 2026-07-15 - 데이터 파이프라인 Supabase 업로드 완성 (Slice 0)
구글폰트 수집→라이선스 판별→Supabase 자동 적재 파이프라인 완성(폰트 136 적재/130 공개, 멱등 검증). PR #7 main 머지. 상세: 없음(`.superpowers/sdd/progress.md`)

## 2026-07-14 - 웹 화면 진입점 추가 (캔버스/비교 nav)
타입 캔버스-비교 화면으로 가는 nav 진입점을 추가해 '진입점 고립' 해소. PR #6 main 머지(후속 `ec59e72`). 상세: 없음

## 2026-07-13 - 웹 Phase 3-4 확장 화면 + 마감
- 상태: 완료
- 요약: 확정 13화면 중 Phase 3-4 확장 화면 구현 및 SSG 마감.
- 커밋/PR: 없음(세부 파일 참조)
- 남은 일: 없음
- 관련 문서: 없음
- 상세: progress-002.md

## 2026-07-13 - 웹 프론트엔드 토대 + 핵심 화면 (Phase 1-2)
- 상태: 완료
- 요약: apps/web 최초 도입(Next.js SSG). 토대 + 홈/목록/상세/트렌드/404 구현.
- 커밋/PR: 없음(세부 파일 참조)
- 남은 일: 없음
- 관련 문서: docs/design/fontagit-v2/
- 상세: progress-001.md
