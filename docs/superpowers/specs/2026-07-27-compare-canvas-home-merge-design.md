# 홈 비교-캔버스 통합 보드 설계 (#118)

- 작성일: 2026-07-27
- 이슈: [#118 캔버스 화면과 비교 화면 기능 통합 및 최적화하기](https://github.com/jojo3420/fontagit/issues/118)
- 관련: #69(플레이그라운드 캔버스 편집기 — 본 작업과 별개, /playground 라우트를 향후 재사용)

## 배경

현재 폰트를 "써보는" 기능이 두 곳에 나뉘어 있다.

- `/playground` 타입 캔버스: 입력 문구를 대표 폰트(Pretendard 96px 고정) + 무료 폰트 8종 그리드에 뿌려줌. 폰트 교체 불가.
- 홈 하단 `/#compare` 폰트 비교 섹션(CompareBoard): 셀렉트 박스 3개로 폰트를 골라 나란히 비교.

두 기능을 하나로 합쳐 홈("/")에서만 노출하고, `/playground`는 향후 #69(진짜 캔버스 편집기)를 위해 비운다.

## 확정된 결정 사항

| 항목 | 결정 |
|------|------|
| 통합 화면 위치 | 홈("/") 기존 비교 섹션 자리. 별도 라우트 없음 |
| /playground 라우트 | 삭제 + Cloudflare `_redirects`로 `/` 302 리다이렉트(#69에서 라우트 재사용 예정이라 301 영구 캐시 회피) |
| 네비게이션 | Header-MobileTabBar의 "캔버스"/"비교" 항목 모두 제거 |
| 폰트 후보 범위 | 정적 등록된 무료 9종(next/font 로드분)만. 확장은 별도 이슈 |
| 대표 견본 영역 | 유지 + 셀렉트 추가(기본 Pretendard, 96px) |
| 견본 문구 기본값 | "다람쥐 헌 쳇바퀴에 타고파 1234 !@#$" (통합 보드에만 적용) |
| 구현 방식 | 신규 컴포넌트 `CompareCanvas` 작성, PlaygroundCanvas-CompareBoard 폐기 |

## 비목표 (이번 범위 아님)

- 캔버스 편집기(텍스트 박스-도형-내보내기) 구현 → #69
- 셀렉트 후보를 Tier A 등 웹폰트 로드 가능 전체로 확장
- 사이트 전역 견본 문구(getSpecimenText 등) 교체
- 홈 Hero-주간랭킹 개편

## 설계

### 1. 신규 컴포넌트 `components/CompareCanvas.tsx` (client)

상태:

- `text: string` — 견본 문구. 기본값 `"다람쥐 헌 쳇바퀴에 타고파 1234 !@#$"`
- `heroSlug: string` — 대표 폰트. 기본값 `"pretendard"`
- `gridSlugs: string[]` — 8칸 폰트. 기본값은 무료 9종 중 대표를 제외한 8종

UI 구성(위→아래):

1. 제목 "폰트 비교" + 부제(같은 문장으로 나란히 놓고 결정하라는 안내)
2. 입력 바: 입력창 + 지우기 버튼 + 프리셋 버튼 4개. 프리셋은 `["다람쥐 헌 쳇바퀴에 타고파 1234 !@#$", "당신의 폰트 아지트", "가나다라 ABC 0123", "The quick brown fox"]` — 기존 캔버스 프리셋의 첫 항목을 기본 문구로 대체
3. 대표 영역: 셀렉트 + TierChip + 상세 링크 + 96px 견본
4. 8칸 그리드: 칸마다 셀렉트 + TierChip + 상세 링크(`/fonts/{slug}`) + 견본

규칙:

- 셀렉트 후보는 `data/fonts.ts`의 `tier === "free"` 9종 전부(대표-그리드 동일 후보). 이 목록은 `lib/fonts.ts`의 next/font 로딩과 쌍으로 관리되는 기존 패턴(기존 CompareBoard OPTIONS와 동일 필터)
- 폰트 적용은 기존 유틸 `familyOf(fontKey)` 재사용(next/font CSS 변수 → `style={{ fontFamily }}`)
- 같은 폰트 중복 선택 허용(방지 로직 없음 — 단순성 우선)
- CompareBoard의 긴 고정 샘플 문단(getSpecimenText)은 넣지 않음(8칸이라 과중)
- 빈 문구(지우기 포함)면 placeholder 문구로 견본 표시(기존 캔버스 동작 계승). 긴 문장은 줄바꿈 + `overflow-wrap`으로 처리
- slug 조회 실패 시 해당 칸 렌더 스킵 가드 — 후보와 slug가 같은 정적 배열이라 실제 발생 경로는 없으며 TS 타입 안전용
- 접근성: 기존 aria-label 패턴 계승(문장 입력, N번 폰트 선택, 지우기 버튼)
- 스타일은 `CompareCanvas.module.css` 신규(PlaygroundCanvas 스타일과 반응형 브레이크포인트 계승-정리, 모바일에서 대표 견본 크기 축소 유지)

### 2. 홈 반영 `app/page.tsx`

- 기존 비교 섹션 자리에서 `CompareLazy`(IntersectionObserver 지연 로딩)가 `CompareBoard` 대신 `CompareCanvas`를 로드하도록 교체
- 섹션 `id="compare"` 유지: 네비 항목은 없어지지만 이미 퍼진 `/#compare` 딥링크가 새 보드로 도착하게 함

### 3. 제거 목록

- `app/playground/` 디렉터리(page.tsx, page.module.css)
- `components/PlaygroundCanvas.tsx` + `.module.css`
- `components/CompareBoard.tsx` + `.module.css`
- `app/sitemap.ts`의 `"/playground/"` 항목
- `components/Header.tsx`의 "캔버스"(/playground)-"비교"(/#compare) 링크 2개
- `components/MobileTabBar.tsx`의 "캔버스"-"비교" 탭 2개

유지: `components/TypeCanvasBar.tsx`(/fonts 섹션 전용, 무관), `lib/specimen`(다른 사용처 유지)

### 4. 리다이렉트 `public/_redirects` (신규)

```
/playground/ / 302
/playground / 302
```

output: "export"라 서버 라우트가 없으므로 Cloudflare Pages의 `_redirects` 정적 파일 방식 사용. public/에 두면 빌드 산출물(out/) 루트로 복사된다. 302인 이유: #69에서 /playground를 캔버스 편집기로 재사용할 예정이라 301의 브라우저 영구 캐시를 피한다.

검증: 로컬 Next 빌드는 `_redirects`를 처리하지 않는다. (1) 빌드 후 `out/_redirects` 존재 확인 (2) 배포 후 `curl -I https://fontagit.com/playground/`로 상태 코드 302와 Location 헤더 확인.

### 5. 테스트

- `CompareCanvas.test.tsx` 신규(핵심 2케이스만): 기본 문구 렌더, 셀렉트 변경 시 fontFamily 반영
- `CompareLazy.test.tsx` 갱신(로드 대상 교체)
- 삭제 컴포넌트의 테스트 파일 정리, `app/page.test.tsx`-sitemap 테스트 영향 확인
- 검증: `npm test` + `npm run build`(정적 export 그린) + 실제 브라우저에서 홈 보드-리다이렉트 확인

## 완료 조건

- [ ] 홈 비교 섹션 자리에서 통합 보드가 지연 로드되고 `/#compare` 딥링크로 도착한다
- [ ] 대표 + 8칸 모두 셀렉트로 폰트를 바꾸면 견본에 즉시 반영된다
- [ ] 기본 문구가 "다람쥐 헌 쳇바퀴에 타고파 1234 !@#$"로 표시된다
- [ ] 네비(Header-MobileTabBar)에 캔버스-비교 항목이 없다
- [ ] 코드-sitemap에서 /playground 참조가 0건이다(최종 grep)
- [ ] `npm test`-`npm run build` 그린, `out/_redirects` 존재
- [ ] 배포 후 /playground가 302로 홈 이동, 데스크톱-모바일 실화면 확인

## 영향 범위-리스크

- 홈 초기 로딩: 보드는 뷰포트 진입 시 지연 로드라 기존과 동일 수준. 8종 견본 렌더는 기존 /playground와 동일 부하
- SEO: /playground 색인 제거는 301 + sitemap 제거로 자연 처리. 홈은 콘텐츠 증가로 영향 없음
- 회귀 위험: 네비 4곳 제거로 인한 레이아웃 어긋남 → Header-MobileTabBar 스냅샷-실화면 확인 필요
- 브랜치: 기능 PR base는 develop(최근 PR #121-#113-#112 실증, main은 release 전용). 구현은 최신 origin/develop 기준 새 브랜치(feature/118-*)에서 진행
- ⚠️ #117은 이미 PR #121로 develop에 머지됨. 워킹트리의 미커밋 변경(Header-HeaderSearch 등)은 잔재일 가능성이 높아 구현 전 origin/develop과 diff 대조 후 정리(폐기 또는 stash)가 선행 조건
