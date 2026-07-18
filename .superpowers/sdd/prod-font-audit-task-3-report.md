# Prod font audit Task 3 보고

## 결과

- prod 공개 기준선: exact count `1,240`
- 실데이터 bootstrap: `matched=1,240`, `unmatched=0`, `conflicts=0`
- 모든 entry의 `public_updates`: 빈 객체 `{}`
- manifest SHA-256: `d538a3e493eb0b193fe25c6783508a8c06b09878d474e80ee137456b5359b38c`

## RED

- 기준 커밋 `393b927` 임시 archive에 현재 테스트만 넣어 실행했다.
- `ModuleNotFoundError: No module named 'fontagit_pipeline.audit_bootstrap'`로 구현 전 실패를 확인했다.
- 보강 테스트에서 Tier B 시드의 존재하지 않는 `slug` 신뢰, DB/Python 정렬 차이, `before.source_tier` 누락, 알 수 없는 기준선 schema 허용을 각각 실패로 확인했다.

## 구현·안전 보강

- Tier A는 `source_tier + name_en + slug + 기존 Google URL` 완전 일치만 자동 연결한다.
- Tier B는 import와 같은 `derive_noonnu_slug`로 slug를 만들고, `source_page` 전체가 `https://noonnu.cc/font_page/<숫자>`일 때만 provider ID를 얻는다.
- 후보가 0개이거나 2개 이상이면 자동 연결하지 않고 검수 대상으로 남긴다.
- `foundry` 비정상 선채움, 기준선 개수·중복·정렬·schema·본문 해시·파일 해시를 bootstrap 전에 차단한다.
- prod API의 DB collation(문자열 정렬 규칙)과 Python 정렬이 달라 첫 export가 안전하게 중단됐다. 조회 후 slug를 로컬에서 일관된 순서로 다시 정렬해 해시가 항상 같도록 수정했다.
- JSON과 동반 `.sha256` 파일은 임시 파일에 쓴 후 원자적으로 교체한다.

## GREEN / 검증

- `uv run pytest tests/test_audit_bootstrap.py -q` → `7 passed`
- `uv run ruff check src/fontagit_pipeline/audit_bootstrap.py src/fontagit_pipeline/__main__.py tests/test_audit_bootstrap.py` → 통과
- `uv run mypy src/fontagit_pipeline/audit_bootstrap.py src/fontagit_pipeline/__main__.py` → 통과
- `uv run pytest -q` → `164 passed`
- anon-only 공개 API export → `record_count=1,240`, slug 정렬·중복 0건 검증
- 실제 `output/tier-a.json` 136건과 `output/tier-b-noonnu-seed.json` 1,157건을 사용한 전수 dry-run → `1,240 / 0 / 0`
- provider 별 자동 연결: Google Fonts 130건, 눈누 1,110건. provider 키 중복 0건.
- 1,240건 전부 `foundry=null`, `before.source_tier` 존재, `public_updates={}`를 확인했다.

## 쓰기 범위·우려

- `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY`만 `SUPABASE_URL`/`SUPABASE_ANON_KEY`로 연결했다.
- service/secret key를 사용하지 않았고 prod 쓰기, migration, 배포를 수행하지 않았다.
- 생성된 기준선·manifest·SHA 산출물은 커밋하지 않았다.
- 현재 기준선 1,240건은 모두 자동 연결됐으며 남은 충돌·미연결 우려는 없다. prod 데이터 수가 바뀌면 1,240 gate가 자동 중단한다.

## Commits

- `cdaa713 feat: bootstrap font audit baseline`
- `edecfbc fix: validate font audit baseline integrity`
- `619abd7 test: consolidate bootstrap review coverage`
- 이번 변경: `fix: enforce prod font tier distribution`

## 리뷰 보강 2: prod Tier 분포·Tier A 시드 검증

- RED: `cd apps/pipeline && uv run pytest tests/test_audit_bootstrap.py -q` → `4 failed, 3 passed`
  - `source_tier=B`인 Tier A 시드가 자동 연결되는 실패를 확인했다.
  - 작은 테스트 기준선이 분포 검증을 명시적으로 override할 API가 없음을 확인했다.
- GREEN: `cd apps/pipeline && uv run pytest tests/test_audit_bootstrap.py -q` → `7 passed`
- `uv run ruff check src/fontagit_pipeline/audit_bootstrap.py src/fontagit_pipeline/__main__.py tests/test_audit_bootstrap.py` → 통과
- `uv run mypy src/fontagit_pipeline/audit_bootstrap.py src/fontagit_pipeline/__main__.py` → 통과
- `uv run pytest -q` → `169 passed`
- anon-only export 명령:
  - `uv run python -m fontagit_pipeline font-audit-export-baseline --source prod-public --out output/audit/prod-fonts-baseline.json`
  - 결과: exact `1,240`, Tier A `130`, Tier B `1,110`, 기타 Tier `0`
- 전수 bootstrap 명령:
  - `uv run python -m fontagit_pipeline font-audit-bootstrap --prod-snapshot output/audit/prod-fonts-baseline.json --out output/audit/bootstrap-manifest.json`
  - 결과: `matched=1,240`, `unmatched=0`, `conflicts=0`, `public_updates` 전부 `{}`
  - manifest SHA-256: `d538a3e493eb0b193fe25c6783508a8c06b09878d474e80ee137456b5359b38c`
- 기본 export/load 경로는 전체 1,240건과 A 130/B 1,110 분포를 동시에 강제한다. 테스트 fixture만 `expected_tier_counts=None` 또는 대체 분포를 명시해 우회할 수 있다.
- service/secret key, prod 쓰기, migration, 배포는 사용·수행하지 않았다.
