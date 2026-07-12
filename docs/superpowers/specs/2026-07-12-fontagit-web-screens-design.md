# FontAgit 화면 세트 구현 설계 (Next.js SSG, 디자인 95% 재현)

- 작성일: 2026-07-12
- 상태: 확정 (사용자 승인)
- 원본 디자인: `docs/design/fontagit-v2/project/FontAgit 화면 세트.dc.html` (Claude Design 핸드오프 번들)
- 관련 문서: `docs/fontagit-master-plan-v3.0.md` (최종 스택 = Next.js SSG)

## 1. 목표와 범위

원본 디자인의 확정 화면 13종을 Next.js App Router 앱(`apps/web`)으로 **시각 95% 재현**한다.
공유 토대(디자인 토큰, 폰트, 레이아웃, 컴포넌트)를 먼저 만들고 그 위에 화면을 단계적으로 얹는다.
콘텐츠는 디자인과 동일한 목업 데이터를 타입 지정 파일로 두고, 나중에 파이프라인 실데이터로 교체 가능하게 필드명을 맞춘다.

### 확정된 결정 (브레인스토밍 결과)

- 결과물: 정식 Next.js 앱 (App Router, SSG). 마스터플랜 확정 스택과 일치. 폐기 없는 제품 토대.
- 범위: 확정 13화면 전체를 스펙에 포함. 구현은 4단계로 phasing.
- 데이터: 디자인 동일 목업 데이터(하드코딩, 교체 가능 구조).
- 스타일링: CSS 변수 토큰 + CSS Modules (컴포넌트별).
- 폰트: 앱에 self-host. 견본 12종은 Google Fonts 패밀리라 `next/font/google`로 자동 self-host, Pretendard는 `next/font/local` woff2.
- 인터랙션: 핵심만 동작(미리보기 입력, 캔버스 입력, 비교 선택, 다크모드 토글). 필터/검색/정렬은 목업(비동작 UI).

### 비범위 (이번 스펙에서 제외)

- 파이프라인 실데이터 연동, 백엔드/DB/검색 API.
- 필터/검색/정렬/비교의 실제 로직 동작(검색 버튼은 라우팅 없는 목업이며, 전용 검색결과 화면은 확정 세트에 없어 제외).
- 창작자 등록 폼의 서버 제출.
- 광고 네트워크 실연동(슬롯 자리만 확보).

## 2. 원본 디자인에서 확정된 사실 (근거)

- 로고: 텐트 심볼(1c 확정). 워드마크 `FontAgit`에서 `A`만 포인트색. 한글 병기 "폰트 아지트".
- 홈: 딥 그린 계열(1d 기본 추천).
- 층위 분리 원칙: 콘텐츠 층(견본/목록/상세/라이선스/검색결과)은 중립-무채색으로 폰트가 유일한 색. 브랜드 층(로고/히어로/About/404/빈상태/마이크로카피)만 아지트지기 인격.
- 견본은 실제 한글 폰트로 렌더하며 이름과 서체가 일치한다.

## 3. 디자인 토큰 (원본 스타일 가이드 10a 기준)

CSS 변수로 `styles/tokens.css`에 정의한다.

### 색 (라이트)

| 토큰 | 값 | 용도 |
|---|---|---|
| `--bg` | `#FAFAF8` | 배경(따뜻한 오프화이트) |
| `--ink` | `#1A1A1A` | 잉크/본문 |
| `--sub` | `#6B6B6B` | 서브 텍스트 |
| `--sub-2` | `#9A9A96` | 약한 서브/플레이스홀더 |
| `--border` | `#E6E6E2` | 경계선 |
| `--surface` | `#FFFFFF` | 카드 표면 |
| `--surface-2` | `#F4F4F0` | 보조 표면(푸터/광고) |
| `--point` | `#2C5545` | 포인트 딥 그린 — 액션에만 |
| `--point-weak` | `rgba(44,85,69,.1)` | 포인트 약한 배경(무료 배지 등) |

### 색 (상태)

| 토큰 | 값 | 용도 |
|---|---|---|
| `--up` | `#2C7A5B` | 상승(▲) |
| `--down` | `#B4564B` | 하락(▼) / 불가 |
| `--hold` | `#9A9A96` | 유지(—) |
| `--warn` | `#B4863C` | 조건부(!) |

### 색 (다크)

`--bg #16171A`, `--ink #EDEDEA`, `--point #7FC2A2`(톤업), 서브/경계는 다크 대응 값으로 오버라이드.

### 타이포

