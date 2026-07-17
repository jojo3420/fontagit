# Progress

## 프로젝트 소개
FontAgit는 한글 폰트를 찾고 라이선스-미리보기 정보를 확인하는 폰트 탐색 웹 서비스다. 눈누(noonnu)의 약점(불확실한 라이선스 고지, 약한 검색)을 겨냥해 "행동별 허용 4행 + 확인일 + 원문 링크" 신뢰 블록과 한글/영문/오타/초성 검색을 차별점으로 삼는다. 스택은 Next.js SSG(정적 사이트 생성) + Supabase, 저장소는 `apps/web`(웹) + `apps/pipeline`(데이터 수집).

## 주요 기능
- 폰트 목록/상세/트렌드/홈 등 핵심 화면 (Phase 1-2)
- Phase 3-4 확장 화면 + SSG 마감
- 알리아스 검색: 한글-영문-붙여쓰기-오타-초성 매칭 + 실시간 자동완성(F-04/F-16/F-19)
- 런칭 MUST 기능 세트(필수 문서, 측정, AdSense, 신고-문의, 목록 필터-정렬, 미리보기 폴백)는 코드 완료되어 develop에 병합됨(main 승격 대기)
- 실서비스 배포: fontagit.com이 Cloudflare Pages로 라이브(정적 export + prod ollidam 130종 데이터), 배포 자동화 스크립트(scripts/deploy.sh)

## 진행 기록

## 2026-07-18 - #62 이슈트래킹 실행 계획 문서 + CWV 실측 + codex 리뷰 2회
- 상태: 완료
- 요약: #25 CWV(Core Web Vitals, 핵심 웹 성능 지표) prod 실측 통과(Lighthouse mobile: Performance 96, LCP 2.1s, CLS 0, TBT 40ms). #62 로드맵 남은 이슈의 통합 실행 계획 문서 작성. codex 계획 리뷰 2회(5/10→7/10) + Claude 크로스 리뷰로 보완. 결정: #28 시드 목표 종수는 유연(완료 판정은 품질 게이트=중복0/결측0/컬렉션10), dev DB 조회 장애(B1)는 시드 비차단, 공유 워킹트리 충돌 방지로 기능 브랜치+병합 담당 세션 원칙.
- 커밋/PR: `e70b485`, `fd4e45c` (develop 직접, PR 없음). #25 실측은 이슈 #25 코멘트로 기록(close는 main 병합 정책 존중해 보류).
- 남은 일: B1(dev DB cert) 진단 → #28 시드 실행(다른 세션 조율), #57(/fonts 페이지네이션)-#53(검색 통일) 설계 착수(worktree 격리), 계획문서 Should(시드 트랜잭션/실제 롤백 상세)
- 관련 문서: docs/superpowers/plans/2026-07-18-issue-62-tracking-execution.md, docs/review/review-result-20260718-003906.md, docs/review/review-result-20260718-010244.md
- 상세: 없음

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

## 2026-07-16 - 알리아스 검색 슬라이스2
- 상태: 완료
- 요약: 한글-영문-오타 매칭 검색(F-04) 구현. pg_trgm 기반 `search_fonts` RPC + `/search` 화면 4상태 UI.
- 커밋/PR: PR #38 계열(develop)
- 남은 일: 없음
- 관련 문서: 없음
- 상세: progress-003.md

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
