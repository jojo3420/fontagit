# 세션 핸드오프 — 2026-07-18 00:15 KST

> **모드**: simple-change (저장: docs/handoff/)
> **Feature**: 눈누 Tier B 2단계 - 제작사 공식 사이트 라이선스/메타 자동 수집
> **성격**: 이번 세션에서 구현한 게 아니라, **다음 세션이 새로 만들 기능의 설계-인계 문서**
> **이전 세션 종결 사유**: 기능 착수 전 인계(범위 확인 후 구현 예정)

## 한 줄 요약
눈누에서 수집한 1,154개 draft 폰트(각각 폰트명-제작사-공식URL 보유)의 **공식 URL을 방문해 라이선스 등 세부 메타를 자동 추출**하고, 사람이 승인한 것만 published로 전환하는 "Tier B 2단계"를 만든다. 이번 세션은 그 전제(1단계 수집-임포트)를 완료했다.

---

## 다음 세션이 가장 먼저 할 일
1. 이 핸드오프를 읽는다 (`docs/handoff/2026-07-18-0015-noonnu-tier-b-stage2.md`)
2. 기획서 근거를 읽는다:
   - `docs/fontagit-master-plan-v3.0.md` 4장(Tier B 2단계 크롤링 설계), 9장(법적 안전선), 13장(review_queue), 5장 F-01(라이선스 4행 스키마)
3. 기존 코드 확인: `apps/pipeline/src/fontagit_pipeline/`의 `noonnu_seed.py`, `noonnu_import.py`, `client.py`, `licenses.py`, `models.py`
4. dev DB 상태 확인: `fontagit.fonts`에서 `source_tier='B' and status='draft'` = 1,154행(각 official_url 있음, 라이선스 필드 null)
5. 아래 "다음 단계 MUST"부터 시작. 착수 전 사용자에게 범위(프로토타입 20건 vs 전량) 확인.

---

## 작업 컨텍스트

### 사용자 원본 요청
> "눈누 기본 베이스 정보(메타정보 3개)를 기반으로 제작사 공식 사이트 라이선스 정보 등 메타 정보 수집 자동화 기능"

### 이번 세션에서 확보된 전제 (1단계 완료)
- 눈누 한글 폰트 **1,157건 사실 수집** → `apps/pipeline/output/tier-b-noonnu-seed.json`(gitignore, 로컬). 필드: name_ko, name_en, maker, official_url, source_tier=B.
- dev DB에 **1,154건 draft 임포트 완료**(status='draft', source_tier='B', official_url 채워짐, category는 임시 '고딕'/'sans-serif' 고정, **라이선스 필드는 null**). 이 null들을 2단계가 채운다.
- 임포터 버그(멱등성) 수정 완료: `noonnu_import.py`의 `.maybe_single()` (커밋 develop d7b6f12).

### 결정 사항 (이번 세션 논의로 합의된 방향)
| # | 결정 | 근거 |
|---|------|------|
| 1 | **하이브리드 방식** 채택: 공식 URL fetch → LLM(대규모 언어모델)로 라이선스 초안 추출 → review_queue에 "제안"으로 적재 → 사람 승인 시 published | 제작사 수백 곳이라 회사별 규칙 파서는 비현실적, 라이선스는 오류 치명적이라 완전 자동 공개 금지 |
| 2 | **공개 전 사람 검증 필수** (자동 published 절대 금지) | 기획서 9장: 라이선스 오기 = 저작권/AdSense 사고 |
| 3 | LLM 추출 시 **근거 원문 인용 + 확인일**을 함께 저장 | 사람이 빠르게 대조-승인하기 위함 (환각 방어) |

### 사용자 제약-금지사항 (반드시 준수)
- 🔴 라이선스 확인 안 된 폰트를 published로 자동 전환 금지. draft 유지 → 사람 승인만.
- 🔴 눈누의 설명/라이선스 요약 문구 복제 금지(9장 5번). 제작사 1차 출처만.
- 🔴 크롤링 예의: robots.txt 준수, 요청 속도 제한(1단계 수집기와 동일 기준), 정중한 User-Agent. 파일 재호스팅 금지.
- 🔴 prod DB 쓰기는 사용자 확인. dev(zgxt...supabase.co)만 자율. MCP는 read-only(쓰기 불가) → 마이그레이션은 사용자 수동 적용.

---

## 목표 데이터 스키마 (2단계가 채울 것)
기획서 5장 F-01 기준 라이선스 4행 + 근거:
- 상업적 이용(is_commercial_free / commercial), 웹폰트 임베딩, 재배포, 수정 허용 여부
- 주의 조건, license_type, **확인일(verified_at)**, **근거 원문 링크/인용**
- (fonts 테이블에 이미 license_type, is_commercial_free, license_verified, official_url 등 컬럼 존재. 0001 스키마 참조)

---

