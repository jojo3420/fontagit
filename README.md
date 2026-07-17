# FontAgit (폰트 아지트)

국내외 무료-유료 폰트를 한곳에서 검색-비교하고, 공식 다운로드/구매 페이지로 바로 연결해 주는 폰트 아카이브 웹사이트입니다. 폰트 파일을 직접 호스팅하지 않고 항상 공식 페이지로 안내합니다.

## 목적

폰트를 찾는 사람은 "이 폰트가 상업적으로 써도 되는지", "어디서 정식으로 받을 수 있는지", "비슷한데 무료인 대안은 없는지"를 매번 여러 사이트를 돌아다니며 확인해야 합니다. FontAgit은 이 정보를 한 화면에 모아 검색 유입 사용자(디자이너, 마케터, 학생, 일반 사용자)가 빠르게 판단하도록 돕는 것을 목표로 합니다. 수익 모델은 검색 유입과 광고입니다.

## 주요 기능

- 폰트 목록 탐색과 폰트별 상세 페이지: 실제 서체 견본, 원하는 문장 직접 미리보기, 상업적 이용 가능 여부, 공식 페이지 링크
- 유료 폰트 상세에서 비슷한 무료 대안 추천
- 인기 폰트 트렌드(주간/월간 TOP)
- 홈 히어로 + 이번 주 TOP 10, 다크모드
- 폰트 데이터 자동 수집 파이프라인: Google Fonts API에서 폰트 메타데이터를 정기적으로 수집해 웹이 사용할 JSON으로 저장

## 저장소 구조

pnpm 워크스페이스 + uv 기반 모노레포입니다. 크게 두 개의 앱으로 나뉩니다.

```
fontagit/
├── apps/
│   ├── pipeline/         # Python 수집 파이프라인 (Google Fonts → JSON)
│   │   ├── src/fontagit_pipeline/
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── uv.lock
│   └── web/              # Next.js 웹 프론트엔드
├── docs/                 # 설계-진행 문서 (PDCA)
├── Makefile              # 자주 쓰는 명령 모음
├── package.json          # pnpm 워크스페이스 루트
└── .env.example          # 환경 변수 예시
```

- `apps/pipeline`: Python 3.12+로 작성된 수집 파이프라인. Google Fonts webfonts API를 조회해 폰트 레코드로 변환하고 `output/tier-a.json`으로 원자적 저장합니다.
- `apps/web`: Next.js 웹사이트. 정적 사이트 생성(static export) 방식으로 배포합니다.

---

## 사전 준비물

| 도구 | 버전 | 용도 |
| --- | --- | --- |
| Python | 3.12 이상 | 파이프라인 실행 |
| uv | 최신 | Python 가상환경-의존성 관리 |
| Node.js | 20 이상 | 웹 실행/빌드 |
| pnpm | 9 이상 | 웹 패키지 관리 |

이 문서는 파이썬 파이프라인 세팅을 중심으로 설명합니다. 웹 실행은 아래 "웹 프론트엔드 실행"을 참고하세요.

---

## 파이썬 가상환경 세팅

가상환경(virtual environment)은 이 프로젝트에서 쓰는 파이썬 패키지를 시스템 파이썬과 분리해 담아 두는 격리 공간입니다. 다른 프로젝트와 버전이 충돌하지 않게 해 줍니다.

이 프로젝트는 `uv`로 가상환경과 의존성을 관리합니다. `uv`는 가상환경 생성부터 패키지 설치까지 한 번에 처리해 주는 빠른 파이썬 도구입니다. 아래 방법 A(권장)를 따르면 됩니다. `uv`를 쓰기 어려운 환경이라면 방법 B로 표준 도구만으로도 세팅할 수 있습니다.

### 방법 A. uv 사용 (권장)

1. uv 설치 (한 번만)

   ```bash
   # macOS / Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   설치 후 새 터미널에서 `uv --version`이 나오는지 확인합니다.

2. 파이프라인 디렉터리로 이동해 의존성 설치

   ```bash
   cd apps/pipeline
   uv sync
   ```

   `uv sync`는 `apps/pipeline/.venv/`에 가상환경을 자동으로 만들고, `uv.lock`에 고정된 버전 그대로 패키지(httpx, pydantic 등)와 개발 도구(pytest, ruff, mypy)를 설치합니다. 별도로 `python -m venv`를 실행할 필요가 없습니다.

3. 가상환경 안에서 명령 실행

   `uv run`을 앞에 붙이면 가상환경을 자동으로 활성화한 상태로 명령이 실행됩니다.

   ```bash
   uv run python -m fontagit_pipeline   # 파이프라인 실행
   uv run pytest                        # 테스트
   ```

   터미널 프롬프트에 가상환경을 계속 켜 두고 싶다면 직접 활성화할 수도 있습니다.

   ```bash
   source .venv/bin/activate   # 활성화 (끄기: deactivate)
   ```

### 방법 B. 표준 venv + pip 사용

`uv` 없이 파이썬 기본 도구만으로 세팅하는 방법입니다.

```bash
cd apps/pipeline

# 1. 가상환경 생성 (.venv 폴더가 만들어짐)
python3 -m venv .venv

# 2. 활성화
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows PowerShell

