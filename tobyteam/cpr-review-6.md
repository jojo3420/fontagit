검토 범위: 제공 diff + 로컬 파일 확인 기준입니다. 서버 실행 검증은 샌드박스 `EPERM`으로 못 했습니다.

## Critical(반드시 수정)
해당 심각도 없음.

## High(수정 권장)
해당 심각도 없음.

## Medium

### 모바일 탭 active 오탐 가능
- **파일:라인**: [MobileTabBar.tsx](/Users/joel.silver/Workspace/gitroom/python/fontagit/apps/web/components/MobileTabBar.tsx:19)
- **문제**: `pathname.startsWith(t.href)`는 `/compare-old`, `/comparison`, `/fonts-old`도 active로 판단합니다.
- **근거**: `/compare`와 `/collections`는 직접 접두어 충돌은 없지만, 잘못된 404 경로에서도 탭이 active가 될 수 있습니다.
- **제안 수정**: `pathname === t.href || pathname.startsWith(`${t.href}/`)` 형태로 바꾸세요.

### 새 테스트가 약하고 flaky 가능
- **파일:라인**: [smoke.spec.ts](/Users/joel.silver/Workspace/gitroom/python/fontagit/apps/web/e2e/smoke.spec.ts:122)
- **문제**: `page.setViewportSize(...)`에 `await`가 없습니다. 또 href 정규식 `/\/compare\/?/`는 `/compare-bad`도 통과할 수 있습니다.
- **근거**: Playwright의 viewport 변경은 비동기입니다. 링크 목적 검증도 정확하지 않습니다.
- **제안 수정**: `await page.setViewportSize(...)`, href는 `/^\/compare\/?$/`, `/^\/playground\/?$/`처럼 끝까지 고정하세요.

### 모바일 변경 핵심 검증 부족
- **파일:라인**: [smoke.spec.ts](/Users/joel.silver/Workspace/gitroom/python/fontagit/apps/web/e2e/smoke.spec.ts:105)
- **문제**: PR 핵심 중 하나가 “모바일 비교 탭 추가”인데, 테스트는 탭바가 보이는지만 봅니다.
- **근거**: `비교` 탭 존재, href, 5탭 구성, 모바일 상단 nav에서 toolLink 숨김을 직접 검증하지 않습니다.
- **제안 수정**: 390px viewport에서 모바일 탭의 `비교` 링크와 href를 assert 하세요.

## Low/Nit

### 진행 문서가 PR 결과와 충돌
- **파일:라인**: [docs/progress.md](/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/progress.md:23)
- **문제**: 이 PR이 진입점을 추가하는데, 문서에는 아직 “캔버스/비교 화면 진입점 추가”가 남은 일로 적혀 있습니다.
- **근거**: PR 목적과 문서 상태가 반대입니다.
- **제안 수정**: 해당 항목을 완료로 옮기거나 PR #6 완료 기록을 새로 추가하세요.

### 헤더 active 비일관성은 현재 결함 아님
- **파일:라인**: [Header.tsx](/Users/joel.silver/Workspace/gitroom/python/fontagit/apps/web/components/Header.tsx:14)
- **문제**: 캔버스/비교만 active가 없는 것은 아닙니다. 헤더 전체가 active 상태를 원래 표시하지 않습니다.
- **근거**: 기존 `폰트`, `트렌드`, `컬렉션`, `등록`도 active 로직이 없습니다.
- **제안 수정**: 이번 PR에서는 건드리지 않는 편이 맞습니다. 필요하면 별도 작업으로 클라이언트 nav 컴포넌트를 분리하세요.

## Verdict
- **Decision**: ⚠️ 조건부 머지
- **Blocking issues**: Critical 0, High 0
- **Residual risks**: 모바일 active 오탐과 테스트 약함은 머지 전 고치는 게 좋습니다.

머지 가능 여부: 지금 바로 머지보다는 Medium 3개 수정 후 머지를 권장합니다.