## 블로커-선행 작업 (착수 전 해결 필요)
| # | 이슈 | 영향 | 조치 |
|---|------|------|------|
| 1 | **review_queue 테이블 없음** (마이그레이션 미존재. 기획서 13장엔 설계됨) | 2단계 "제안" 적재처 없음 | 신규 마이그레이션으로 review_queue(또는 license_proposals) 생성. 사용자 수동 적용 |
| 2 | **파이프라인에 LLM 클라이언트 없음** (deps: httpx, beautifulsoup4만) | LLM 추출 불가 | anthropic SDK 추가 + API 키 env(config.py에 추가). Claude로 페이지→라이선스 4행 구조화 |
| 3 | ⚠️ 제작사 사이트가 JS 렌더/PDF/이미지인 경우 | 텍스트 추출 실패 | httpx로 안 되는 곳은 playwright(브라우저 렌더) 필요분만. PDF/이미지는 사람 몫으로 라벨 |
| 4 | category 임시 고정('고딕') | 분류 부정확 | 2단계에서 실제 분류 보정 or 사람 승인 시 수정 |

---

## 다음 단계 (Next)

🔴 **MUST**:
- [ ] 설계 확정: review_queue(또는 license_proposals) 스키마 + 상태 흐름(proposed→approved→published) 마이그레이션 작성
- [ ] LLM 클라이언트 도입: anthropic SDK + config에 API 키. 프롬프트 = "페이지 텍스트 → 라이선스 4행 + 확인일 + 근거 원문 인용(JSON)"
- [ ] `noonnu_enrich.py`(신규): draft 폰트의 official_url fetch(httpx, robots/rate limit) → LLM 추출 → review_queue 적재. **published 전환 금지**
- [ ] 소량 프로토타입(20건) 실행 → 추출 정확도를 사용자에게 보고 후 확대 여부 결정

🟡 **SHOULD**:
- [ ] JS 렌더 사이트 대응(playwright 선택 도입), 실패/미확정 라벨링
- [ ] 사람 승인 경로(운영자 검수 큐 조회/승인 - 최소 CLI 또는 간단 화면)

🟢 **NICE-TO-DO**:
- [ ] 대형 제작사(산돌급 등) 회사별 규칙 파서 병행으로 정확도 상향
- [ ] PDF/이미지 라이선스 OCR

---

## 핵심 파일 경로 (Refs)
| 카테고리 | 경로 |
|---|---|
| 1단계 수집기 | `apps/pipeline/src/fontagit_pipeline/noonnu_seed.py` |
| draft 임포터 | `apps/pipeline/src/fontagit_pipeline/noonnu_import.py` |
| HTTP 클라이언트 패턴 | `apps/pipeline/src/fontagit_pipeline/client.py` |
| 기존 라이선스 로직(Tier A) | `apps/pipeline/src/fontagit_pipeline/licenses.py` |
| pydantic 모델 | `apps/pipeline/src/fontagit_pipeline/models.py` |
| CLI 진입점 | `apps/pipeline/src/fontagit_pipeline/__main__.py` (noonnu-seed/noonnu-import 서브명령) |
| 수집 결과(사실) | `apps/pipeline/output/tier-b-noonnu-seed.json` (1,157건, gitignore) |
| 기획서 | `docs/fontagit-master-plan-v3.0.md` (4장/9장/13장/5장 F-01) |
| 이 핸드오프 | `docs/handoff/2026-07-18-0015-noonnu-tier-b-stage2.md` |

---

## 검증 상태
| 항목 | 상태 |
|---|---|
| 1단계 수집(1,157) | ✅ 완료 |
| draft 임포트(1,154) | ✅ 완료 (dev). ⚠️ dev MCP는 self-signed 인증서 오류로 재조회 불가, 파이프라인 로그가 증거 |
| 임포터 버그 수정 | ✅ develop d7b6f12 (ruff/pytest 통과) |
| 2단계 기능 | ⏳ 미착수 (이 핸드오프가 착수 근거) |

---

## 재개 프롬프트 (새 세션 첫 메시지로 붙여넣기)

```
이전 세션 작업을 이어받아 "눈누 Tier B 2단계(제작사 공식 사이트 라이선스 자동 수집)" 기능을 만듭니다. 먼저 핸드오프를 읽고 컨텍스트를 복원하세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/handoff/2026-07-18-0015-noonnu-tier-b-stage2.md

복원 순서:
1. 위 핸드오프 전체를 읽는다
2. 기획서 4장/9장/13장/5장 F-01을 읽는다
3. apps/pipeline/src/fontagit_pipeline/의 noonnu_seed.py, noonnu_import.py, client.py, licenses.py 확인
4. git status && git log --oneline -10 로 상태 확인
5. 핸드오프의 "다음 단계 MUST"부터 시작하되, 착수 전 프로토타입(20건) vs 전량 범위를 사용자에게 확인
6. 제약 준수: 라이선스 확인 전 published 금지, 눈누 문구 미복제, robots/rate limit, prod 쓰기 사용자 확인

핸드오프를 읽었음을 확인하고 MUST 중 어디부터 시작할지 한 줄로 보고하세요.
```
