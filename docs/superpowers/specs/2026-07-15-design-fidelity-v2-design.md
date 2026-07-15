# 디자인 일치(Design Fidelity) — fontagit-v2 목업 대비 실제 화면 정합

작성일: 2026-07-15 (듀얼 리뷰 반영 개정)
대상 앱: `apps/web` (Next.js 16 / React 19 / CSS Modules / Pretendard)
기준 디자인: `docs/design/fontagit-v2/project/FontAgit 화면 세트.dc.html`

## 1. 목표와 성공 기준

- 디자인 목업 각 화면과 실제 렌더가 레이아웃/모듈 구성에서 90% 이상 동일. 구현 요소 누락 금지.
- 판정: 화면별 캡처를 섹션 2.2의 배점 체크리스트로 채점, 90점 이상이면 합격.
- 비목표(Non-goal): 색/토큰 재설계. `styles/tokens.css`는 이미 디자인과 일치. 토큰은 손대지 않고 기존 변수 재사용.

## 2. 검증 루프 (화면마다 반복)

1. 디자인 프레임 캡처: 디자인 HTML을 브라우저(JetBrains 내장 서버 `localhost:63342` 등)에서 열어 대상 프레임 캡처.
2. 실제 렌더 캡처: `localhost:3000`의 대응 라우트를 같은 뷰포트로 캡처.
3. diff 항목화 후 섹션 2.2로 채점.
4. 수정 후 재캡처. 90점 도달까지 반복.
5. 뷰포트 3종 확인: 데스크톱(>=1180px), 모바일(약 360px), 다크모드.
- 도구: Playwright(회귀 캡처) 또는 e2e 스킬. 폰트 렌더 미세차는 diff 노이즈로 간주.

## 2.1 프레임-라우트 매핑표 (M1)

| 프레임 | 실제 라우트 | 대표 데이터(slug) | 뷰포트 | 슬라이스 |
|--------|------------|------------------|--------|---------|
| 헤더/푸터(전역) | 모든 페이지 | - | 데/모/다 | 0 |
| 1g 무료 상세 | `/fonts/nanum-myeongjo` | nanum-myeongjo (무료/명조) | 데/모/다 | 1 |
| 6a 유료 상세 | `/fonts/sandoll-gothic-neo` | sandoll-gothic-neo (유료/고딕) | 데/모/다 | 1 |
| 1d 홈 | `/` | weeklyTrends | 데/모/다 | 2 |
| 1f 목록 | `/fonts` | 10개 폰트 | 데/모/다 | 3 |
| 1h 트렌드 | `/trends` | weekly/monthly | 데/모/다 | 4 |
| 5a 비교 | `/compare` | 최대 3종 | 데/모/다 | 5 |
| 3a 캔버스 | `/playground` | - | 데/모/다 | 6 |
| 8a 컬렉션 상세 | `/collections/[slug]` | collections | 데/모/다 | 7 |
| 8b 등록 | `/submit` | - | 데/모/다 | 8 |

- 유료 대표 `sandoll-gothic-neo`는 실제 서체 미보유 -> 대체 렌더 `fontKey: blackHanSans`(기구현). 디자인 6a의 예시명(산돌 정체)과 데이터명(산돌 고딕 Neo)이 달라도 모듈 구성 일치로 판정.

## 2.2 90% 판정 체크리스트 배점 (M2)

화면당 100점 만점, 합격선 90.

| 항목 | 배점 | 판정 내용 |
|------|------|----------|
| 모듈 존재 | 40 | 디자인의 모든 블록이 실제에도 존재하는가(누락 0 목표) |
| 레이아웃/정렬 | 30 | 단 구성(1단/2단), 좌우 배치, 정렬, sticky |
| 간격/타이포/모서리 | 20 | 패딩/갭, 폰트 크기/굵기, radius, 테두리 |
| 텍스트 라벨 | 10 | 제목/버튼/캡션 문구 일치 |

- 예외(Header): 네비 항목 수/라벨은 채점 제외(섹션 7 참조).

## 3. 데이터 모델 확장 (`types/font.ts`, `data/fonts.ts`)