- UI 폰트: Pretendard (메뉴/버튼/설명은 항상 UI 폰트, 견본 폰트로 UI 렌더 금지).
- 스케일: 히어로 42 / 화면 제목 24 / 본문 15 / 캡션 12.
- 견본 폰트(Google Fonts): Black Han Sans(검은고딕), Gowun Batang(고운바탕), Nanum Myeongjo(나눔명조), Jua(주아), Do Hyeon(도현), Gowun Dodum(고운돋움), Kirang Haerang(기랑해랑), Nanum Brush Script(나눔손글씨 붓), Gaegu(개구), Song Myung(송명), Noto Sans KR(노토 산스 KR). 각각 `next/font/google`로 CSS 변수 노출.
- 폰트 로딩 전략(중요): 한글 웹폰트는 글리프가 많아 용량이 크고, 위 견본 폰트 대부분은 단일 굵기다(Black Han Sans/Jua/Do Hyeon 등). CWV(Core Web Vitals, 로딩 속도 지표) 저하를 막기 위해 (1) 전 폰트를 전역 preload 하지 않고 화면에 실제 노출되는 폰트만 로드, (2) `display: 'swap'` 적용, (3) 상세/캔버스처럼 특정 폰트가 필요한 라우트에서만 해당 폰트를 로드한다. 단일 굵기 폰트는 굵기 배열을 억지로 늘리지 않는다.

### 반경/간격

카드 radius 10-12px, 칩 radius 20px(pill), 버튼 radius 10-12px. 간격은 8의 배수 기반.

## 4. 라우트 맵 (13화면)

| 화면 | 라우트 | 핵심 구성 |
|---|---|---|
| 홈 (1d) | `/` | 헤더, 히어로(검색+필터칩), 이번주 TOP10, 추천 컬렉션, 신규 등록, 광고 슬롯 |
| 목록 (1f) | `/fonts` | 필터 바 + 폰트 카드 그리드 |
| 상세 무료 (1g) | `/fonts/[slug]` | 견본, 미리보기 입력, 굵기, 라이선스, 공식 이동 |
| 상세 유료 (6a) | `/fonts/[slug]` | 동일 라우트에서 tier=paid 분기: 구매 이동 + "비슷한 무료 대안 3개" 모듈 |
| 트렌드 (1h) | `/trends` | TOP10 확장, 주간/월간 토글 |
| 타입 캔버스 (3a) | `/playground` | 한 문장을 모든 폰트로, 딥 그린 테마, 입력 반영 |
| 비교 (5a) | `/compare` | 최대 3종 나란히, 캔버스 입력 연동 |
| 컬렉션 목록 | `/collections` | 헤더 nav '컬렉션'의 대상. 컬렉션 카드 인덱스(원본에 전용 화면 없음, 토큰/카드 재사용한 최소 화면) |
| 컬렉션 상세 (8a) | `/collections/[slug]` | 서문 + 폰트별 한 줄 코멘트 |
| 등록 (8b) | `/submit` | 창작자 등록 폼(UI만) |
| 시스템 (1i) | `not-found.tsx` + `EmptyState` | 404(아지트지기 보이스) + 빈 상태 |
| 모바일 (4a-4b-4c) | 위 라우트의 반응형 | 홈/상세/캔버스가 소형 화면에서 모바일 디자인으로 |
| 런칭자산 (7) | `app/icon.*`, `app/opengraph-image.*`, `fonts/[slug]/opengraph-image.*` | 파비콘 세트 + 기본 OG 카드(1200x630) + 폰트 상세 동적 OG(폰트명 노출, 7b) |
| 다크모드 (9b) | 전역 테마 | `data-theme` + CSS 변수 오버라이드 |

라우트 이름 규칙: 마스터플랜 URL 규칙과 정합(`/fonts`, `/trends`, `/compare`, `/playground`, `/submit`).

## 5. 폴더 구조 (`apps/web`)

```
apps/web/
  app/
    layout.tsx              루트 레이아웃(폰트 등록, 테마, 헤더/푸터)
    page.tsx                홈 (1d)
    fonts/page.tsx          목록 (1f)
    fonts/[slug]/page.tsx   상세 (1g/6a, tier 분기)
    trends/page.tsx         트렌드 (1h)
    playground/page.tsx     타입 캔버스 (3a)
    compare/page.tsx        비교 (5a)
    collections/page.tsx    컬렉션 목록
    collections/[slug]/page.tsx  컬렉션 상세 (8a)
    fonts/[slug]/opengraph-image.tsx  폰트 상세 동적 OG (7b)
    submit/page.tsx         등록 (8b)
    not-found.tsx           404 (1i)
    icon.tsx / opengraph-image.tsx  파비콘 + 기본 OG (7)
  components/
    Header.tsx  Footer.tsx  Hero.tsx
    TierChip.tsx  LicenseBadge.tsx  FilterChip.tsx  Button.tsx
    TrendRow.tsx  TrendTable.tsx  FontCard.tsx  FontGrid.tsx
    PreviewInput.tsx  Specimen.tsx  AdSlot.tsx  EmptyState.tsx
    ThemeToggle.tsx  MobileTabBar.tsx
    (각 컴포넌트에 *.module.css 동반)
  lib/fonts.ts              next/font 등록 + CSS 변수 export
  data/fonts.ts             목업 폰트 데이터
  data/collections.ts       목업 컬렉션
  data/trends.ts            목업 트렌드(주간/월간)
  types/font.ts             Font, Collection, TrendItem 타입
  styles/tokens.css         CSS 변수 토큰
  styles/globals.css        리셋 + 기본 타이포
```

