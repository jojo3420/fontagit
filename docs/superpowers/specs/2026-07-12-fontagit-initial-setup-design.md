# FontAgit 초기 세팅 설계

> 작성일: 2026-07-12 | 기반: `docs/fontagit-master-plan-v3.0.md`
> 범위: 저장소 뼈대(모노레포) + Tier A 구글폰트 수집 스크립트(동작). 인프라 연결 없음(로컬 스캐폴드).
> 개정: 2026-07-12 Codex 리뷰(`docs/review/review-result-20260712-193250.md`) 반영 — 라이선스 기본값, 중복 제거, 오류 처리, 출력 계약 등 보강.

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
| 라이선스 기본값 | 검증 전 `license=null`, `license_verified=false` | API가 라이선스 미제공. 단정하면 허위(기획 9장 위반) |

### 기획서 추적성 (요약)

| 이번 설계 항목 | 마스터 기획 근거 |
|---|---|
| Tier A API 자동 수집 | 4장 Tier A(구글폰트 OFL, API 자동 수집) |
| 링크만-재호스팅 금지 | 9장 법적 안전선 2-4항 |
| 라이선스 검증 전 비공개 | 9장 8항, 2장 "AI 초안 사람 검수" |
| 별칭(alias) 데이터 | 6장 검색 설계, F-04 |
| 모노레포 3층 대응 | 12장 인프라(로컬/VM1/VM2) |

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
│       │   ├── transform.py          # 필터(한글 전체 + 라틴 100) + dedup + 별칭
│       │   ├── writer.py             # JSON 원자적 저장
│       │   └── __main__.py           # 오케스트레이션 + logging + 종료 코드
│       ├── tests/
│       │   └── fixtures/             # API 응답 샘플 JSON
│       ├── output/                   # tier-a.json (gitignore)
│       └── pyproject.toml
├── docs/                             # 기존 기획서 + 스펙 + 리뷰
├── pnpm-workspace.yaml               # packages: ['apps/web']
├── package.json                      # 루트, web 스크립트
├── Makefile                          # web/pipeline 공통 명령
├── .env.example                      # GOOGLE_FONTS_API_KEY=
├── .tool-versions 또는 .nvmrc        # Node 버전 고정
└── .gitignore                        # 기존 Python + Node 추가
```

## 4. 파이프라인 설계 (동작 핵심)

SRP 기준 모듈 분리. 조회/변환/쓰기를 분리해 순수 로직만 단독 테스트.

### 4-1. 모듈
- `config`: `pydantic-settings`로 `.env`에서 `GOOGLE_FONTS_API_KEY` 로드. 없으면 명확한 메시지 후 종료 코드 2. `.env`는 **`apps/pipeline` 기준 경로**에서 로드(실행 위치 고정).
- `client`: `httpx`로 webfonts API 호출. 타임아웃(연결/읽기 각 10초), 제한 재시도(최대 2회, 지수 백오프). 요청 URL 전체를 로그에 남기지 않고 **키는 마스킹**(`key=***`).
- `models`(pydantic):
  - `GoogleFontRaw`: family, variants[], subsets[], version, lastModified, files{variant:url}, category, menu.
  - `FontRecord`(우리 스키마, 미래 `fonts` 테이블 미러): name_en, name_ko(nullable), tier="A", category, subsets[], variants[], official_url, license(nullable), license_verified, aliases[], version, last_modified.
- `transform`: 필터-정규화-중복 제거-별칭 생성(4-2, 4-3).
- `writer`: 임시 파일에 쓴 뒤 성공 시 `output/tier-a.json`으로 원자적 교체(rename). UTF-8, 들여쓰기.
- `__main__`: 조회, 필터, 변환, 저장을 순서대로 실행하며 각 단계를 `logging`으로 남긴다(print 금지). 네트워크-JSON 파싱-저장 실패 시 로그 + 비정상 종료 코드.

### 4-2. 수집 알고리즘 (고정)
1. `sort=popularity`로 전체 목록 1회 조회(webfonts는 페이지네이션 없이 단일 응답).
2. `subsets`에 `korean` 포함 폰트 **전부** 추출.
3. `subsets`에 `latin` 포함 폰트를 인기순으로 **위에서부터 100개** 추출.
4. 두 집합을 **`family` 키로 합집합(dedup)**. 한글 폰트가 라틴 100에도 들면 1건으로 병합. 순서는 한글 집합 먼저, 그다음 라틴에서 새로 추가된 것.

### 4-3. 정규화-매핑 규칙
- `variants`: `regular`는 `400`, `italic`은 `400 italic` 식으로 숫자 weight + italic 플래그로 정규화.
- `official_url`: `https://fonts.google.com/specimen/<Family>` 형태, **공백만 `+`로 치환**(구글 규칙, 퍼센트 인코딩 금지). family가 비ASCII면 로그 남기고 건너뛴다.
- `aliases`: `[family, 소문자, 공백제거, "family ttf"]`를 생성 후 소문자 기준 중복 제거, 삽입 순서 유지. `name_ko`가 있으면 그 파생형도 추가(Tier A는 대부분 없음).
- 라이선스: `license=null`, `license_verified=false`. 실제 라이선스는 이후 사람 검수 또는 google/fonts 메타데이터로 채운다. **검증 전에는 공개하지 않는다.**
- `files`의 TTF URL은 참조만. **재호스팅-변환-자체 CDN 금지**. 다운로드 링크는 공식 specimen 페이지로만.