라이선스 요약 카드용 필드 추가:
- `license.type`: string — 예 "상용 라이선스", "SIL OFL"
- `license.webfont`: "included" | "separate" | "no"
- `license.redistribution`: "yes" | "no"
- `priceFrom?`: number — 유료 시작가(예 99000). 무료 미설정.
- 판매처 라벨: `officialUrl` 호스트에서 파생.
- 기존 유지: commercial(yes/conditional/no), verifiedAt, foundry, availableWeights, moves, freeAlternatives.

라이선스 값 표기 매핑:
- commercial yes/conditional/no -> 상업적 사용 = 가능/구매 시/불가
- webfont included/separate/no -> 웹폰트 = 포함/별도 구매/불가
- redistribution yes/no -> 재배포 = 가능/불가
- 10개 폰트(무료 9 + 유료 1) 데이터를 실제 값으로 채움.

### 3.1 데이터 예외 정책 (M3)

- **officialUrl 파생**: 값 없음/파싱 실패 -> "이동 -> 호스트" 줄 숨김. `www.` 접두 제거 후 호스트만 표기.
- **무료 대안 카드**: 대안 0개 -> 카드 렌더 안 함. 1~2개 -> 제목 "비슷한 무료 대안 N개"로 실제 개수 반영. 3개 -> "3개".
- **priceFrom 없는 유료**: CTA 버튼을 "구매 페이지로 이동"(가격 생략)으로.
- **verifiedAt 없음**: 서브라인에서 "확인일" 표기 생략.
- **validator**: `lib/data.ts`의 assertDataIntegrity()에서 유료면 `commercial/webfont/redistribution` 필수, priceFrom 권장 검증. 필수 결측 시 빌드 실패.

## 4. 슬라이스 1 — 폰트 상세 (최우선)

파일: `app/fonts/[slug]/page.tsx` + `.module.css`, 신규 컴포넌트 Breadcrumb / LicenseSummaryCard / AlternativesCard. 기준 프레임: 1g(무료), 6a(유료).
현재 1단(max 900px) -> 2단: 본문(좌) + 사이드바(우, 약 360px), 컨테이너 약 1180px. 모바일 1단.

### 왼쪽 본문 (모듈 순서)
1. 브레드크럼(신규): 폰트 > 카테고리 > 폰트명. 회색, `>` 구분.
2. 제목행: H1 폰트명 + 티어 배지(유료/무료).
3. 메타: foundry, N가지 굵기, 이동 moves회.
4. 견본 박스(테두리 카드, radius 12): 대형 견본 텍스트.
   - 무료(1g): 하단에 미리보기 입력(PreviewInput). 유료(6a): 입력 없음 + 대체 견본 캡션.

### 오른쪽 사이드바 (sticky, 데스크톱)
5. 라이선스 요약 카드: 제목 "라이선스 요약" + 서브(`license.type` / 확인일 verifiedAt) + 아이콘행 3개(상업적 사용/웹폰트/재배포) + 안내 박스 + CTA 버튼 + "이동 -> 판매처 호스트".
6. 비슷한 무료 대안 카드(유료 전용, 대안 1개 이상일 때만): 제목 "비슷한 무료 대안 N개" + N행(폰트명 + 무료 배지).

### 4.1 신규 컴포넌트 props (S1)

- **Breadcrumb**: `items: { label: string; href?: string }[]`. 마지막 항목은 링크 없음.
- **LicenseSummaryCard**: `licenseType: string; verifiedAt?: string; rows: { label: string; value: string; state: "ok" | "cond" | "no" }[]; notice: string; cta: { label: string; href: string; priceFrom?: number }; sellerHost?: string`. state로 아이콘+색 결정(텍스트 병기, 색만으로 구분 금지).
- **AlternativesCard**: `title: string; subtitle: string; items: { slug: string; nameKo: string; fontKey: string }[]`. items 0개면 부모가 렌더하지 않음.

### 4.2 모바일 규칙 (S2, 프레임 4b)