## 6. 공유 컴포넌트 명세

각 컴포넌트는 단일 목적, 명확한 props 인터페이스, 독립 이해/테스트 가능해야 한다.

- `Header`: 로고(FontAgit, A만 포인트) + 한글 병기 + nav(폰트/트렌드/컬렉션/등록) + 검색 아이콘 + 테마 토글. 스크롤 시 경계선 유지.
- `Footer`: 브랜드 층. 아지트지기 톤 한 줄 + 링크.
- `Hero`: h1(42) + 서브 + 검색 박스(56px) + 검색 버튼(포인트) + 필터 칩 행.
- `TierChip`: `free`(포인트 약배경+포인트 텍스트) / `paid`(회색 배경+서브 텍스트).
- `LicenseBadge`: `yes`(체크, 포인트) / `conditional`(!, warn) / `no`(x, down). 색 단독 금지 — 아이콘+텍스트 병행(WCAG AA).
- `FilterChip`: 활성(포인트 보더+텍스트) / 비활성(경계 보더+서브). 클릭 시 시각 토글만(목업).
- `Button`: primary(포인트 배경, 흰 텍스트) / secondary(포인트 보더).
- `TrendRow`: 순위(포인트) + 변동(▲up/▼down/—hold/NEW) + 이름(견본 폰트 렌더) + 이동수 + TierChip.
- `FontCard`: 견본 글자(견본 폰트) + 이름 + 메타(파운드리/굵기/이동수) + TierChip + LicenseBadge.
- `PreviewInput`: 입력값을 견본 텍스트에 라이브 반영(핵심 인터랙션). 기본 문구 "입력해 보세요".
- `Specimen`: 상세용 대형 견본 블록. 여러 문장/크기로 렌더한다. 다굵기 폰트만 굵기별 견본을 보이고, 단일 굵기 폰트(대부분의 무료 한글 폰트)는 문장/크기 변화 견본만 보인다. `weights`는 표시용 메타값으로 실제 렌더 굵기 수와 다를 수 있다.
- `AdSlot`: 고정 높이(예: 90px) 자리, 점선 플레이스홀더. CLS 방지.
- `EmptyState`: 아이콘 + 아지트지기 보이스 카피.
- `ThemeToggle`: `data-theme` 전환(라이트/다크), 시스템 설정 초기값.
- `MobileTabBar`: 모바일 하단 탭바(홈/폰트/트렌드/등록 등).

보이스 규칙: 브랜드 층 카피는 존댓말-다정-담백(예 404 "길을 잘못 드셨어요. 아지트 입구로 모실게요."). 정보 층은 건조한 사실만(예 "상업적 사용 가능 - 확인일 2026-07-12"). "안전함/문제없음" 같은 보증 표현 금지.

## 7. 데이터 모델 (목업)

`types/font.ts`:

```ts
export type Category = '고딕' | '명조' | '손글씨' | '장식';
export type Tier = 'free' | 'paid';
export type Commercial = 'yes' | 'conditional' | 'no';
export type TrendChange = 'up' | 'down' | 'hold' | 'new';

export interface Font {
  slug: string;
  nameKo: string;
  nameEn: string;
  fontVar: string;          // 견본 렌더용 CSS 변수 (예 var(--font-jua))
  tier: Tier;
  category: Category;
  foundry: string;          // 파운드리/제작사 (예 산돌)
  weights: number;          // 굵기 수 (예 9)
  moves: number;            // 이동수 (예 3120)
  license: { commercial: Commercial; verifiedAt: string };
  officialUrl: string;
  aliases: string[];        // 한/영/오타 검색용
  freeAlternatives?: string[]; // 유료 상세의 무료 대안 slug (최대 3)
}

export interface TrendItem {
  rank: number;
  change: TrendChange;
  changeAmount?: number;
  font: Pick<Font, 'nameKo' | 'fontVar' | 'tier'>;
  moves: number;
}

export interface Collection {
  slug: string;
  title: string;
  intro: string;           // 서문(브랜드 층 보이스)
  items: { fontSlug: string; comment: string }[]; // 폰트별 한 줄 코멘트
}
```