### 4-4. 출력 계약 (`tier-a.json`)
배열이 아니라 메타 포함 객체로 저장(출처-생성 시점 추적).
```json
{
  "schema_version": 1,
  "generated_at": "2026-07-12T10:00:00Z",
  "source": "google-fonts-webfonts-api",
  "record_count": 137,
  "fonts": [
    {
      "name_en": "Noto Sans KR",
      "name_ko": null,
      "tier": "A",
      "category": "sans-serif",
      "subsets": ["korean", "latin"],
      "variants": ["100", "300", "400", "500", "700", "900"],
      "official_url": "https://fonts.google.com/specimen/Noto+Sans+KR",
      "license": null,
      "license_verified": false,
      "aliases": ["Noto Sans KR", "noto sans kr", "notosanskr", "Noto Sans KR ttf"],
      "version": "v36",
      "last_modified": "2024-09-01"
    }
  ]
}
```

## 5. web 스캐폴드 (뼈대만)

- Next.js 15 App Router + TypeScript + Tailwind CSS.
- 테마 토큰: 포인트 딥 그린 `#2C5545`, 다크모드 활성.
- UI 폰트 Pretendard: **npm 패키지(`pretendard`)로 self-host**(외부 CDN 아님). 이 비호스팅 원칙은 "아카이브 대상 폰트"에 적용되는 규칙이고, UI 크롬 폰트는 별개다.
- 홈 라우트 하나(placeholder). 검색-상세-컬렉션-Top10 등 기능 페이지 없음.

## 6. 툴링-환경 재현성

- Python: `uv`(환경-패키지) + `ruff`(lint/format) + `mypy`(타입) + `pytest`. HTTP는 httpx, 설정은 pydantic-settings.
- Web: `pnpm` + Next.js 15 + Tailwind.
- 버전 고정: Python은 `pyproject.toml`의 `requires-python`, Node는 `.nvmrc`/`.tool-versions`, pnpm은 `packageManager` 필드. 잠금 파일 `uv.lock`-`pnpm-lock.yaml`을 커밋한다.
- 공통: 루트 `Makefile` 타깃 — `make web-dev`, `make collect`(파이프라인 수집), `make test`, `make lint`. 각 타깃은 올바른 작업 디렉터리로 진입해 실행한다.

## 7. 검증

- 단위 테스트(pytest, 픽스처 기반): 핵심 로직 위주로 함수당 성공 1개 + 치명 예외 1~2개. 대상 — 한글 subset 필터, 라틴 상위 100 절단, family dedup(교집합 병합), variants 정규화, 별칭 중복 제거. 사소한 URL 문자열 조립은 별도 테스트 생략.
- 통합(수동): 무료 API 키를 `.env`에 넣고 `make collect` 실행. **고정 개수 대신 조건으로 검증** — 한글 폰트 전체 포함, 라틴 선택 결과 100개, family 중복 없음, `license=null`, 필수 필드 100%.
- lint/type: `make lint`, `mypy` 통과.

## 8. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| API 키 미보유로 통합 검증 지연 | 단위 테스트로 로직 검증, 키 확보 후 통합 실행 |
| 잘못된 라이선스 공개(최대 위험) | `license=null` + 검증 전 비공개, 사람 검수(기획 9장) |
| 구글 폰트 목록 변동 | 고정 개수 검증 금지, 조건(한글 전체-라틴 100-무중복) 검증 |
| 네트워크 실패-부분 응답 | 타임아웃-제한 재시도-종료 코드, 저장은 원자적 교체 |
| API 키 로그 노출 | 전체 URL 미기록, 키 마스킹 |
| 혼합 모노레포 명령 혼선 | `Makefile`로 web/pipeline 명령-작업 디렉터리 일원화 |

## 9. 다음 단계

이 스펙을 승인하면 `writing-plans` 스킬로 구현 계획을 작성하고, 이어서 구현으로 넘어간다(구현은 오케스트레이션 위임).
