# 플레이그라운드 캔버스 편집기 설계 (Playground Canvas Editor)

- 날짜: 2026-07-18 (리뷰 보강: 같은 날 deep-reasoner 적대적 리뷰 + Codex 교차 리뷰 반영, `docs/review/review-result-20260718-081437.md`)
- 상태: 조건부 승인 — 선행 의존성(FontPicker 정책 함수) 해결을 구현 계획 Slice 0으로 포함해야 착수 가능
- 목표: `/playground`에 텍스트 중심 디자인 캔버스를 제공해 무료 폰트를 설치 없이 굴려보게 하고, 폰트 탐색→선택(다운로드) 전환을 높인다.

## 배경과 범위 결정

- 피그마 수준 벡터 편집(펜 툴-패스-불리언)은 범위 외. 텍스트 배치 중심 캔버스로 확정.
- 이미지 업로드 포함(브라우저 메모리 한정, 서버 업로드 없음).
- 저장 기능 미제공. PNG/PDF 내보내기만 제공.
- 1순위 성공 기준: 폰트 탐색→선택 전환. 편집기는 퍼널 수단이다.
- 지원 범위: 데스크톱 우선. 모바일은 보기 + 터치 이동 수준의 축소 경험(⚠️ Fabric v6 터치 제스처 지원 범위는 구현 계획에서 검증).

## 엔진 선택: Fabric.js

- 비교: Fabric.js(채택) vs react-konva(텍스트 인라인 편집 직접 구현 필요, 공수 1.5~2배) vs DOM 자체 구현(핸들-내보내기 수작업).
- 상용 SDK 배제 근거(2026-07-18 확인): tldraw 4.x는 상용 무료 사용 불가, Polotno는 월 $899.
- Fabric.js v6: MIT, TypeScript 내장, IText 인라인 편집, 객체 이동/회전/크기조절, PNG 내보내기 내장. gzip 약 80~100KB. undo/redo는 내장이 아니므로 직접 구현한다(아래 편집 기능).
- 제약: `/playground` 진입 시에만 동적 로드(dynamic import, SSR 제외)해 타 페이지 번들에 영향 금지.

## 아키텍처

- 기존 `PlaygroundCanvas`(플레이스홀더 55줄)를 새 편집기로 대체. `GlyphCheckerSection`은 유지.
- 정적 export(output: 'export') 구조 유지 — 서버 라우트-DB 변경 없음.
- 편집 상태의 SSoT는 Fabric 캔버스 객체 트리. React UI(패널-툴바)는 Fabric 이벤트(`selection:created` 등) 구독으로 동기화.
- 편집기 트리는 "use client" 경계 안에서만 동작. `CanvasStage`는 마운트 시 초기화, 언마운트 시 `canvas.dispose()` cleanup — React 19 StrictMode 이중 마운트에서도 캔버스-이벤트가 중복 생성되지 않아야 한다.
- 이탈 보호: 편집 내용이 있으면 `beforeunload` 경고 + 내부 라우팅 이동 시 확인 1회.

## 컴포넌트 (단일 책임)

| 컴포넌트 | 책임 |
|---|---|
| `CanvasStage` | Fabric 캔버스 초기화-이벤트 바인딩-dispose, 줌-화면 맞춤 |
| `EditorToolbar` | 텍스트/도형(사각형-원-선)/이미지 추가, undo-redo, 삭제-복제, 앞뒤 순서 |
| `FontPicker` | 렌더링 가능 폰트만 노출(self-host + Google Tier A), 검색, 폰트별 라이선스 확인 링크 |
| `PropertiesPanel` | 선택 객체 속성 편집(크기-색-자간-행간-정렬-불투명도, 텍스트는 weight 선택 포함) |
| `ExportMenu` | PNG/PDF 내보내기, 해상도 규칙과 라이선스 고지 표시 |
| `FontFunnelCta` | 선택 텍스트의 폰트 → 폰트 상세/다운로드 링크 (전환 퍼널 핵심) |

### 선행 의존성 (Slice 0)

`FontPicker`의 "렌더링 가능 폰트" 판별은 Tier A 동적 프리뷰 계획(`docs/superpowers/plans/2026-07-18-tier-a-dynamic-font-preview.md`)의 `resolveFontPreview` 정책 함수를 재사용한다. 2026-07-18 현재 미구현이므로, 해당 계획을 먼저 실행하거나 본 기능 구현 계획의 Slice 0으로 정책 함수(Task 1 범위)만 선행 구현한다. 이 결정 없이는 착수 불가.

## 편집 기능 최소선

