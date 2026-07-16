# 세션 핸드오프 - 2026-07-16 (슬라이스2 검색 F-04)

> **모드**: superpowers-plan
> **Feature**: 알리아스 검색 (F-04, 슬라이스2)
> **이전 세션 종결 사유**: 컨텍스트 한계 (슬라이스1 전체 + PR#13 머지 + 슬라이스2 착수까지 진행)

## 한 줄 요약

웹 실데이터 연동 슬라이스1을 완료해 main에 머지(PR #13)했고, 슬라이스2(알리아스 검색) 계획까지 작성했다. 다음 세션은 **슬라이스2 계획을 검증한 뒤 subagent-driven으로 구현**하면 된다.

---

## 다음 세션이 가장 먼저 할 일

🔴 **반드시 (must)** - 컨텍스트 복원 순서:
1. **이 핸드오프 파일을 읽는다**
2. **스펙을 읽는다**: `docs/superpowers/specs/2026-07-15-web-data-integration-design.md` (v1.1, 슬라이스2 섹션 + 6장 검색설계)
3. **슬라이스2 계획을 읽는다**: `docs/superpowers/plans/2026-07-16-slice2-alias-search.md` (Task 0~5, 아직 검증 안 됨)
4. **git 상태 확인**: `git status && git log --oneline -6` (브랜치 `feat/search-alias-f04`)
5. **아래 "다음 단계 MUST"부터 시작**: 슬라이스2 계획을 내(메인)가 직접 검증(결함 확인) 후 subagent-driven 구현

---

## 작업 컨텍스트

### 사용자 원본 요청
> 마스터 기획서(docs/fontagit-master-plan-v3.0.md) 기준으로 잔여작업 진행. 슬라이스1(실데이터 연동)→슬라이스2(검색)→슬라이스3(클릭집계)→슬라이스4(등록폼) 순차. 현재 슬라이스2 착수 단계.

### 추가 합의-변경 사항
- 아키텍처: 정적(output:export) 유지 + 브라우저가 anon key로 Supabase 직접 호출(옵션1). 데이터 계층(lib/db) 추상화로 미래 엣지함수 전환 대비.
- 이 프로젝트는 **단독 세션**으로 진행(과거 "UI 타 세션" 분담 폐기). apps/web 포함 전 영역 작업.
- 견본 폰트: 시스템폰트 폴백(구글폰트 실서체는 후속 세션).

### 사용자 제약-금지사항 (반드시 준수)
🔴 **반드시 (must)**:
- `output:"export"` 정적 유지. API route/서버 상주 금지. 검색은 클라이언트 컴포넌트가 브라우저에서 RPC 호출.
- Supabase 접근은 `apps/web/lib/db/` 계층 경유. `client.ts`의 `{db:{schema:'fontagit'}}` 재사용.
- **prod(ollidam) DB 쓰기 금지** - 조회만(`mcp__supabase-prod__query` 읽기전용). prod 폰트 적재는 맨 마지막.
- `.env` 값(anon key 등) 응답/로그에 노출 금지 - 키 이름만 쓰거나 마스킹.
- **기본 Bash 샌드박스는 외부 네트워크 차단**(curl HTTP 000). Supabase 접근/빌드(pnpm build)/git push/gh는 `dangerouslyDisableSandbox: true`로 실행. **단, 서브에이전트에 이 우회를 지시하면 auto 승인 분류기가 차단함**(슬라이스1에서 겪음) → 네트워크 필요 작업은 메인 에이전트가 직접 실행.
- 트렌드 문구 정직성: 현재 트렌드는 임시 최신등록순인데 UI는 "인기/이동 클릭 기준" 표기 유지 중 → **prod 배포 전 슬라이스3(클릭집계) 완료 필수**(그전 배포 시 거짓 표기, 기획서 7-1 위반). `lib/db/trends.ts` 주석 참조.

---

## Plan / Design 인덱스

| 단계 | 문서 | 진행률 | 상태 |
|------|------|--------|------|
| 스펙(전체) | `docs/superpowers/specs/2026-07-15-web-data-integration-design.md` (v1.1) | 슬라이스1~4 설계 확정 | ✅ |
| 슬라이스1 계획 | `docs/superpowers/plans/2026-07-15-slice1-realdata-integration.md` | 완료(main 머지) | ✅ |
| 슬라이스2 계획 | `docs/superpowers/plans/2026-07-16-slice2-alias-search.md` | 0/10 체크박스, **미검증** | 🚧 |
| PR#13 리뷰 | `docs/review/pr-review-13-20260716-100323.md` | Codex 5.5/10 반영 완료 | ✅ |

---

## 코드 변경 상태 (git)

### 브랜치
`feat/search-alias-f04` (origin 푸시됨). main에서 분기.

### Uncommitted (작업 중)
- `docs/superpowers/plans/2026-07-16-slice2-alias-search.md` (untracked, 슬라이스2 계획 - 이 핸드오프와 함께 커밋 예정)

### 이번 브랜치 커밋
| SHA | 메시지 |
|-----|--------|
| `acd392c` | docs: 슬라이스2~4 마이그레이션 번호 0005~0007로 정정 (PR리뷰 High5) |
| `59a09e5` | docs: progress 일지 갱신 |
| `8d87b97` | (main) feat: 웹 실데이터 연동 슬라이스1 (PR #13 MERGED) |

---

## 결정 사항 (Decisions - 뒤집지 말 것)

| # | 결정 | 근거 |
|---|------|------|
| 1 | 검색은 클라이언트에서 anon RPC 직접 호출 | output:export 정적 유지, 옵션1 |
| 2 | 정규화 SSoT: 공백제거+소문자 | 파이프라인 `normalize_alias`(re.sub(\s+,"",lower))와 동일해야 정확 매칭. DB `normalize_search` 함수를 단일 출처로 |
| 3 | 검색 마이그레이션 번호 `0005` | 0001~0004 이미 사용(0003 컬렉션시드, 0004 RLS) |
| 4 | 검색 점수화: 정확별칭>부분일치>trgm 유사도 | 기획서 6장 |
| 5 | 마이그레이션 번호: 검색0005/클릭0006/등록0007 | High5 충돌 정리 |

---

## 블로커 - 미해결 이슈

| # | 이슈 | 영향 | 다음 시도 |
|---|------|------|----------|
| 1 | 슬라이스2 계획 미검증(서브에이전트 self-review만) | 구현 전 검증 필요 | 메인이 직접 mappers/RPC/UI 정확성 확인(슬라이스1처럼) |
| 2 | Task1 마이그레이션 0005(pg_trgm+search_fonts RPC)는 anon 쓰기 불가 | DB 적용 차단 | 사용자가 dev Supabase SQL Editor에서 적용(pg_trgm create extension 권한 필요). URL: dev 프로젝트 zgxtfcpiokhkcrywlxmc |
| 3 | ⚠️ PR#13 후속 미반영 항목(Should) | 품질 | 컬렉션 조립 테스트, prod 0건 빌드 가드, prod BASE_URL 필수화 - 후속 |

---

## 환경 핵심 정보 (다음 세션 필수)

- **dev Supabase**: 프로젝트 `zgxtfcpiokhkcrywlxmc` (`apps/web/.env.local`의 NEXT_PUBLIC_SUPABASE_URL/ANON_KEY). 스키마 `fontagit`. published 폰트 130건, **name_ko 전부 null**(매퍼가 nameEn 폴백), 컬렉션 3종 시드됨, aliases 적재됨.
- **prod Supabase**: `supabase.ollidam.com` (자체호스팅). **폰트 0건**(마지막에 적재). `mcp__supabase-prod__query` 읽기전용 등록.
- 검색 UI 현황: `app/search` 라우트 없음(신설). `components/Header.tsx`/`Hero.tsx`에 검색창 UI 참조 존재 - 계획 Task3에서 연결.
- Next.js 16.2.10(최신, `apps/web/AGENTS.md` 경고: 학습데이터와 다름, node_modules/next 확인).

---

## 다음 단계 (Next)

🔴 **MUST**:
- [ ] 슬라이스2 계획(`2026-07-16-slice2-alias-search.md`) 결함 검증 (메인 직접)
- [ ] subagent-driven으로 Task 0~5 구현 (게이트→마이그레이션0005→lib/db/search.ts→검색UI→계약→테스트)
- [ ] Task1 마이그레이션 0005 dev 적용(사용자 SQL Editor, pg_trgm + search_fonts RPC + normalize_search)

🟡 **SHOULD**:
- [ ] 슬라이스3 클릭집계(F-03) - 트렌드 정직성 해소(prod 배포 전 필수)
- [ ] 슬라이스4 등록폼 제출(F-14)
- [ ] PR#13 후속 Should(컬렉션 조립 테스트, prod 0건 가드, BASE_URL 필수화)

🟢 **NICE-TO-DO**:
- [ ] name_ko 전부 null 파이프라인 보강(한글명 매핑)
- [ ] prod 폰트 적재 + 컬렉션 시드(0003)

---

## 핵심 파일 경로 (Refs)

| 카테고리 | 경로 |
|---------|------|
| 스펙 | `docs/superpowers/specs/2026-07-15-web-data-integration-design.md` |
| 슬라이스2 계획 | `docs/superpowers/plans/2026-07-16-slice2-alias-search.md` |
| 데이터 계층(슬라이스1) | `apps/web/lib/db/{client,fonts,collections,mappers,trends}.ts` |
| 정규화 SSoT 원본 | `apps/pipeline/src/fontagit_pipeline/uploader.py` (normalize_alias) |
| 진행 원장 | `.superpowers/sdd/progress.md` |
| 핸드오프(이 파일) | `docs/superpowers/handoff/2026-07-16-slice2-search-handoff.md` |

---

## 검증 상태

| 항목 | 상태 | 비고 |
|------|------|------|
| 슬라이스1 빌드 | ✅ SSG 276페이지 성공 | main 8d87b97 |
| 슬라이스1 테스트 | ✅ vitest 82 green | main |
| 슬라이스2 구현 | ⏳ 미착수 | 계획만 작성 |
| 슬라이스2 계획 검증 | ⚠️ 미검증 | 다음 세션 MUST |

---

## 재개 프롬프트 (다음 세션에 그대로 복사-붙여넣기)

```
이전 세션의 작업을 이어받습니다. 다음 핸드오프 파일을 먼저 읽고 컨텍스트를 복원해주세요:

/Users/joel.silver/Workspace/gitroom/python/fontagit/docs/superpowers/handoff/2026-07-16-slice2-search-handoff.md

복원 순서:
1. 위 핸드오프 파일 전체를 읽는다
2. 스펙(2026-07-15-web-data-integration-design.md)과 슬라이스2 계획(2026-07-16-slice2-alias-search.md)을 읽는다
3. git status, git log --oneline -6로 현재 상태 확인 (브랜치 feat/search-alias-f04)
4. 핸드오프의 "다음 단계 MUST" 부터 시작: 슬라이스2 계획 검증 → subagent-driven 구현
5. 사용자 제약-금지사항 준수 (특히: 네트워크 필요 작업은 메인이 dangerouslyDisableSandbox로 직접, 서브에이전트 위임 금지 / prod DB 쓰기 금지 / 트렌드 정직성)
6. 결정 사항 표는 뒤집지 않음 (변경 시 사용자 확인)

진행 전에 핸드오프를 읽었음을 확인하고, MUST 중 어디부터 시작할지 한 줄로 보고해주세요.
```