- 1단 스택 순서: 브레드크럼 -> 제목/메타 -> 견본 박스 -> 라이선스 요약 -> (유료)무료 대안.
- 사이드바 sticky 해제(일반 흐름).
- 무료: 미리보기 입력을 화면 하단 고정(fixed bottom). 유료: 입력 없음.
- CTA 버튼은 라이선스 카드 내부에서 전체폭.

### 완료 기준(슬라이스 1)
- 무료(`/fonts/nanum-myeongjo`)/유료(`/fonts/sandoll-gothic-neo`) 두 변형 모두 섹션 2.2 기준 90점 이상.
- 데이터 모델 확장 반영, 10개 폰트 라이선스 값 채움.
- 데스크톱 2단 / 모바일 1단 / 다크모드 캡처 확인.

## 5. 나머지 슬라이스 (각 착수 시 슬라이스 1 수준으로 상세화)

- 슬라이스 2 — 홈(1d) `app/page.tsx`: 1단 -> 2단. 좌측 히어로(H1 + 검색 입력 + 카테고리 칩), 우측 인기 TOP 10 순위.
- 슬라이스 3 — 목록(1f) `app/fonts/page.tsx`: 상단 가로 FilterChip -> 왼쪽 필터 사이드바 + 카드 그리드.
- 슬라이스 4 — 트렌드(1h) `app/trends/page.tsx`: TOP 10 확장(주간/월간) 정합.
- 슬라이스 5 — 비교(5a) `app/compare/page.tsx`: 최대 3열 캔버스 + 공유 입력 동기화.
- 슬라이스 6 — 캔버스(3a) `app/playground/page.tsx`: 한 글자를 전체 폰트로 세로 스택, 딥그린 톤.
- 슬라이스 7 — 컬렉션(8a) `app/collections/[slug]/page.tsx`: 서문 + 폰트별 한 줄 코멘트.
- 슬라이스 8 — 등록(8b) `app/submit/page.tsx`: 폼 레이아웃 + 검증 상태 정합.

각 슬라이스는 모바일(4a/4b/4c) + 다크(9b)도 함께 검증.

## 6. 슬라이스 0 — 공통 크롬 + 데이터 모델 (슬라이스 1 선행)

- `components/Header.tsx`: 로고 톤 정합. 네비 6개 유지(수용한 차이). 테마 토글/검색 아이콘 유지.
- `components/Footer.tsx`: 디자인 톤 정합.
- 데이터 모델 확장(섹션 3)은 슬라이스 1 의존이므로 여기서 함께 수행.

## 7. 수용한 차이 (Divergence)

- 상단 네비 6개 유지: 디자인 헤더(폰트/트렌드만)와 의도적으로 다름. 캔버스/비교/컬렉션/등록은 실제 라우트라 접근성 우선.
- **Header 채점 규칙 (S3)**: 채점 제외 = 네비 항목 수/라벨. 채점 포함 = 로고 형태-위치, 헤더 높이, 좌우 패딩, 우측 액션(테마/검색) 정렬-간격.
- 테마 토글/검색 아이콘 유지(다크모드는 디자인 9b에 존재).

## 8. 파일 영향 범위(초기)

- 신규 컴포넌트: Breadcrumb, LicenseSummaryCard, AlternativesCard(+ CSS Module).
- 수정: types/font.ts, data/fonts.ts, lib/data.ts, app/fonts/[slug]/page.tsx(+css), components/Header.tsx(+css), components/Footer.tsx(+css).
- 슬라이스 2~8은 각 라우트 page.tsx + page.module.css 및 관련 컴포넌트.

## 9. 리스크

- 디자인 프레임이 단일 HTML 캔버스에 모여 있어 개별 프레임 격리 캡처 필요.
- 폰트 렌더 차이로 픽셀 완전 일치 불가 -> 섹션 2.2 배점으로 판정.
- 유료 폰트는 실제 서체 미보유 -> 대체 견본(fontKey) 유지.
- 데이터 모델 확장 시 기존 10개 폰트 값 정확성 필요(라이선스 오표기 주의).

## 10. 다크모드 확인 항목 (N1, 참고)

- 신규 카드의 안내 박스(surface-2 배경) 대비, CTA 버튼(on-point 텍스트) 대비, 카드 테두리(border 변수) 가시성 최소 확인.