파이프라인 `FontRecord`(`name_en`, `name_ko`, `tier`, `category`, `official_url`, `aliases`, `license_verified` 등)와 필드명을 최대한 맞춰 나중 교체 비용을 낮춘다.

목업 데이터는 디자인에 등장하는 실제 폰트로 채운다: 프리텐다드, 노토 산스 KR, 검은고딕, 배민 주아, 고운바탕, 나눔명조, 배민 도현, 고운돋움, 기랑해랑, 나눔손글씨 붓, 개구체, 송명체 등.

## 8. 반응형 - 인터랙션 - 다크모드

- 반응형: 데스크톱 라우트가 소형 화면에서 모바일 디자인(4a/4b/4c)으로 접힌다. 상세는 미리보기 입력을 하단 고정, 하단 탭바 노출, 필터는 시트로 접어 화면을 견본에 양보. 브레이크포인트는 원본 모바일 프레임 폭 기준으로 설정.
- 인터랙션(핵심만): 미리보기 입력 라이브 반영, 타입 캔버스 입력, 비교 폰트 선택, 다크모드 토글. 이들은 클라이언트 컴포넌트로 최소 상태만. 필터/검색/정렬/비교 로직은 비동작 UI.
- 다크모드: `<html data-theme>` + `styles/tokens.css`의 다크 오버라이드. `prefers-color-scheme` 초기값 + 헤더 토글. 다크 홈은 포인트 톤업(#7FC2A2). SSG라 초기 테마가 늦게 적용되면 잘못된 테마가 깜빡이므로(FOUC), `layout.tsx`에 페인트 전 `data-theme`를 설정하는 인라인 스크립트를 넣어 하이드레이션 불일치를 막는다.

## 9. 검증

- 렌더 스모크: Playwright로 각 라우트 로드 + 콘솔 에러 0 확인.
- 시각 대조: 데스크톱/모바일 뷰포트 스크린샷 대조(95% 목표). 원본 `.dc.html`은 dc-runtime이 있어야 렌더되므로 기준선은 (1) 최초 1회 원본을 브라우저로 렌더해 확보한 참조 스크린샷, 또는 (2) 원본 소스에서 추출한 토큰/레이아웃 값과의 1:1 대조로 삼는다.
- 단위 테스트: 분기 로직 위주 — `LicenseBadge`(3상태), 상세 tier 분기(무료 vs 유료+대안 모듈), 트렌드 변동 표시. 로직 없는 순수 마크업 컴포넌트는 스냅샷 최소.
- CWV: 폰트 `display: swap`, 광고 슬롯 고정 높이(CLS 0 지향), SSG 정적 출력 확인.

## 10. 구현 단계 (플랜에서 태스크로 분해)

1. 토대: `apps/web` 스캐폴드(Next.js App Router, TypeScript, 정적 출력). 패키지명은 기존 `pnpm --filter web` 및 `web:dev`/`web:build` 스크립트와 맞추기 위해 반드시 `web`로 한다. 정적 출력은 `output: 'export'`(또는 SSG 빌드)로 하고, 동적 라우트(`[slug]`)는 `generateStaticParams`로 사전 생성하며 동적 OG 이미지도 빌드 시 생성한다. 이어서 토큰 + 폰트 등록 + 루트 레이아웃 + Header/Footer + 원자 컴포넌트(Chip/Badge/Button).
2. 핵심: 홈(1d) → 목록(1f) → 상세 무료/유료(1g/6a) → 트렌드(1h).
3. 확장: 캔버스(3a) → 비교(5a) → 컬렉션(8a) → 등록(8b) → 시스템(1i, 404/빈상태).
4. 마감: 모바일 반응형(4a/4b/4c) → 다크모드(9b) → 런칭자산(파비콘/OG, 7).

## 11. 리스크와 대응

- 폰트 라이선스: 견본 렌더용 웹폰트 임베딩은 대부분 무료 한글 폰트가 허용하나, 실서비스 전 각 폰트 웹 사용 조건 재확인 필요(이번 스펙은 목업 재현 단계).
- Pretendard woff2 확보: 변수 폰트(Pretendard Variable) woff2를 로컬 포함. 없으면 초기 세팅에서 다운로드 단계 필요.
- 95% 판정 주관성: "동일" 기준을 픽셀 대조 스크린샷으로 객관화. 토큰 값-간격-폰트 매핑을 원본과 1:1로 맞춘다.
- 범위 과대: 13화면 전체는 크다. 단계별 vertical slice로 각 단계 완료 기준을 명확히(플랜에서 태스크 분해).
