# Tier A 폰트 미리보기 계획 적대적 리뷰

## 대상

- `docs/superpowers/plans/2026-07-18-tier-a-dynamic-font-preview.md` (Plan)

## 종합 점수: 86/100

- 완성도: 22/25
- 일관성: 23/25
- 실현 가능성: 17/20
- 엣지케이스/리스크: 12/15
- 추적성: 12/15

## 반드시

### CSS family 선언만으로 실제 렌더링 성공을 오판할 수 있음

- 위치: `docs/superpowers/plans/2026-07-18-tier-a-dynamic-font-preview.md:296`
- 현재: 계산된 `font-family`와 `<link>` 존재만 확인한다.
- 제안: `document.fonts.load()` 완료 후 Orbitron `FontFace`가 `loaded`인지 확인한다.
- 근거: CSS에 존재하지 않는 family를 써도 `getComputedStyle()`은 그 문자열을 그대로 반환하며 실제 화면은 폴백 글꼴일 수 있다.
- 영향: 원래 버그가 남아도 검증이 통과하는 거짓 양성 가능성.

## 권장

### 기존 TypeScript 기준선 오류를 성공 조건에서 분리해야 함

- 위치: `docs/superpowers/plans/2026-07-18-tier-a-dynamic-font-preview.md:267`
- 현재: `tsc` 오류 0건을 요구하지만 수정 전 실행에서도 오류가 존재한다.
- 제안: 수정 전 오류 목록과 대조해 새 오류 0건을 요구하고 기존 오류는 별도 범위로 남긴다.
- 근거: 수정 전 `pnpm exec tsc --noEmit`이 `mappers.test.ts`, `WeeklyRankPanel.test.tsx`, `filters.test.ts`에서 실패했다.
- 영향: 이번 변경과 무관한 작업 혼입 또는 검증 결과 과장 위험.

### 수동 DB 타입은 과거 fixture를 안전하게 받아야 함

- 위치: `docs/superpowers/plans/2026-07-18-tier-a-dynamic-font-preview.md:94`
- 현재: `FontRow.source_tier`를 필수로 추가하면 기존 fixture 전체에 새 타입 오류가 추가된다.
- 제안: 수동 partial row 타입에서는 optional로 받고, 값이 없으면 외부 요청을 금지한다.
- 근거: 실제 DB에는 `source_tier`가 필수지만 현재 `FontRow`는 이미 전체 스키마가 아닌 부분 타입이다.
- 영향: 실제 기능과 무관한 테스트 fixture 대량 수정.

### 외부 네트워크 실패 폴백을 직접 검증해야 함

- 위치: `docs/superpowers/plans/2026-07-18-tier-a-dynamic-font-preview.md:296`
- 현재: 정상 Google 응답만 확인한다.
- 제안: Google Fonts 요청을 차단한 브라우저 컨텍스트에서 견본 표시와 Pretendard 폭 일치를 확인한다.
- 근거: 목표에 “로딩 전·실패 시 Pretendard 폴백”이 명시되어 있다.
- 영향: 오프라인·차단 환경에서 빈 글자나 레이아웃 깨짐을 놓칠 수 있다.

## 자기 비평 결과

- 1차 지적: 5건
- 유지: 4건
- 제거: 1건
- 제거 사유: `text=`로 글립을 제한하자는 지적은 상세 화면의 사용자 입력 문장 전체를 렌더링해야 하는 요구와 충돌하며, 뷰포트 지연 로딩으로 초기 성능 위험을 이미 줄인다.

## 적용 결과

- 반드시 1건과 권장 3건을 Plan에 반영했다.
- 구현 전 차단 이슈는 남아 있지 않다.

✅ 완료