- undo/redo: 캔버스 JSON 스냅샷 스택으로 직접 구현(깊이 30), 단축키 Cmd/Ctrl+Z, Shift+Cmd/Ctrl+Z.
- 키보드: Delete/Backspace 삭제, 방향키 1px 이동(Shift 10px), Cmd/Ctrl+D 복제.
- 레이어 순서: 선택 객체 "앞으로/뒤로" 버튼(레이어 패널은 비범위).
- 뷰포트: 캔버스 프리셋을 화면에 맞춤(fit) 후 25~200% 줌. 캔버스 논리 크기와 표시 배율 분리.

## 데이터 흐름

1. 폰트 목록: 기존 폰트 데이터 + tier 정책으로 "웹 렌더링 가능" 폰트만 필터. 눈누 Tier B는 웹폰트 파일이 없어 대상 외.
2. 폰트 적용 대상: 선택된 텍스트 객체. 선택이 없으면 이후 추가되는 텍스트의 기본값으로 설정.
3. 폰트 로딩 규칙: CSS2 stylesheet 주입(중복 URL 1회) → `document.fonts.load` 완료 대기(타임아웃 5초) → 대상 객체 fontFamily 반영 + 치수 재계산(`initDimensions`, `setCoords`) → `requestRenderAll()`. 요청 세대 토큰으로 마지막 선택만 반영(연속 클릭 경쟁 조건 방지). 로딩 전-실패 시 Pretendard 폴백 + 안내.
4. 굵기-스타일: 해당 폰트의 `availableWeights`에 있는 weight만 UI에 노출-요청. italic 축은 비범위.
5. 이미지: 로컬 파일 → FileReader dataURL → `fabric.Image`. 서버 전송 없음.
6. 내보내기: PNG는 `toDataURL({multiplier})`. PDF는 한글 폰트 임베드 문제를 피해 PNG 래스터를 단일 페이지에 삽입(jsPDF `addImage`, 페이지 크기 = 캔버스 비율, 배경 흰색, 파일명 `fontagit-{프리셋}-{YYYYMMDD}.{ext}`).

## 내보내기-메모리 안정성

- 최대 출력 픽셀 캡 16M(약 4096x4096 상당). multiplier = min(2, 캡/캔버스 픽셀의 제곱근), 모바일(터치-저사양)은 1배 고정. 축소 적용 시 사용자에게 표시.
- 이미지 업로드: 형식 png/jpg/webp, 파일 10MB, 원본 총 픽셀 4096x4096 초과 시 리사이즈 후 배치.
- PDF는 래스터(이미지형)임을 내보내기 메뉴에 고지: "확대-인쇄 품질 제한".

## 라이선스 고지 (신뢰 장치)

- 무료 폰트도 이미지 제작-임베드 허용 범위가 폰트별로 다르다. FontPicker 각 항목에서 폰트 상세(라이선스 정보)로 이동 가능해야 하고, 내보내기 시 "사용한 폰트의 라이선스 조건을 확인하세요" 1줄 + 사용 폰트 목록-상세 링크를 표시한다.

## 에러 처리-경계 검증

- 폰트 로드 실패-타임아웃: 폴백 유지 + 사용자 안내(토스트).
- 이미지 형식-크기-픽셀 위반: 업로드 거부 + 사유 안내.
- 내보내기 실패: 오류 안내 + 재시도.
- 캔버스 프리셋: 유튜브 썸네일 1280x720, 채널아트 2560x1440, SNS 정사각 1080x1080, 자유 크기(최대 4096x4096).

## 성공 지표 계측 (GA4)

- `playground_font_selected` (폰트 적용, 파라미터: font_id)
- `playground_font_cta_clicked` (편집기 → 폰트 상세 이동)
- `font_download_clicked` 기존 이벤트와 연결해 퍼널 완성: 적용 → 상세 → 다운로드.
- CTA 노출 규칙: 단일 텍스트 객체 선택 시 해당 폰트의 상세 링크 표시, 다중-도형 선택 시 숨김.

## 테스트

- vitest 단위: 폰트 로딩 정책(세대 토큰-타임아웃), 이미지 검증, multiplier 계산, export 유틸 (Fabric 의존 컴포넌트는 mock).
- Playwright 2개: (1) 텍스트 추가 → 폰트 적용 → PNG 내보내기, (2) 폰트 적용 → CTA 클릭 → 폰트 상세 도달(전환 여정).
- env 주의: db import 컴포넌트 테스트는 db 모듈 mock 필수(기존 관례).
- 배포 후 스모크: 운영에서 fonts.googleapis.com 로드, PNG/PDF 다운로드, CTA 이동 확인(CSP 부재는 2026-07-18 확인됨 — 추후 CSP 도입 시 style-src/font-src 허용 필요).

## 공수 추정

- vertical slice 8~10개(Slice 0 선행 의존 포함), 최근 검색 자동완성 기능의 2.5~3배 규모.

## 비범위 (YAGNI)

- 저장/불러오기, 계정, 협업, 벡터 패스 편집, italic 축, 레이어 패널, 서버 업로드, 템플릿 마켓.
