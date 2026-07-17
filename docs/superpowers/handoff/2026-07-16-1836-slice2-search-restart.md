# 세션 핸드오프 — 2026-07-16 18:36 KST

> **모드**: superpowers-plan
> **Feature**: 슬라이스2 알리아스 검색(F-04) 재개
> **이전 세션 종결 사유**: 슬라이스 0.5 완료-머지 후 사용자 마감 지시

## 한 줄 요약

슬라이스 0.5(한글 이름-별칭 적재 + Tier A 전수 동기화)를 완료해 PR #14로 main에 머지했다. 다음 세션은 슬라이스2 검색(F-04)을 계획 문서 갱신부터 재개한다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** — 컨텍스트 복원 순서:

1. **이 핸드오프 파일을 읽는다** (`docs/superpowers/handoff/2026-07-16-1836-slice2-search-restart.md`)
2. **문서를 읽는다**:
   - 스펙: `docs/superpowers/specs/2026-07-15-web-data-integration-design.md` (슬라이스2 절)
   - 슬라이스2 계획: `docs/superpowers/plans/2026-07-16-slice2-alias-search.md` (0/10 체크박스, **갱신 필요 — 아래 MUST 참조**)
   - 0.5 스펙(제약-정규화 규칙의 SSoT): `docs/superpowers/specs/2026-07-16-slice0.5-korean-aliases-design.md` (v1.1, 특히 6장)
