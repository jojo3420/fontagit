# 세션 핸드오프 — 2026-07-16 21:30 KST

> **모드**: superpowers-plan
> **Feature**: 슬라이스3 Top10 클릭 집계(F-03) 착수
> **이전 세션 종결 사유**: 슬라이스2 완결(PR #15, #16 머지) 후 사용자 마감 지시

## 한 줄 요약

슬라이스2 알리아스 검색을 완결했다(PR #15 머지 + 이연분 PR #16 머지, main `6d11ef0`). 다음 세션은 슬라이스3 클릭 집계(F-03)를 **계획 문서 작성(writing-plans)부터** 시작한다 — 슬라이스3은 스펙만 있고 plan 문서가 아직 없다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. **이 핸드오프 파일을 읽는다** (`docs/superpowers/handoff/2026-07-16-2130-slice3-click-tracking.md`)
2. **문서를 읽는다**:
   - 스펙: `docs/superpowers/specs/2026-07-15-web-data-integration-design.md` (슬라이스3 절 + P0 결정들)
   - 마스터 플랜: `docs/fontagit-master-plan-v3.0.md` **7장**(클릭 집계 설계 원문 — 단 스키마는 public이 아닌 fontagit, 아래 결정 #3 참고)
   - 참고 구현 패턴: `supabase/migrations/0006_search_fonts.sql`(SECURITY DEFINER + 스키마 한정 호출 + anon grant 패턴), `apps/web/lib/db/search.ts`(데이터 계층), `supabase/tests/search_fonts_test.sql`(psql assert 테스트)
3. **git 상태 확인**: `git status && git log --oneline -5` — main `6d11ef0`(PR #16 squash)이 최신
4. **아래 "다음 단계 MUST"부터**: 슬라이스3 계획 문서 작성 → 사용자 확인 → subagent-driven 구현

---

## 작업 컨텍스트

### 슬라이스3 요구사항 (스펙 발췌 — SSoT)

- 마이그레이션 **0007**: `font_clicks`(익명 — IP/식별자 컬럼 자체가 없음, `font_id` FK, `clicked_at` timestamptz default now, 인덱스) + `font_click_daily`(롤업 테이블). **anon은 원본 테이블 직접 접근 불가** — `record_click`/`get_top_fonts` RPC로만.
- 공식 링크 이동 시 `record_click(fontId)`를 **fire-and-forget**: 실패/지연이 이동을 막으면 안 됨(짧은 timeout 후 무조건 `window.location` 이동).
- **Top10은 빌드타임 생성**: 홈/트렌드 SSG가 `get_top_fonts`로 랭킹 조회. **데이터 없으면 "최신 등록" 폴백**. 표기는 반드시 **"이동 클릭 기준"**(다운로드 순위 사칭 금지 — 정직성).
- 일별 롤업 cron-보관정책은 후속(이번 슬라이스 아님).
- 완료 기준: 클릭 기록-랭킹 조회 동작, 원본 테이블 anon 미노출, 개인식별정보 미저장 확인.
- ⚠️ 정직성 게이트(마스터 플랜 3-1 KP6): 클릭 집계 완료 전까지 임시 랭킹을 "인기"로 표기한 채 prod 배포 금지.

### 사용자 제약-금지사항 (반드시 준수 — 이전 세션들에서 계승)

🔴 **반드시 (must)**:
- **prod DB 쓰기 금지** — dev(`zgxtfcpiokhkcrywlxmc`)만. prod는 조회조차 신중히.
- **네트워크 필요 작업(psql, push, gh, pnpm add, codex)은 메인 세션이 직접**(dangerouslyDisableSandbox) — 서브에이전트 위임 금지. 예외: 공개정보 웹조사는 병렬 서브에이전트 허용.
- 서브에이전트 커밋 시 **`git add`는 명시 경로만**(`-A`/`.` 금지).
- 정직성: 근거 없는 데이터 창작 금지. 클릭 수치도 실집계만.
- 서브에이전트 보고를 믿지 말 것 — 이번 세션에서 fix 서브에이전트가 지시 2건을 미이행하고 완료 보고한 사례 있음(실코드 대조로 적발). 커밋 후 반드시 grep/sed로 실코드 검증.

---

## Plan / Design 인덱스

| 단계 | 문서 | 진행률 | 상태 |
|------|------|--------|------|
| 상위 스펙 | `docs/superpowers/specs/2026-07-15-web-data-integration-design.md` | 슬라이스1, 0.5, 2 완료 | 🚧 |
| 슬라이스2 계획 | `docs/superpowers/plans/2026-07-16-slice2-alias-search.md` v1.2 | 완결(머지) | ✅ |
| **슬라이스3 계획** | **없음 — 다음 세션이 작성** | 0% | ⏳ |
| 진행 일지 | `docs/progress.md` + `docs/progress-003.md` | 최신(이번 세션 반영) | ✅ |

---

## 코드 변경 상태 (git)

- 워킹트리: **클린**. main `6d11ef0` = origin/main.
- untracked 잔존물(커밋 여부는 사용자 결정 — 건드리지 말 것): `docs/review/pr-review-15-*.md`, `docs/review/pr-review-16-*.md`, `.playwright-mcp/`, `docs/design/8b_registration_form_spec.md`, `docs/review/screens/`
- 로컬 브랜치: main, develop(보호), `feat/search-alias-f04`(UNMERGED — 구 핸드오프 문서 커밋 `3183e97`만 main에 없음. 삭제 여부 사용자 결정 대기)
- 이번 세션 머지: PR #15(`30af81f`, 슬라이스2 검색), PR #16(`6d11ef0`, 검색 이연분) — 둘 다 squash

---

## 결정 사항 (Decisions — 뒤집지 않음, 변경 시 사용자 확인)

| # | 결정 | 근거 | 누가 |
|---|------|------|------|
| 1 | **마이그레이션 번호: 클릭=0007**, 등록=0008 (0006=검색, 적용됨) | 번호 선점 합의 | 합의(계승) |
| 2 | 정규화 SSoT: NFC → 공백제거 → lower | 0.5 스펙 4.3 | 합의(계승) |
| 3 | 앱 스키마는 `fontagit`(마스터 플랜 7장 SQL 예시의 `public.font_clicks`는 구버전 표기 — fontagit 스키마로 구현) | 스펙 P0-4, 기존 0001~0006 전부 fontagit | 합의 |
| 4 | 쓰기 경로는 RPC(SECURITY DEFINER, `set search_path = fontagit, pg_temp`, anon execute 전용)만 — 원본 테이블 anon 접근 차단 | 스펙 P0 보안 | 합의 |
| 5 | pg_trgm처럼 public 스키마 확장 함수를 SECURITY DEFINER에서 쓸 땐 search_path를 넓히지 말고 스키마 한정 호출(`public.fn()`) | PR #15에서 확립 | 합의 |
| 6 | RPC 입력은 서버측에서도 방어(클라 검증은 우회 가능 — anon 공개 RPC) | PR #16 Codex 리뷰 | 합의 |
| 7 | Top10은 빌드타임 SSG + 데이터 부족 시 "최신 등록" 폴백, 표기 "이동 클릭 기준" | 스펙 슬라이스3 | 합의(계승) |
| 8 | DB 테스트는 `supabase/tests/*.sql` psql assert 방식(인프라 도입 없음), 테스트용 dev 직접 삽입 금지(파이프라인이 SSoT) | PR #16에서 확립 | 합의 |

---

## 블로커 - 미해결 이슈

없음 (진행 차단 0). 알아둘 것:
- ⚠️ **codex CLI 원본 행**: `/opt/homebrew/bin/codex`(cask 0.144.5)가 `_dyld_start`에서 무한 정지(quarantine 제거로도 미해결). **우회: 바이너리를 다른 경로로 복사(cp + xattr -c) 후 실행하면 정상** — 이번 세션 검증됨. 근본 해결은 사용자가 `brew reinstall --cask codex --no-quarantine` (권고했으나 실행 여부 미확인 ⚠️).
- dev 접속: 비번=루트 `.env.sandbox`, region=`apps/pipeline/.env`, pooler `aws-0-{region}.pooler.supabase.com:5432 user=postgres.zgxtfcpiokhkcrywlxmc`

---

## 다음 단계 (Next)

🔴 **MUST** (슬라이스3 착수):
- [ ] 슬라이스3 계획 문서 작성 (superpowers:writing-plans) — 스펙 슬라이스3 절 + 마스터 플랜 7장 기반. Task 구성 참고: 0007 마이그레이션(테이블 2 + record_click/get_top_fonts RPC + RLS) → lib/db/clicks.ts + trends.ts 연결 → 상세 페이지 공식 링크에 fire-and-forget 훅 → 홈/트렌드 빌드타임 랭킹 + 폴백 → SQL assert 테스트
- [ ] dev 실측 게이트: fonts 테이블 FK 대상 확인, 기존 trends.ts가 지금 무엇을 조회하는지(`apps/web/lib/db/trends.ts`) 확인 후 계획에 반영
- [ ] 계획 확정 후 subagent-driven 구현 (0007 dev 적용-검증은 메인 psql 직접)

🟡 **SHOULD**:
- [ ] 검색 이연분(다음 iteration): 뒤로가기 시 URL→입력 역방향 동기화, 검색 상태 boolean 4개 → 단일 상태 머신, SQL 테스트 부정 케이스(파이프라인 경유 픽스처)
- [ ] 슬라이스 0.5 이연분(Codex Medium): tier-a.json 최종 교체, sources URL 형식 검증, korean_names.json 최상위 객체 가드, 동기화 RPC 통합 테스트

🟢 **NICE-TO-DO**:
- [ ] `feat/search-alias-f04` 브랜치 처리(핸드오프 문서 `3183e97`을 main에 가져올지) — 사용자 결정
- [ ] test_uploader.py:77 import 상단 이동

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 스펙(슬라이스3 절) | `docs/superpowers/specs/2026-07-15-web-data-integration-design.md` |
| 마스터 플랜 7장 | `docs/fontagit-master-plan-v3.0.md` |
| RPC 패턴 참고 | `supabase/migrations/0006_search_fonts.sql` |
| 웹 데이터 계층 | `apps/web/lib/db/` (clicks.ts 신설 예정, trends.ts 존재) |
| DB 테스트 패턴 | `supabase/tests/search_fonts_test.sql` |
| 트렌드 화면 | `apps/web/app/trends/`, 홈 `apps/web/app/page.tsx` |
| 핸드오프(이 파일) | `docs/superpowers/handoff/2026-07-16-2130-slice3-click-tracking.md` |

---

## 검증 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| 웹 테스트 | ✅ 96/96 (pnpm test) | PR #16 머지 직전 실측 |
| tsc / build | ✅ 0 에러 / SSG 277p | 동일 시점 |
| SQL 통합 테스트 | ✅ dev ALL PASS (10케이스) | `supabase/tests/search_fonts_test.sql` |
| dev DB | ✅ 0006 적용됨, 검색 실동작 | 본고딕 100/본고딩 17 등 |
| prod | ✅ 무변경 | 0006, 0007 미적용 — 배포 시 순서대로 적용 |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-16-2130-slice3-click-tracking.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. 스펙(2026-07-15-web-data-integration-design.md 슬라이스3 절)과 마스터 플랜 7장, 0006 마이그레이션 패턴을 읽는다
3. git status, git log --oneline -5로 상태 확인 (main에 6d11ef0 존재 확인)
4. 핸드오프 "다음 단계 MUST"부터: dev 실측 게이트 → 슬라이스3 계획 문서 작성(writing-plans) → 사용자 확인 → subagent-driven 구현
5. 사용자 제약-금지사항 준수 (prod 쓰기 금지 / 네트워크 작업 메인 직접 / git add 명시 경로만 / 서브에이전트 보고 실코드 검증)
6. 결정 사항 표는 뒤집지 않음 (특히 클릭=0007, fontagit 스키마, RPC-only 쓰기, 빌드타임 Top10 + 폴백)

진행 전에 핸드오프를 읽었음을 확인하고, MUST 중 어디부터 시작할지 한 줄로 보고해주세요.
```

---

✅ 핸드오프 메모 작성 완료. 다음 세션은 위 재개 프롬프트로 시작.
