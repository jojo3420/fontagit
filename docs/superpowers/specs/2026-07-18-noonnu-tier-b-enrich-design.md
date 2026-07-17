# 눈누 Tier B 2단계 — 라이선스-스타일 반자동 수집 및 발행 설계

> 작성일: 2026-07-18 - 상태: 설계 승인(사용자 위임) - 선행 문서: `docs/handoff/2026-07-18-0015-noonnu-tier-b-stage2.md`
> 기획 근거: `docs/fontagit-master-plan-v3.0.md` 4장(Tier B 2단계), 5장 F-01(라이선스 4행), 9장(법적 안전선), 13장(review_queue)

## 1. 한 줄 요약

눈누 상세페이지에서 라이선스 허용표-스타일을 **결정론적으로(LLM 없이) 사실만** 추출해, 상업 사용이 명백히 열린 폰트는 자동 발행하고 애매한 소수만 사람이 일괄 승인하는 반자동 파이프라인. dev 검증 후 사용자 확인 하에 prod 발행.

## 2. 확정된 결정 (브레인스토밍 + 자체 적대적 리뷰)

| # | 결정 | 근거 |
|---|------|------|
| D1 | 전량 1,154건 대상 설계 | 사용자 선택 |
| D2 | 눈누 상세페이지에서 사실 추출 (제작사 크롤링 아님) | 사용자 선택. 기존 stage-1 크롤러가 이미 같은 페이지를 robots 준수로 파싱 중 |
| D3 | 사실만 추출 + 발행 전 사람이 제작사 링크로 라이선스 교차확인 | 기획서 9장 #5(눈누 문구 복제 금지, 1차 출처) 준수 |
| D4 | LLM 미도입 (핸드오프 블로커 #2 폐기) | 눈누 데이터가 구조화된 사실이라 결정론 파싱으로 충분, API 비용 0 |
| D5 | 반자동: 명백히 안전한 다수 자동 발행 + 애매한 소수만 사람 | 사용자 요구(검수 최소화) |
| D6 | 자동 게이트 = **상업 4카테고리(인쇄물-웹사이트-포장지-영상) 전부 '사용가능' + price=0** | 자체 적대적 리뷰 결과. "6개 전부 허용만 자동"은 임베딩 조건부 때문에 자동률이 0에 수렴해 폐기 |
| D7 | 검수 도구는 CLI(Python, 파이프라인 동일 스택) | 솔로 운영에 가장 단순 |
| D8 | 스타일(굵기/이태릭)은 best-effort | `@font-face` 결측이 표본상 ~40% → 전량 보장 불가. 없으면 발행은 진행하되 '미확인' 처리 |

## 3. 자체 적대적 리뷰 요지 (truth-check, mode Full)

눈누 8개 페이지 실측으로 검증한 결과와 정정 사항:
- **검증됨**: 허용표는 6개 고정 카테고리로 매우 일관 → 결정론 파싱 가능(신뢰도 중간, 소표본 한계).
- **반증 1**: "조건부 허용"은 거의 항상 '임베딩'에 붙음. 우리는 웹폰트를 임베딩하지 않고 이미지+링크만 하므로(9장 #4) 임베딩 조건부는 **발행 안전성과 무관 → 표시용 사실로만 저장**. 자동 게이트는 상업 4카테고리로 한정(D6).
- **반증 2**: `@font-face` 굵기 추출 40% 실패 → 스타일 best-effort(D8).
- **잔존 리스크**: 눈누 카테고리화가 제작사 실약관과 다를 수 있음(rule #5). 방어: 자동분 5% 표본점검 + OFL/표준 무료 신호 우선 + 신고→보류 백스톱(F-08).

## 4. 상태 흐름

```
draft (임포트됨, 라이선스 null)
  │  noonnu-enrich: 눈누 재방문 → 파싱 → 분류
  ├─ auto_safe  → fonts 직접 기록 + status=published (원자적) + license_proposals(review_status=auto_published, 증거)
  └─ needs_review → license_proposals(review_status=proposed), fonts는 draft 유지
                      │  noonnu-review approve → fonts 기록 + published
                      └  noonnu-review reject  → rejected, draft 유지
자동분: audit-sample 5% 사후 점검 → 문제 시 unpublish
```

자동 발행은 오직 D6 게이트 통과분에만 적용된다. 그 외 어떤 경로로도 라이선스 미확정 폰트가 published 되지 않는다.

## 5. DB 스키마 변경 (마이그레이션 `0016`, 사용자 수동 적용)

MCP는 읽기 전용 → 사용자가 dev에 psql로 직접 적용(기존 패턴). prod는 별도 승인 후 적용.

### 5-1. fonts 컬럼 추가 (F-01 라이선스 4행 + 근거)
- `allow_embedding text` — 3-state('allowed'/'conditional'/'denied'), nullable
- `allow_redistribute text` — 동일. **눈누 6표에 없는 항목** → license_type이 OFL 등 표준일 때만 표준값, 그 외 null(unknown)
- `allow_modify text` — 동일. 재배포와 같은 규칙
- `license_note text` — 조건부 주의(우리 표현. 눈누 문구 복제 아님)
- `verified_at timestamptz` — 확인일
- `license_source_url text` — 근거 링크(제작사 공식 + 눈누 근거)
- `auto_approved boolean not null default false` — 자동 발행분 식별(표본점검용)
- 3-state 컬럼에 CHECK 제약(허용값 3종 또는 null)
- 상업은 기존 `is_commercial_free` 재사용, 굵기/이태릭은 기존 `weights[]`/`variants[]` 재사용

### 5-2. 발행 제약 완화
현재 `fonts_published_license_chk`가 published를 OFL/Apache/UFL로 제한해 Tier B를 막음. 재작성:
```
check (status <> 'published' or (
  license_verified = true
  and (source_tier <> 'A' or license_type in ('OFL','Apache-2.0','UFL'))
))
```
→ published는 항상 `license_verified=true` 필수. Tier A만 라이선스 타입 화이트리스트 유지, Tier B는 verified면 발행 허용.

### 5-3. `license_proposals` 테이블 신규 (기획서 13장 review_queue)
운영 전용 — RLS 활성화 + anon 정책 없음(잠금), `grant ... to service_role`.
- `id uuid pk`, `font_id uuid → fonts(id) on delete cascade`, `slug text`
- `source_url text` (눈누 font_page), `raw_permissions jsonb` (눈누 6카테고리 원본 = 증거)
- 제안값: `proposed_commercial_free bool`, `proposed_embedding/redistribute/modify text`, `proposed_license_type text`, `proposed_weights int[]`, `proposed_italic bool`, `proposed_category_ko text`(nullable)
- `parse_status text` check('parsed'/'partial'/'failed')
- `classification text` check('auto_safe'/'needs_review')
- `review_status text default 'proposed'` check('proposed'/'approved'/'rejected'/'auto_published')
- `scraped_at timestamptz`, `reviewed_at timestamptz`, `reviewer_note text`
- `unique(font_id)` → 재실행 시 멱등 upsert(제안 갱신)

## 6. 컴포넌트

### 6-1. `noonnu_enrich.py` (신규 모듈)
- **입력원**: 눈누 URL은 fonts에 없고 seed JSON(`output/tier-b-noonnu-seed.json`)의 `source_page`에 있음 → seed 레코드를 순회하며 slug로 dev DB의 font_id 매칭. published 폰트는 건너뜀.
- **HTTP**: `noonnu_seed`의 robots 정책 + 1.5초 딜레이 + UA + httpx 재사용(신규 크롤링 규약 없음).
- **파싱(결정론)**:
  - JSON-LD `SoftwareApplication` → name, `offers.price`(무료 신호), creator
  - 허용표 → 6카테고리 status(인쇄물/웹사이트/포장지/영상/임베딩/BICI). 파싱 실패 시 `parse_status=failed`
  - `@font-face` → `weights[]`, `italic`(best-effort, 없으면 빈 값)
  - license 본문에 'OFL'/'SIL' → `license_type='OFL'`, 그 외 무료 → `'custom-free'`
- **매핑(6카테고리 → F-01 4행)**:
  - 상업적 이용 = 인쇄물-웹사이트-포장지-영상 모두 사용가능 → `is_commercial_free`
  - 웹폰트 임베딩 = 임베딩 status → `allow_embedding`
  - 재배포/수정 = 표에 없음 → OFL이면 표준값(재배포=conditional, 수정=allowed), 아니면 null(상세페이지에서 공식 약관 링크 안내)
- **분류(D6 게이트)**: `parse_status=parsed AND price==0 AND {인쇄물,웹사이트,포장지,영상} 전부 '사용가능'` → `auto_safe`. 그 외(상업 카테고리 조건부/불가, price≠0, 파싱실패, official_url 없음) → `needs_review`
- **쓰기**:
  - auto_safe → fonts 업데이트(라이선스 4행/굵기/이태릭/verified_at/license_source_url/`license_verified=true`/`auto_approved=true`/`status=published`) + proposals(review_status=auto_published, 증거)
  - needs_review → proposals(review_status=proposed)만, fonts는 draft
- **CLI**: `--limit N`, `--slug S`로 소량 실행

### 6-2. `noonnu-review` (검수 CLI)
- `list` — needs_review 제안을 제작사/license_type로 묶어 출력
- `show <slug>` — 제안 상세 + raw_permissions + 눈누 URL + 제작사 official_url(사람이 열어 대조)
- `approve <slug>` / `approve --maker <제작사>` (일괄) — fonts 기록 + published, proposal=approved
- `reject <slug> --note <사유>` — proposal=rejected, fonts는 draft
- `audit-sample [--pct 5]` — auto_published 표본 추출(사후 점검), `unpublish <slug>`로 되돌림

### 6-3. prod 발행 (`noonnu-publish` 또는 uploader 확장)
- dev-first 원칙. prod는 `--env prod` + 확인 프롬프트 필수(제약 🔴).
- 검증된 published Tier B 폰트(+aliases)를 prod DB에 service_role로 upsert(기존 uploader 패턴 재사용).
- 선행: prod에 0016 마이그레이션 수동 적용.

## 7. 에러 처리 - 멱등성

- 파싱 실패 → `parse_status=failed`, needs_review, **자동 발행 절대 없음**. 배치는 항목별 try로 계속(seed 패턴).
- robots 불허/fetch 오류 → 스킵 + 카운트 로그.
- 멱등성: proposal은 `unique(font_id)` upsert로 재실행 안전. published 폰트는 downgrade 안 함.
- 스타일 결측(`weights=[]`) → 실패 아님, 상세페이지에서 '스타일 정보 미확인'.

## 8. 테스트 전략 (TDD)

순수 함수 위주 단위 테스트, 라이브 네트워크 없이 저장된 눈누 HTML 픽스처 사용:
- `parse_permission_table(html)` → 6카테고리 status dict (픽스처: 실측한 눈누 페이지)
- `classify(proposal)` → auto_safe/needs_review. 엣지: 임베딩만 조건부→auto, 웹사이트 조건부→review, 파싱실패→review, price≠0→review
- `map_to_license_rows(...)` → F-01 4행 매핑(OFL 표준값 vs unknown)
- `extract_styles(html)` → weights/italic, 결측 처리
멱등 upsert는 통합 테스트(dev, 깨끗한 env).

## 9. 블로커 처리 (핸드오프 대비)

| 핸드오프 블로커 | 처리 |
|---|---|
| #1 review_queue 없음 | 0016에서 `license_proposals` 생성 |
| #2 LLM 클라이언트 없음 | 폐기 — 결정론 파싱으로 불필요(D4) |
| #3 JS/PDF 렌더 | 눈누 서버 HTML로 충분(실측 확인). 파싱 실패분만 사람 |
| #4 category 임시 고정 | `proposed_category_ko` best-effort, 검수 시 사람 보정 |

## 10. 실행 순서 (구현 후 운영)

1. 사용자: dev에 `0016` 마이그레이션 적용
2. `noonnu-enrich --limit 20` → 추출 정확도 사용자 보고
3. 정확도 OK → dev 전량 enrich
4. `noonnu-review`로 needs_review 큐 일괄 처리
5. `audit-sample`로 자동분 5% 점검
6. 사용자: prod에 `0016` 적용
7. `noonnu-publish --env prod`(확인 프롬프트) → 최종 발행

## 11. 미해결 - 리스크

- 눈누 표 구조 일관성은 8건 실측 기준(전체 1,157 대비 소표본). 소수 이형 폰트는 파싱 실패→사람으로 흡수.
- 눈누 카테고리 ≠ 제작사 실약관 가능성 → 자동분 표본점검 + 신고 백스톱으로 방어. 재확인 정책은 기획서 14장(트래픽 상위 50 분기별) 따름.
- 스타일 전량 정확이 필요해지면 폰트파일 분석(fonttools, Approach B)을 후속 NICE로 추가.