3. **git 상태 확인**: `git status && git log --oneline -10` — main에 `f888f02`(PR #14 squash)가 있어야 정상
4. **아래 MUST 1(브랜치 준비)부터 시작한다**

---

## 작업 컨텍스트

### 사용자 원본 요청 (이번 세션)

> 슬라이스2 검색(F-04) 핸드오프 이어받기 → 계획 검증 → subagent-driven 구현

실측 검증에서 한글 데이터 0건이 드러나 사용자 결정으로 슬라이스 0.5(한글 적재)를 선행했고, 이번 세션에서 완결했다.

### 사용자 제약-금지사항 (반드시 준수)

🔴 **반드시 (must)**:
- **prod DB 쓰기 금지** — dev(`zgxtfcpiokhkcrywlxmc`)만. prod는 조회조차 신중히.
- **네트워크 필요 작업(파이프라인 실행, psql, push, gh)은 메인 세션이 직접**(dangerouslyDisableSandbox) — 서브에이전트 위임 금지. 예외: 공개정보 웹조사는 병렬 서브에이전트 허용(사용자 확정).
- **트렌드-데이터 정직성**: 근거 없는 데이터 창작 금지(별칭-순위 등).
- 서브에이전트 커밋 시 **`git add`는 명시 경로만**(`-A`/`.` 금지) — 이번 세션에서 무관 untracked 41파일 혼입 사고 있었음(soft reset으로 정화). untracked 잔존물: `.playwright-mcp/`, `docs/design/8b_registration_form_spec.md`, `docs/review/pr-review-*.md`, `docs/review/screens/` (커밋 여부는 사용자 결정 사항 — 건드리지 말 것).

---

## Plan / Design 인덱스

| 단계 | 문서 | 진행률 | 상태 |
|------|------|--------|------|
| 슬라이스 0.5 스펙 v1.1 | `docs/superpowers/specs/2026-07-16-slice0.5-korean-aliases-design.md` | 완료 | ✅ |
| 슬라이스 0.5 계획 | `docs/superpowers/plans/2026-07-16-slice0.5-korean-aliases.md` | Task 1~5 완료 | ✅ |
| Tier A 동기화 설계-계획 | `docs/superpowers/{specs,plans}/2026-07-16-tier-a-stale-font-sync*.md` | 완료 | ✅ |
| **슬라이스2 계획** | `docs/superpowers/plans/2026-07-16-slice2-alias-search.md` | 0/10, **stale — 갱신 후 착수** | 🚧 |
| PR #14 리뷰 | `tobyteam/cpr-review-14-20260716-181809.md` | 반영 완료(High 2건) + 이연분 기록 | ✅ |

---

## 코드 변경 상태 (git)

- 워킹트리: **클린**(추적 파일 변경 0). 브랜치 `feat/search-alias-f04`는 origin과 동기화됨.
- **PR #14 MERGED**: https://github.com/jojo3420/fontagit/pull/14 → main squash `f888f02`
- ⚠️ **주의**: progress 갱신 커밋 `2f57c1c`는 머지 후 `feat/search-alias-f04`에만 존재(main에 없음). 다음 세션은 main에서 새 브랜치 분기 후 `git cherry-pick 2f57c1c`로 가져오거나 슬라이스2 PR에 포함시킬 것.

### 이번 세션 주요 커밋 (전부 push됨)

| SHA | 내용 |
|-----|------|
| `62bc0ef`~`a71d0ab` | 슬라이스 0.5 설계(v1.1, Codex 리뷰 반영) + 구현 계획 |
| `a22a06e`+`9b2544a` | 매핑 JSON(38종)+로더 (리뷰 fix 포함) |
| `354c8cf`+`1eaed9c` | transform 통합 fail-fast (리뷰 fix 포함) |
| `1048aaf` | normalize_alias NFC (SSoT 순서: NFC → 공백제거 → lower) |
| `c7cfc7f`/`6492c73`/`bda2729` | Tier A 전수 동기화(RPC+업로더+CLI) |
| `6c83a74` | PR 리뷰 High 2건(strict 중단, 한글30/라틴90 하한) |
| `2f57c1c` | progress 갱신 (⚠️ 브랜치에만) |

---

## 결정 사항 (Decisions — 뒤집지 않음)

| # | 결정 | 근거 | 누가 |
|---|------|------|------|
| 1 | 한글 별칭 적재를 검색보다 선행(슬라이스 0.5) | 실측: 한글 데이터 0건 → 검색 가치 실증 불가 | 사용자 |
| 2 | 큐레이션은 웹검색 근거만, 음역 창작 금지, 확인 불가는 null | 정직성 원칙 | 사용자 |
| 3 | 정규화 SSoT: **NFC → 공백제거 → lower** (Python 기준, SQL 동일 순서로 구현할 것) | 스펙 v1.1 | 합의 |
| 4 | **마이그레이션 번호**: 0005=Tier A 동기화(적용됨), **검색=0006**, 클릭=0007, 등록=0008 | 0005 선점 | 합의 |
| 5 | 137건 upsert+동기화 단일 트랜잭션화는 다음 PR로 이연 | 아키텍처 변경, upsert 멱등으로 완화됨 | 사용자 |
| 6 | name_ko는 공식 표기만(예: 본고딕=눈누 실증), 없으면 null 7종 유지 | 큐레이션 근거 | 합의 |

---

## 블로커 - 미해결 이슈

없음 (진행 차단 이슈 0). 이연 항목은 아래 SHOULD/NICE 참조.

---

## 다음 단계 (Next)

🔴 **MUST** (슬라이스2 착수 전제):
- [ ] main에서 새 브랜치(예: `feat/search-f04`) 분기 + `git cherry-pick 2f57c1c`(progress)
- [ ] **슬라이스2 계획 문서 갱신** (`2026-07-16-slice2-alias-search.md`) — 4가지 stale 교정:
  1. 마이그레이션 번호 0005 → **0006** (결정 #4)
  2. SQL 버그 B: `50 - (similarity(...) * 0)::int` → 실제 유사도 점수 반영으로 수정
  3. SQL 버그 C: trgm 유사도 대상 `fonts.name_en` → `aliases.alias_norm`(GIN 인덱스 대상과 일치)
  4. 테스트-완료 기준의 지마켓 산스 → 실데이터(본고딕/노토산스/나눔고딕 + 오타 변형) 교체, `normalize_search`에 NFC 반영(결정 #3)
- [ ] 갱신된 계획으로 subagent-driven 구현 (Task 0 dev 게이트는 재확인: pg_trgm 미설치가 정상, 0006이 설치)

🟡 **SHOULD** (Codex Medium 이연분 — 슬라이스2 PR 또는 별도):
- [ ] tier-a.json을 업로드 성공 후 최종 교체(임시 파일 경유)
- [ ] `sources` URL 형식(http/s) 검증 추가
- [ ] korean_names.json 최상위가 객체인지 가드(배열이면 AttributeError)
- [ ] 동기화 RPC 통합 테스트(stale 5종 경계, anon 거부)

🟢 **NICE-TO-DO**:
- [ ] upsert+동기화 단일 트랜잭션 RPC 설계(결정 #5 이연분)
- [ ] test_uploader.py:77 테스트 내부 import 상단 이동

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 파이프라인 한글 매핑 | `apps/pipeline/src/fontagit_pipeline/{data/korean_names.json, korean_names.py}` |
| transform/uploader | `apps/pipeline/src/fontagit_pipeline/{transform.py, uploader.py}` (strict, 하한, NFC) |
| 동기화 RPC | `supabase/migrations/0005_sync_tier_a_fonts.sql` |
| 웹 데이터 계층(슬라이스2 대상) | `apps/web/lib/db/` (search.ts 신설 예정), `apps/web/components/Header.tsx`(검색 버튼 미연결) |
| dev 접속 | 비번=루트 `.env.sandbox`, region=`apps/pipeline/.env`, pooler `aws-0-{region}.pooler.supabase.com:5432 user=postgres.zgxtfcpiokhkcrywlxmc` |
| 핸드오프(이 파일) | `docs/superpowers/handoff/2026-07-16-1836-slice2-search-restart.md` |

---

## 검증 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| 파이프라인 테스트 | ✅ 90/90 (uv run pytest) | 머지 직전 재확인 |
| dev DB | ✅ 137종/공개 130, 한글별칭 32종, name_ko 31종 | 매핑 기대값 일치 |
| PR #14 | ✅ MERGED (f888f02) | squash |
| prod | ✅ 무변경 | 쓰기 0 |
| 웹(apps/web) 빌드 | ⚠️ 이번 세션 미실행 | 슬라이스2에서 확인 |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-16-1836-slice2-search-restart.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. 스펙(2026-07-15-web-data-integration-design.md)과 슬라이스2 계획(2026-07-16-slice2-alias-search.md), 0.5 스펙 6장을 읽는다
3. git status, git log --oneline -10로 상태 확인 (main에 f888f02 존재 확인)
4. 핸드오프 "다음 단계 MUST"부터: 새 브랜치+cherry-pick 2f57c1c → 슬라이스2 계획 4개 stale 교정 → subagent-driven 구현
5. 사용자 제약-금지사항 준수 (prod 쓰기 금지 / 네트워크 작업 메인 직접 / 정직성 / git add 명시 경로만)
6. 결정 사항 표는 뒤집지 않음 (특히 검색 마이그레이션=0006, 정규화 NFC→공백제거→lower)

진행 전에 핸드오프를 읽었음을 확인하고, MUST 중 어디부터 시작할지 한 줄로 보고해주세요.
```

---

✅ 핸드오프 메모 작성 완료. 다음 세션은 위 재개 프롬프트로 시작.
