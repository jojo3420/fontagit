# progress-012: 캔버스-비교 화면 홈 통합 보드 (#118, PR #127, v0.9.0) (2026-07-27)

## 맥락

폰트를 "써보는" 기능이 /playground(타입 캔버스, 폰트 고정)와 홈 하단 /#compare(3슬롯 비교)로 이원화되어 있었다. 이슈 #118로 하나로 합치되, 캔버스 레이아웃(대표 + 8칸)을 유지하고 모든 칸에 셀렉트를 붙여 홈("/")에서만 노출하기로 결정. /playground 라우트는 #69(진짜 캔버스 편집기)를 위해 비움.

## 구현 요약

- 신규 `apps/web/components/CompareCanvas.tsx`(+module.css/test): 대표 견본 96px + 8칸 그리드, 전 칸 셀렉트(후보 = data/fonts.ts free 9종, familyOf 재사용), 프리셋 4개, 기본 문구 "다람쥐 헌 쳇바퀴에 타고파 1234 !@#$", h2 id="compare-heading" 유지(홈 section aria-labelledby 의존), 빈 문구 fallback `text || " "`
- `CompareLazy`가 CompareBoard 대신 CompareCanvas를 lazy 로드(IntersectionObserver 패턴 유지). app/page.tsx 무변경
- 삭제: app/playground/, PlaygroundCanvas, CompareBoard(+css). Header-MobileTabBar에서 캔버스/비교 항목 제거, sitemap 정적 5개로 축소, verify-seo-output.mjs(+node-test) 기대 URL 갱신
- `apps/web/public/_redirects` 신설: `/playground/ / 302` + `/playground / 302` — 301 금지(#69 라우트 재사용 시 브라우저 영구 캐시 함정)
- E2E smoke.spec.ts: playground 테스트 → 홈 보드 테스트(스크롤 후 lazy 마운트 대기), 네비 부재 검증, 모바일 탭 3개 기준
- base는 main(사용자 결정, 기존 develop 관례 변경), PR #127 스쿼시 머지 → v0.9.0 태그 배포(fontagit.com), 302 실측 확인

## 시도와 실패 (재발 방지)

1. **전사 태스크 임의 재작성 사고**: 계획에 코드 전문이 있는 태스크를 Haiku 서브에이전트가 자기 방식으로 재작성(무료 필터 누락으로 유료 폰트 후보 노출, 프리셋 미구현, aria-label 변형, 그리드 기본값 오류). 좁은 단위 테스트 2케이스와 태스크 리뷰어 모두 통과시켰고 E2E에서야 발각. 교정: 브리프 코드와 라인 단위 대조 재리뷰로 재전사 검증. 전사 태스크 리뷰엔 "라인 단위 대조 + 임의 변경 Critical" 지시 필수
2. **E2E --update-snapshots가 깨진 화면을 기준선으로 오염**: e2e 환경에서 폰트 상세가 404인 상태로 스냅샷을 갱신해 상세 페이지 기준선 4개가 404 화면과 바이트 동일하게 커밋됨. Codex PR 리뷰가 해시 대조로 발견, origin/main 기준선으로 복구(aa27d60). --update-snapshots 실행 시 실패 테스트의 스냅샷도 갱신되는지 확인할 것
3. **next/link와 IO 스텁 충돌**: CompareCanvas가 Link를 쓰자 CompareLazy.test의 IntersectionObserver 스텁에 unobserve가 없어 cleanup TypeError. 스텁에 no-op unobserve 보강으로 해결
4. **deploy.sh는 stale .next를 정리 안 함**: E2E가 dev DB로 만든 fetch-cache가 남아 있으면 prod 배포 데이터 오염 위험 → 배포 전 `rm -rf apps/web/.next` 수동 실행함

## 결정 근거와 기각된 대안

- 302 vs 301: #69에서 /playground 재사용 예정이라 301 영구 캐시 기각
- 셀렉트 후보 확장(Tier A 수백 종) 기각: 동적 로딩-검색 UI 필요, 별도 이슈로
- slug 실패 대체 UI 기각: 후보와 slug가 동일 정적 배열이라 실패 경로 없음(YAGNI)
- 홈 배치: Hero-주간랭킹 유지, 기존 비교 섹션 자리 대체(홈 재구성 기각)

## 재현-검증 명령어

- 단위: `cd apps/web && npm test` (245+)
- E2E: `cd apps/web && npm run e2e -- --workers=1` — 상세 페이지 404 x4, preview input x2는 이 세션 이전부터 실패(미해결, 원인 조사 필요)
- 리다이렉트: `curl -I https://fontagit.com/playground/` → 302 + `location: /`
- 후속 개선 목록: docs/review/pr-review-127-20260727-152601.md
