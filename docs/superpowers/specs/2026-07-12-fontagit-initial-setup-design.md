# FontAgit 초기 세팅 설계

> 작성일: 2026-07-12 | 기반: `docs/fontagit-master-plan-v3.0.md`
> 범위: 저장소 뼈대(모노레포) + Tier A 구글폰트 수집 스크립트(동작). 인프라 연결 없음(로컬 스캐폴드).

## 1. 목표와 비목표

목표
- 모노레포 뼈대: `apps/web`(Next.js 스캐폴드) + `apps/pipeline`(Python).
- **동작하는 Tier A 수집 스크립트**: 구글폰트 Developer API에서 한글 지원 폰트 전체 + 라틴 인기 100개를 수집해 로컬 JSON으로 출력.
- 수집 결과는 나중에 Supabase 업로드에 쓸 중간 산출물(로컬 파일).

비목표(이번 세션 제외)
- 실제 Supabase/오라클 VM 연결, 스키마 실행.
- web의 실제 기능 페이지(검색-상세-컬렉션-Top10). 홈 뼈대만.
- Tier B/C 크롤링, 이미지 생성, 링크 점검.

## 2. 결정 사항 (확정)

| 항목 | 결정 | 근거 |
|---|---|---|
| 저장소 | 모노레포(web + pipeline) | 기획 3층 구조와 정합, 관리 일원화 |
| 이번 산출물 | 뼈대 + Tier A 수집 스크립트 | 데이터 시드(S1) 착수 |
| 인프라 | 로컬 스캐폴드만 | 위험 0으로 기반부터 |
| 수집 소스 | 구글폰트 Developer API(키 필요) | subsets(korean)/variants/files 풍부, 기획 "자동 수집"과 일치 |
| API 키 | `.env`의 `GOOGLE_FONTS_API_KEY`로 분리 | 시크릿 하드코딩 금지 |

## 3. 저장소 구조

```
fontagit/
├── apps/
│   ├── web/                          # Next.js(App Router) + TS + Tailwind
│   │   └── (홈 뼈대만, 기능 페이지 없음)
│   └── pipeline/
│       ├── src/fontagit_pipeline/
│       │   ├── config.py             # pydantic-settings, .env 키 로드
│       │   ├── client.py             # httpx 구글폰트 webfonts API 호출
│       │   ├── models.py             # GoogleFontRaw(API 원형) + FontRecord(정규화)
│       │   ├── transform.py          # 필터(한글 전체 + 라틴 100) + 별칭 생성
│       │   ├── writer.py             # JSON 출력
│       │   └── __main__.py           # 오케스트레이션 + logging
│       ├── tests/
│       │   └── fixtures/             # API 응답 샘플 JSON
│       ├── output/                   # tier-a.json (gitignore)
│       └── pyproject.toml
├── docs/                             # 기존 기획서 + 스펙
├── pnpm-workspace.yaml               # packages: ['apps/web']
├── package.json                      # 루트, web 스크립트
├── Makefile                          # web/pipeline 공통 명령
├── .env.example                      # GOOGLE_FONTS_API_KEY=
└── .gitignore                        # 기존 Python + Node 추가
```

## 4. 파이프라인 설계 (동작 핵심)

SRP 기준 모듈 분리. 조회/변환/쓰기를 분리해 순수 로직만 단독 테스트.

- `config`: `pydantic-settings`로 `.env`에서 `GOOGLE_FONTS_API_KEY` 로드. 없으면 명확한 에러 메시지 후 종료.
- `client`: `httpx`로 `GET https://www.googleapis.com/webfonts/v1/webfonts?key=…&sort=popularity`. 반환 원형 그대로.
- `models`(pydantic):
  - `GoogleFontRaw`: family, variants[], subsets[], version, lastModified, files{variant:url}, category, menu.
  - `FontRecord`(우리 스키마, 미래 `fonts` 테이블 미러): name_en, name_ko(nullable), tier="A", category, subsets[], variants[], official_url, license, license_verified, aliases[], version, last_modified.
- `transform`:
  - 필터: `korean` subset 포함 폰트 전부 + `latin` 포함 폰트 인기 상위 100.
  - 매핑: `official_url`은 `https://fonts.google.com/specimen/<Family>` 형태(Family의 공백은 `+`로 치환).
  - 별칭: [family, 소문자, 공백제거, "family ttf"] 정도의 기본 세트.
- `writer`: `output/tier-a.json`에 레코드 배열 저장(UTF-8, 들여쓰기).
- `__main__`: 조회, 필터, 변환, 저장을 순서대로 실행하며 각 단계를 `logging`으로 남긴다(print 금지).

정직성/법적 안전선(기획 9장 반영)
- 구글 API는 라이선스를 주지 않음 → `license="OFL", license_verified=false`로 표기. "AI 초안-사람 검수" 원칙과 일치.
- `files`의 TTF URL은 참조만. **재호스팅-변환-자체 CDN 금지**. 다운로드 링크는 공식 specimen 페이지로만.

출력 예 (`tier-a.json` 한 항목)
```json
{
  "name_en": "Noto Sans KR",
  "name_ko": null,
  "tier": "A",
  "category": "sans-serif",
  "subsets": ["korean", "latin"],
  "variants": ["100", "300", "400", "500", "700", "900"],
  "official_url": "https://fonts.google.com/specimen/Noto+Sans+KR",
  "license": "OFL",
  "license_verified": false,
  "aliases": ["Noto Sans KR", "noto sans kr", "notosanskr", "Noto Sans KR ttf"],
  "version": "v36",
  "last_modified": "2024-09-01"
}
```

## 5. web 스캐폴드 (뼈대만)

- Next.js 15 App Router + TypeScript + Tailwind CSS.
- 테마 토큰: 포인트 딥 그린 `#2C5545`, 다크모드 활성.
- UI 폰트 Pretendard 설정(견본 폰트와 분리 원칙 반영).
- 홈 라우트 하나(placeholder). 검색-상세-컬렉션-Top10 등 기능 페이지 없음.

## 6. 툴링

- Python: `uv`(환경-패키지) + `ruff`(lint/format) + `mypy`(타입) + `pytest`.
- Web: `pnpm` + Next.js 15 + Tailwind.
- 공통: 루트 `Makefile` 타깃 — `make web-dev`, `make collect`(파이프라인 수집), `make test`, `make lint`.

## 7. 검증

- 단위 테스트(pytest, 픽스처 기반, 5개 이내): 한글 subset 필터, 라틴 상위 100 절단, 별칭 생성, `official_url` 매핑, 라이선스 미검증 플래그.
- 통합(수동): 무료 API 키를 `.env`에 넣고 `make collect` → `output/tier-a.json`에 130여 개 레코드가 필수 필드 100%로 생성되는지 확인.
- lint/type: `make lint`, `mypy` 통과.

## 8. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| API 키 미보유로 통합 검증 지연 | 단위 테스트로 로직 검증, 키 확보 후 통합 실행 |
| 라틴 "인기 100" 기준 모호 | API `sort=popularity` 순서 사용, 라틴 포함 상위 100 절단 |
| 라이선스 부정확 | `license_verified=false`로 표기, 공개 전 사람 검수(기획 원칙) |
| 혼합 모노레포 명령 혼선 | `Makefile`로 web/pipeline 명령 일원화 |

## 9. 다음 단계

이 스펙을 승인하면 `writing-plans` 스킬로 구현 계획을 작성하고, 이어서 구현으로 넘어간다(구현은 오케스트레이션 위임).