# 3. 이 프로젝트를 개발 모드로 설치 (의존성 포함)
pip install -e ".[dev]"
```

활성화된 상태에서는 `uv run` 없이 `python -m fontagit_pipeline`, `pytest`를 바로 쓰면 됩니다. 작업이 끝나면 `deactivate`로 빠져나옵니다.

> 참고: `.venv/` 폴더는 `.gitignore`에 등록되어 있어 git으로 관리되지 않습니다. 각자 로컬에서 위 절차로 새로 만들면 됩니다.

---

## 환경 변수 설정

파이프라인은 Google Fonts API를 호출하므로 API 키가 필요합니다.

1. Google Fonts API 키를 발급받습니다. (Google Cloud Console → API 및 서비스 → "Web Fonts Developer API" 사용 설정 후 키 생성)
2. 파이프라인 디렉터리에 `.env` 파일을 만들고 키를 채웁니다.

   ```bash
   cd apps/pipeline
   cp ../../.env.example .env
   ```

   `.env` 내용:

   ```
   GOOGLE_FONTS_API_KEY=발급받은_키를_여기에
   ```

키가 비어 있으면 파이프라인은 실행 즉시 종료 코드 `2`와 함께 안내 메시지를 출력합니다.

---

## 파이프라인 실행

가상환경 세팅과 `.env` 설정을 마쳤다면 다음으로 실행합니다.

```bash
# apps/pipeline 안에서
uv run python -m fontagit_pipeline

# 또는 저장소 루트에서 Makefile 사용
make collect
```

동작 순서는 다음과 같습니다.

1. `.env`에서 API 키를 로드합니다.
2. Google Fonts webfonts API를 조회합니다.
3. 응답을 폰트 레코드로 변환합니다(라틴 폰트는 상위 100개로 제한).
4. 결과를 `apps/pipeline/output/tier-a.json`에 원자적으로 저장합니다. 변환 결과가 0건이면 기존 파일을 덮어쓰지 않고 종료합니다.

종료 코드: `0` 성공 / `2` API 키 누락 / `3` API 조회-검증-저장 실패.

---

## 테스트와 정적 검사

```bash
# 저장소 루트에서
make test    # pytest 실행
make lint    # ruff 린트 + mypy 타입 검사

# 또는 apps/pipeline 안에서 직접
uv run pytest
uv run ruff check .
uv run mypy src
```

---

## 웹 프론트엔드 실행

웹은 Node.js와 pnpm이 필요합니다.

```bash
# 저장소 루트에서
pnpm install          # 의존성 설치 (최초 1회)
make web-dev          # 개발 서버 실행 (pnpm --filter web dev)
```

브라우저에서 http://localhost:3000 을 열면 됩니다. 빌드는 `pnpm web:build`로 실행하며, 정적 사이트로 export됩니다. 웹 관련 상세 내용은 `apps/web/README.md`를 참고하세요.

---

## 자주 쓰는 명령 요약 (Makefile)

| 명령 | 설명 |
| --- | --- |
| `make collect` | 파이프라인 실행 (폰트 데이터 수집) |
| `make test` | 파이프라인 테스트 |
| `make lint` | ruff + mypy 검사 |
| `make web-dev` | 웹 개발 서버 실행 |

## 배포 (Cloudflare Pages)

웹은 정적 사이트(static export)라 **Cloudflare Pages**에 올립니다. 서버가 없고, 페이지는 빌드 시점에 Supabase 데이터를 구워 넣습니다. 실서비스 도메인은 **fontagit.com**입니다.

전제:
- Cloudflare Pages 프로젝트 이름: `fontagit`
- Pages 배포 토큰: `apps/web/.env.local`의 `CF_TOKEN` (권한: Account > Cloudflare Pages > Edit). git 비추적 파일이며 절대 커밋 금지.
- account id: `2686c11634da0d924f089b7e56a9e227`

### production 배포 (2단계)

```bash
# 1) prod 데이터로 빌드
#    주의: .env.local(dev Supabase)이 .env.production(prod ollidam)을 덮어쓰므로,
#    prod 값을 process env로 먼저 주입해 우선순위를 뒤집는다.
set -a && source apps/web/.env.production && set +a
pnpm --filter web build     # 결과: apps/web/out/

# 2) production(main 브랜치)로 배포 → 라이브 URL + 커스텀 도메인 갱신
export CLOUDFLARE_API_TOKEN=$(grep '^CF_TOKEN=' apps/web/.env.local | cut -d= -f2-)
export CLOUDFLARE_ACCOUNT_ID=2686c11634da0d924f089b7e56a9e227
npx wrangler pages deploy apps/web/out --project-name fontagit --branch main
```

데이터가 바뀌면 위 2단계를 다시 실행합니다.

### preview 배포

`--branch main` 대신 다른 브랜치명을 주면 라이브에 영향 없는 미리보기 URL만 생깁니다.

```bash
npx wrangler pages deploy apps/web/out --project-name fontagit --branch preview
```

### 도메인-리다이렉트

- `fontagit.com`(apex) → Pages 프로젝트에 연결(CNAME → `fontagit.pages.dev`, proxied).
- `www.fontagit.com` → `fontagit.com` 301 리다이렉트(Redirect Rule), http → https 강제(Always Use HTTPS).
- 상세 절차-롤백-검증: `docs/superpowers/specs/2026-07-17-prod-deploy-cloudflare-pages-design.md`

## 문서

- 설계-진행 이력: `docs/` (마스터 플랜, 진행 일지 등)
- 웹 앱 안내: `apps/web/README.md`
