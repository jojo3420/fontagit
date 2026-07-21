# Review Report: 2026-07-20-fonts-section-hierarchy-canvas-design.md
> Generated: 2026-07-20 21:48
> Reviewer: Antigravity CLI (agy) — model: Gemini 3.5 Flash (High)
> Cross-review: Claude (코드 대조 검증 포함)

---

## 1. agy 리뷰 요약

- 전체 점수: 8.2/10
- 한줄 요약: DB 스키마 무변경 하이브리드 매핑 + 슬림 스티키 캔버스는 기획 의도에 부합하나, 대량 폰트의 초기 페이로드와 실시간 동시 리렌더링/웹폰트 동적 로딩 성능 대비책 보완 필요.

항목별: 완성도 주의 / 누락 주의 / 일관성 OK / 실현가능성 OK.

구체적 피드백(요약):
1. RSC→RCC 직렬화: 전체 폰트(약 1,110종)를 클라이언트로 전달 시 페이로드/LCP/TTI 악영향.
2. 입력 랙: 타이핑마다 60개(12×5) FontCard 동시 리렌더 → 버벅임.
3. 웹폰트 로딩 폭증: 커스텀 문구 입력 순간 노출 폰트 일제 로딩 → FOUT/FOIT.
4. 자동 매핑 취약성: weights 타입(문자열/숫자), category_ko 정규화, 빈 배열 방어 누락 우려.

개선 제안: (1) useTransition/useDeferredValue [최우선] (2) 개요 뷰 페이로드 제한(top N/projection) (3) Intersection Observer 지연 로딩 (4) sectionOf 방어 코드.

---

## 2. Claude 크로스 리뷰

### 종합 소견
agy의 성능 관점 지적은 방향이 타당하나, 코드를 보지 못해 **이미 구현/방어된 부분을 새 리스크로 오인**한 항목이 다수다. 실제로 새로 유효한 지적은 "실시간 입력 랙(useDeferredValue)" 하나가 핵심이고, 나머지는 기존 조건이거나 타입 시스템으로 이미 차단돼 있다.

### 항목별 판정 (코드 근거 대조)

| # | agy 피드백 | 판정 | Claude 의견 (근거) |
|---|-----------|------|------------------|
| 1 | RSC→RCC 전체 폰트 직렬화 페이로드 | 부분 동의 | 현재 `/fonts`가 이미 전체 폰트를 클라이언트로 넘기고 무한스크롤 처리 중(`ClientFontsList.tsx:33,41,48`). 이 설계가 만든 신규 리스크 아님 = 기존 조건. 다만 섹션 개요는 서버 그룹핑 후 top N만 전달하면 오히려 개선 가능 → Should. |
| 2 | 실시간 입력 랙(리렌더) | 동의 | 캔버스 문구를 상위로 끌어올려 매 입력마다 노출 카드 리렌더는 실제 신규 리스크. `useDeferredValue`로 저비용 완화 타당 → Must. |
| 3 | 웹폰트 지연 로딩(Intersection Observer) | 동의하지 않음(대부분 기구현) | `FontCard`가 이미 `LazyFontPreview`로 뷰포트 진입 시 로딩(`FontCard.tsx:4,16`). 신규 작업 아님. 단 `previewText`가 `LazyFontPreview` 내부 렌더 경로를 타도록 연결하는 것만 보장하면 됨 → Must(통합 가드, 신규 구현 아님). |
| 4 | weights/category 파싱-정규화 취약성 | 동의하지 않음(대부분 무효) | `weights: number[]`로 타입 고정(`lib/db/types.ts:11`), 도메인 `availableWeights`는 빈 배열 시 `[400]` 기본값(`mappers.ts:65`)이라 런타임 파싱/빈배열 우려 해당 없음. `category`도 타입 유니온이라 문자열 정규화 불필요. 실제 액션은 "규칙이 `font.availableWeights`(number[])를 정확히 참조"뿐 → Must(문구 정정). |

### 동의하는 핵심 피드백 (Top)
1. **입력 랙 방지(useDeferredValue)** — 실시간 동기화의 유일한 진짜 신규 성능 리스크. 설계에 명시.
2. **개요 뷰 서버 그룹핑 + top N 전달** — 페이로드를 기존보다 줄이는 개선(회귀 아님).

### 동의하지 않는 피드백
- **지연 로딩 제안(#3)**: 이미 `LazyFontPreview`로 구현됨. 재구현 불필요.
- **weights/category 파싱-정규화(#4)**: 타입 시스템(number[], Category 유니온)과 mapper 기본값으로 이미 방어. 유일한 실제 조치는 필드명 정정(`availableWeights`).

### agy가 놓친 추가 관점
- 기존 `/playground`의 `PlaygroundCanvas`가 이미 "문구 입력→전체 카드 반영" 패턴을 보유. 신규 `TypeCanvasBar`는 이를 재사용/정렬해 중복을 피해야 함(설계 일관성).

---

## 3. 최종 권고사항

### 즉시 반영 (Must)
1. 캔버스 문구 → FontCard 렌더에 `useDeferredValue`(또는 `useTransition`) 적용을 설계에 명시(입력 랙 방지).
2. `previewText`가 기존 `LazyFontPreview` 경로를 통해 렌더되도록 통합(뷰포트 밖 카드 로딩 방지 유지).
3. `sectionOf` 규칙 문구를 `font.availableWeights`(number[], 빈 배열 시 [400] 보장) 참조로 정정.

### 검토 후 반영 (Should)
4. 섹션 개요 모드는 서버에서 그룹핑 후 각 섹션 top N + 총개수만 클라이언트로 전달(페이로드 절감).

### 참고 (Nice to have)
5. 신규 `TypeCanvasBar`를 기존 `PlaygroundCanvas` 패턴과 정렬해 중복 최소화(가능하면 공통화).
6. category 정규화/weights 파싱 방어는 타입상 불필요 — 추가 구현 금지(YAGNI).
