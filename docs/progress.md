# Progress

## 프로젝트 소개

FontAgit(폰트 아지트)는 국내외 무료-유료 폰트를 검색-비교하고 공식 다운로드/구매 페이지로 연결해 주는 폰트 아카이브 웹사이트입니다. 폰트 파일을 직접 호스팅하지 않고 공식 페이지로 안내하며, 검색 유입과 광고를 수익 모델로 합니다. 검색으로 들어오는 일반 사용자, 디자이너, 마케터, 학생이 주 사용자입니다.

## 주요 기능

- 폰트 목록 탐색과 폰트별 상세 페이지(실제 서체 견본, 원하는 문장 미리보기 입력, 상업적 이용 가능 여부, 공식 페이지 링크)
- 유료 폰트 상세에서 비슷한 무료 대안 추천
- 인기 폰트 트렌드(주간/월간 TOP)
- 홈 히어로 + 이번 주 TOP 10, 다크모드
- 폰트 데이터 자동 수집 파이프라인(구글폰트 OFL 등, 서버 배치 — 이전 작업, main 반영됨)

## 진행 기록

## 2026-07-13 - 웹 Phase 3-4 확장 화면 + 마감

- 상태: 구현 완료, PR 대기
- 완료한 일: Phase 1-2 토대 위에 확장 화면 5개(타입 캔버스 `/playground`, 비교 `/compare`, 컬렉션 목록-상세 `/collections`, 창작자 등록 `/submit`, 빈 상태 `EmptyState`)와 마감 3개(모바일 하단 탭바 `MobileTabBar` + safe-area, 다크모드 토글 `ThemeToggle`, 파비콘 + OG 이미지)를 디자인 95% 재현으로 구현. 헤더 nav 404 블로커 해소, 컬렉션 빌드타임 무결성 검증 추가.
- 커밋/PR: 웹 커밋 16개(`63332e2`..`1b89f43`, 각 Task feat + 리뷰 fix). Base `413e3fb`(계획 + Codex 리뷰 반영). PR 대기.
- 결정사항: Phase 1-2 결정 승계(CSS Modules, 정적 export, 목업 데이터, 인터랙션 핵심만 동작). 비교는 폰트 슬롯 3개 고정 + select 교체. OG는 satori에 한글 폰트(Pretendard-Bold.otf) 임베드(미임베드 시 한글이 네모로 깨짐). 다크 토글은 `useSyncExternalStore`로 FOUC 스크립트가 설정한 `data-theme`를 구독(setState-in-effect 회피).
- 남은 일: 배포 도메인 확정 후 `layout.tsx` metadata에 `metadataBase` 설정(현재 og:image 절대 URL이 localhost). 필터/검색/등록폼은 여전히 비동작 목업. 실데이터 파이프라인 연동은 후속.
- 관련 문서: `docs/superpowers/plans/2026-07-13-fontagit-web-phase3-4.md`, `docs/review/review-result-20260713-145158.md`(Codex + Claude 크로스 리뷰)
- 상세 히스토리: progress-002.md

## 2026-07-13 - 웹 프론트엔드 토대 + 핵심 화면 구축 (Phase 1-2)

- 상태: 완료
- 완료한 일: 웹사이트 화면(apps/web)을 새로 구축. 홈, 폰트 목록, 폰트 상세(무료/유료 구분 + 무료 대안), 트렌드, 없는 페이지(404)를 디자인과 95% 동일하게 구현. 내용은 임시 목업 데이터로 채움.
- 커밋/PR: 웹 커밋 다수(`3634686`..`148d770`), PR #4 머지 완료(`4fe1da5`). https://github.com/jojo3420/fontagit/pull/4
- 결정사항: 스타일은 CSS Modules + CSS 변수 토큰(Tailwind 제거), 배포는 정적 사이트 생성(`output: 'export'`), 폰트는 앱에 self-host(next/font + Pretendard), 화면 데이터는 목업(추후 파이프라인 실데이터로 교체 예정).
- 남은 일: Phase 3-4 화면(타입 캔버스, 비교, 컬렉션, 창작자 등록, 모바일 정밀화, 다크모드 토글 UI, 런칭 자산 OG). 헤더의 컬렉션-등록 링크는 아직 대상 페이지가 없어 클릭 시 404. 필터/검색은 현재 목업(비동작). README와 중복 pnpm-workspace 경고 정리.
- 관련 문서: `docs/superpowers/specs/2026-07-12-fontagit-web-screens-design.md`, `docs/superpowers/plans/2026-07-12-fontagit-web-foundation-and-core.md`, `docs/review/pr-review-4-dual-20260713-120348.md`
- 상세 히스토리: progress-001.md
