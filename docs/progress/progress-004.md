# progress-004: 눈누 Tier B 라이선스-스타일 반자동 수집 파이프라인 (2026-07-18)

## 맥락 (왜 필요했나)
1단계에서 눈누 한글 폰트 1,154건을 draft로 임포트(폰트명-제작사-official_url만, 라이선스 null). 2단계는 눈누 상세페이지에서 라이선스-스타일 사실을 추출해 채우고 발행. 제약: 라이선스 오기=저작권/AdSense 사고 → 자동 발행 최소, 눈누 문구 복제 금지(기획서 9장 #5), robots/rate limit 준수.

## 구현 요약 (무엇을 어디에)
- 마이그레이션 `supabase/migrations/0016_noonnu_enrich.sql`:
  - fonts 컬럼 추가: allow_embedding/allow_redistribute/allow_modify(3-state 'allowed'/'conditional'/'denied'|null), license_note, verified_at, license_source_url, auto_approved.
  - 발행 제약 완화: `fonts_published_license_chk` → published는 license_verified=true 필수, Tier A만 OFL/Apache/UFL 화이트리스트(Tier B는 verified면 발행).
  - 신규 테이블 `license_proposals`(검수 큐, RLS 잠금, service_role만). raw_permissions(jsonb 증거), proposed_*, parse_status, classification, review_status(proposed/approved/rejected/auto_published), unique(font_id).
- `apps/pipeline/src/fontagit_pipeline/noonnu_enrich.py`: 눈누 파싱(JSON-LD 메타, 허용표 6카테고리, @font-face 굵기/이태릭) + 분류 게이트 + 오케스트레이터. LLM 미사용(BeautifulSoup+정규식).
- `noonnu_review.py`: 검수 CLI 로직(list/approve/reject/sample_auto_published/unpublish). 승인 시 fonts 발행(auto_approved=False).
- `noonnu_publish.py`: dev published Tier B → prod upsert. dry_run 기본, --confirm+대화형 'yes' 이중 확인.
- `noonnu_seed.py`: `derive_noonnu_slug` 공유 함수(import/enrich 슬러그 정합, 한글 보존).
- `__main__.py`: noonnu-enrich/review/publish 서브커맨드.

## 핵심 설계 결정 (코드로 복원 불가)
- 데이터 출처: 눈누 상세페이지에서 **사실만**(허용표 O/X, @font-face 굵기). 발행 전 사람이 제작사 링크로 라이선스 교차확인.
- 자동 발행 게이트(D6): `parse_status=='parsed' AND price==0 AND {인쇄물,웹사이트,포장지,영상} 4개 전부 'allowed'`. **임베딩은 게이트 아님**(우리는 이미지+링크만, 웹폰트 임베딩 안 함) — 자체 적대적 리뷰로 "6개 전부 허용" 원안이 자동률 0 수렴함을 실측(눈누 임베딩 조건부 빈번)해 정정.
- **재배포/수정은 눈누 허용표에 없는 정보 → 항상 None(unknown)**, 상세페이지에서 "제작사 약관 확인" 안내. OFL 키워드 추정은 눈누 허용표의 OFL 행 때문에 거의 전건 오판 → 제거(guess_license_type는 항상 'custom-free').
- LLM 미도입: 눈누가 구조화 사실 출처라 결정론 파싱으로 충분(핸드오프의 anthropic SDK 블로커 폐기).

## 시도와 실패 (재발 방지)
3-라운드 리뷰로 잡은 결함(테스트는 통과했으나 설계/런타임 위반):
- 1차 구현이 classify 게이트에 embedding 포함(D6 위반, 자동률 0) + parse_status='ok'(0016 CHECK 위반) + _font_update 발행필드 누락 + extract_styles 미호출.
- `_derive_slug`가 한글 제거→빈 슬러그, import는 한글 보존 → enrich가 한글전용 폰트 대량 skip. 공유 함수로 근본 해결.
- codex 리뷰: noonnu_review가 fonts에 없는 `font_id` 컬럼 select(approve 파손) / `int(float(price))` 절삭으로 유료가 무료 통과 / `soup.find("table")` 첫표+중복 덮어쓰기 / approve가 review_status 미확인.

## 재현-검증
- `cd apps/pipeline && python -m pytest tests/ -q` → 140 passed.
- `ruff check .` + `mypy src/fontagit_pipeline/` 통과.
- 운영(사용자 게이트): dev 0016 적용 → `python -m fontagit_pipeline noonnu-enrich --limit 20` → `noonnu-review list/approve` → `noonnu-review audit-sample` → prod 0016 → `noonnu-publish --confirm`.

## 미완료 (다음 세션)
- dev 0016 마이그레이션 적용은 사용자 몫(미적용). 이후 enrich/검수/prod 적재/deploy 전부 이에 의존.
- 상세페이지 라이선스 4행(임베딩/재배포/수정) 렌더 UI는 이 PR 범위 밖(별도 프론트 작업).
- 완전 원자성(fonts+proposal RPC 트랜잭션)은 MCP 읽기전용 제약으로 미도입(auto 경로 순서 재배치로 부분 완화).
